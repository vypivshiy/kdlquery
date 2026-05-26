from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Generic, TypeVar

from .types import (
    CSTArgEntry,
    CSTDocument,
    CSTNode,
    CSTPropEntry,
    CSTValue,
    Span,
)


# ---------------------------------------------------------------------------
# Severity
# ---------------------------------------------------------------------------


class Severity(str, Enum):
    """Severity level of a read diagnostic."""

    ERROR = "error"
    WARNING = "warning"


# ---------------------------------------------------------------------------
# ReadDiagnostic
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReadDiagnostic:
    """A diagnostic message produced during tree reading.

    Attributes:
        message: Human-readable description of the diagnostic.
        severity: Severity level (error or warning).
        span: Source location the diagnostic refers to.
        path: Slash-separated path to the node within the document.
        hint: Optional suggestion for resolving the issue.
        code: Optional machine-readable diagnostic code.
        label: Optional short label for the diagnostic.
        notes: Optional additional context lines.
    """

    message: str
    severity: Severity
    span: Span
    path: str = ""
    hint: str = ""
    code: str = ""
    label: str | None = None
    notes: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# DiagnosticCollector
# ---------------------------------------------------------------------------


@dataclass
class DiagnosticCollector:
    """Collects diagnostic messages during tree walking with path tracking.

    Maintains a stack of path segments so that each diagnostic is
    automatically annotated with its location within the document tree.

    Attributes:
        diagnostics: Read-only list of collected diagnostics.
        path: Current slash-separated path (e.g. ``"root/child"``).
    """

    _diagnostics: list[ReadDiagnostic] = field(
        default_factory=list,
    )
    _path_segments: list[str] = field(default_factory=list)

    @property
    def diagnostics(self) -> list[ReadDiagnostic]:
        """list[ReadDiagnostic]: All diagnostics collected so far."""
        return self._diagnostics

    @property
    def path(self) -> str:
        """str: Current path built from pushed segments."""
        return "/".join(self._path_segments)

    def push(self, segment: str) -> None:
        """Push a path segment onto the stack.

        Args:
            segment: Path segment (typically a node name).
        """
        self._path_segments.append(segment)

    def pop(self) -> None:
        """Pop the most recently pushed path segment."""
        self._path_segments.pop()

    def error(
        self,
        message: str,
        *,
        span: Span,
        hint: str = "",
        code: str = "",
        label: str | None = None,
        notes: list[str] | None = None,
    ) -> None:
        """Record an error-level diagnostic.

        Args:
            message: Human-readable error description.
            span: Source location this error refers to.
            hint: Optional suggestion for resolving the error.
            code: Optional machine-readable error code.
            label: Optional short label.
            notes: Optional additional context lines.
        """
        self._diagnostics.append(
            ReadDiagnostic(
                message=message,
                severity=Severity.ERROR,
                span=span,
                path=self.path,
                hint=hint,
                code=code,
                label=label,
                notes=tuple(notes) if notes else (),
            )
        )

    def warning(
        self,
        message: str,
        *,
        span: Span,
        hint: str = "",
        code: str = "",
        label: str | None = None,
        notes: list[str] | None = None,
    ) -> None:
        """Record a warning-level diagnostic.

        Args:
            message: Human-readable warning description.
            span: Source location this warning refers to.
            hint: Optional suggestion for resolving the warning.
            code: Optional machine-readable warning code.
            label: Optional short label.
            notes: Optional additional context lines.
        """
        self._diagnostics.append(
            ReadDiagnostic(
                message=message,
                severity=Severity.WARNING,
                span=span,
                path=self.path,
                hint=hint,
                code=code,
                label=label,
                notes=tuple(notes) if notes else (),
            )
        )


# ---------------------------------------------------------------------------
# KdlValue
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class KdlValue:
    """A typed value extracted from a KDL node entry.

    Represents either a positional argument or a named property value
    in the high-level tree model.

    Attributes:
        value: The parsed Python value (str, int, float, bool, or None).
        span: Source location of this value in the original document.
        type_annotation: Raw type annotation string (e.g. ``"(u8)"``),
            or ``None`` if untyped.
    """

    value: Any
    span: Span
    type_annotation: str | None = None


# ---------------------------------------------------------------------------
# KdlNode
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class KdlNode:
    """An immutable node in a parsed KDL document tree.

    Corresponds to a single KDL node with its name, optional type annotation,
    positional arguments, named properties, and child nodes.

    Attributes:
        name: Node identifier string.
        type_annotation: Raw type annotation on the node itself, or ``None``.
        args: Positional argument values in source order.
        properties: Named property values keyed by property name.
        children: Child nodes in source order.
        span: Source location of this node in the original document.
    """

    name: str
    type_annotation: str | None
    args: tuple[KdlValue, ...]
    properties: MappingProxyType[str, KdlValue]
    children: tuple[KdlNode, ...]
    span: Span

    @staticmethod
    def _value_type_annotation(entry_value: object) -> str | None:
        """Extract the raw type annotation from a CST value, if present.

        Args:
            entry_value: A CST value object (CSTValue or CSTIdentifier).

        Returns:
            The raw type annotation string, or ``None``.
        """
        if isinstance(entry_value, CSTValue) and entry_value.type_annotation:
            return entry_value.type_annotation.raw
        return None

    @classmethod
    def from_cst(cls, node: CSTNode) -> KdlNode:
        """Construct a KdlNode from a CST node produced by the parser.

        Recursively converts all entries and children to the high-level
        model.

        Args:
            node: The CST node to convert.

        Returns:
            A frozen KdlNode with all entries and children converted.
        """
        args: list[KdlValue] = []
        properties: dict[str, KdlValue] = {}

        for entry in node.entries:
            if isinstance(entry, CSTArgEntry):
                args.append(
                    KdlValue(
                        value=entry.value.value,
                        span=entry.span,
                        type_annotation=cls._value_type_annotation(entry.value),
                    )
                )
            elif isinstance(entry, CSTPropEntry):
                properties[entry.key.value] = KdlValue(
                    value=entry.value.value,
                    span=entry.span,
                    type_annotation=cls._value_type_annotation(entry.value),
                )

        children = tuple(cls.from_cst(c) for c in node.children)
        type_ann = node.type_annotation.raw if node.type_annotation else None

        return cls(
            name=node.name.value,
            type_annotation=type_ann,
            args=tuple(args),
            properties=MappingProxyType(properties),
            children=children,
            span=node.span,
        )

    def get_arg(self, index: int, default: Any = None) -> Any:
        """Get a positional argument value by index.

        Args:
            index: Zero-based argument position.
            default: Value returned when the index is out of range.

        Returns:
            The unwrapped argument value, or ``default`` if out of range.
        """
        if 0 <= index < len(self.args):
            return self.args[index].value
        return default

    def get_prop(self, key: str, default: Any = None) -> Any:
        """Get a named property value.

        Args:
            key: Property name.
            default: Value returned when the property is absent.

        Returns:
            The unwrapped property value, or ``default`` if not found.
        """
        if key in self.properties:
            return self.properties[key].value
        return default

    def has_prop(self, key: str) -> bool:
        """Check whether a named property exists.

        Args:
            key: Property name.

        Returns:
            ``True`` if the node has a property with this name.
        """
        return key in self.properties

    def iter_args(self) -> Iterator[Any]:
        """Yield all positional argument values (unwrapped).

        Yields:
            Each argument's Python value in source order.
        """
        for a in self.args:
            yield a.value

    def iter_props(self) -> Iterator[tuple[str, Any]]:
        """Yield all named properties as ``(key, value)`` pairs.

        Yields:
            Tuples of ``(property_name, unwrapped_value)``.
        """
        for k, v in self.properties.items():
            yield k, v.value


# ---------------------------------------------------------------------------
# WalkContext
# ---------------------------------------------------------------------------


T_node = TypeVar("T_node")


@dataclass
class WalkContext(Generic[T_node]):
    """Context passed to Reader callbacks during tree walking.

    Provides the current node, its position in the tree, and methods
    for recursing into children and reporting diagnostics.

    Attributes:
        node: The KDL node currently being visited.
        parent: The parent node, or ``None`` for root-level nodes.
        index: Position of this node among its siblings.
        depth: Depth in the tree (``0`` for root-level nodes).
    """

    node: KdlNode
    parent: KdlNode | None
    index: int
    depth: int
    _walker: Walker[T_node]
    _processed: list[T_node] = field(default_factory=list)
    _collector: DiagnosticCollector = field(default_factory=DiagnosticCollector)

    def error(
        self,
        message: str,
        *,
        span: Span | None = None,
        hint: str = "",
        code: str = "",
        label: str | None = None,
        notes: list[str] | None = None,
    ) -> None:
        """Record an error-level diagnostic for the current node.

        Args:
            message: Human-readable error description.
            span: Source location. Defaults to the current node's span.
            hint: Optional suggestion for resolving the error.
            code: Optional machine-readable error code.
            label: Optional short label.
            notes: Optional additional context lines.
        """
        self._collector.error(
            message,
            span=span if span is not None else self.node.span,
            hint=hint,
            code=code,
            label=label,
            notes=notes,
        )

    def warning(
        self,
        message: str,
        *,
        span: Span | None = None,
        hint: str = "",
        code: str = "",
        label: str | None = None,
        notes: list[str] | None = None,
    ) -> None:
        """Record a warning-level diagnostic for the current node.

        Args:
            message: Human-readable warning description.
            span: Source location. Defaults to the current node's span.
            hint: Optional suggestion for resolving the warning.
            code: Optional machine-readable warning code.
            label: Optional short label.
            notes: Optional additional context lines.
        """
        self._collector.warning(
            message,
            span=span if span is not None else self.node.span,
            hint=hint,
            code=code,
            label=label,
            notes=notes,
        )

    def push(self, segment: str) -> None:
        """Push a path segment for diagnostic path tracking.

        Args:
            segment: Path segment to append (typically a node name).
        """
        self._collector.push(segment)

    def pop(self) -> None:
        """Pop the most recently pushed path segment."""
        self._collector.pop()

    def walk_children(self) -> list[T_node]:
        """Recursively walk all children of the current node.

        Returns:
            List of processed child results produced by the Reader.
        """
        return self._walker.walk_children(self.node, self)


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------


R = TypeVar("R")


class Reader(ABC, Generic[T_node, R]):
    """Abstract base class for processing a KDL document tree.

    Implementations receive each node during traversal via ``on_node``,
    produce an intermediate result of type ``T_node``, and finally
    aggregate all results via ``finalize`` into a return type ``R``.

    Type Parameters:
        T_node: The intermediate type produced for each visited node.
        R: The final result type returned by ``finalize``.
    """

    @abstractmethod
    def on_node(
        self,
        node: KdlNode,
        ctx: WalkContext[T_node],
    ) -> T_node:
        """Process a single KDL node during tree traversal.

        Args:
            node: The KDL node being visited.
            ctx: Walk context with parent, depth, index, and child
                recursion utilities.

        Returns:
            A processed result for this node.
        """
        ...

    @abstractmethod
    def error_node(
        self,
        node: KdlNode,
        message: str,
        ctx: WalkContext[T_node],
    ) -> T_node:
        """Handle a node whose processing raised an exception (strict mode).

        Called only when the Walker is in strict mode and ``on_node``
        raises. Implementations typically return a fallback value.

        Args:
            node: The KDL node that caused the error.
            message: String representation of the exception.
            ctx: Walk context for the errored node.

        Returns:
            A fallback result for this node.
        """
        ...

    @abstractmethod
    def finalize(
        self,
        nodes: list[T_node],
        diagnostics: list[ReadDiagnostic],
    ) -> R:
        """Aggregate all node results into the final output.

        Args:
            nodes: Results from all root-level nodes, in source order.
            diagnostics: All diagnostics collected during traversal.

        Returns:
            The final aggregated result.
        """
        ...


# ---------------------------------------------------------------------------
# Walker
# ---------------------------------------------------------------------------


class Walker(Generic[T_node]):
    """Depth-first tree traversal engine that drives a Reader.

    Converts CST nodes to KdlNode instances, walks the tree, and
    delegates processing to the Reader via WalkContext.

    Type Parameters:
        T_node: The intermediate type produced by the Reader for each node.

    Attributes:
        strict: When ``True``, exceptions in ``on_node`` are caught and
            delegated to ``error_node`` instead of propagating.
    """

    def __init__(
        self,
        reader: Reader[T_node, Any],
        *,
        strict: bool = False,
    ) -> None:
        """Initialize the Walker.

        Args:
            reader: The Reader implementation that processes each node.
            strict: If ``True``, catch exceptions in ``on_node`` and
                call ``error_node`` instead of raising.
        """
        self._reader = reader
        self._strict = strict

    @property
    def strict(self) -> bool:
        """bool: Whether strict error handling is enabled."""
        return self._strict

    def walk(
        self,
        node: KdlNode,
        parent: KdlNode | None = None,
        index: int = 0,
        depth: int = 0,
        processed: list[T_node] | None = None,
        collector: DiagnosticCollector | None = None,
    ) -> T_node:
        """Walk a single node through the Reader.

        Args:
            node: The KDL node to process.
            parent: The parent node, or ``None`` for root nodes.
            index: Position of this node among its siblings.
            depth: Depth in the tree (``0`` for root nodes).
            processed: Shared list to append results to. Created if
                not provided.
            collector: Shared diagnostic collector. Created if not
                provided.

        Returns:
            The processed result for this node.
        """
        _collector = collector if collector is not None else DiagnosticCollector()
        _processed = processed if processed is not None else []

        ctx = WalkContext[T_node](
            node=node,
            parent=parent,
            index=index,
            depth=depth,
            _walker=self,
            _processed=_processed,
            _collector=_collector,
        )

        _collector.push(node.name)
        try:
            result = self._reader.on_node(node, ctx)
        except Exception as exc:
            if self._strict:
                result = self._reader.error_node(node, str(exc), ctx)
            else:
                raise
        finally:
            _collector.pop()

        _processed.append(result)
        return result

    def walk_children(
        self,
        parent: KdlNode,
        parent_ctx: WalkContext[T_node] | None = None,
    ) -> list[T_node]:
        """Walk all children of a parent node.

        Args:
            parent: The node whose children to traverse.
            parent_ctx: Walk context of the parent, used to share
                diagnostics and compute child depth. If ``None``, a
                fresh collector and depth ``1`` are used.

        Returns:
            List of processed results for each child, in source order.
        """
        collector = (
            parent_ctx._collector if parent_ctx is not None else DiagnosticCollector()
        )
        child_depth = (parent_ctx.depth + 1) if parent_ctx is not None else 1
        results: list[T_node] = []

        for i, child in enumerate(parent.children):
            self.walk(
                node=child,
                parent=parent,
                index=i,
                depth=child_depth,
                processed=results,
                collector=collector,
            )

        return results

    def walk_document(
        self,
        document: CSTDocument,
    ) -> tuple[list[T_node], list[ReadDiagnostic]]:
        """Walk an entire CST document through the Reader.

        Converts all top-level CST nodes to KdlNode instances and
        traverses them recursively.

        Args:
            document: The CST document produced by the parser.

        Returns:
            A tuple of ``(root_results, diagnostics)`` where
            ``root_results`` is a list of processed root-level nodes
            and ``diagnostics`` is a list of collected diagnostics.
        """
        collector = DiagnosticCollector()
        children = tuple(KdlNode.from_cst(n) for n in document.nodes)
        results: list[T_node] = []

        for i, child in enumerate(children):
            self.walk(
                node=child,
                parent=None,
                index=i,
                depth=0,
                processed=results,
                collector=collector,
            )

        return results, collector.diagnostics


# ---------------------------------------------------------------------------
# parse_into
# ---------------------------------------------------------------------------


def parse_into(
    document: CSTDocument,
    reader: Reader[T_node, R],
    *,
    strict: bool = False,
) -> tuple[R, list[ReadDiagnostic]]:
    """Parse a CST document through a Reader in a single call.

    Convenience function that creates a Walker, walks the document,
    and finalizes the result.

    Args:
        document: The CST document produced by ``KDL2CSTParser.parse``.
        reader: The Reader implementation to process the tree.
        strict: If ``True``, catch exceptions in ``on_node`` and call
            ``error_node`` instead of raising.

    Returns:
        A tuple of ``(final_result, diagnostics)`` where
        ``final_result`` is the value returned by ``reader.finalize``
        and ``diagnostics`` is the list of collected diagnostics.
    """
    walker = Walker(reader, strict=strict)
    nodes, diagnostics = walker.walk_document(document)
    result = reader.finalize(nodes, diagnostics)
    return result, diagnostics


__all__ = [
    "DiagnosticCollector",
    "KdlValue",
    "KdlNode",
    "ReadDiagnostic",
    "Reader",
    "Severity",
    "WalkContext",
    "Walker",
    "parse_into",
]
