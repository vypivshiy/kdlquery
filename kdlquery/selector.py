from __future__ import annotations

import functools
import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterator, NamedTuple, Protocol

from .reader import KdlNode


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------


class SelectorError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Context protocol
# ---------------------------------------------------------------------------


class MatchContext(Protocol):
    def iter_nodes(self) -> Iterator[KdlNode]: ...
    def parent_of(self, node: KdlNode) -> KdlNode | None: ...
    def siblings_of(self, node: KdlNode) -> list[KdlNode]: ...
    def index_of(self, node: KdlNode) -> int: ...


class _SubtreeContext:
    __slots__ = ("_node",)

    def __init__(self, node: KdlNode) -> None:
        self._node = node

    def iter_nodes(self) -> Iterator[KdlNode]:
        return self._node.iter_descendants()

    def parent_of(self, node: KdlNode) -> KdlNode | None:
        if node is self._node:
            return None  # boundary: don't traverse above subtree root
        return node.parent

    def siblings_of(self, node: KdlNode) -> list[KdlNode]:
        parent = node.parent
        if parent is not None:
            return parent.children
        return self._node.children

    def index_of(self, node: KdlNode) -> int:
        siblings = self.siblings_of(node)
        for i, s in enumerate(siblings):
            if s is node:
                return i
        return -1


class _SingleNodeContext:
    """MatchContext for a single node, used by :meth:`KdlNode.matches`."""

    __slots__ = ("_node",)

    def __init__(self, node: KdlNode) -> None:
        self._node = node

    def iter_nodes(self) -> Iterator[KdlNode]:
        yield self._node

    def parent_of(self, node: KdlNode) -> KdlNode | None:
        return node.parent

    def siblings_of(self, node: KdlNode) -> list[KdlNode]:
        return node.siblings()

    def index_of(self, node: KdlNode) -> int:
        siblings = self.siblings_of(node)
        for i, s in enumerate(siblings):
            if s is node:
                return i
        return -1


# ---------------------------------------------------------------------------
# AST types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class NodeSelector:
    name: str | None  # None = wildcard (*)
    type_annotation: str | None


@dataclass(frozen=True, slots=True)
class AttributeFilter:
    key: str | int  # str = property name, int = arg index
    type_annotation: str | None  # type annotation on the value
    op: str  # "exists", "=", "^=", "$=", "~="
    value: Any
    wildcard_arg: bool  # True for [*=val]


@dataclass(frozen=True, slots=True)
class NthExpr:
    a: int
    b: int


@dataclass(frozen=True, slots=True)
class PseudoClass:
    name: str
    nth: NthExpr | None = None
    not_selectors: tuple[ComplexSelector, ...] = ()
    has_selectors: tuple[tuple[Combinator | None, ComplexSelector], ...] = ()


@dataclass(frozen=True, slots=True)
class CompoundSelector:
    node: NodeSelector
    filters: tuple[AttributeFilter, ...]
    pseudos: tuple[PseudoClass, ...]


class Combinator(str, Enum):
    DESCENDANT = " "
    CHILD = ">"
    ADJACENT = "+"
    GENERAL_SIBLING = "~"


@dataclass(frozen=True, slots=True)
class ComplexSelector:
    compounds: tuple[CompoundSelector, ...]
    combinators: tuple[Combinator, ...]


@dataclass(frozen=True, slots=True)
class SelectorList:
    selectors: tuple[ComplexSelector, ...]


# ---------------------------------------------------------------------------
# Lexer
# ---------------------------------------------------------------------------


class _TokType(str, Enum):
    IDENT = "IDENT"
    STRING = "STRING"
    NUMBER = "NUMBER"
    BOOL = "BOOL"
    STAR = "STAR"
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    LBRACKET = "LBRACKET"
    RBRACKET = "RBRACKET"
    EQUAL = "EQUAL"
    CARET_EQ = "CARET_EQ"
    DOLLAR_EQ = "DOLLAR_EQ"
    TILDE_EQ = "TILDE_EQ"
    COLON = "COLON"
    GT = "GT"
    PLUS = "PLUS"
    TILDE = "TILDE"
    COMMA = "COMMA"
    EOF = "EOF"


class _Tok(NamedTuple):
    typ: _TokType
    raw: str
    value: Any


_SPECIAL = set('()[]{}=^$~*+>:#"\'/,')


def _unescape_string(s: str) -> str:
    parts: list[str] = []
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            i += 1
            parts.append(s[i])
        else:
            parts.append(s[i])
        i += 1
    return "".join(parts)


class SelectorLexer:
    def __init__(self, source: str):
        self._src = source
        self._i = 0

    def tokenize(self) -> list[_Tok]:
        tokens: list[_Tok] = []
        while self._i < len(self._src):
            self._skip_ws()
            if self._i >= len(self._src):
                break
            ch = self._src[self._i]
            tok = self._next(ch)
            if tok is not None:
                tokens.append(tok)
        tokens.append(_Tok(_TokType.EOF, "", None))
        return tokens

    def _skip_ws(self) -> None:
        while self._i < len(self._src) and self._src[self._i] in " \t":
            self._i += 1

    def _next(self, ch: str) -> _Tok | None:
        if ch == "(":
            self._i += 1
            return _Tok(_TokType.LPAREN, "(", None)
        if ch == ")":
            self._i += 1
            return _Tok(_TokType.RPAREN, ")", None)
        if ch == "[":
            self._i += 1
            return _Tok(_TokType.LBRACKET, "[", None)
        if ch == "]":
            self._i += 1
            return _Tok(_TokType.RBRACKET, "]", None)
        if ch == "*":
            self._i += 1
            return _Tok(_TokType.STAR, "*", None)
        if ch == ">":
            self._i += 1
            return _Tok(_TokType.GT, ">", None)
        if ch == "+":
            self._i += 1
            return _Tok(_TokType.PLUS, "+", None)
        if ch == ":":
            self._i += 1
            return _Tok(_TokType.COLON, ":", None)
        if ch == ",":
            self._i += 1
            return _Tok(_TokType.COMMA, ",", None)
        if ch == "=":
            self._i += 1
            return _Tok(_TokType.EQUAL, "=", None)
        if ch == "^":
            self._i += 1
            if self._i < len(self._src) and self._src[self._i] == "=":
                self._i += 1
                return _Tok(_TokType.CARET_EQ, "^=", None)
            raise SelectorError(f"Unexpected '^' at position {self._i - 1}")
        if ch == "$":
            self._i += 1
            if self._i < len(self._src) and self._src[self._i] == "=":
                self._i += 1
                return _Tok(_TokType.DOLLAR_EQ, "$=", None)
            raise SelectorError(f"Unexpected '$' at position {self._i - 1}")
        if ch == "~":
            self._i += 1
            if self._i < len(self._src) and self._src[self._i] == "=":
                self._i += 1
                return _Tok(_TokType.TILDE_EQ, "~=", None)
            return _Tok(_TokType.TILDE, "~", None)
        if ch == "#":
            return self._read_bool()
        if ch in ('"', "'"):
            return self._read_string(ch)
        if ch.isdigit() or (
            ch == "-" and self._i + 1 < len(self._src) and self._src[self._i + 1].isdigit()
        ):
            return self._read_number()
        if ch == "\\" or (ch not in _SPECIAL and not ch.isspace()):
            return self._read_ident()
        raise SelectorError(f"Unexpected character '{ch}' at position {self._i}")

    def _read_bool(self) -> _Tok:
        start = self._i
        self._i += 1
        for kw, val in (
            ("true", True),
            ("false", False),
            ("null", None),
            ("-inf", -math.inf),
            ("inf", math.inf),
            ("nan", math.nan),
        ):
            if self._src.startswith(kw, self._i):
                end = self._i + len(kw)
                if (
                    end == len(self._src)
                    or self._src[end] in _SPECIAL
                    or self._src[end].isspace()
                ):
                    self._i = end
                    return _Tok(_TokType.BOOL, self._src[start:end], val)
        raise SelectorError(f"Invalid token at position {start}: '{self._src[start:]}'")

    def _read_string(self, quote: str = '"') -> _Tok:
        start = self._i
        self._i += 1
        inner_start = self._i
        while self._i < len(self._src) and self._src[self._i] != quote:
            if self._src[self._i] == "\\" and self._i + 1 < len(self._src):
                self._i += 2
            else:
                self._i += 1
        if self._i >= len(self._src):
            raise SelectorError(f"Unterminated string starting at position {start}")
        inner = self._src[inner_start : self._i]
        self._i += 1
        return _Tok(_TokType.STRING, self._src[start : self._i], _unescape_string(inner))

    def _read_number(self) -> _Tok:
        start = self._i
        if self._src[self._i] in "+-":
            self._i += 1
        while self._i < len(self._src) and (
            self._src[self._i].isdigit() or self._src[self._i] == "."
        ):
            self._i += 1
        raw = self._src[start : self._i]
        try:
            val: int | float = float(raw) if "." in raw else int(raw)
        except ValueError as exc:
            raise SelectorError(f"Invalid number at position {start}: '{raw}'") from exc
        return _Tok(_TokType.NUMBER, raw, val)

    def _read_ident(self) -> _Tok:
        start = self._i
        while self._i < len(self._src):
            ch = self._src[self._i]
            if ch == "\\":
                if self._i + 1 >= len(self._src):
                    raise SelectorError(
                        f"Unterminated escape sequence at position {self._i}"
                    )
                self._i += 2
            elif ch not in _SPECIAL and not ch.isspace():
                self._i += 1
            else:
                break
        raw = self._src[start : self._i]
        return _Tok(_TokType.IDENT, raw, _unescape_string(raw))


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class SelectorParser:
    def __init__(self, tokens: list[_Tok]):
        self._tokens = tokens
        self._i = 0

    def parse(self) -> SelectorList:
        first = self._complex()
        selectors = [first]
        while self._cur().typ == _TokType.COMMA:
            self._advance()
            selectors.append(self._complex())
        if self._cur().typ != _TokType.EOF:
            raise SelectorError(f"Unexpected token: {self._cur().raw}")
        return SelectorList(selectors=tuple(selectors))

    def _cur(self) -> _Tok:
        return self._tokens[self._i]

    def _advance(self) -> _Tok:
        tok = self._tokens[self._i]
        self._i += 1
        return tok

    def _expect(self, typ: _TokType) -> _Tok:
        tok = self._advance()
        if tok.typ != typ:
            raise SelectorError(f"Expected {typ.value}, got '{tok.raw}'")
        return tok

    # --- grammar ---

    def _complex(self) -> ComplexSelector:
        first = self._compound()
        compounds = [first]
        combinators: list[Combinator] = []
        while True:
            comb = self._try_combinator()
            if comb is None:
                break
            combinators.append(comb)
            compounds.append(self._compound())
        return ComplexSelector(
            compounds=tuple(compounds),
            combinators=tuple(combinators),
        )

    def _try_combinator(self) -> Combinator | None:
        tok = self._cur()
        if tok.typ == _TokType.GT:
            self._advance()
            return Combinator.CHILD
        if tok.typ == _TokType.PLUS:
            self._advance()
            return Combinator.ADJACENT
        if tok.typ == _TokType.TILDE:
            self._advance()
            return Combinator.GENERAL_SIBLING
        if tok.typ in (_TokType.IDENT, _TokType.STAR, _TokType.LPAREN, _TokType.STRING):
            return Combinator.DESCENDANT
        return None

    def _compound(self) -> CompoundSelector:
        node = self._node_selector()
        filters: list[AttributeFilter] = []
        while self._cur().typ == _TokType.LBRACKET:
            filters.append(self._filter())
        pseudos: list[PseudoClass] = []
        while self._cur().typ == _TokType.COLON:
            pseudos.append(self._pseudo())
        return CompoundSelector(
            node=node,
            filters=tuple(filters),
            pseudos=tuple(pseudos),
        )

    def _node_selector(self) -> NodeSelector:
        if self._cur().typ == _TokType.LPAREN:
            type_ann = self._type_annotation()
            if self._cur().typ in (_TokType.IDENT, _TokType.STRING):
                name: str | None = self._advance().value
            elif self._cur().typ == _TokType.STAR:
                self._advance()
                name = None
            else:
                name = None
            return NodeSelector(name=name, type_annotation=type_ann)
        if self._cur().typ == _TokType.STAR:
            self._advance()
            return NodeSelector(name=None, type_annotation=None)
        if self._cur().typ in (_TokType.IDENT, _TokType.STRING):
            name = self._advance().value
            return NodeSelector(name=name, type_annotation=None)
        # Bare filter/pseudo without node selector → implicit wildcard
        if self._cur().typ in (_TokType.LBRACKET, _TokType.COLON):
            return NodeSelector(name=None, type_annotation=None)
        raise SelectorError(f"Expected node selector, got '{self._cur().raw}'")

    def _type_annotation(self) -> str:
        self._expect(_TokType.LPAREN)
        tok = self._cur()
        if tok.typ in (_TokType.IDENT, _TokType.STRING):
            self._advance()
        else:
            raise SelectorError(
                f"Expected type annotation identifier or string, got '{tok.raw}'"
            )
        self._expect(_TokType.RPAREN)
        norm = _normalize_type_annotation(f"({tok.value})")
        assert norm is not None
        return norm

    def _filter(self) -> AttributeFilter:
        self._expect(_TokType.LBRACKET)
        filt = self._filter_inner()
        self._expect(_TokType.RBRACKET)
        return filt

    def _filter_inner(self) -> AttributeFilter:
        if self._cur().typ == _TokType.STAR:
            self._advance()
            op, val = self._operator_and_value()
            return AttributeFilter(
                key="*",
                type_annotation=None,
                op=op,
                value=val,
                wildcard_arg=True,
            )

        type_ann: str | None = None
        if self._cur().typ == _TokType.LPAREN:
            type_ann = self._type_annotation()

        if self._cur().typ == _TokType.NUMBER:
            key: str | int = self._advance().value
            if not isinstance(key, int):
                raise SelectorError(f"Expected integer index, got '{key}'")
        elif self._cur().typ in (_TokType.IDENT, _TokType.STRING):
            key = self._advance().value
        else:
            raise SelectorError(f"Expected key name or index, got '{self._cur().raw}'")

        if self._cur().typ == _TokType.RBRACKET:
            return AttributeFilter(
                key=key,
                type_annotation=type_ann,
                op="exists",
                value=None,
                wildcard_arg=False,
            )

        op, val = self._operator_and_value()
        return AttributeFilter(
            key=key,
            type_annotation=type_ann,
            op=op,
            value=val,
            wildcard_arg=False,
        )

    def _operator_and_value(self) -> tuple[str, Any]:
        tok = self._advance()
        ops = {
            _TokType.EQUAL: "=",
            _TokType.CARET_EQ: "^=",
            _TokType.DOLLAR_EQ: "$=",
            _TokType.TILDE_EQ: "~=",
        }
        if tok.typ not in ops:
            raise SelectorError(f"Expected operator, got '{tok.raw}'")
        val = self._parse_value()
        return ops[tok.typ], val

    def _parse_value(self) -> Any:
        tok = self._cur()
        if tok.typ == _TokType.PLUS:
            self._advance()
            num_tok = self._cur()
            if num_tok.typ != _TokType.NUMBER or num_tok.raw.startswith("-"):
                raise SelectorError(f"Expected number after '+', got '{num_tok.raw}'")
            self._advance()
            return num_tok.value
        if tok.typ in (_TokType.STRING, _TokType.NUMBER, _TokType.BOOL):
            self._advance()
            return tok.value
        if tok.typ == _TokType.IDENT:
            self._advance()
            return tok.value
        raise SelectorError(f"Expected value, got '{tok.raw}'")

    def _pseudo(self) -> PseudoClass:
        self._expect(_TokType.COLON)
        name_tok = self._expect(_TokType.IDENT)
        name = name_tok.value
        nth: NthExpr | None = None
        not_selectors: tuple[ComplexSelector, ...] = ()
        has_selectors: tuple[tuple[Combinator | None, ComplexSelector], ...] = ()

        if self._cur().typ == _TokType.LPAREN:
            self._advance()
            if name == "not":
                first = self._complex()
                ns = [first]
                while self._cur().typ == _TokType.COMMA:
                    self._advance()
                    ns.append(self._complex())
                not_selectors = tuple(ns)
            elif name == "has":
                hs: list[tuple[Combinator | None, ComplexSelector]] = []
                initial = self._try_has_initial_combinator()
                sel = self._complex()
                hs.append((initial, sel))
                while self._cur().typ == _TokType.COMMA:
                    self._advance()
                    initial = self._try_has_initial_combinator()
                    sel = self._complex()
                    hs.append((initial, sel))
                has_selectors = tuple(hs)
            else:
                nth = self._nth_expr()
            self._expect(_TokType.RPAREN)

        return PseudoClass(
            name=name,
            nth=nth,
            not_selectors=not_selectors,
            has_selectors=has_selectors,
        )

    def _try_has_initial_combinator(self) -> Combinator | None:
        if self._cur().typ == _TokType.GT:
            self._advance()
            return Combinator.CHILD
        if self._cur().typ == _TokType.PLUS:
            self._advance()
            return Combinator.ADJACENT
        if self._cur().typ == _TokType.TILDE:
            self._advance()
            return Combinator.GENERAL_SIBLING
        return None

    def _nth_expr(self) -> NthExpr:
        tok = self._cur()
        if tok.typ == _TokType.IDENT:
            if tok.raw == "odd":
                self._advance()
                return NthExpr(a=2, b=1)
            if tok.raw == "even":
                self._advance()
                return NthExpr(a=2, b=0)

        has_plus = False
        if self._cur().typ == _TokType.PLUS:
            has_plus = True
            self._advance()

        cur = self._cur()
        if cur.typ == _TokType.NUMBER:
            if has_plus and cur.raw.startswith("-"):
                raise SelectorError(f"Invalid nth expression, got '{cur.raw}'")
            num = self._advance().value
            if not isinstance(num, int):
                raise SelectorError(f"Invalid nth expression, got '{cur.raw}'")
            if self._cur().typ == _TokType.IDENT:
                ident_raw = self._cur().raw
                if ident_raw == "n":
                    self._advance()
                    b = self._nth_offset()
                    return NthExpr(a=num, b=b)
                if ident_raw.startswith("n-") and ident_raw[2:].isdigit():
                    self._advance()
                    return NthExpr(a=num, b=int(ident_raw[1:]))
            return NthExpr(a=0, b=num)

        if cur.typ == _TokType.IDENT:
            ident_raw = cur.raw
            if has_plus and ident_raw.startswith("-"):
                raise SelectorError(f"Invalid nth expression, got '{ident_raw}'")
            if ident_raw == "n":
                self._advance()
                b = self._nth_offset()
                return NthExpr(a=1, b=b)
            if ident_raw == "-n":
                self._advance()
                b = self._nth_offset()
                return NthExpr(a=-1, b=b)
            if ident_raw.startswith("n-") and ident_raw[2:].isdigit():
                self._advance()
                return NthExpr(a=1, b=int(ident_raw[1:]))
            if ident_raw.startswith("-n-") and ident_raw[3:].isdigit():
                self._advance()
                return NthExpr(a=-1, b=int(ident_raw[2:]))

        raise SelectorError(f"Invalid nth expression, got '{cur.raw}'")

    def _nth_offset(self) -> int:
        if self._cur().typ == _TokType.PLUS:
            self._advance()
            tok = self._expect(_TokType.NUMBER)
            if not isinstance(tok.value, int) or tok.raw.startswith("-"):
                raise SelectorError(f"Invalid nth offset, got '{tok.raw}'")
            return tok.value
        if self._cur().typ == _TokType.IDENT and self._cur().raw == "-":
            self._advance()
            tok = self._expect(_TokType.NUMBER)
            if not isinstance(tok.value, int) or tok.raw.startswith("-"):
                raise SelectorError(f"Invalid nth offset, got '{tok.raw}'")
            return -tok.value
        if self._cur().typ == _TokType.NUMBER and self._cur().raw.startswith("-"):
            tok = self._advance()
            if not isinstance(tok.value, int):
                raise SelectorError(f"Invalid nth offset, got '{tok.raw}'")
            return tok.value
        return 0


# ---------------------------------------------------------------------------
# Matcher
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=512)
def _normalize_type_annotation(ann: str | None) -> str | None:
    if ann is None:
        return None
    s = ann.strip()
    while len(s) >= 2 and s.startswith("(") and s.endswith(")"):
        s = s[1:-1].strip()
    if len(s) >= 2 and (
        (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'"))
    ):
        if s.startswith('"'):
            from .parser import _decode_quoted

            try:
                return _decode_quoted(s)
            except ValueError:
                pass
        return _unescape_string(s[1:-1])
    return s


class SelectorMatcher:
    def __init__(self, context: MatchContext):
        self._ctx = context

    @staticmethod
    def _type_annotations_match(actual: str | None, expected: str | None) -> bool:
        if actual is None or expected is None:
            return False
        return _normalize_type_annotation(actual) == _normalize_type_annotation(expected)

    def match(self, selector: SelectorList) -> list[KdlNode]:
        results: list[KdlNode] = []
        seen: set[int] = set()
        selectors = selector.selectors
        for node in self._ctx.iter_nodes():
            nid = id(node)
            if nid in seen:
                continue
            for complex_sel in selectors:
                if self._matches_complex(node, complex_sel):
                    seen.add(nid)
                    results.append(node)
                    break
        return results

    def match_one(self, selector: SelectorList) -> KdlNode | None:
        for node in self._ctx.iter_nodes():
            for complex_sel in selector.selectors:
                if self._matches_complex(node, complex_sel):
                    return node
        return None

    def _matches_complex(self, node: KdlNode, sel: ComplexSelector) -> bool:
        if not self._matches_compound(node, sel.compounds[-1]):
            return False
        if not sel.combinators:
            return True
        return self._matches_chain_from_right(
            node, sel, len(sel.combinators) - 1, boundary=None, allowed_first=None
        )

    def _matches_chain_from_right(
        self,
        current: KdlNode,
        sel: ComplexSelector,
        comb_idx: int,
        boundary: KdlNode | None,
        allowed_first: set[int] | None,
    ) -> bool:
        if comb_idx < 0:
            if allowed_first is not None:
                return id(current) in allowed_first
            return True

        comb = sel.combinators[comb_idx]
        target = sel.compounds[comb_idx]

        if comb == Combinator.CHILD:
            parent = None if current is boundary else self._ctx.parent_of(current)
            if (
                parent is not None
                and parent is not boundary
                and self._matches_compound(parent, target)
            ):
                return self._matches_chain_from_right(
                    parent, sel, comb_idx - 1, boundary, allowed_first
                )
            return False

        if comb == Combinator.DESCENDANT:
            cur = None if current is boundary else self._ctx.parent_of(current)
            while cur is not None and cur is not boundary:
                if self._matches_compound(cur, target) and self._matches_chain_from_right(
                    cur, sel, comb_idx - 1, boundary, allowed_first
                ):
                    return True
                cur = self._ctx.parent_of(cur)
            return False

        if comb == Combinator.ADJACENT:
            if current is boundary:
                return False
            idx = self._ctx.index_of(current)
            if idx <= 0:
                return False
            siblings = self._ctx.siblings_of(current)
            prev = siblings[idx - 1]
            if self._matches_compound(prev, target):
                return self._matches_chain_from_right(
                    prev, sel, comb_idx - 1, boundary, allowed_first
                )
            return False

        if comb == Combinator.GENERAL_SIBLING:
            if current is boundary:
                return False
            idx = self._ctx.index_of(current)
            if idx <= 0:
                return False
            siblings = self._ctx.siblings_of(current)
            for j in range(idx - 1, -1, -1):
                prev = siblings[j]
                if self._matches_compound(prev, target) and self._matches_chain_from_right(
                    prev, sel, comb_idx - 1, boundary, allowed_first
                ):
                    return True
            return False

        return False

    def _resolve_combinator(
        self,
        node: KdlNode,
        comb: Combinator,
        target: CompoundSelector,
    ) -> KdlNode | None:
        if comb == Combinator.CHILD:
            parent = self._ctx.parent_of(node)
            if parent is not None and self._matches_compound(parent, target):
                return parent
            return None

        if comb == Combinator.DESCENDANT:
            cur = self._ctx.parent_of(node)
            while cur is not None:
                if self._matches_compound(cur, target):
                    return cur
                cur = self._ctx.parent_of(cur)
            return None

        if comb == Combinator.ADJACENT:
            idx = self._ctx.index_of(node)
            if idx <= 0:
                return None
            siblings = self._ctx.siblings_of(node)
            prev = siblings[idx - 1]
            if self._matches_compound(prev, target):
                return prev
            return None

        if comb == Combinator.GENERAL_SIBLING:
            idx = self._ctx.index_of(node)
            if idx <= 0:
                return None
            siblings = self._ctx.siblings_of(node)
            for j in range(idx - 1, -1, -1):
                if self._matches_compound(siblings[j], target):
                    return siblings[j]
            return None

        return None

    def _matches_compound(self, node: KdlNode, compound: CompoundSelector) -> bool:
        if not self._matches_node(node, compound.node):
            return False
        for filt in compound.filters:
            if not self._matches_filter(node, filt):
                return False
        for pseudo in compound.pseudos:
            if not self._matches_pseudo(node, pseudo, compound.node):
                return False
        return True

    def _matches_node(self, node: KdlNode, sel: NodeSelector) -> bool:
        if sel.name is not None and node.name != sel.name:
            return False
        if sel.type_annotation is not None:
            return self._type_annotations_match(node.type_annotation, sel.type_annotation)
        return True

    def _matches_filter(self, node: KdlNode, filt: AttributeFilter) -> bool:
        if filt.wildcard_arg:
            for arg in node.args:
                if self._compare(arg.value, filt.op, filt.value):
                    return True
            return False
        if isinstance(filt.key, int):
            return self._match_arg(node, filt)
        return self._match_prop(node, filt)

    def _match_prop(self, node: KdlNode, filt: AttributeFilter) -> bool:
        key = filt.key
        assert isinstance(key, str)
        if key not in node.properties:
            return False
        kv = node.properties[key]
        if (
            filt.type_annotation is not None
            and not self._type_annotations_match(kv.type_annotation, filt.type_annotation)
        ):
            return False
        if filt.op == "exists":
            return True
        return self._compare(kv.value, filt.op, filt.value)

    def _match_arg(self, node: KdlNode, filt: AttributeFilter) -> bool:
        idx = filt.key
        assert isinstance(idx, int)
        if idx < 0 or idx >= len(node.args):
            return False
        kv = node.args[idx]
        if (
            filt.type_annotation is not None
            and not self._type_annotations_match(kv.type_annotation, filt.type_annotation)
        ):
            return False
        if filt.op == "exists":
            return True
        return self._compare(kv.value, filt.op, filt.value)

    @staticmethod
    def _compare(actual: Any, op: str, expected: Any) -> bool:
        if op == "=":
            if isinstance(expected, float) and math.isnan(expected):
                return isinstance(actual, float) and math.isnan(actual)
            return bool(actual == expected)
        if op == "^=":
            return str(actual).startswith(str(expected))
        if op == "$=":
            return str(actual).endswith(str(expected))
        if op == "~=":
            return str(expected) in str(actual)
        return False

    def _matches_pseudo(
        self, node: KdlNode, pseudo: PseudoClass, node_sel: NodeSelector
    ) -> bool:
        if pseudo.name == "not" and pseudo.not_selectors:
            return not any(
                self._matches_complex(node, sel) for sel in pseudo.not_selectors
            )
        if pseudo.name == "has" and pseudo.has_selectors:
            return any(
                self._matches_has(node, initial, sel)
                for initial, sel in pseudo.has_selectors
            )
        if pseudo.name == "root":
            return self._ctx.parent_of(node) is None
        if pseudo.name == "empty":
            return len(node.children) == 0
        if pseudo.name == "first-child":
            for s in self._ctx.siblings_of(node):
                if self._matches_node(s, node_sel):
                    return s is node
            return False
        if pseudo.name == "last-child":
            for s in reversed(self._ctx.siblings_of(node)):
                if self._matches_node(s, node_sel):
                    return s is node
            return False
        if pseudo.name == "only-child":
            found_node = False
            for s in self._ctx.siblings_of(node):
                if self._matches_node(s, node_sel):
                    if s is node:
                        found_node = True
                    else:
                        return False
            return found_node
        if pseudo.name == "nth-child" and pseudo.nth is not None:
            pos = 0
            for s in self._ctx.siblings_of(node):
                if self._matches_node(s, node_sel):
                    pos += 1
                    if s is node:
                        return self._matches_nth_1based(pos, pseudo.nth)
            return False
        return False

    def _matches_has(
        self,
        node: KdlNode,
        initial: Combinator | None,
        sel: ComplexSelector,
    ) -> bool:
        if initial is None:
            if not sel.combinators:
                return any(
                    self._matches_compound(c, sel.compounds[0])
                    for c in node.iter_descendants()
                )
            last = sel.compounds[-1]
            last_comb_idx = len(sel.combinators) - 1
            for target_node in node.iter_descendants():
                if self._matches_compound(
                    target_node, last
                ) and self._matches_chain_from_right(
                    target_node, sel, last_comb_idx, boundary=node, allowed_first=None
                ):
                    return True
            return False

        if initial == Combinator.CHILD:
            matched_children = [
                c for c in node.children if self._matches_compound(c, sel.compounds[0])
            ]
            if not matched_children:
                return False
            if not sel.combinators:
                return True
            allowed_first = {id(c) for c in matched_children}
            last = sel.compounds[-1]
            last_comb_idx = len(sel.combinators) - 1
            for target_node in node.iter_descendants():
                if self._matches_compound(
                    target_node, last
                ) and self._matches_chain_from_right(
                    target_node,
                    sel,
                    last_comb_idx,
                    boundary=node,
                    allowed_first=allowed_first,
                ):
                    return True
            return False

        if initial in (Combinator.ADJACENT, Combinator.GENERAL_SIBLING):
            siblings = self._ctx.siblings_of(node)
            idx = self._ctx.index_of(node)
            if idx < 0 or idx + 1 >= len(siblings):
                return False
            if initial == Combinator.ADJACENT:
                foll_siblings = [siblings[idx + 1]]
            else:
                foll_siblings = siblings[idx + 1 :]
            matched_sibs = [
                s for s in foll_siblings if self._matches_compound(s, sel.compounds[0])
            ]
            if not matched_sibs:
                return False
            if not sel.combinators:
                return True
            allowed_first = {id(s) for s in matched_sibs}
            boundary = self._ctx.parent_of(node)
            last = sel.compounds[-1]
            last_comb_idx = len(sel.combinators) - 1
            for s in siblings[idx + 1 :]:
                if self._matches_compound(s, last) and self._matches_chain_from_right(
                    s, sel, last_comb_idx, boundary=boundary, allowed_first=allowed_first
                ):
                    return True
                for desc in s.iter_descendants():
                    if self._matches_compound(
                        desc, last
                    ) and self._matches_chain_from_right(
                        desc,
                        sel,
                        last_comb_idx,
                        boundary=boundary,
                        allowed_first=allowed_first,
                    ):
                        return True
            return False

        return False

    @staticmethod
    def _matches_nth_1based(pos: int, nth: NthExpr) -> bool:
        if nth.a == 0:
            return pos == nth.b
        diff = pos - nth.b
        if nth.a < 0:
            return diff <= 0 and diff % nth.a == 0
        return diff >= 0 and diff % nth.a == 0


@functools.lru_cache(maxsize=256)
def _parse_selector(selector: str) -> SelectorList:
    tokens = SelectorLexer(selector).tokenize()
    return SelectorParser(tokens).parse()


__all__ = [
    "MatchContext",
    "SelectorError",
    "SelectorLexer",
    "SelectorParser",
    "SelectorMatcher",
    "SelectorList",
    "ComplexSelector",
    "CompoundSelector",
    "NodeSelector",
    "AttributeFilter",
    "PseudoClass",
    "NthExpr",
    "Combinator",
]
