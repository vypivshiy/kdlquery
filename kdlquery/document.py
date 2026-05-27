from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from .types import CSTDocument, Span
from .reader import KdlNode


@dataclass
class KdlDocument:
    """Owns a parsed KDL document tree and provides structural queries.

    Maintains internal parent/depth maps keyed by node identity, enabling
    parent, sibling, depth, and index lookups without mutating the
    frozen KdlNode tree.

    Attributes:
        nodes: Top-level nodes of the document, in source order.
        span: Source location spanning the entire document.
    """

    nodes: tuple[KdlNode, ...]
    span: Span
    _parent_map: dict[int, KdlNode] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _depth_map: dict[int, int] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )

    @classmethod
    def from_cst(cls, cst_doc: CSTDocument) -> KdlDocument:
        """Construct a KdlDocument from a CST document.

        Converts all CST nodes to KdlNode instances and builds the
        internal parent and depth maps in a single pass.

        Args:
            cst_doc: The CST document produced by ``KDL2CSTParser.parse``.

        Returns:
            A fully initialized KdlDocument with parent and depth maps.
        """
        nodes = tuple(KdlNode.from_cst(n) for n in cst_doc.nodes)
        doc = cls(nodes=nodes, span=cst_doc.span)
        doc._build_maps()
        return doc

    def _build_maps(self) -> None:
        """Populate the parent and depth maps via iterative pre-order traversal."""
        stack: list[tuple[KdlNode, KdlNode | None, int]] = [
            (n, None, 0) for n in reversed(self.nodes)
        ]
        while stack:
            node, parent, depth = stack.pop()
            if parent is not None:
                self._parent_map[id(node)] = parent
            self._depth_map[id(node)] = depth
            for child in reversed(node.children):
                stack.append((child, node, depth + 1))

    def parent_of(self, node: KdlNode) -> KdlNode | None:
        """Return the parent of a node.

        Args:
            node: The node whose parent to look up. Must be a node
                owned by this document.

        Returns:
            The parent node, or ``None`` if this is a root-level node.
        """
        return self._parent_map.get(id(node))

    def depth_of(self, node: KdlNode) -> int:
        """Return the depth of a node in the tree.

        Args:
            node: The node whose depth to look up. Must be a node
                owned by this document.

        Returns:
            Depth value where ``0`` means root-level.
        """
        return self._depth_map.get(id(node), 0)

    def index_of(self, node: KdlNode) -> int:
        """Return the position of a node among its siblings.

        Args:
            node: The node whose index to look up. Must be a node
                owned by this document.

        Returns:
            Zero-based index among siblings, or ``-1`` if not found.
        """
        parent = self.parent_of(node)
        siblings = parent.children if parent is not None else self.nodes
        for i, s in enumerate(siblings):
            if s is node:
                return i
        return -1

    def siblings_of(self, node: KdlNode) -> tuple[KdlNode, ...]:
        """Return the sibling tuple containing the given node.

        For root-level nodes, returns ``self.nodes``. For child nodes,
        returns ``parent.children``.

        Args:
            node: The node whose siblings to look up. Must be a node
                owned by this document.

        Returns:
            Tuple of sibling nodes (includes the node itself).
        """
        parent = self.parent_of(node)
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


__all__ = [
    "KdlDocument",
]
