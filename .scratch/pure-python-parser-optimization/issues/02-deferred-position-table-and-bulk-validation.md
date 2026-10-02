# 02: Deferred Position Table and Bulk Codepoint Validation

**What to build:**
Implement a precomputed `line_starts` offset table built once per document via newline regex scanning, and provide `offset_to_position(offset: int) -> Position` using `bisect_right` for O(log N) line and column resolution. Replace character-by-character codepoint validation with a single compiled regex search `_DISALLOWED_RE = re.compile(r"[\x00-\x08\x0e-\x1f\x7f\ud800-\udfff\u200e\u200f\u202a-\u202e\u2066-\u2069]")`. Validate BOM restrictions (`\ufeff` outside offset 0) in bulk with `"\ufeff" in source[1:]`.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] `line_starts` table is constructed using regex finditer over newline characters.
- [ ] `offset_to_position` computes 1-based line and column accurately using `bisect_right`.
- [ ] Character-by-character `_check_disallowed_literal` loop is replaced by bulk `_DISALLOWED_RE` check.
- [ ] BOM validation checks `source[1:]` in bulk.
- [ ] Exact line, column, and error codes are preserved for all invalid inputs in compliance tests.
- [ ] All existing tests pass.
