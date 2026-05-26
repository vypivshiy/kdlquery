from __future__ import annotations

from enum import Enum
from typing import Any, NamedTuple


class KDLParseError(ValueError):
    def __init__(self, msg: str, line: int, col: int):
        self.msg = msg
        self.line = line
        self.col = col
        super().__init__(f"{msg}: line {line} column {col}")


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
    "Position",
    "Span",
    "Token",
    "TokenType",
]
