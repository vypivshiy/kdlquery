from __future__ import annotations

from enum import Enum
from typing import Any, NamedTuple


class KDLParseError(ValueError):
    def __init__(self, msg: str, line: int, col: int, *, code: str = ""):
        self.msg = msg
        self.line = line
        self.col = col
        self.code = code
        self.hint = _PARSE_ERROR_HINTS.get(code, "")
        super().__init__(f"{msg}: line {line} column {col}")


# Path-like, lowercase kebab. Extensible. Stable machine-readable category codes.
# Adding a new category = add a key here + emit its `code` from the parser.
_PARSE_ERROR_HINTS: dict[str, str] = {
    "raw-string/unterminated": "KDL raw strings need a matching trailing # for each leading #. "
    'Example: #"(\\d+)"# — not #"(\\d+)". Multi-hash: ##"..."##.',
    "raw-string/newline": 'Single-line raw strings cannot span lines. Close with "# before the '
    'newline, or switch to a multiline raw string: #"""\n...\n"""#.',
    "multiline-raw-string/no-leading-newline": "Multiline raw string content must start with a newline right after "
    'the opening delimiter: #"""\n<body>\n"""#.',
    "multiline-raw-string/decode": "Multiline raw string body violates KDL2 indent/escape rules.",
    "quoted-string/unterminated": 'Quoted string is missing the closing ". Use """...""" for multiline.',
    "quoted-string/newline": "Quoted strings cannot contain a literal newline. Close the string on "
    'the same line, or use a multiline string: """\n...\n""".',
    "quoted-string/decode": 'Invalid escape sequence in quoted string. KDL2 allows: \\", \\\\, '
    "\\n, \\r, \\t, \\uXXXX, \\UXXXXXXXX, and whitespace escapes.",
    "multiline-string/no-leading-newline": "Multiline string content must start with a newline right after the "
    'opening """: """\n<body>\n""".',
    "multiline-string/unterminated": 'Multiline string missing the closing """.',
    "multiline-string/decode": "Multiline string body violates KDL2 indent/escape rules.",
    "block-comment/unterminated": "Block comment /* ... */ is missing a closing */.",
    "unexpected-character": "Character is not valid in KDL2 at this position.",
    "bom-outside-start": "U+FEFF BOM is only permitted as the very first code point.",
    "surrogate-codepoint": "Lone UTF-16 surrogate code points are not allowed in KDL2 source.",
    "control-codepoint": "C0/C1 control characters (other than tab/newline) are not allowed.",
    "direction-control-codepoint": "Bi-directional control characters are not allowed in KDL2 source.",
    "number/invalid-trailing": "Number literal must be followed by whitespace or a delimiter; an "
    "identifier character is attached.",
    "reserved-bare-identifier": "This identifier is reserved by KDL2 and cannot be used as a bare "
    "identifier. Quote it as a string if you need it as a value.",
    "children-block/unterminated": "{ ... } children block is missing the closing }.",
    "node/multiple-children-blocks": "A KDL node can have at most one children block. Merge them or split "
    "into nested nodes.",
    "expected-eol": "Expected end of node (newline / semicolon / EOF). Likely a missing "
    "separator or an extra token on the same line.",
    "expected-whitespace": "KDL2 requires whitespace between entries. Add a space or newline.",
    "slashdash/no-children-block": "A trailing slashdash (/) must be immediately followed by a { ... } "
    "children block to omit.",
    "expected-identifier": "Expected an identifier at this position.",
    "expected-value": "Expected a value (string / number / bool / null) at this position.",
    "expected-token": "Unexpected token — the parser expected a specific token here.",
}

# Public, frozen set of all stable category codes. Useful for self-doc and
# downstream consumers that want to enumerate the categories.
PARSE_ERROR_CODES: frozenset[str] = frozenset(_PARSE_ERROR_HINTS.keys())


class Position(NamedTuple):
    offset: int
    line: int
    column: int


class Span(NamedTuple):
    start: Position
    end: Position


class TokenType(str, Enum):
    IDENT = "IDENT"
    STRING = "STRING"
    NUMBER = "NUMBER"
    BOOL = "BOOL"
    NULL = "NULL"
    KEYWORD_NUMBER = "KEYWORD_NUMBER"
    LBRACE = "LBRACE"
    RBRACE = "RBRACE"
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    EQUAL = "EQUAL"
    SEMI = "SEMI"
    NEWLINE = "NEWLINE"
    SLASHDASH = "SLASHDASH"
    EOF = "EOF"


class Token(NamedTuple):
    typ: TokenType
    raw: str
    value: Any
    span: Span


class CSTTypeAnnotation(NamedTuple):
    raw: str
    span: Span


class CSTIdentifier(NamedTuple):
    value: str
    raw: str
    span: Span


class CSTValue(NamedTuple):
    value: Any
    raw: str
    span: Span
    type_annotation: CSTTypeAnnotation | None = None


class CSTArgEntry(NamedTuple):
    value: CSTValue | CSTIdentifier
    span: Span


class CSTPropEntry(NamedTuple):
    key: CSTIdentifier
    value: CSTValue | CSTIdentifier
    span: Span


CSTEntry = CSTArgEntry | CSTPropEntry


class CSTNode(NamedTuple):
    name: CSTIdentifier
    type_annotation: CSTTypeAnnotation | None
    entries: list[CSTEntry]
    children: list["CSTNode"]
    span: Span
    has_children_block: bool = False
    children_block_span: Span | None = None


class CSTDocument(NamedTuple):
    nodes: list[CSTNode]
    span: Span


__all__ = [
    "CSTArgEntry",
    "CSTDocument",
    "CSTEntry",
    "CSTIdentifier",
    "CSTNode",
    "CSTPropEntry",
    "CSTTypeAnnotation",
    "CSTValue",
    "KDLParseError",
    "PARSE_ERROR_CODES",
    "Position",
    "Span",
    "Token",
    "TokenType",
]
