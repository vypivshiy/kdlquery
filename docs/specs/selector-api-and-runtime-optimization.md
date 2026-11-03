# Specification: CSS3 Node Selector Fixes, Ergonomic Tree API & Runtime Optimizations

## Problem Statement

While `kdlquery` 1.6.0 introduced a high-throughput regex lexer and direct single-pass AST construction, several functional bugs, performance bottlenecks, and API friction points remain across the selector engine, tree mutation/reader APIs, and runtime data structures:

1. **Broken Complex and Sibling Queries Inside `:has()`**: In the CSS3 Node Selector engine, `_matches_has` evaluates inner complex selectors (e.g. `app:has(> router > route)` or `app:has(server > host)`) left-to-right by calling `_resolve_combinator`, which actually traverses upward (from child to parent or preceding sibling). As a result, any `:has()` query containing an internal combinator always fails. Additionally, leading `+` and `~` combinators inside `:has(+ sibling)` and `:has(~ sibling)` are parsed by the grammar but ignored during matching, falling back to descendant iteration instead of sibling resolution.
2. **Incomplete KDL 2.0 Literal & `:nth-child()` Support in Selectors**: The CSS3 Node Selector lexer cannot tokenize negative numbers (`node[offset=-5]` is lexed as an identifier string `"-5"`, failing integer equality) or KDL 2.0 keyword literals (`#null`, `#inf`, `#-inf`, `#nan`, which raise `SelectorError` or fail `NaN` comparison). Furthermore, `:nth-child()` lacks standard `odd`, `even`, and negative-step (`-n+3`) expressions.
3. **Runtime Memory Overhead and Avoidable Allocations**:
   - Core tree and selector data classes (`KdlNode`, `KdlValue`, `KdlDocument`, `ReadDiagnostic`, `WalkContext`, `DiagnosticCollector`, `_CstNodeFrame`, and selector AST nodes) do not use `__slots__`, allocating a per-instance `__dict__` on every parsed node and value.
   - During `AstBuilder` and slashdash (`/-`) parsing with `_NullBuilder`, the parser eagerly computes `Position` and `Span` coordinates via `bisect_right` for intermediate tokens (node names, property keys, children braces, and discarded subtrees) that are subsequently overwritten or discarded.
   - `SelectorMatcher` rebuilds filtered sibling lists (`same_type`) for every candidate node in `:first-child`, `:last-child`, `:nth-child()`, and `:only-child` ($O(M^2)$ per parent), and repeatedly normalizes selector type annotations on every node visit.
   - The serializer scans strings character-by-character in pure Python for `_escape_quoted` and `_is_bare_ident` even when strings contain only plain ASCII identifier characters.
4. **Reader & Mutation API Friction**:
   - `parse_into()` and `Walker.walk_document()` strictly require a `CSTDocument`, forcing `Reader` consumers to use `KDL2CSTParser` and convert nodes via `KdlNode.from_cst()`, forfeiting direct `AstBuilder` speedups and leaving `node.document` unset (`None`) during traversal.
   - `KdlNode.remove_child()` clears `child._document = None` on the removed child but fails to clear `_document` on its descendants, leaving stale document references in removed subtrees.
   - Constructing or mutating trees via `KdlNode.create()`, `add_arg()`, and `set_prop()` requires wrapping every primitive in `KdlValue.create(...)`.
5. **Incomplete Package Metadata**: The package metadata lacks license, keywords, and PyPI classifiers.

## Solution

Deliver a cohesive set of selector fixes, API ergonomics improvements, and pure-Python runtime optimizations:

1. **Fix & Complete the CSS3 Node Selector Engine**:
   - Repair `:has()` evaluation so complex selectors (`node:has(> a > b)`, `node:has(a > b)`) match right-to-left within the scoped candidate subtree, and honor leading `+` (adjacent sibling) and `~` (general sibling) combinators.
   - Extend the selector lexer and matcher to support negative int/float literals, `#null`, `#inf`, `#-inf`, and `#nan` (using `math.isnan` for `=` equality), plus `odd`, `even`, and negative `An+B` (`-n+3`) in `:nth-child()`.
2. **Optimize Memory & Pure-Python Hot Paths**:
   - Enable `slots=True` across all tree, reader, builder, and selector dataclasses while preserving full tree mutability.
   - Skip unused intermediate `Span` and `Position` calculations in the parser when operating with `_NullBuilder` (slashdash `/-`) or `AstBuilder`.
   - Eliminate quadratic sibling list allocations in `SelectorMatcher` pseudo-classes, pre-normalize type annotations at selector parse time, and cache dynamic normalization.
   - Add compiled regex fast-paths to the serializer for bare identifier checks and unescaped quoted strings.
3. **Unify Reader & Tree Mutation Ergonomics**:
   - Allow `parse_into()` and `Walker.walk_document()` to accept `KdlDocument`, `CSTDocument`, or raw KDL `str`, automatically wiring `node.document` across the tree.
   - Fix `KdlNode.remove_child()` to recursively clear `_document` across all descendants of the removed node.
   - Allow `KdlNode.create()`, `KdlNode.add_arg()`, and `KdlNode.set_prop()` to accept raw Python primitives (`str`, `int`, `float`, `bool`, `None`) in addition to `KdlValue`, with optional `type_annotation` support on `add_arg()` and `set_prop()`.
4. **Enrich Package Metadata**:
   - Add `license`, `keywords`, and `classifiers` to `pyproject.toml`, and update user/LLM documentation.

## User Stories

1. As a developer querying nested KDL structures, I want `doc.select("app:has(> router > route)")` and `doc.select("app:has(server > host)")` to accurately match ancestor nodes when the full target chain exists within the node's subtree, so that complex structural predicates work as expected.
2. As a developer querying sibling relationships, I want `doc.select("route:has(+ route[0='POST'])")` and `doc.select("plugin:has(~ plugin[enabled=#false])")` to evaluate against following siblings, so that forward-looking sibling queries work in CSS3 Node Selectors.
3. As a developer filtering KDL nodes with numeric properties or arguments, I want `doc.select("node[offset=-5]")` and `doc.select("node[delta=-0.5]")` to match negative integers and floats, so that signed numeric values can be queried directly.
4. As a developer working with KDL 2.0 keyword values, I want `doc.select("node[val=#null]")`, `doc.select("node[val=#inf]")`, `doc.select("node[val=#-inf]")`, and `doc.select("node[val=#nan]")` to match their respective Python values (`None`, `inf`, `-inf`, `nan`), so that all KDL 2.0 primitives are queryable.
5. As a developer selecting positional patterns, I want `:nth-child(odd)`, `:nth-child(even)`, and `:nth-child(-n+3)` to work in CSS3 Node Selectors, so that standard CSS3 positional expressions are supported.
6. As a developer parsing large KDL documents into memory, I want `KdlNode`, `KdlValue`, and `KdlDocument` instances to use `__slots__`, so that per-node memory overhead is reduced without sacrificing tree mutability.
7. As a developer mutating `KdlNode` and `KdlDocument` trees, I want all mutation operations (`add_child`, `insert_child`, `remove_child`, `add_arg`, `set_prop`, `remove_prop`, and direct attribute assignment) to continue functioning identically with `slots=True`.
8. As a developer parsing documents containing slashdash (`/-`) comments or using `kdlquery.parse()`, I want the parser to avoid computing line/column coordinates for discarded tokens or unused intermediate spans, so that parsing throughput improves.
9. As a developer running `:first-child`, `:last-child`, `:nth-child()`, and `:only-child` queries on nodes with many children, I want sibling position checks to avoid $O(M^2)$ list reconstructions and redundant type-annotation normalization, so that selector queries remain fast on wide trees.
10. As a developer serializing large KDL trees via `doc.to_kdl()`, I want bare identifier validation and string escaping to use compiled regex fast-paths, so that serialization throughput improves on string-heavy documents.
11. As a developer using the `Reader` API, I want to pass a KDL `str` or `KdlDocument` directly to `parse_into(source, reader)` without manually invoking `KDL2CSTParser`, so that I get single-pass `AstBuilder` speed and a simpler API while retaining backward compatibility with `CSTDocument`.
12. As a developer implementing `Reader.on_node`, I want `node.document` to be populated regardless of whether `parse_into` was called with a `str`, `KdlDocument`, or `CSTDocument`, so that document-level navigation (`node.siblings()`, `node.index()`) works consistently inside readers.
13. As a developer detaching a subtree via `parent.remove_child(index)`, I want `document` back-references to be cleared on both the removed child and all of its descendants, so that detached subtrees do not retain stale document references.
14. As a developer building or editing KDL trees programmatically, I want `KdlNode.create("server", args=["primary"], properties={"port": 8080})`, `node.add_arg("secondary")`, and `node.set_prop("port", 8080, type_annotation="(u16)")` to automatically wrap raw primitives into `KdlValue` instances while still accepting explicit `KdlValue` objects.
15. As a user discovering `kdlquery` on PyPI, I want accurate license, keyword, and classifier metadata displayed on the package page.

## Implementation Decisions

### 1. CSS3 Node Selector Engine Fixes & Extensions

- **Scoped `:has()` Complex Selector Resolution**:
  - When `:has()` has no leading combinator (`initial is None`), candidate target nodes (matching the rightmost compound `sel.compounds[-1]`) are drawn from `node.iter_descendants()`. Every ancestor/sibling step resolved via `sel.combinators` from right to left must remain strictly within `node`'s descendant subtree (i.e. `node` itself is the exclusive upper boundary, matching `_SubtreeContext` semantics).
  - When `:has()` has a leading `>` (`Combinator.CHILD`), the leftmost compound `sel.compounds[0]` must match a direct child of `node`. If there are no further combinators, any matching direct child satisfies `:has()`. If further combinators exist, candidate target nodes are drawn from the subtree of `node` (or evaluated such that the chain starts at a direct child of `node` and resolves downward/right-to-left to the target).
  - When `:has()` has a leading `+` (`Combinator.ADJACENT`) or `~` (`Combinator.GENERAL_SIBLING`), the leftmost compound `sel.compounds[0]` must match the immediately following sibling (`+`) or any following sibling (`~`) of `node`. Any subsequent combinators in `sel` are resolved relative to that matched sibling's subtree.
- **Negative Numbers and KDL 2.0 Keyword Literals in Selector Lexer & Matcher**:
  - Extend `SelectorLexer` to recognize `#null` (`None`), `#inf` (`math.inf`), `#-inf` (`-math.inf`), and `#nan` (`math.nan`) in addition to `#true` and `#false`.
  - In `SelectorLexer`, when reading an operator value (or signed numeric token such as `-5`, `+5`, `-0.5`), recognize leading `-` or `+` followed by digits as a `NUMBER` token (`int` or `float`) rather than a bare identifier, while preserving `-n` handling in `:nth-child()`.
  - In `SelectorMatcher._compare`, handle `=` comparison when both `actual` and `expected` are `float` and `math.isnan(expected)` by returning `math.isnan(actual)`.
- **Extended `:nth-child()` Expressions**:
  - Support `odd` (`NthExpr(a=2, b=1)`) and `even` (`NthExpr(a=2, b=0)`).
  - Support negative coefficients on `n`, including `-n` (`a=-1`) and `-2n` (`a=-2`), with optional `+B` or `-B` offsets (e.g. `-n+3`).
  - Update `_matches_nth_1based(pos, nth)` to handle negative `a` (`diff = pos - nth.b`; when `nth.a < 0`, require `diff <= 0 and diff % nth.a == 0`).

### 2. Pure-Python Runtime & Memory Optimizations

- **`slots=True` Across Data Model**:
  - Apply `@dataclass(slots=True)` (or `@dataclass(frozen=True, slots=True)` where already frozen) to `KdlDocument`, `KdlNode`, `KdlValue`, `_Keyword`, `ReadDiagnostic`, `DiagnosticCollector`, `WalkContext`, `_CstNodeFrame`, and all selector AST dataclasses (`NodeSelector`, `AttributeFilter`, `NthExpr`, `PseudoClass`, `CompoundSelector`, `ComplexSelector`, `SelectorList`).
  - All mutable fields on `KdlNode` (`name`, `type_annotation`, `args`, `properties`, `children`, `span`, `parent`, `_document`) and `KdlDocument` (`nodes`, `span`) remain mutable attributes.
- **Avoid Redundant `Span` / `Position` Calculations in Parser**:
  - Introduce a lightweight check or builder capability flag so that when `self.builder is _NULL_BUILDER` (inside `/-` slashdash discarded nodes/entries), `_Parser` skips `_pos()` / `_span()` `bisect_right` lookups entirely and passes `_EMPTY_SPAN`.
  - When building with `AstBuilder` (which does not consume `name_span`, `key_span`, `lbrace_span`, `children_block_span`, or intermediate `start_span`), avoid computing unused `Position` objects, computing only the final `node_span` (start offset of node/type to end offset of node), `arg` span, and `prop` entry span.
- **Selector Matcher & Type Normalization Optimizations**:
  - Normalize `type_annotation` strings in `NodeSelector` and `AttributeFilter` once during selector parsing (`SelectorParser`), and decorate `_normalize_type_annotation` with `@functools.lru_cache(maxsize=512)` so node/value type annotations are normalized in $O(1)$ amortized time.
  - In `SelectorMatcher._matches_pseudo`, avoid allocating a full `same_type` list on every check:
    - For `first-child`: iterate `siblings` and verify `node` is the first sibling matching `node_sel`.
    - For `last-child`: iterate ` reversed(siblings)` and verify `node` is the first sibling from the end matching `node_sel`.
    - For `only-child`: short-circuit as soon as a second sibling matching `node_sel` is found.
- **Serializer Fast-Paths**:
  - In `_escape_quoted(s)`, use a precompiled regex for characters requiring escaping (`[\x00-\x1f"\\\x7f\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff\ud800-\udfff]`). If the regex does not match `s`, return `f'"{s}"'` immediately in C without a per-character Python loop; otherwise use `re.sub` with a replacement callback.
  - Similarly optimize multiline line escaping and `_is_bare_ident(s)` using the precompiled identifier and disallowed-codepoint regexes.

### 3. Reader & Mutation API Enhancements

- **Unified `parse_into` and `Walker.walk_document` Input Contract**:
  - Update `Walker.walk_document(self, document: CSTDocument | KdlDocument | str)` and `parse_into(document: CSTDocument | KdlDocument | str, reader: Reader[T_node, R], *, strict: bool = False)`:
    - If `document` is a `str`, parse it via `parse(document)` into a `KdlDocument`.
    - If `document` is a `CSTDocument`, convert it via `KdlDocument.from_cst(document)` so all nodes have `_document` wired.
    - If `document` is a `KdlDocument`, ensure `_wire_document_refs()` has been applied and traverse `document.nodes` directly.
- **Recursive Document Unwiring in `KdlNode.remove_child`**:
  - In `KdlNode.remove_child(index)`, clear `child._document = None` and iterate `for desc in child.iter_descendants(): desc._document = None`.
- **Auto-Coercion of Primitive Values in `KdlNode`**:
  - Add a helper `_coerce_value(val: KdlValue | Any, type_annotation: str | None = None) -> KdlValue`:
    - If `isinstance(val, KdlValue)`: if `type_annotation is not None`, return `KdlValue(value=val.value, span=val.span, type_annotation=type_annotation)`; otherwise return `val`.
    - Otherwise wrap via `KdlValue.create(val, type_annotation=type_annotation)`.
  - Update `KdlNode.create()` so `args` accepts `Iterable[KdlValue | Any]` and `properties` accepts `Mapping[str, KdlValue | Any]`.
  - Update `KdlNode.add_arg(self, value: KdlValue | Any, *, type_annotation: str | None = None) -> None` and `KdlNode.set_prop(self, key: str, value: KdlValue | Any, *, type_annotation: str | None = None) -> None`.

### 4. Packaging Metadata & Documentation

- Add `license = "MIT"`, `keywords`, and standard Python 3.10–3.14 / topic `classifiers` to `pyproject.toml` (leaving `version = "1.6.0"` untouched for manual version bump).
- Update `README.md` and `llm.txt` to document the new selector capabilities, `parse_into(str | KdlDocument | CSTDocument, ...)`, and primitive value coercion in `KdlNode`.

## Testing Decisions

### High-Level Seams

All features and optimizations will be tested exclusively through the public top-level seams of `kdlquery` without coupling to private internal state:

1. **Selector Seam (`doc.select`, `doc.select_one`, `node.select`, `node.matches`)**:
   - Test `:has()` with multi-step complex selectors (`> a > b`, `a > b`, `a + b`, `a ~ b`) and leading sibling combinators (`:has(+ ...)`, `:has(~ ...)`), including boundary checks verifying that `node:has(a > b)` does not match when `a` is `node` itself or an ancestor of `node`.
   - Test negative numbers (`[x=-5]`, `[x=-3.14]`, `[0=-1]`), `#null`, `#inf`, `#-inf`, and `#nan` in property and argument filters.
   - Test `:nth-child(odd)`, `:nth-child(even)`, `:nth-child(-n+3)`, and `:nth-child(-2n+4)`.
2. **Reader & Document Seam (`parse_into`, `Walker.walk_document`)**:
   - Test `parse_into` with raw `str`, `KdlDocument`, and `CSTDocument` inputs, asserting identical output and verifying that `node.document` and root-level `node.siblings()` / `node.index()` are available inside `Reader.on_node`.
3. **Tree Construction, Mutation & Serialization Seam (`KdlNode.create`, `add_arg`, `set_prop`, `remove_child`, `to_kdl`)**:
   - Test creating and mutating nodes with raw primitives (`int`, `float`, `bool`, `None`, `str`) alongside `KdlValue` instances and optional `type_annotation` arguments.
   - Test that `parent.remove_child(i)` clears `document` on both the child and deeply nested grandchildren.
   - Verify round-trip serialization and `slots=True` compatibility across all existing mutation and navigation tests (`test_write.py`, `test_navigation.py`, `test_reader.py`, `test_tree_builder.py`, `test_kdl_parser.py`, `test_benchmark.py`).

## Out of Scope

- Bumping the version string in `pyproject.toml` (will be performed manually by the maintainer).
- Implementing the unfinalized official KQL draft (governed by ADR-0002).
- Adding C/Rust native extensions.

## Further Notes

- Prior art in the repository: `tests/test_selector.py`, `tests/test_reader.py`, `tests/test_write.py`, `tests/test_tree_builder.py`, and `tests/test_benchmark.py`.
