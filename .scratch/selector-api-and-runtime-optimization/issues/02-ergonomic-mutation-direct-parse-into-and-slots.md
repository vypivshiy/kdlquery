# 02: Ergonomic Tree Mutation, Direct `parse_into` (`str | KdlDocument | CSTDocument`), and Slotted Data Model

**What to build:**
Enable `slots=True` across the tree and reader data model (`KdlDocument`, `KdlNode`, `KdlValue`, `_Keyword`, `ReadDiagnostic`, `DiagnosticCollector`, `WalkContext`) while preserving full mutability of `KdlNode` and `KdlDocument`. Fix `KdlNode.remove_child()` so that `_document = None` is cleared recursively across all descendants of the removed child. Allow `KdlNode.create()`, `KdlNode.add_arg()`, and `KdlNode.set_prop()` to accept raw Python primitives (`str`, `int`, `float`, `bool`, `None`) alongside `KdlValue`, with optional `type_annotation` support on `add_arg()` and `set_prop()`. Expand `parse_into()` and `Walker.walk_document()` to accept `str`, `KdlDocument`, or `CSTDocument`, automatically wiring `node.document` across the tree.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] `KdlDocument`, `KdlNode`, `KdlValue`, `_Keyword`, `ReadDiagnostic`, `DiagnosticCollector`, and `WalkContext` use `slots=True` (no `__dict__` on instances) while all tree mutations continue to work identically.
- [ ] `KdlNode.remove_child(index)` clears `document` (`_document = None`) on both the removed child and all of its nested descendants.
- [ ] `KdlNode.create()` accepts raw Python primitives or `KdlValue` in `args` and `properties`.
- [ ] `KdlNode.add_arg(value, *, type_annotation=None)` and `KdlNode.set_prop(key, value, *, type_annotation=None)` accept raw Python primitives or `KdlValue`.
- [ ] `parse_into()` and `Walker.walk_document()` accept `str`, `KdlDocument`, or `CSTDocument` and ensure `node.document` is wired during `Reader` traversal.
- [ ] All existing and new reader, navigation, and mutation tests pass cleanly.
