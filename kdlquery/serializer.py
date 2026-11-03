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
import re
from typing import TYPE_CHECKING

from .parser import _RESERVED_BARE_IDS
from .reader import KdlValue, _Keyword

if TYPE_CHECKING:
    from .document import KdlDocument
    from .reader import KdlNode


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

_NEEDS_ESCAPE_RE = re.compile(
    r'[\x00-\x1f"\\\x7f\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff\ud800-\udfff]'
)

_NON_BARE_IDENT_CHARS = (
    r'\\/(){};\[\]"=\#'
    r"\x00-\x20\x7f"
    r"\u0085\u00a0\u1680\u2000-\u200a\u200e\u200f\u2028-\u202f\u205f\u2066-\u2069\u3000\ufeff"
    r"\ud800-\udfff"
)

_BARE_IDENT_RE = re.compile(
    rf"(?:[^0-9+\-.{_NON_BARE_IDENT_CHARS}]|\.(?![0-9])|[+-](?![0-9]|\.[0-9]))[^{_NON_BARE_IDENT_CHARS}]*\Z"
)


def _is_bare_ident(s: str) -> bool:
    """Return ``True`` if ``s`` can be emitted as a KDL identifier string."""
    if s in _RESERVED_BARE_IDS:
        return False
    return _BARE_IDENT_RE.match(s) is not None


def _replace_escape_match(m: re.Match[str]) -> str:
    """Return the escaped form for a matched character in a KDL string."""
    ch = m.group(0)
    simple = _SIMPLE_ESCAPES.get(ch)
    if simple is not None:
        return simple
    cp = ord(ch)
    if 0xD800 <= cp <= 0xDFFF:
        raise ValueError(
            f"Cannot serialize surrogate code point U+{cp:04X}; "
            "KDL strings must be Unicode Scalar Values."
        )
    return f"\\u{{{cp:X}}}"


def _escape_quoted(s: str) -> str:
    """Build a single-line KDL quoted string body for ``s`` (with quotes).

    The string must not contain literal newlines; newline characters are
    emitted via the ``\\n`` escape.
    """
    if _NEEDS_ESCAPE_RE.search(s) is None:
        return f'"{s}"'
    return f'"{_NEEDS_ESCAPE_RE.sub(_replace_escape_match, s)}"'


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
        if not line:
            body_lines.append("")
        elif _NEEDS_ESCAPE_RE.search(line) is None:
            body_lines.append(inner + line)
        else:
            body_lines.append(inner + _NEEDS_ESCAPE_RE.sub(_replace_escape_match, line))
    body = "\n".join(body_lines)
    return f'"""\n{body}\n{closer}"""'


def _serialize_string_body(s: str, depth: int, indent_str: str) -> str:
    """Pick the most compact spec-compliant string form for ``s``."""
    if "\n" in s:
        return _serialize_multiline(s, depth, indent_str)
    if _is_bare_ident(s):
        return s
    return _escape_quoted(s)


def _serialize_float(value: float) -> str:
    """Render a Python float as a KDL number literal."""
    if math.isnan(value):
        return "#nan"
    if math.isinf(value):
        return "#inf" if value > 0 else "#-inf"
    return repr(value)


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
        return _serialize_float(value)
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
