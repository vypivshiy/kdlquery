from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar, runtime_checkable

from .document import KdlDocument
from .reader import KdlNode, KdlValue
from .types import (
    CSTArgEntry,
    CSTDocument,
    CSTEntry,
    CSTIdentifier,
    CSTNode,
    CSTPropEntry,
    CSTTypeAnnotation,
    CSTValue,
    Span,
)

T_co = TypeVar("T_co", covariant=True)


@runtime_checkable
class TreeBuilder(Protocol[T_co]):
    """Protocol defining the lifecycle events of KDL document tree building."""

    def start_node(
        self,
        name: str,
        type_annotation: str | None,
        span: Span,
        **kwargs: Any,
    ) -> None:
        """Called when a node is opened.

        Args:
            name: Node identifier.
            type_annotation: Raw type annotation (e.g. ``"(u8)"``) or ``None``.
            span: Span covering node start up to name end.
        """
        ...

    def add_arg(
        self,
        value: Any,
        type_annotation: str | None,
        span: Span,
        **kwargs: Any,
    ) -> None:
        """Add a positional argument to the currently open node.

        Args:
            value: Argument value (primitive or decoded value).
            type_annotation: Raw type annotation or ``None``.
            span: Span covering the argument value and its type annotation.
        """
        ...

    def add_prop(
        self,
        key: str,
        value: Any,
        type_annotation: str | None,
        span: Span,
        **kwargs: Any,
    ) -> None:
        """Add a named property to the currently open node.

        Args:
            key: Property key identifier.
            value: Property value.
            type_annotation: Raw type annotation or ``None``.
            span: Span covering key, equal sign, and value.
        """
        ...

    def start_children(self, span: Span) -> None:
        """Called when entering a children block ``{ ... }``.

        Args:
            span: Span of the opening brace ``{`` (or block start).
        """
        ...

    def end_children(self, span: Span) -> None:
        """Called when leaving a children block ``{ ... }``.

        Args:
            span: Span covering the entire children block from ``{`` to ``}``.
        """
        ...

    def end_node(self, span: Span) -> None:
        """Called when the currently open node is closed.

        Args:
            span: Complete span of the node from its start to its terminator.
        """
        ...

    def finish_document(self, span: Span) -> T_co:
        """Finalize and return the constructed document.

        Args:
            span: Span covering the entire document.

        Returns:
            The constructed document (e.g. ``KdlDocument`` or ``CSTDocument``).
        """
        ...


class AstBuilder:
    """Directly constructs a KdlDocument without intermediate CST allocations.

    Wires parent references (node.parent = parent) and document references
    (node._document = doc) in-flight during parsing.
    """

    def __init__(self) -> None:
        self.doc: KdlDocument = KdlDocument(nodes=[])
        self.nodes: list[KdlNode] = self.doc.nodes
        self._stack: list[KdlNode] = []

    def start_node(
        self,
        name: str,
        type_annotation: str | None,
        span: Span,
        **kwargs: Any,
    ) -> None:
        node = KdlNode(
            name=name,
            type_annotation=type_annotation,
            span=span,
        )
        node._document = self.doc
        if self._stack:
            parent = self._stack[-1]
            node.parent = parent
            parent.children.append(node)
        else:
            node.parent = None
            self.nodes.append(node)
        self._stack.append(node)

    def add_arg(
        self,
        value: Any,
        type_annotation: str | None,
        span: Span,
        **kwargs: Any,
    ) -> None:
        if self._stack:
            self._stack[-1].args.append(
                KdlValue(
                    value=value,
                    span=span,
                    type_annotation=type_annotation,
                )
            )

    def add_prop(
        self,
        key: str,
        value: Any,
        type_annotation: str | None,
        span: Span,
        **kwargs: Any,
    ) -> None:
        if self._stack:
            self._stack[-1].properties[key] = KdlValue(
                value=value,
                span=span,
                type_annotation=type_annotation,
            )

    def start_children(self, span: Span) -> None:
        pass

    def end_children(self, span: Span) -> None:
        pass

    def end_node(self, span: Span) -> None:
        if self._stack:
            node = self._stack.pop()
            node.span = span

    def finish_document(self, span: Span) -> KdlDocument:
        self.doc.span = span
        return self.doc


@dataclass
class _CstNodeFrame:
    name: CSTIdentifier
    type_annotation: CSTTypeAnnotation | None
    entries: list[CSTEntry] = field(default_factory=list)
    children: list[CSTNode] = field(default_factory=list)
    has_children_block: bool = False
    children_block_span: Span | None = None


class CstBuilder:
    """Builds a full immutable CSTDocument with CSTNode and CSTEntry objects.

    Preserves lossless tokens and spans for tooling and round-trip CST transformations.
    """

    def __init__(self) -> None:
        self.nodes: list[CSTNode] = []
        self._stack: list[_CstNodeFrame] = []

    def start_node(
        self,
        name: str,
        type_annotation: str | None,
        span: Span,
        *,
        name_raw: str | None = None,
        name_span: Span | None = None,
        type_span: Span | None = None,
        **kwargs: Any,
    ) -> None:
        name_id = CSTIdentifier(
            value=name,
            raw=name_raw if name_raw is not None else name,
            span=name_span if name_span is not None else span,
        )
        type_ann = (
            CSTTypeAnnotation(
                raw=type_annotation,
                span=type_span if type_span is not None else span,
            )
            if type_annotation is not None
            else None
        )
        self._stack.append(_CstNodeFrame(name=name_id, type_annotation=type_ann))

    def add_arg(
        self,
        value: Any,
        type_annotation: str | None,
        span: Span,
        *,
        raw: str | None = None,
        val_span: Span | None = None,
        type_span: Span | None = None,
        is_bare_ident: bool = False,
        **kwargs: Any,
    ) -> None:
        if not self._stack:
            return
        frame = self._stack[-1]
        v_span = val_span if val_span is not None else span
        v_raw = raw if raw is not None else str(value)
        if is_bare_ident:
            val_obj: CSTValue | CSTIdentifier = CSTIdentifier(
                value=str(value),
                raw=v_raw,
                span=v_span,
            )
        else:
            type_ann = (
                CSTTypeAnnotation(
                    raw=type_annotation,
                    span=type_span if type_span is not None else v_span,
                )
                if type_annotation is not None
                else None
            )
            val_obj = CSTValue(
                value=value,
                raw=v_raw,
                span=v_span,
                type_annotation=type_ann,
            )
        frame.entries.append(CSTArgEntry(value=val_obj, span=span))

    def add_prop(
        self,
        key: str,
        value: Any,
        type_annotation: str | None,
        span: Span,
        *,
        key_raw: str | None = None,
        key_span: Span | None = None,
        val_raw: str | None = None,
        val_span: Span | None = None,
        type_span: Span | None = None,
        is_bare_ident: bool = False,
        **kwargs: Any,
    ) -> None:
        if not self._stack:
            return
        frame = self._stack[-1]
        k_span = key_span if key_span is not None else span
        k_raw = key_raw if key_raw is not None else key
        key_id = CSTIdentifier(value=key, raw=k_raw, span=k_span)

        v_span = val_span if val_span is not None else span
        v_raw = val_raw if val_raw is not None else str(value)
        if is_bare_ident:
            val_obj: CSTValue | CSTIdentifier = CSTIdentifier(
                value=str(value),
                raw=v_raw,
                span=v_span,
            )
        else:
            type_ann = (
                CSTTypeAnnotation(
                    raw=type_annotation,
                    span=type_span if type_span is not None else v_span,
                )
                if type_annotation is not None
                else None
            )
            val_obj = CSTValue(
                value=value,
                raw=v_raw,
                span=v_span,
                type_annotation=type_ann,
            )
        frame.entries.append(CSTPropEntry(key=key_id, value=val_obj, span=span))

    def start_children(self, span: Span) -> None:
        if self._stack:
            self._stack[-1].has_children_block = True

    def end_children(self, span: Span) -> None:
        if self._stack:
            frame = self._stack[-1]
            frame.has_children_block = True
            frame.children_block_span = span

    def end_node(self, span: Span) -> None:
        if not self._stack:
            return
        frame = self._stack.pop()
        node = CSTNode(
            name=frame.name,
            type_annotation=frame.type_annotation,
            entries=frame.entries,
            children=frame.children,
            span=span,
            has_children_block=frame.has_children_block,
            children_block_span=frame.children_block_span,
        )
        if self._stack:
            self._stack[-1].children.append(node)
        else:
            self.nodes.append(node)

    def finish_document(self, span: Span) -> CSTDocument:
        return CSTDocument(nodes=self.nodes, span=span)


class _NullBuilder:
    """Builder that discards all events (used for slashdash components)."""

    def start_node(
        self,
        name: str,
        type_annotation: str | None,
        span: Span,
        **kwargs: Any,
    ) -> None:
        pass

    def add_arg(
        self,
        value: Any,
        type_annotation: str | None,
        span: Span,
        **kwargs: Any,
    ) -> None:
        pass

    def add_prop(
        self,
        key: str,
        value: Any,
        type_annotation: str | None,
        span: Span,
        **kwargs: Any,
    ) -> None:
        pass

    def start_children(self, span: Span) -> None:
        pass

    def end_children(self, span: Span) -> None:
        pass

    def end_node(self, span: Span) -> None:
        pass

    def finish_document(self, span: Span) -> None:
        return None


_NULL_BUILDER = _NullBuilder()

__all__ = [
    "TreeBuilder",
    "AstBuilder",
    "CstBuilder",
    "_NullBuilder",
    "_NULL_BUILDER",
]
