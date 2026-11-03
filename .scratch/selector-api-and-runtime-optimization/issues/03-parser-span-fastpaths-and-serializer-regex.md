# 03: Parser Span Fast-Paths (`AstBuilder` / `_NullBuilder`) and Regex-Accelerated Serialization

**What to build:**
Enable `slots=True` on `_CstNodeFrame`. Optimize the parser so that when discarding components with `_NullBuilder` (under `/-` slashdash), `Position` and `Span` calculations (`bisect_right`) are bypassed entirely, and when building with `AstBuilder`, unused intermediate spans (`name_span`, `key_span`, `lbrace_span`, `children_block_span`, and initial node `start_span`) are not computed. Accelerate KDL 2.0 serialization by adding compiled regex fast-paths to `_escape_quoted`, `_serialize_multiline`, and `_is_bare_ident`, bypassing character-by-character Python loops for clean strings and valid bare identifiers.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] `_CstNodeFrame` uses `slots=True`.
- [ ] Discarded slashdash (`/-`) subtrees and entries under `_NullBuilder` do not trigger `bisect_right` position lookups.
- [ ] `AstBuilder` parsing avoids computing unused intermediate spans while preserving exact `node.span`, `arg.span`, `prop.span`, and `doc.span` coordinates.
- [ ] `_escape_quoted`, `_serialize_multiline`, and `_is_bare_ident` use compiled regex fast-paths and pass all serialization and round-trip tests.
- [ ] All 403 official KDL 2.0 compliance tests, CST/AST equivalence tests, and performance benchmarks pass.
