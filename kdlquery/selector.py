from __future__ import annotations

import functools
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
    def siblings_of(self, node: KdlNode) -> tuple[KdlNode, ...]: ...
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

    def siblings_of(self, node: KdlNode) -> tuple[KdlNode, ...]:
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

    def siblings_of(self, node: KdlNode) -> tuple[KdlNode, ...]:
        parent = node.parent
        if parent is not None:
            return parent.children
        return (node,)

    def index_of(self, node: KdlNode) -> int:
        siblings = self.siblings_of(node)
        for i, s in enumerate(siblings):
            if s is node:
                return i
        return -1


# ---------------------------------------------------------------------------
# AST types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NodeSelector:
    name: str | None  # None = wildcard (*)
    type_annotation: str | None


@dataclass(frozen=True)
class AttributeFilter:
    key: str | int  # str = property name, int = arg index
    type_annotation: str | None  # type annotation on the value
    op: str  # "exists", "=", "^=", "$=", "~="
    value: Any
    wildcard_arg: bool  # True for [*=val]


@dataclass(frozen=True)
class NthExpr:
    a: int
    b: int


@dataclass(frozen=True)
class PseudoClass:
    name: str
    nth: NthExpr | None = None
    not_selectors: tuple[ComplexSelector, ...] = ()
    has_selectors: tuple[tuple[Combinator | None, ComplexSelector], ...] = ()


@dataclass(frozen=True)
class CompoundSelector:
    node: NodeSelector
    filters: tuple[AttributeFilter, ...]
    pseudos: tuple[PseudoClass, ...]


class Combinator(str, Enum):
    DESCENDANT = " "
    CHILD = ">"
    ADJACENT = "+"
    GENERAL_SIBLING = "~"


@dataclass(frozen=True)
class ComplexSelector:
    compounds: tuple[CompoundSelector, ...]
    combinators: tuple[Combinator, ...]


@dataclass(frozen=True)
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


_SPECIAL = set('()[]{}=^$~*+>:#"/,')


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
        if ch == '"':
            return self._read_string()
        if ch.isdigit():
            return self._read_number()
        if ch not in _SPECIAL and not ch.isspace():
            return self._read_ident()
        raise SelectorError(f"Unexpected character '{ch}' at position {self._i}")

    def _read_bool(self) -> _Tok:
        start = self._i
        self._i += 1
        if self._src.startswith("true", self._i):
            self._i += 4
            return _Tok(_TokType.BOOL, self._src[start : self._i], True)
        if self._src.startswith("false", self._i):
            self._i += 5
            return _Tok(_TokType.BOOL, self._src[start : self._i], False)
        raise SelectorError(f"Invalid token at position {start}: '{self._src[start:]}'")

    def _read_string(self) -> _Tok:
        start = self._i
        self._i += 1
        parts: list[str] = []
        while self._i < len(self._src) and self._src[self._i] != '"':
            if self._src[self._i] == "\\" and self._i + 1 < len(self._src):
                self._i += 1
                parts.append(self._src[self._i])
            else:
                parts.append(self._src[self._i])
            self._i += 1
        if self._i >= len(self._src):
            raise SelectorError(f"Unterminated string starting at position {start}")
        self._i += 1
        return _Tok(_TokType.STRING, self._src[start : self._i], "".join(parts))

    def _read_number(self) -> _Tok:
        start = self._i
        while self._i < len(self._src) and (
            self._src[self._i].isdigit() or self._src[self._i] == "."
        ):
            self._i += 1
        raw = self._src[start : self._i]
        val: int | float = float(raw) if "." in raw else int(raw)
        return _Tok(_TokType.NUMBER, raw, val)

    def _read_ident(self) -> _Tok:
        start = self._i
        while (
            self._i < len(self._src)
            and self._src[self._i] not in _SPECIAL
            and not self._src[self._i].isspace()
        ):
            self._i += 1
        raw = self._src[start : self._i]
        return _Tok(_TokType.IDENT, raw, raw)


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
        if tok.typ in (_TokType.IDENT, _TokType.STAR, _TokType.LPAREN):
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
            if self._cur().typ == _TokType.IDENT:
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
        if self._cur().typ == _TokType.IDENT:
            name = self._advance().value
            return NodeSelector(name=name, type_annotation=None)
        # Bare filter/pseudo without node selector → implicit wildcard
        if self._cur().typ in (_TokType.LBRACKET, _TokType.COLON):
            return NodeSelector(name=None, type_annotation=None)
        raise SelectorError(f"Expected node selector, got '{self._cur().raw}'")

    def _type_annotation(self) -> str:
        self._expect(_TokType.LPAREN)
        ident = self._expect(_TokType.IDENT)
        self._expect(_TokType.RPAREN)
        return f"({ident.raw})"

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
        elif self._cur().typ == _TokType.IDENT:
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
        if self._cur().typ == _TokType.NUMBER:
            num = self._advance().value
            if self._cur().typ == _TokType.IDENT and self._cur().raw == "n":
                self._advance()
                a = int(num)
                b = self._nth_offset()
                return NthExpr(a=a, b=b)
            return NthExpr(a=0, b=int(num))
        if self._cur().typ == _TokType.IDENT and self._cur().raw == "n":
            self._advance()
            b = self._nth_offset()
            return NthExpr(a=1, b=b)
        raise SelectorError(f"Invalid nth expression, got '{self._cur().raw}'")

    def _nth_offset(self) -> int:
        if self._cur().typ == _TokType.PLUS:
            self._advance()
            return int(self._expect(_TokType.NUMBER).value)
        if self._cur().typ == _TokType.TILDE:
            # '-' is not a token type, lexer doesn't produce negative numbers as minus+number
            # but '~' could be misinterpreted. Actually '-' would be IDENT or part of NUMBER.
            # Let's handle the minus sign.
            pass
        if self._cur().typ == _TokType.IDENT and self._cur().raw.startswith("-"):
            raw = self._advance().raw
            return int(raw)
        if self._cur().typ == _TokType.NUMBER:
            return int(self._advance().value)
        return 0


# ---------------------------------------------------------------------------
# Matcher
# ---------------------------------------------------------------------------


class SelectorMatcher:
    def __init__(self, context: MatchContext):
        self._ctx = context

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
        current = node
        for i in range(len(sel.combinators) - 1, -1, -1):
            compound = sel.compounds[i]
            comb = sel.combinators[i]
            candidate = self._resolve_combinator(current, comb, compound)
            if candidate is None:
                return False
            current = candidate
        return True

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
        if (
            sel.type_annotation is not None
            and node.type_annotation != sel.type_annotation
        ):
            return False
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
            and kv.type_annotation != filt.type_annotation
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
            and kv.type_annotation != filt.type_annotation
        ):
            return False
        if filt.op == "exists":
            return True
        return self._compare(kv.value, filt.op, filt.value)

    @staticmethod
    def _compare(actual: Any, op: str, expected: Any) -> bool:
        if op == "=":
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
        siblings = self._ctx.siblings_of(node)
        same_type = [s for s in siblings if self._matches_node(s, node_sel)]
        if pseudo.name == "only-child":
            return len(same_type) == 1
        pos = 0
        for i, s in enumerate(same_type):
            if s is node:
                pos = i + 1
                break
        if pos == 0:
            return False
        if pseudo.name == "first-child":
            return pos == 1
        if pseudo.name == "last-child":
            return pos == len(same_type)
        if pseudo.name == "nth-child" and pseudo.nth is not None:
            return self._matches_nth_1based(pos, pseudo.nth)
        return False

    def _matches_has(
        self,
        node: KdlNode,
        initial: Combinator | None,
        sel: ComplexSelector,
    ) -> bool:
        if initial == Combinator.CHILD:
            candidates: Iterator[KdlNode] = iter(node.children)
        else:
            candidates = self._iter_subtree(node)

        if not sel.combinators:
            return any(self._matches_compound(c, sel.compounds[0]) for c in candidates)

        for candidate in candidates:
            if not self._matches_compound(candidate, sel.compounds[0]):
                continue
            current = candidate
            matched = True
            for j, comb in enumerate(sel.combinators):
                nxt = self._resolve_combinator(current, comb, sel.compounds[j + 1])
                if nxt is None:
                    matched = False
                    break
                current = nxt
            if matched:
                return True
        return False

    @staticmethod
    def _iter_subtree(node: KdlNode) -> Iterator[KdlNode]:
        for child in node.children:
            yield child
            yield from SelectorMatcher._iter_subtree(child)

    @staticmethod
    def _matches_nth_1based(pos: int, nth: NthExpr) -> bool:
        if nth.a == 0:
            return pos == nth.b
        diff = pos - nth.b
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
