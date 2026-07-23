"""KDL 2.0 serializer.

Converts the high-level :class:`~kdlquery.reader.KdlNode` /
:class:`~kdlquery.reader.KdlValue` / :class:`~kdlquery.document.KdlDocument`
tree back into KDL 2.0 source text.

The output is spec-compliant (https://kdl.dev/spec, version 2.0.0) but not
necessarily byte-identical to the original source:

- Numbers always render as decimal (hex/octal/binary formats are lost).
- Strings always render as quoted or multi-line (raw strings are not emitted).
- Comments (``//``, ``/* */``, ``/-`` slashdash) are not preserved — they are
  discarded at parse time.
- Children blocks always render multi-line (one child per line).
- BOM and version markers are not emitted.

Public entry points are :func:`value_to_kdl`, :func:`node_to_kdl`,
:func:`doc_to_kdl`. They are also exposed as methods on the corresponding
classes.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from .reader import KdlValue, _Keyword

if TYPE_CHECKING:
    from .document import KdlDocument
    from .reader import KdlNode


# Characters disallowed anywhere in a bare identifier (KDL 2.0 §3.10.2).
_DISALLOWED_IDENT_CHARS: frozenset[str] = frozenset('\\/(){};[]"=#')

# Bare identifiers reserved by KDL 2.0 (must be quoted or # prefixed).
_RESERVED_BARE_IDS: frozenset[str] = frozenset(
    {"true", "false", "null", "inf", "-inf", "nan"}
)

# Unicode whitespace (KDL 2.0 §3.17) excluding newlines.
_UNICODE_SPACES: frozenset[str] = frozenset(
    (
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
    )
)

# Newline sequences (KDL 2.0 §3.18). CRLF is treated as a single newline but
# for serialization purposes we only need the individual code points.
_NEWLINES: frozenset[str] = frozenset(
    ("\r", "\n", "\u0085", "\u000b", "\u000c", "\u2028", "\u2029")
)

# Simple (single-character) escapes for quoted strings (KDL 2.0 §3.11.1).
_SIMPLE_ESCAPES: dict[str, str] = {
    "\\": "\\\\",
    '"': '\\"',
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
    "\b": "\\b",
    "\f": "\\f",
}


def _is_disallowed_literal(ch: str) -> bool:
    """Return True if ``ch`` is a disallowed literal code point (KDL §3.19).

    Such code points cannot appear literally anywhere in a KDL document
    and must be expressed via ``\\u{...}`` escapes inside strings.
    Surrogates (U+D800-DFFF) are also rejected here because they are not
    Unicode Scalar Values and cannot be represented at all.
    """
    cp = ord(ch)
    # C0 control characters (other than tab U+0009) and DEL.
    if (0x00 <= cp <= 0x1F and cp != 0x09) or cp == 0x7F:
        return True
    # UTF-16 surrogates — not Unicode Scalar Values.
    if 0xD800 <= cp <= 0xDFFF:
        return True
    # Bi-directional control characters.
    if cp in (0x200E, 0x200F) or 0x202A <= cp <= 0x202E or 0x2066 <= cp <= 0x2069:
        return True
    # ZWNBSP / BOM (allowed only as first code point of a document).
    if cp == 0xFEFF:
        return True
    return False


def _is_bare_ident(s: str) -> bool:
    """Return ``True`` if ``s`` can be emitted as a KDL identifier string.

    Implements the rules from KDL 2.0 §3.10:
    - non-empty
    - not a reserved keyword (``true``, ``false``, ``null``, ``inf``, ...)
    - first character is not a digit or a non-identifier character
    - ``+``/``-`` first: second char must not be a digit; if second is ``.``,
      third must not be a digit
    - ``.`` first: second char must not be a digit
    - no character is a non-identifier character, whitespace, newline,
      or disallowed literal code point
    """
    if not s or s in _RESERVED_BARE_IDS:
        return False
    first = s[0]
    if (
        first.isdigit()
        or first in _DISALLOWED_IDENT_CHARS
        or first in _UNICODE_SPACES
        or first in _NEWLINES
        or _is_disallowed_literal(first)
    ):
        return False
    if first in "+-" and len(s) > 1:
        if s[1].isdigit():
            return False
        if s[1] == "." and len(s) > 2 and s[2].isdigit():
            return False
    if first == "." and len(s) > 1 and s[1].isdigit():
        return False
    for ch in s[1:]:
        if (
            ch in _DISALLOWED_IDENT_CHARS
            or ch in _UNICODE_SPACES
            or ch in _NEWLINES
            or _is_disallowed_literal(ch)
        ):
            return False
    return True


def _escape_char(ch: str) -> str | None:
    """Return the escaped form of ``ch`` or ``None`` if it may stay literal.

    Raises:
        ValueError: If ``ch`` is a lone UTF-16 surrogate (U+D800-DFFF),
            which cannot be represented in KDL even via ``\\u{...}``.
    """
    simple = _SIMPLE_ESCAPES.get(ch)
    if simple is not None:
        return simple
    cp = ord(ch)
    if 0xD800 <= cp <= 0xDFFF:
        raise ValueError(
            f"Cannot serialize surrogate code point U+{cp:04X}; "
            "KDL strings must be Unicode Scalar Values."
        )
    # C0 controls (other than tab/LF/CR already handled above) and DEL.
    if (0x00 <= cp <= 0x1F) or cp == 0x7F:
        return f"\\u{{{cp:X}}}"
    # Bi-directional control characters (KDL 2.0 §3.19).
    if cp in (0x200E, 0x200F) or 0x202A <= cp <= 0x202E or 0x2066 <= cp <= 0x2069:
        return f"\\u{{{cp:X}}}"
    # ZWNBSP / BOM anywhere except the very first code point of a document.
    if cp == 0xFEFF:
        return f"\\u{{{cp:X}}}"
    return None


def _escape_quoted(s: str) -> str:
    """Build a single-line KDL quoted string body for ``s`` (with quotes).

    The string must not contain literal newlines; newline characters are
    emitted via the ``\\n`` escape.
    """
    out: list[str] = ['"']
    for ch in s:
        esc = _escape_char(ch)
        out.append(esc if esc is not None else ch)
    out.append('"')
    return "".join(out)


def _serialize_multiline(s: str, depth: int, indent_str: str) -> str:
    """Build a KDL multi-line string for ``s``.

    Uses triple double-quote delimiters. Each non-empty line is prefixed
    with ``indent_str * (depth + 1)``; empty lines remain empty. The
    closing triple quote is placed on its own line at
    ``indent_str * depth``.
    """
    inner = indent_str * (depth + 1)
    closer = indent_str * depth
    lines = s.split("\n")
    body_lines: list[str] = []
    for line in lines:
        esc_buf: list[str] = []
        for ch in line:
            esc = _escape_char(ch)
            esc_buf.append(esc if esc is not None else ch)
        rendered = "".join(esc_buf)
        if rendered == "":
            body_lines.append("")
        else:
            body_lines.append(inner + rendered)
    body = "\n".join(body_lines)
    return f'"""\n{body}\n{closer}"""'


def _serialize_string_body(s: str, depth: int, indent_str: str) -> str:
    """Pick the most compact spec-compliant string form for ``s``."""
    if "\n" in s:
        return _serialize_multiline(s, depth, indent_str)
    if _is_bare_ident(s):
        return s
    return _escape_quoted(s)


def _serialize_number(value: float | int) -> str:
    """Render a Python int/float as a KDL number literal."""
    if isinstance(value, bool):
        # Already excluded by caller, but guard against regressions.
        raise TypeError("bool must be handled before number serialization")
    if isinstance(value, float):
        if math.isnan(value):
            return "#nan"
        if math.isinf(value):
            return "#inf" if value > 0 else "#-inf"
        return repr(value)
    return str(value)


def _serialize_raw_value(
    value: object,
    depth: int,
    indent_str: str,
) -> str:
    """Serialize a bare Python value (unwrapped) to KDL text.

    Order matters: ``bool`` must be checked before ``int`` because Python
    treats ``bool`` as a subclass of ``int``.
    """
    if value is None:
        return "#null"
    if isinstance(value, bool):
        return "#true" if value else "#false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _serialize_number(value)
    if isinstance(value, str):
        return _serialize_string_body(value, depth, indent_str)
    if isinstance(value, _Keyword):
        return value.raw
    raise TypeError(f"Cannot serialize value of type {type(value).__name__!r} as KDL")


def value_to_kdl(
    value: KdlValue,
    *,
    indent: int = 0,
    indent_str: str = "    ",
) -> str:
    """Serialize a :class:`~kdlquery.reader.KdlValue` to KDL 2.0 text.

    Args:
        value: The KdlValue to serialize.
        indent: Current depth (used for multi-line string reindentation).
        indent_str: Indentation unit (default 4 spaces).

    Returns:
        KDL 2.0 representation, including any type annotation prefix.
    """
    body = _serialize_raw_value(value.value, indent, indent_str)
    if value.type_annotation:
        return f"{value.type_annotation} {body}"
    return body


def _serialize_node(
    node: "KdlNode",
    depth: int,
    indent_str: str,
    *,
    force_children_block: bool,
) -> str:
    """Render a single KdlNode (no trailing newline)."""
    parts: list[str] = []
    if node.type_annotation:
        parts.append(node.type_annotation)
    parts.append(_serialize_string_body(node.name, depth, indent_str))
    for arg in node.args:
        parts.append(value_to_kdl(arg, indent=depth + 1, indent_str=indent_str))
    for key, val in node.properties.items():
        key_str = key if _is_bare_ident(key) else _escape_quoted(key)
        parts.append(
            f"{key_str}={value_to_kdl(val, indent=depth + 1, indent_str=indent_str)}"
        )
    head = " ".join(parts)

    has_children = bool(node.children)
    if not has_children and not force_children_block:
        return head
    if not has_children:
        return f"{head} {{}}"

    inner = indent_str * (depth + 1)
    closer = indent_str * depth
    child_lines = [
        _serialize_node(
            child,
            depth + 1,
            indent_str,
            force_children_block=False,
        )
        for child in node.children
    ]
    body = "\n".join(inner + line for line in child_lines)
    return f"{head} {{\n{body}\n{closer}}}"


def node_to_kdl(
    node: "KdlNode",
    *,
    indent: int = 0,
    indent_str: str = "    ",
    force_children_block: bool = False,
) -> str:
    """Serialize a :class:`~kdlquery.reader.KdlNode` (and subtree) to KDL text.

    Args:
        node: The KdlNode to serialize.
        indent: Starting depth for indentation.
        indent_str: Indentation unit (default 4 spaces).
        force_children_block: When ``True``, emit an empty ``{}`` block
            even if :attr:`~kdlquery.reader.KdlNode.children` is empty.
            Only honored for the top-level node; descendants always
            omit empty blocks.

    Returns:
        KDL 2.0 representation of the node (no trailing newline).
    """
    return _serialize_node(
        node,
        indent,
        indent_str,
        force_children_block=force_children_block,
    )


def doc_to_kdl(doc: "KdlDocument", *, indent_str: str = "    ") -> str:
    """Serialize a :class:`~kdlquery.document.KdlDocument` to KDL text.

    Nodes are joined with newlines and the output ends with a trailing
    newline. An empty document serializes to an empty string.

    Args:
        doc: The KdlDocument to serialize.
        indent_str: Indentation unit (default 4 spaces).

    Returns:
        KDL 2.0 representation of the document.
    """
    if not doc.nodes:
        return ""
    body = "\n".join(node_to_kdl(n, indent=0, indent_str=indent_str) for n in doc.nodes)
    return body + "\n"


__all__ = [
    "value_to_kdl",
    "node_to_kdl",
    "doc_to_kdl",
]
