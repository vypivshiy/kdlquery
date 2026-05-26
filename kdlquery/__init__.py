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
from .parser import KDL2CSTParser, KDLLexer
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
from .dict_reader import DictReader


def parse(source: str) -> KdlDocument:
    """Parse a KDL 2.0 string into a KdlDocument tree.

    This is the simplest entry point for most use cases. It parses the
    source into a CST, converts it to a KdlNode tree, and builds the
    parent and depth maps for structural queries.

    Args:
        source: A KDL 2.0 document as a string.

    Returns:
        A KdlDocument with parent, depth, and sibling maps ready for
        querying.

    Raises:
        KDLParseError: If the source is not valid KDL 2.0.
    """
    cst = KDL2CSTParser().parse(source)
    return KdlDocument.from_cst(cst)


__all__ = [
    "CSTArgEntry",
    "CSTDocument",
    "CSTEntry",
    "CSTIdentifier",
    "CSTNode",
    "CSTPropEntry",
    "CSTTypeAnnotation",
    "CSTValue",
    "KDL2CSTParser",
    "KDLParseError",
    "KDLLexer",
    "Position",
    "Span",
    "Token",
    "TokenType",
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
    "DictReader",
]
