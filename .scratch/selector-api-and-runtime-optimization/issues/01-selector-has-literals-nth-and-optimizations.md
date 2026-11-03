# 01: CSS3 Node Selector `:has()`, KDL 2.0 Literals, `:nth-child()` & Matcher Optimizations

**What to build:**
Repair and extend the CSS3 Node Selector engine so that `:has()` accurately evaluates multi-step complex selectors (`> a > b`, `a > b`, `a + b`, `a ~ b`) strictly within the scoped subtree of the candidate node and honors leading `+` and `~` sibling combinators (`:has(+ ...)`, `:has(~ ...)`). Extend the selector lexer and matcher to tokenize and compare negative numbers (`-5`, `-0.5`), `#null`, `#inf`, `#-inf`, and `#nan` (using `math.isnan` for `=` equality), and add support for `odd`, `even`, and negative-step expressions (`-n+3`) in `:nth-child()`. Optimize selector evaluation by adding `slots=True` to all selector AST dataclasses, pre-normalizing type annotations at selector parse time with an LRU-cached `_normalize_type_annotation`, and eliminating $O(M^2)$ `same_type` list allocations in `:first-child`, `:last-child`, `:only-child`, and `:nth-child()`.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] `node:has(> a > b)` and `node:has(a > b)` evaluate complex selectors accurately within `node`'s descendant subtree without matching `node` itself or its ancestors as `a`.
- [ ] `node:has(+ sibling)` and `node:has(~ sibling)` evaluate against the immediately following sibling or all following siblings of `node` (including complex sub-selectors).
- [ ] Negative integers and floats (`[offset=-5]`, `[0=-0.5]`) and KDL 2.0 keyword literals (`#null`, `#inf`, `#-inf`, `#nan`) are tokenized and matched in property and argument filters.
- [ ] `:nth-child(odd)`, `:nth-child(even)`, and negative-step `:nth-child(-n+B)` expressions match the expected 1-based positions.
- [ ] All selector AST dataclasses use `slots=True`, type annotations are pre-normalized/cached, and positional pseudo-classes avoid full sibling list allocations where possible.
- [ ] All existing and new selector tests pass cleanly.
