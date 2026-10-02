# 01: O(1) Token Slicing and Fast-Path String Escape Decoding

**What to build:**
Eliminate the quadratic complexity bottleneck in `_Parser._slice(start, end)` by slicing the retained source string directly `source[start:end]` or anchoring to the local token index `self.i`, returning `tok.raw` directly for unannotated values. Eliminate string allocation copies in `_try_read_number` by using `rx.match(self.c.src, pos=self.c.i)` instead of slicing `rem = self.c.src[self.c.i :]`, and gating radix matching behind `ch == '0' and peek in 'xXoObB'`. Add an immediate fast path to `_decode_escape_body`: `if "\\" not in body: return body` to bypass character traversal on strings without escapes.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] `_slice(start, end)` operates in O(1) time without looping over all tokens from index 0.
- [ ] Values without type annotations return `tok.raw` directly.
- [ ] `_try_read_number` matches regexes with `pos=self.c.i` avoiding full-string tail slices.
- [ ] Radix checks (`0x`, `0o`, `0b`) are gated by single-character lookahead.
- [ ] `_decode_escape_body` returns immediately when `\` is not present.
- [ ] All 403 KDL 2.0 compliance test cases pass without regressions.
