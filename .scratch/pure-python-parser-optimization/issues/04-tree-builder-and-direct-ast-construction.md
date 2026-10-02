# 04: Tree Builder Seam and Direct AST Construction

**What to build:**
Introduce a Tree Builder seam (`TreeBuilder`, `AstBuilder`, `CstBuilder`). Refactor the parser to drive the builder events (`start_node`, `add_arg`, `add_prop`, `start_children`, `end_children`, `end_node`, `finish_document`). Implement `AstBuilder` to construct `KdlDocument`, `KdlNode`, and `KdlValue` directly in a single pass, wiring `node.parent = parent` and `node._document = doc` in-flight without intermediate CST object allocation. Implement `CstBuilder` used by `KDL2CSTParser` to maintain 100% compatibility for lossless CST workflows. Update `kdlquery.parse(source)` to use `AstBuilder` directly.

**Blocked by:** 03-regex-scanner-and-two-tier-lexer

**Status:** resolved

- [x] `TreeBuilder` protocol defines builder lifecycle methods.
- [x] `AstBuilder` builds `KdlDocument` directly in a single pass without intermediate `CSTNode` allocations.
- [x] Parent references (`node.parent`) and document references (`node._document`) are wired in-flight during AST construction.
- [x] `CstBuilder` builds complete `CSTDocument` identical to previous parser output.
- [x] `kdlquery.parse(source)` uses `AstBuilder` for high-throughput AST generation.
- [x] `KDL2CSTParser().parse(source)` uses `CstBuilder` and passes all existing CST tests.
- [x] CSS3 selectors and document navigation (`select`, `select_one`, `iter_nodes`, `parents`, `siblings`) function identically.
