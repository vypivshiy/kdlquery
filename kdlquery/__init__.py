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
    PARSE_ERROR_CODES,
    Position,
    Span,
    Token,
    TokenType,
)
from .builder import AstBuilder, CstBuilder, TreeBuilder
from .parser import KDL2CSTParser, KDLLexer, _Parser
from .reader import (
    DiagnosticCollector,
    KdlValue,
    KdlNode,
    ReadDiagnostic,
    Reader,
    Severity,
    WalkContext,
    Walker,
    parse_into,
)
from .document import KdlDocument
from .selector import SelectorError
from .dict_reader import DictReader


def parse(source: str) -> KdlDocument:
    """Parse a KDL 2.0 string into a KdlDocument tree.

    Directly constructs a KdlDocument tree with parent and document
    back-references wired in-flight via AstBuilder, avoiding intermediate
    CST allocations.

    Args:
        source: A KDL 2.0 document as a string.

    Returns:
        A KdlDocument ready for querying and navigation.

    Raises:
        KDLParseError: If the source is not valid KDL 2.0.
    """
    tokens = KDLLexer(source).tokenize()
    builder = AstBuilder()
    p = _Parser(tokens, source=source, builder=builder)
    return p.parse_document()


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
    "PARSE_ERROR_CODES",
    "KDLLexer",
    "Position",
    "Span",
    "Token",
    "TokenType",
    "TreeBuilder",
    "DiagnosticCollector",
    "KdlValue",
    "KdlNode",
    "KdlDocument",
    "ReadDiagnostic",
    "Reader",
    "Severity",
    "WalkContext",
    "Walker",
    "parse_into",
    "parse",
    "SelectorError",
    "DictReader",
]
