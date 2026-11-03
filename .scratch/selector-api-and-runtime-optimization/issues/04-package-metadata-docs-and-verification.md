# 04: Package Metadata, Documentation Sync & Full Suite Verification

**What to build:**
Enrich `pyproject.toml` with `license = "MIT"`, `keywords`, and standard PyPI `classifiers` without modifying `version`. Update `README.md` and `llm.txt` to document the newly supported selector features (`:has(+ ...)`, `:has(~ ...)`, negative numbers, `#null`/`#inf`/`#-inf`/`#nan`, `:nth-child(odd/even/-n+B)`), raw primitive auto-wrapping on `KdlNode`, and `parse_into(str | KdlDocument | CSTDocument, ...)`. Run full test, typecheck, and linter verification across the repository.

**Blocked by:** 01: CSS3 Node Selector `:has()`, KDL 2.0 Literals, `:nth-child()` & Matcher Optimizations, 02: Ergonomic Tree Mutation, Direct `parse_into` (`str | KdlDocument | CSTDocument`), and Slotted Data Model, 03: Parser Span Fast-Paths (`AstBuilder` / `_NullBuilder`) and Regex-Accelerated Serialization

**Status:** ready-for-agent

- [ ] `pyproject.toml` includes `license`, `keywords`, and `classifiers` while keeping `version = "1.6.0"` unchanged.
- [ ] `README.md` and `llm.txt` accurately reflect the updated selector syntax, `KdlNode` mutation ergonomics, and `parse_into` capabilities.
- [ ] `uv run pytest`, `uv run mypy kdlquery`, and `uv run ruff check .` pass with zero errors.
