from __future__ import annotations

from bisect import bisect_right
import math
import re
from typing import Any, Generic, NamedTuple, TypeVar, overload

from .builder import AstBuilder, CstBuilder, TreeBuilder, _NULL_BUILDER

from .types import (
    CSTArgEntry,
    CSTDocument,
    CSTEntry,
    CSTIdentifier,
    CSTNode,
    CSTPropEntry,
    CSTTypeAnnotation,
    CSTValue,
    KDLParseError,
    Position,
    Span,
    Token,
    TokenType,
)


# KDL newline set (CRLF treated as single newline)
_NEWLINES: frozenset[str] = frozenset(
    {"\n", "\r", "\u0085", "\u000b", "\u000c", "\u2028", "\u2029"}
)

# KDL unicode-space (excluding newlines)
_UNICODE_SPACES: frozenset[str] = frozenset(
    {
        "\u0009",
        "\u0020",
        "\u00a0",
        "\u1680",
        "\u2000",
        "\u2001",
        "\u2002",
        "\u2003",
        "\u2004",
        "\u2005",
        "\u2006",
        "\u2007",
        "\u2008",
        "\u2009",
        "\u200a",
        "\u202f",
        "\u205f",
        "\u3000",
    }
)
_UNICODE_SPACES_STR = (
    "\t \u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u202f\u205f\u3000"
)

_DISALLOWED_IDENT_CHARS: frozenset[str] = frozenset('\\/(){};[]"=#')

# Bare identifiers that are reserved in KDL2 (must use # prefix or quotes)
_RESERVED_BARE_IDS: frozenset[str] = frozenset(
    {"true", "false", "null", "inf", "nan", "-inf"}
)

_NEWLINE_RE = re.compile(r"\r\n|[\n\r\u0085\u000b\u000c\u2028\u2029]")
_DISALLOWED_RE = re.compile(
    r"[\x00-\x08\x0e-\x1f\x7f\ud800-\udfff\u200e\u200f\u202a-\u202e\u2066-\u2069]"
)


def _is_ident_continue(ch: str) -> bool:
    if not ch:
        return False
    if ch in _DISALLOWED_IDENT_CHARS:
        return False
    if ch in _UNICODE_SPACES or ch in _NEWLINES:
        return False
    return True


def _build_line_starts(source: str) -> list[int]:
    return [0] + [m.end() for m in _NEWLINE_RE.finditer(source)]


def _offset_to_position(line_starts: list[int], offset: int) -> Position:
    line_idx = max(0, bisect_right(line_starts, offset) - 1)
    line = line_idx + 1
    col = offset - line_starts[line_idx] + 1
    return Position(offset=offset, line=line, column=col)


def offset_to_position(line_starts: list[int], offset: int) -> Position:
    return _offset_to_position(line_starts, offset)


def _validate_source(source: str, line_starts: list[int]) -> None:
    m = _DISALLOWED_RE.search(source)
    has_bom = "\ufeff" in source[1:]
    bom_offset = source.find("\ufeff", 1) if has_bom else -1

    if bom_offset != -1 and (m is None or bom_offset < m.start()):
        pos = _offset_to_position(line_starts, bom_offset)
        raise KDLParseError(
            "Disallowed literal BOM U+FEFF outside document start",
            line=pos.line,
            col=pos.column,
            code="bom-outside-start",
        )

    if m is not None:
        offset = m.start()
        pos = _offset_to_position(line_starts, offset)
        cp = ord(source[offset])
        if 0xD800 <= cp <= 0xDFFF:
            raise KDLParseError(
                "Disallowed surrogate code point",
                line=pos.line,
                col=pos.column,
                code="surrogate-codepoint",
            )
        if (0x0000 <= cp <= 0x0008) or (0x000E <= cp <= 0x001F) or cp == 0x007F:
            raise KDLParseError(
                f"Disallowed control code point U+{cp:04X}",
                line=pos.line,
                col=pos.column,
                code="control-codepoint",
            )
        if (
            (0x200E <= cp <= 0x200F)
            or (0x202A <= cp <= 0x202E)
            or (0x2066 <= cp <= 0x2069)
        ):
            raise KDLParseError(
                f"Disallowed direction-control code point U+{cp:04X}",
                line=pos.line,
                col=pos.column,
                code="direction-control-codepoint",
            )
        raise KDLParseError(
            f"Disallowed code point U+{cp:04X}",
            line=pos.line,
            col=pos.column,
            code="control-codepoint",
        )


_UNICODE_SPACES_PATTERN = r"[\t \u00a0\u1680\u2000-\u200a\u202f\u205f\u3000]+"
_NEWLINE_PATTERN = r"\r\n|[\n\r\u0085\u000b\u000c\u2028\u2029]"
_SLASHDASH_PATTERN = r"/-"
_DELIM_PATTERN = r"[{}()=;]"
_LINE_COMMENT_PATTERN = r"//[^\n\r\u0085\u000b\u000c\u2028\u2029]*"
_STRING_PATTERN = (
    r'"(?!"")(?:[^"\\\n\r\u0085\u000b\u000c\u2028\u2029]|\\[^\n\r\u0085\u000b\u000c\u2028\u2029])*"'
)
_HEX_PATTERN = r"[+-]?0[xX][0-9a-fA-F][0-9a-fA-F_]*"
_OCT_PATTERN = r"[+-]?0[oO][0-7][0-7_]*"
_BIN_PATTERN = r"[+-]?0[bB][01][01_]*"
_DECIMAL_PATTERN = (
    r"[+-]?[0-9][0-9_]*(?:\.[0-9][0-9_]*)?(?:[eE][+-]?[0-9][0-9_]*)?"
)
_HASH_KW_PATTERN = r"#(?:true|false|null|inf|-inf|nan)"

_NON_IDENT_CHARS = (
    r'\\/(){};\[\]"=\#\t \u00a0\u1680\u2000-\u200a\u202f\u205f\u3000\n\r\u0085\u000b\u000c\u2028\u2029'
)
_IDENT_CHAR = rf"[^{_NON_IDENT_CHARS}]"
_IDENT_PATTERN = (
    rf"(?:[^0-9+\-.{_NON_IDENT_CHARS}]|\.(?![0-9])|[+-](?![0-9]|\.[0-9])){_IDENT_CHAR}*"
)

_MASTER_RE = re.compile(
    rf"(?P<WS>{_UNICODE_SPACES_PATTERN})"
    rf"|(?P<NL>{_NEWLINE_PATTERN})"
    rf"|(?P<SLASHDASH>{_SLASHDASH_PATTERN})"
    rf"|(?P<DELIM>{_DELIM_PATTERN})"
    rf"|(?P<LINE_COMMENT>{_LINE_COMMENT_PATTERN})"
    rf"|(?P<STR>{_STRING_PATTERN})"
    rf"|(?P<NUM_HEX>{_HEX_PATTERN})"
    rf"|(?P<NUM_OCT>{_OCT_PATTERN})"
    rf"|(?P<NUM_BIN>{_BIN_PATTERN})"
    rf"|(?P<NUM_DEC>{_DECIMAL_PATTERN})"
    rf"|(?P<HASH_KW>{_HASH_KW_PATTERN})"
    rf"|(?P<IDENT>{_IDENT_PATTERN})"
)

_DELIM_MAP: dict[str, TokenType] = {
    "{": TokenType.LBRACE,
    "}": TokenType.RBRACE,
    "(": TokenType.LPAREN,
    ")": TokenType.RPAREN,
    "=": TokenType.EQUAL,
    ";": TokenType.SEMI,
}

_HASH_KEYWORDS: tuple[tuple[str, TokenType, Any], ...] = (
    ("#true", TokenType.BOOL, True),
    ("#false", TokenType.BOOL, False),
    ("#null", TokenType.NULL, None),
    ("#-inf", TokenType.KEYWORD_NUMBER, -math.inf),
    ("#inf", TokenType.KEYWORD_NUMBER, math.inf),
    ("#nan", TokenType.KEYWORD_NUMBER, math.nan),
)

_HASH_KW_VALS: dict[str, tuple[TokenType, Any]] = {
    kw: (typ, val) for kw, typ, val in _HASH_KEYWORDS
}

_BLOCK_COMMENT_SEARCH_RE = re.compile(r"/\*|\*/")


def _parse_int_like(raw: str, base: int) -> int:
    sign = 1
    s = raw
    if s[0] == "+":
        s = s[1:]
    elif s[0] == "-":
        sign = -1
        s = s[1:]

    s = s[2:]
    return sign * int(s.replace("_", ""), base)


def _parse_number(raw: str, group: str) -> int | float:
    if group == "NUM_HEX":
        return _parse_int_like(raw, 16)
    if group == "NUM_OCT":
        return _parse_int_like(raw, 8)
    if group == "NUM_BIN":
        return _parse_int_like(raw, 2)
    norm = raw.replace("_", "")
    if "." in norm or "e" in norm or "E" in norm:
        return float(norm)
    return int(norm)


_WS_ESCAPE_CLASS = (
    r"[\t \u00a0\u1680\u2000-\u200a\u202f\u205f\u3000\n\r\u0085\u000b\u000c\u2028\u2029]"
)
_ESCAPE_RE = re.compile(
    r"\\(?:([nrtbf\"\\s])|u\{([^}]*)\}|(" + _WS_ESCAPE_CLASS + r"+)|(u\{.*)|(.|$))",
    re.DOTALL,
)

_ESC_MAP = {
    "n": "\n",
    "r": "\r",
    "t": "\t",
    "b": "\b",
    "f": "\f",
    '"': '"',
    "\\": "\\",
    "s": " ",
}


def _replace_escape(m: re.Match[str]) -> str:
    simple = m.group(1)
    if simple is not None:
        return _ESC_MAP[simple]

    hex_part = m.group(2)
    if hex_part is not None:
        if not (1 <= len(hex_part) <= 6) or not all(
            c in "0123456789abcdefABCDEF" for c in hex_part
        ):
            raise ValueError(f"Invalid \\u{{}} escape: \\u{{{hex_part}}}")
        cp = int(hex_part, 16)
        if 0xD800 <= cp <= 0xDFFF:
            raise ValueError(
                f"Surrogate code point U+{cp:04X} is not a valid Unicode scalar value"
            )
        if cp > 0x10FFFF:
            raise ValueError(
                f"Code point U+{cp:X} exceeds maximum Unicode scalar value U+10FFFF"
            )
        return chr(cp)

    ws = m.group(3)
    if ws is not None:
        return ""

    unterminated_u = m.group(4)
    if unterminated_u is not None:
        raise ValueError("Unterminated \\u{} escape sequence")

    other = m.group(5)
    if not other:
        raise ValueError("Unterminated escape sequence at end of string")
    raise ValueError(f"Invalid escape sequence: \\{other}")


def _decode_escape_body(body: str) -> str:
    """Decode KDL2 escape sequences in an already-stripped string body."""
    if "\\" not in body:
        return body
    return _ESCAPE_RE.sub(_replace_escape, body)


def _decode_quoted(raw: str) -> str:
    """Decode a quoted string. Raises ValueError for invalid escape sequences."""
    return _decode_escape_body(raw[1:-1])


def _count_trailing_backslashes(s: str) -> int:
    count = 0
    i = len(s) - 1
    while i >= 0 and s[i] == "\\":
        count += 1
        i -= 1
    return count


def _extract_prefix_from_closing_raw(raw: str) -> str:
    """Determine the indent prefix from the closing-delimiter line raw string.

    The prefix is all initial literal Unicode-whitespace characters.  Any
    whitespace-escape sequence (``\\<ws>`` or ``\\s``) that follows terminates
    the literal prefix region and is itself silently consumed.  Anything else
    on the closing line is an error.
    """
    rem = raw.lstrip(_UNICODE_SPACES_STR)
    if not rem:
        return raw

    prefix_len = len(raw) - len(rem)
    prefix = raw[:prefix_len]

    i = prefix_len
    while i < len(raw):
        if raw[i] == "\\":
            i += 1
            if i >= len(raw):
                raise ValueError("Unterminated escape on closing delimiter line")
            esc = raw[i]
            if esc in _UNICODE_SPACES or esc in _NEWLINES:
                while i < len(raw) and (
                    raw[i] in _UNICODE_SPACES or raw[i] in _NEWLINES
                ):
                    i += 1
            elif esc == "s":
                i += 1
            else:
                raise ValueError(
                    f"Non-whitespace escape on closing delimiter line: \\{esc!r}"
                )
        else:
            raise ValueError(
                f"Non-whitespace character on closing delimiter line: {raw[i]!r}"
            )
    return prefix


def _multiline_extract_prefix(
    lines: list[str], *, is_raw: bool
) -> tuple[str, list[str]]:
    """Return (prefix, content_lines) from the split lines of a multiline string body.

    The closing-delimiter's indentation defines the required prefix.
    Two cases:
    - Normal: the last element of *lines* is the closing-delimiter's line.
    - Escline-before-close: the second-to-last line ends with an odd number of
      backslashes (an escline), meaning its trailing ``\\`` + the following newline
      was consumed by the escline mechanism.  The "effective closing raw" is the
      content before that ``\\`` concatenated with the last line.  If that combined
      text is not purely whitespace, a ValueError is raised.
    """
    if not is_raw and len(lines) >= 2:
        n = _count_trailing_backslashes(lines[-2])
        if n % 2 == 1:
            effective_closing = lines[-2][:-1] + lines[-1]
            prefix = _extract_prefix_from_closing_raw(effective_closing)
            return prefix, lines[:-2]

    closing_raw = lines[-1]
    prefix = _extract_prefix_from_closing_raw(closing_raw)
    return prefix, lines[:-1]


def _multiline_resolve_esclines(lines: list[str]) -> list[str]:
    """Merge continuation lines created by esclines (lines ending with odd-count backslashes)."""
    result: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        n = _count_trailing_backslashes(line)
        if n % 2 == 1:
            merged = line[:-1]
            i += 1
            while i < len(lines):
                nxt = lines[i]
                n2 = _count_trailing_backslashes(nxt)
                if n2 % 2 == 1:
                    merged += nxt[:-1]
                    i += 1
                else:
                    merged += nxt
                    i += 1
                    break
            result.append(merged)
        else:
            result.append(line)
            i += 1
    return result


def _decode_multiline(content: str, *, is_raw: bool = False) -> str:
    text = content.replace("\r\n", "\n").replace("\r", "\n")
    if text.startswith("\n"):
        text = text[1:]

    lines = text.split("\n")

    prefix, content_lines = _multiline_extract_prefix(lines, is_raw=is_raw)

    if not is_raw:
        logical_lines = _multiline_resolve_esclines(content_lines)
    else:
        logical_lines = content_lines

    result_lines: list[str] = []
    for line in logical_lines:
        if not line or not line.strip(_UNICODE_SPACES_STR):
            result_lines.append("")
        elif line.startswith(prefix):
            result_lines.append(line[len(prefix) :])
        else:
            raise ValueError(
                f"Content line does not match required prefix {prefix!r}: {line!r}"
            )
    result = "\n".join(result_lines)

    if not is_raw:
        result = _decode_escape_body(result)

    return result


class RawToken(NamedTuple):
    typ: TokenType
    raw: str
    value: Any
    start_offset: int
    end_offset: int

    @property
    def start(self) -> int:
        return self.start_offset

    @property
    def end(self) -> int:
        return self.end_offset


class KDLLexer:
    def __init__(self, source: str):
        self._line_starts: list[int] = _build_line_starts(source)
        _validate_source(source, self._line_starts)
        self.source = source
        self._pending_escline: bool = False

    def offset_to_position(self, offset: int) -> Position:
        return _offset_to_position(self._line_starts, offset)

    def tokenize_raw(self) -> list[RawToken]:
        source = self.source
        src_len = len(source)
        tokens: list[RawToken] = []
        self._pending_escline = False
        pos = 0

        while pos < src_len:
            m = _MASTER_RE.match(source, pos)
            if m is not None:
                grp = m.lastgroup
                end = m.end()

                if grp == "WS":
                    pos = end
                    continue

                if grp == "NL":
                    raw = m.group(0)
                    tokens.append(RawToken(TokenType.NEWLINE, raw, "\n", pos, end))
                    pos = end
                    continue

                if grp == "DELIM":
                    raw = m.group(0)
                    typ = _DELIM_MAP[raw]
                    self._pending_escline = False
                    tokens.append(RawToken(typ, raw, raw, pos, end))
                    pos = end
                    continue

                if grp == "SLASHDASH":
                    self._pending_escline = False
                    tokens.append(RawToken(TokenType.SLASHDASH, "/-", "/-", pos, end))
                    pos = end
                    continue

                if grp == "LINE_COMMENT":
                    if self._pending_escline:
                        pos_obj = _offset_to_position(self._line_starts, pos)
                        raise KDLParseError(
                            "Single-line comment '//' cannot follow an escline '\\' across lines "
                            "because it silently terminates the node in KDL. Use block comments '/* ... */', "
                            "or place comments before the node or after its definition.",
                            line=pos_obj.line,
                            col=pos_obj.column,
                            code="escline-comment-continuation",
                        )
                    pos = end
                    continue

                if grp == "STR":
                    raw = m.group(0)
                    try:
                        str_val = _decode_quoted(raw)
                    except ValueError as exc:
                        pos_obj = _offset_to_position(self._line_starts, pos)
                        raise KDLParseError(
                            str(exc),
                            line=pos_obj.line,
                            col=pos_obj.column,
                            code="quoted-string/decode",
                        ) from exc
                    self._pending_escline = False
                    tokens.append(RawToken(TokenType.STRING, raw, str_val, pos, end))
                    pos = end
                    continue

                if grp in ("NUM_HEX", "NUM_OCT", "NUM_BIN", "NUM_DEC"):
                    raw = m.group(0)
                    if end < src_len and _is_ident_continue(source[end]):
                        pos_obj = _offset_to_position(self._line_starts, pos)
                        raise KDLParseError(
                            f"Invalid number: {raw!r} immediately followed by {source[end]!r}",
                            line=pos_obj.line,
                            col=pos_obj.column,
                            code="number/invalid-trailing",
                        )
                    num_val = _parse_number(raw, grp)
                    self._pending_escline = False
                    tokens.append(RawToken(TokenType.NUMBER, raw, num_val, pos, end))
                    pos = end
                    continue

                if grp == "HASH_KW":
                    raw = m.group(0)
                    if end < src_len and _is_ident_continue(source[end]):
                        pos_obj = _offset_to_position(self._line_starts, pos)
                        raise KDLParseError(
                            f"Unexpected character {raw[0]!r}",
                            line=pos_obj.line,
                            col=pos_obj.column,
                            code="unexpected-character",
                        )
                    kw_typ, kw_val = _HASH_KW_VALS[raw]
                    self._pending_escline = False
                    tokens.append(RawToken(kw_typ, raw, kw_val, pos, end))
                    pos = end
                    continue

                if grp == "IDENT":
                    raw = m.group(0)
                    if raw in _RESERVED_BARE_IDS:
                        pos_obj = _offset_to_position(self._line_starts, pos)
                        raise KDLParseError(
                            f"Reserved identifier {raw!r} is not valid as a bare identifier in KDL2",
                            line=pos_obj.line,
                            col=pos_obj.column,
                            code="reserved-bare-identifier",
                        )
                    self._pending_escline = False
                    tokens.append(RawToken(TokenType.IDENT, raw, raw, pos, end))
                    pos = end
                    continue

            # Fallback for tokens not matched by master regex
            ch = source[pos]
            if source.startswith("/*", pos):
                pos = self._consume_block_comment(pos)
                continue

            if ch == "\\":
                new_pos = self._try_consume_escline(pos)
                if new_pos is not None:
                    pos = new_pos
                    continue
                pos_obj = _offset_to_position(self._line_starts, pos)
                raise KDLParseError(
                    "Unexpected character '\\'",
                    line=pos_obj.line,
                    col=pos_obj.column,
                    code="unexpected-character",
                )

            if ch == "#":
                tok, new_pos = self._read_hash_prefixed(pos)
                if tok is not None:
                    self._pending_escline = False
                    tokens.append(tok)
                    pos = new_pos
                    continue
                pos_obj = _offset_to_position(self._line_starts, pos)
                raise KDLParseError(
                    "Unexpected character '#'",
                    line=pos_obj.line,
                    col=pos_obj.column,
                    code="unexpected-character",
                )

            if ch == '"':
                tok, new_pos = self._read_quoted_or_multiline_string(pos)
                self._pending_escline = False
                tokens.append(tok)
                pos = new_pos
                continue

            pos_obj = _offset_to_position(self._line_starts, pos)
            raise KDLParseError(
                f"Unexpected character {ch!r}",
                line=pos_obj.line,
                col=pos_obj.column,
                code="unexpected-character",
            )

        tokens.append(RawToken(TokenType.EOF, "", None, src_len, src_len))
        return tokens

    def tokenize(self) -> list[Token]:
        raw_tokens = self.tokenize_raw()
        line_starts = self._line_starts
        tokens: list[Token] = []
        for typ, raw, val, start_off, end_off in raw_tokens:
            start_pos = _offset_to_position(line_starts, start_off)
            end_pos = (
                start_pos
                if end_off == start_off
                else _offset_to_position(line_starts, end_off)
            )
            tokens.append(Token(typ, raw, val, Span(start_pos, end_pos)))
        return tokens

    def _try_consume_escline(self, pos: int) -> int | None:
        # escline := '\\' ws* (single-line-comment | newline | eof)
        source = self.source
        src_len = len(source)
        p = pos + 1

        while p < src_len and source[p] in _UNICODE_SPACES:
            p += 1

        if p + 1 < src_len and source[p] == "/" and source[p + 1] == "/":
            p += 2
            m = _NEWLINE_RE.search(source, p)
            if m:
                p = m.start()
            else:
                p = src_len

        if p >= src_len:
            self._pending_escline = False
            return p

        if source.startswith("\r\n", p):
            self._pending_escline = True
            return p + 2

        if source[p] in _NEWLINES:
            self._pending_escline = True
            return p + 1

        return None

    def _consume_block_comment(self, pos: int) -> int:
        source = self.source
        p = pos + 2
        depth = 1
        while depth > 0:
            m = _BLOCK_COMMENT_SEARCH_RE.search(source, p)
            if m is None:
                pos_obj = _offset_to_position(self._line_starts, pos)
                raise KDLParseError(
                    "Unterminated block comment",
                    line=pos_obj.line,
                    col=pos_obj.column,
                    code="block-comment/unterminated",
                )
            if m.group(0) == "/*":
                depth += 1
            else:
                depth -= 1
            p = m.end()
        return p

    def _read_hash_prefixed(self, pos: int) -> tuple[RawToken | None, int]:
        source = self.source
        src_len = len(source)

        for kw, typ, val in _HASH_KEYWORDS:
            if source.startswith(kw, pos):
                kw_len = len(kw)
                after = pos + kw_len
                if after >= src_len or not _is_ident_continue(source[after]):
                    return RawToken(typ, kw, val, pos, after), after

        j = pos
        while j < src_len and source[j] == "#":
            j += 1
        hashes = j - pos

        if j >= src_len or source[j] != '"':
            return None, pos

        qlen = 3 if source.startswith('"""', j) else 1
        opening_len = hashes + qlen
        closing = ('"""' if qlen == 3 else '"') + ("#" * hashes)
        content_start = pos + opening_len

        pos_obj = _offset_to_position(self._line_starts, pos)

        if qlen == 3:
            if content_start < src_len and not (
                source.startswith("\r\n", content_start)
                or source[content_start] in _NEWLINES
            ):
                raise KDLParseError(
                    "Multiline raw string must begin with a newline immediately after opening delimiter",
                    line=pos_obj.line,
                    col=pos_obj.column,
                    code="multiline-raw-string/no-leading-newline",
                )

        close_idx = source.find(closing, content_start)
        if qlen == 1:
            nl_match = _NEWLINE_RE.search(source, content_start)
            if nl_match is not None and (
                close_idx == -1 or nl_match.start() < close_idx
            ):
                raise KDLParseError(
                    "Newline in single-quote raw string",
                    line=pos_obj.line,
                    col=pos_obj.column,
                    code="raw-string/newline",
                )

        if close_idx == -1:
            raise KDLParseError(
                "Unterminated raw string",
                line=pos_obj.line,
                col=pos_obj.column,
                code="raw-string/unterminated",
            )

        content = source[content_start:close_idx]
        end_idx = close_idx + len(closing)
        raw = source[pos:end_idx]

        if qlen == 3:
            try:
                value = _decode_multiline(content, is_raw=True)
            except ValueError as exc:
                raise KDLParseError(
                    str(exc),
                    line=pos_obj.line,
                    col=pos_obj.column,
                    code="multiline-raw-string/decode",
                ) from exc
        else:
            value = content

        return RawToken(TokenType.STRING, raw, value, pos, end_idx), end_idx

    def _read_quoted_or_multiline_string(self, pos: int) -> tuple[RawToken, int]:
        source = self.source
        src_len = len(source)
        pos_obj = _offset_to_position(self._line_starts, pos)

        if source.startswith('"""', pos):
            content_start = pos + 3
            if content_start < src_len and not (
                source.startswith("\r\n", content_start)
                or source[content_start] in _NEWLINES
            ):
                raise KDLParseError(
                    'Multiline string must begin with a newline immediately after opening """',
                    line=pos_obj.line,
                    col=pos_obj.column,
                    code="multiline-string/no-leading-newline",
                )

            p = content_start
            while p < src_len:
                if source.startswith('"""', p):
                    content = source[content_start:p]
                    end_pos = p + 3
                    raw = source[pos:end_pos]
                    try:
                        value = _decode_multiline(content, is_raw=False)
                    except ValueError as exc:
                        raise KDLParseError(
                            str(exc),
                            line=pos_obj.line,
                            col=pos_obj.column,
                            code="multiline-string/decode",
                        ) from exc
                    return RawToken(TokenType.STRING, raw, value, pos, end_pos), end_pos

                if source[p] == "\\":
                    new_p = self._try_consume_escline(p)
                    if new_p is not None:
                        p = new_p
                        continue
                    p += 1
                    if p < src_len:
                        p += 1
                    continue

                if source.startswith("\r\n", p):
                    p += 2
                    continue

                p += 1

            raise KDLParseError(
                "Unterminated multiline string",
                line=pos_obj.line,
                col=pos_obj.column,
                code="multiline-string/unterminated",
            )

        p = pos + 1
        while p < src_len:
            ch = source[p]
            if ch == "\\":
                p += 1
                if p >= src_len:
                    break
                if source.startswith("\r\n", p):
                    p += 2
                    while p < src_len:
                        if source.startswith("\r\n", p):
                            p += 2
                        elif source[p] in _NEWLINES or source[p] in _UNICODE_SPACES:
                            p += 1
                        else:
                            break
                elif source[p] in _UNICODE_SPACES or source[p] in _NEWLINES:
                    while p < src_len:
                        if source.startswith("\r\n", p):
                            p += 2
                        elif source[p] in _NEWLINES or source[p] in _UNICODE_SPACES:
                            p += 1
                        else:
                            break
                else:
                    p += 1
                continue

            if ch in _NEWLINES:
                nl_pos = _offset_to_position(self._line_starts, p)
                raise KDLParseError(
                    "Newline in quoted string",
                    line=nl_pos.line,
                    col=nl_pos.column,
                    code="quoted-string/newline",
                )

            if ch == '"':
                end_pos = p + 1
                raw = source[pos:end_pos]
                try:
                    value = _decode_quoted(raw)
                except ValueError as exc:
                    raise KDLParseError(
                        str(exc),
                        line=pos_obj.line,
                        col=pos_obj.column,
                        code="quoted-string/decode",
                    ) from exc
                return RawToken(TokenType.STRING, raw, value, pos, end_pos), end_pos

            p += 1

        raise KDLParseError(
            "Unterminated quoted string",
            line=pos_obj.line,
            col=pos_obj.column,
            code="quoted-string/unterminated",
        )



class KDL2CSTParser:
    def parse(self, source: str) -> CSTDocument:
        lexer = KDLLexer(source)
        tokens = lexer.tokenize_raw()
        builder = CstBuilder()
        p = _Parser(
            tokens, source=source, builder=builder, line_starts=lexer._line_starts
        )
        return p.parse_document()


T = TypeVar("T")


class ParsedIdentifier(NamedTuple):
    value: str
    raw: str
    span: Span


class ParsedType(NamedTuple):
    raw: str
    span: Span


class ParsedValue(NamedTuple):
    value: Any
    raw: str
    span: Span
    type_annotation: ParsedType | None
    is_bare_ident: bool


class _Parser(Generic[T]):
    @overload
    def __init__(
        self: _Parser[CSTDocument],
        tokens: list[RawToken] | list[Token],
        source: str | None = None,
        builder: None = None,
        line_starts: list[int] | None = None,
    ) -> None: ...

    @overload
    def __init__(
        self: _Parser[T],
        tokens: list[RawToken] | list[Token],
        source: str | None = None,
        builder: TreeBuilder[T] = ...,
        line_starts: list[int] | None = None,
    ) -> None: ...

    def __init__(
        self,
        tokens: list[RawToken] | list[Token],
        source: str | None = None,
        builder: TreeBuilder[Any] | None = None,
        line_starts: list[int] | None = None,
    ):
        self.source = source
        self.i = 0
        if builder is None:
            self.builder: TreeBuilder[Any] = CstBuilder()
        else:
            self.builder = builder

        self._offset_map: dict[int, Position] | None = None
        if tokens and isinstance(tokens[0], Token):
            adapted_tokens: list[RawToken] = []
            offset_map: dict[int, Position] = {}
            for t in tokens:  # type: ignore[union-attr]
                adapted_tokens.append(
                    RawToken(
                        t.typ,
                        t.raw,
                        t.value,
                        t.span.start.offset,
                        t.span.end.offset,
                    )
                )
                offset_map[t.span.start.offset] = t.span.start
                offset_map[t.span.end.offset] = t.span.end
            self.tokens: list[RawToken] = adapted_tokens
            self._offset_map = offset_map
        else:
            self.tokens = tokens  # type: ignore[assignment]

        if line_starts is not None:
            self._line_starts: list[int] | None = line_starts
        elif source is not None:
            self._line_starts = _build_line_starts(source)
        else:
            self._line_starts = None

    def _pos(self, offset: int) -> Position:
        if self._line_starts is not None:
            return offset_to_position(self._line_starts, offset)
        if self._offset_map is not None and offset in self._offset_map:
            return self._offset_map[offset]
        return Position(offset=offset, line=1, column=offset + 1)

    def _span(self, start_offset: int, end_offset: int) -> Span:
        return Span(self._pos(start_offset), self._pos(end_offset))

    def parse_document(self) -> T:
        self._skip_separators()
        start_pos = self._pos(self._peek().start_offset)

        while not self._at(TokenType.EOF):
            if self._match(TokenType.SLASHDASH):
                self._skip_separators()
                self._parse_discarded_component(allow_node=True)
                consumed = self._consume_terminators()
                if not consumed and not self._at(TokenType.EOF):
                    raise self._error_here(
                        "Expected newline or semicolon after node",
                        code="expected-eol",
                    )
                self._skip_separators()
                continue

            self._parse_node()
            consumed = self._consume_terminators()
            if not consumed and not self._at(TokenType.EOF):
                raise self._error_here(
                    "Expected newline or semicolon after node",
                    code="expected-eol",
                )
            self._skip_separators()

        end_pos = self._pos(self._peek().end_offset)
        res = self.builder.finish_document(Span(start_pos, end_pos))
        return res  # type: ignore[no-any-return]

    def _parse_discarded_component(self, *, allow_node: bool) -> None:
        # Slashdash can drop node / argument / property / children block.
        # We parse and discard exactly one component.
        if self._at(TokenType.LBRACE):
            self._discard_children_block()
            return

        saved_builder = self.builder
        self.builder = _NULL_BUILDER
        try:
            if allow_node:
                self._parse_node()
            else:
                self._parse_entry()
        finally:
            self.builder = saved_builder

    def _discard_children_block(self) -> None:
        self._expect(TokenType.LBRACE)
        depth = 1
        while depth > 0:
            tok = self._peek()
            if tok.typ == TokenType.EOF:
                pos = self._pos(tok.start_offset)
                raise KDLParseError(
                    "Unterminated children block",
                    line=pos.line,
                    col=pos.column,
                    code="children-block/unterminated",
                )
            if tok.typ == TokenType.LBRACE:
                depth += 1
            elif tok.typ == TokenType.RBRACE:
                depth -= 1
            self._advance()

    def _parse_node(self) -> None:
        node_type = self._try_parse_type_annotation()
        name = self._parse_identifier_like()

        start_span = Span(
            node_type.span.start if node_type else name.span.start,
            name.span.end,
        )

        self.builder.start_node(
            name.value,
            node_type.raw if node_type else None,
            start_span,
            name_raw=name.raw,
            name_span=name.span,
            type_span=node_type.span if node_type else None,
        )

        has_children_block = False

        # Node Space: track end offset of last significant token before each entry
        prev_end = name.span.end.offset

        while not self._is_node_terminator() and not self._at(TokenType.LBRACE):
            if self._match(TokenType.SLASHDASH):
                self._skip_separators()
                if self._at(TokenType.LBRACE):
                    # Slashdash-discarded children block: after this, no more entries
                    # are allowed (children-block position reached). Discard it and
                    # exit the entries loop so the "while True" block takes over.
                    self._discard_children_block()
                    break
                self._parse_discarded_component(allow_node=False)
                # Do NOT skip separators here: leave newlines to terminate the node
                continue
            # Require Node Space before each entry
            next_tok = self._peek()
            if next_tok.start_offset == prev_end:
                raise self._error_tok(
                    next_tok,
                    "Expected whitespace before entry",
                    code="expected-whitespace",
                )
            entry_span = self._parse_entry()
            prev_end = entry_span.end.offset

        while True:
            if self._match(TokenType.SLASHDASH):
                self._skip_separators()
                if self._at(TokenType.LBRACE):
                    self._discard_children_block()
                    self._skip_separators()
                    continue
                raise self._error_here(
                    "Slashdash in node tail must precede children block",
                    code="slashdash/no-children-block",
                )

            if not self._match(TokenType.LBRACE):
                break
            if has_children_block:
                raise self._error_here(
                    "Node cannot have multiple children blocks",
                    code="node/multiple-children-blocks",
                )
            has_children_block = True
            lbrace = self._prev()
            lbrace_span = self._span(lbrace.start_offset, lbrace.end_offset)
            self.builder.start_children(lbrace_span)

            self._skip_separators()
            while not self._at(TokenType.RBRACE):
                if self._match(TokenType.SLASHDASH):
                    self._skip_separators()
                    self._parse_discarded_component(allow_node=True)
                    self._skip_separators()
                    continue

                if self._at(TokenType.EOF):
                    raise self._error_here(
                        "Unterminated children block",
                        code="children-block/unterminated",
                    )
                self._parse_node()
                self._consume_terminators()
                self._skip_separators()
            rbrace = self._expect(TokenType.RBRACE)
            children_block_span = Span(lbrace_span.start, self._pos(rbrace.end_offset))
            self.builder.end_children(children_block_span)

        end_pos = self._pos(self._prev().end_offset) if self.i > 0 else name.span.end
        node_span = Span(
            (node_type.span.start if node_type else name.span.start), end_pos
        )
        self.builder.end_node(node_span)

    def _parse_entry(self) -> Span:
        # property: key = value, where key is an identifier string
        if (
            self._is_identifier_token(self._peek())
            and self._peek(1).typ == TokenType.EQUAL
        ):
            key = self._parse_identifier_like()
            self._expect(TokenType.EQUAL)
            parsed_val = self._parse_value_like_info()
            entry_span = Span(key.span.start, parsed_val.span.end)
            self.builder.add_prop(
                key.value,
                parsed_val.value,
                parsed_val.type_annotation.raw if parsed_val.type_annotation else None,
                entry_span,
                key_raw=key.raw,
                key_span=key.span,
                value_raw=parsed_val.raw,
                value_span=parsed_val.span,
                type_span=parsed_val.type_annotation.span if parsed_val.type_annotation else None,
                is_bare_ident=parsed_val.is_bare_ident,
            )
            return entry_span

        parsed_val = self._parse_value_like_info()
        self.builder.add_arg(
            parsed_val.value,
            parsed_val.type_annotation.raw if parsed_val.type_annotation else None,
            parsed_val.span,
            raw=parsed_val.raw,
            value_span=parsed_val.span,
            type_span=parsed_val.type_annotation.span if parsed_val.type_annotation else None,
            is_bare_ident=parsed_val.is_bare_ident,
        )
        return parsed_val.span

    def _try_parse_type_annotation(self) -> ParsedType | None:
        if not self._match(TokenType.LPAREN):
            return None

        lparen = self._prev()
        self._parse_identifier_like()
        rparen = self._expect(TokenType.RPAREN)

        raw = self._slice(lparen.start_offset, rparen.end_offset)
        return ParsedType(
            raw=raw,
            span=self._span(lparen.start_offset, rparen.end_offset),
        )

    def _parse_identifier_like(self) -> ParsedIdentifier:
        tok = self._peek()
        if not self._is_identifier_token(tok):
            raise self._error_tok(
                tok, f"Expected identifier, got {tok.typ}", code="expected-identifier"
            )
        self._advance()
        return ParsedIdentifier(
            value=str(tok.value),
            raw=tok.raw,
            span=self._span(tok.start_offset, tok.end_offset),
        )

    def _parse_value_like_info(self) -> ParsedValue:
        ty = self._try_parse_type_annotation()
        tok = self._peek()

        if tok.typ in (
            TokenType.STRING,
            TokenType.NUMBER,
            TokenType.BOOL,
            TokenType.NULL,
            TokenType.KEYWORD_NUMBER,
        ):
            self._advance()
            if ty:
                raw = self._slice(ty.span.start.offset, tok.end_offset)
                start_pos = ty.span.start
            else:
                raw = tok.raw
                start_pos = self._pos(tok.start_offset)
            val_span = Span(start_pos, self._pos(tok.end_offset))
            return ParsedValue(
                value=tok.value,
                raw=raw,
                span=val_span,
                type_annotation=ty,
                is_bare_ident=False,
            )

        if tok.typ == TokenType.IDENT:
            self._advance()
            if ty:
                raw = self._slice(ty.span.start.offset, tok.end_offset)
                val_span = Span(ty.span.start, self._pos(tok.end_offset))
                return ParsedValue(
                    value=str(tok.value),
                    raw=raw,
                    span=val_span,
                    type_annotation=ty,
                    is_bare_ident=False,
                )
            tok_span = self._span(tok.start_offset, tok.end_offset)
            return ParsedValue(
                value=str(tok.value),
                raw=tok.raw,
                span=tok_span,
                type_annotation=None,
                is_bare_ident=True,
            )

        raise self._error_tok(
            tok, f"Expected value, got {tok.typ}", code="expected-value"
        )

    def _is_node_terminator(self) -> bool:
        return (
            self._at(TokenType.NEWLINE)
            or self._at(TokenType.SEMI)
            or self._at(TokenType.RBRACE)
            or self._at(TokenType.EOF)
        )

    def _consume_terminators(self) -> bool:
        consumed = False
        while self._match(TokenType.NEWLINE) or self._match(TokenType.SEMI):
            consumed = True
        return consumed

    def _skip_separators(self) -> None:
        while self._at(TokenType.NEWLINE) or self._at(TokenType.SEMI):
            self._advance()

    def _is_identifier_token(self, tok: RawToken) -> bool:
        return tok.typ in (TokenType.IDENT, TokenType.STRING)

    def _slice(self, start: int, end: int) -> str:
        if self.source is not None:
            return self.source[start:end]
        out: list[str] = []
        for idx in range(max(0, self.i - 10), min(len(self.tokens), self.i + 10)):
            t = self.tokens[idx]
            if t.end_offset <= start:
                continue
            if t.start_offset >= end:
                break
            out.append(t.raw)
        return "".join(out)

    def _at(self, typ: TokenType) -> bool:
        return self._peek().typ == typ

    def _match(self, typ: TokenType) -> bool:
        if self._at(typ):
            self._advance()
            return True
        return False

    def _expect(self, typ: TokenType) -> RawToken:
        tok = self._peek()
        if tok.typ != typ:
            raise self._error_tok(
                tok, f"Expected {typ}, got {tok.typ}", code="expected-token"
            )
        return self._advance()

    def _advance(self) -> RawToken:
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def _peek(self, n: int = 0) -> RawToken:
        if not self.tokens:
            return RawToken(TokenType.EOF, "", None, 0, 0)
        idx = self.i + n
        if idx >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[idx]

    def _prev(self) -> RawToken:
        if not self.tokens or self.i == 0:
            return self._peek()
        return self.tokens[self.i - 1]

    def _error_tok(self, tok: RawToken, message: str, *, code: str = "") -> KDLParseError:
        pos = self._pos(tok.start_offset)
        return KDLParseError(
            message,
            line=pos.line,
            col=pos.column,
            code=code,
        )

    def _error_here(self, message: str, *, code: str = "") -> KDLParseError:
        return self._error_tok(self._peek(), message, code=code)


__all__ = [
    "AstBuilder",
    "CSTArgEntry",
    "CSTDocument",
    "CSTEntry",
    "CSTIdentifier",
    "CSTNode",
    "CSTPropEntry",
    "CSTTypeAnnotation",
    "CSTValue",
    "CstBuilder",
    "KDL2CSTParser",
    "KDLParseError",
    "KDLLexer",
    "Position",
    "RawToken",
    "Span",
    "Token",
    "TokenType",
    "TreeBuilder",
    "_Parser",
    "_build_line_starts",
    "_offset_to_position",
    "offset_to_position",
]
