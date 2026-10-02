# 03: Regex-Driven Token Scanner and Two-Tier Lexer

**What to build:**
Replace the shallow per-character cursor loop with a compiled master regex scanner using named groups for high-frequency tokens (whitespace, newlines, delimiters, slashdash, numbers, bare identifiers, standard quoted strings). Implement specialized handlers for multi-hash raw strings, multiline blocks, and nested block comments. Strictly enforce ADR-0001 (prohibit single-line comments `//` following an escline `\`). Vectorize escape decoding with `re.sub()` and multiline prefix stripping with string methods. Provide a two-tier lexer architecture: fast internal tuple stream `(TokenType, raw, value, start_offset, end_offset)` and preserve the public `KDLLexer.tokenize() -> list[Token]` API.

**Blocked by:** 01-o1-token-slicing-and-escape-fastpath, 02-deferred-position-table-and-bulk-validation

**Status:** ready-for-agent

- [ ] Master regex scanner matches high-frequency tokens via `match(source, pos)` in native C speed.
- [ ] Multi-hash raw strings and multiline strings match all KDL 2.0 specifications.
- [ ] Nested block comments `/* ... */` track nesting depth correctly.
- [ ] Escline comment continuation prohibition (ADR-0001) is strictly enforced with error code `escline-comment-continuation`.
- [ ] String escape decoding is vectorized using `re.sub()`.
- [ ] Fast internal raw-offset tuple stream is available for high-performance parser consumption.
- [ ] Public `KDLLexer.tokenize() -> list[Token]` retains 100% backward compatibility.
- [ ] All 403 KDL 2.0 compliance test cases pass.
