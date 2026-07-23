from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from .types import CSTDocument, Span
from .reader import KdlNode, _EMPTY_SPAN


@dataclass
class KdlDocument:
    """Owns a parsed KDL document tree and provides structural queries.

    Nodes carry their own ``parent`` references, so this class no longer
    maintains separate parent/depth maps.

    Attributes:
        nodes: Top-level nodes of the document, in source order. Mutable
            list — use :meth:`add_node` / :meth:`insert_node` /
            :meth:`remove_node` for editing so document back-references
            stay consistent.
        span: Source location spanning the entire document.
    """

    nodes: list[KdlNode]
    span: Span = _EMPTY_SPAN

    @classmethod
    def from_cst(cls, cst_doc: CSTDocument) -> KdlDocument:
        """Construct a KdlDocument from a CST document.

        Converts all CST nodes to KdlNode instances and wires document
        back-references so that ``node.document`` returns this document.

        Args:
            cst_doc: The CST document produced by ``KDL2CSTParser.parse``.

        Returns:
            A fully initialized KdlDocument.
        """
        nodes = [KdlNode.from_cst(n) for n in cst_doc.nodes]
        doc = cls(nodes=nodes, span=cst_doc.span)
        doc._wire_document_refs()
        return doc

    def _wire_document_refs(self) -> None:
        """Set ``_document`` back-reference on all nodes."""
        for node in self.iter_nodes():
            node._document = self

    # ------------------------------------------------------------------
    # Mutation API
    # ------------------------------------------------------------------

    def add_node(self, node: KdlNode) -> KdlNode:
        """Append a top-level node to this document.

        Args:
            node: The KdlNode to append. Its ``_document`` back-reference
                is set to this document (recursively for its subtree).

        Returns:
            The appended node (for chaining).
        """
        self.nodes.append(node)
        node._document = self
        for descendant in node.iter_descendants():
            descendant._document = self
        return node

    def insert_node(self, index: int, node: KdlNode) -> KdlNode:
        """Insert a top-level node at ``index``.

        Args:
            index: Zero-based insertion position (negative indices
                follow Python list semantics).
            node: The KdlNode to insert. Document back-references are
                wired as in :meth:`add_node`.

        Returns:
            The inserted node (for chaining).
        """
        self.nodes.insert(index, node)
        node._document = self
        for descendant in node.iter_descendants():
            descendant._document = self
        return node

    def remove_node(self, index: int) -> KdlNode:
        """Remove and return the top-level node at ``index``.

        Args:
            index: Zero-based position of the node to remove.

        Returns:
            The removed KdlNode. Its ``_document`` back-reference (and
            that of its descendants) is cleared.
        """
        node = self.nodes.pop(index)
        node._document = None
        for descendant in node.iter_descendants():
            descendant._document = None
        return node

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def parent_of(self, node: KdlNode) -> KdlNode | None:
        """Return the parent of a node.

        Args:
            node: The node whose parent to look up. Must be a node
                owned by this document.

        Returns:
            The parent node, or ``None`` if this is a root-level node.
        """
        return node.parent

    def depth_of(self, node: KdlNode) -> int:
        """Return the depth of a node in the tree.

        Args:
            node: The node whose depth to look up. Must be a node
                owned by this document.

        Returns:
            Depth value where ``0`` means root-level.
        """
        return node.depth()

    def index_of(self, node: KdlNode) -> int:
        """Return the position of a node among its siblings.

        Args:
            node: The node whose index to look up. Must be a node
                owned by this document.

        Returns:
            Zero-based index among siblings, or ``-1`` if not found.
        """
        parent = node.parent
        if parent is not None:
            for i, s in enumerate(parent.children):
                if s is node:
                    return i
            return -1
        for i, root_node in enumerate(self.nodes):
            if root_node is node:
                return i
        return -1

    def siblings_of(self, node: KdlNode) -> list[KdlNode]:
        """Return the sibling list containing the given node.

        For root-level nodes, returns ``self.nodes``. For child nodes,
        returns ``parent.children``.

        Args:
            node: The node whose siblings to look up. Must be a node
                owned by this document.

        Returns:
            List of sibling nodes (includes the node itself).
        """
        parent = node.parent
        if parent is not None:
            return parent.children
        return self.nodes

    def iter_nodes(self) -> Iterator[KdlNode]:
        """Iterate all nodes in the document in pre-order (depth-first).

        Yields:
            Each KdlNode in the tree, parent before children.
        """
        stack: list[KdlNode] = list(reversed(self.nodes))
        while stack:
            node = stack.pop()
            yield node
            for child in reversed(node.children):
                stack.append(child)

    def select(self, selector: str) -> list[KdlNode]:
        """Select nodes matching a CSS3-like selector.

        Args:
            selector: A CSS3-compatible selector string.

        Returns:
            List of matching nodes in document order.

        Raises:
            SelectorError: If the selector syntax is invalid.
        """
        from .selector import SelectorMatcher, _parse_selector

        sel = _parse_selector(selector)
        return SelectorMatcher(self).match(sel)

    def select_one(self, selector: str) -> KdlNode | None:
        """Return the first node matching a selector, or None.

        Lazily evaluates — stops iteration at the first match.

        Args:
            selector: A CSS3-compatible selector string.

        Returns:
            The first matching node in document order, or ``None``.

        Raises:
            SelectorError: If the selector syntax is invalid.
        """
        from .selector import SelectorMatcher, _parse_selector

        sel = _parse_selector(selector)
        return SelectorMatcher(self).match_one(sel)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_kdl(self, *, indent_str: str = "    ") -> str:
        """Serialize this document to KDL 2.0 text.

        Nodes are joined with newlines and terminated by a trailing
        newline. An empty document serializes to an empty string.

        Args:
            indent_str: Indentation unit (default 4 spaces).

        Returns:
            KDL 2.0 representation of the document.
        """
        from .serializer import doc_to_kdl

        return doc_to_kdl(self, indent_str=indent_str)


__all__ = [
    "KdlDocument",
]
