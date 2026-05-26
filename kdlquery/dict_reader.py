from __future__ import annotations

from typing import Any, TypedDict

from .reader import (
    KdlNode,
    ReadDiagnostic,
    Reader,
    WalkContext,
)


class Node(TypedDict):
    """A plain-dict representation of a KDL node.

    Attributes:
        name: Node identifier string.
        args: Tuple of unwrapped positional argument values.
        props: Dict of unwrapped named property values.
        children: List of child Node dicts.
    """

    name: str
    args: tuple[Any, ...]
    props: dict[str, Any]
    children: list[Node]


class DictReader(Reader[Node, list[Node]]):
    """Reader that converts a KDL document tree into nested dicts.

    Each node becomes a ``Node`` TypedDict with unwrapped argument and
    property values. Children are processed recursively.
    """

    def on_node(
        self,
        node: KdlNode,
        ctx: WalkContext[Node],
    ) -> Node:
        """Convert a KDL node into a plain dict.

        Args:
            node: The KDL node to convert.
            ctx: Walk context used to recurse into children.

        Returns:
            A Node dict with unwrapped values and recursively
            processed children.
        """
        child_nodes = ctx.walk_children()
        return Node(
            name=node.name,
            args=tuple(a.value for a in node.args),
            props={k: v.value for k, v in node.properties.items()},
            children=child_nodes,
        )

    def error_node(
        self,
        node: KdlNode,
        message: str,
        ctx: WalkContext[Node],
    ) -> Node:
        """Produce a minimal fallback dict for an errored node.

        Args:
            node: The KDL node that caused the error.
            message: String representation of the exception.
            ctx: Walk context for the errored node.

        Returns:
            A Node dict with the node name but empty args, props,
            and children.
        """
        return Node(
            name=node.name,
            args=(),
            props={},
            children=[],
        )

    def finalize(
        self,
        nodes: list[Node],
        diagnostics: list[ReadDiagnostic],
    ) -> list[Node]:
        """Return the list of root-level node dicts unchanged.

        Args:
            nodes: Root-level Node dicts in source order.
            diagnostics: Diagnostics collected during traversal.

        Returns:
            The same list of Node dicts.
        """
        return nodes
