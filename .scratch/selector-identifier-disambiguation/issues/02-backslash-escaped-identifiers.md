# 02: Backslash-escaped identifiers in selector lexer and parser

**What to build:**
Support CSS-style backslash escaping within unquoted identifiers for node names (e.g. `a\>b`, `a\+b`, `a\,b`, `a\:b`, `a\~b`), so developers can select nodes containing special characters without surrounding them in quotes. The selector lexer automatically unescapes these escape sequences so that the AST node stores the literal string matching `KdlNode.name`.

**Blocked by:** None (can start immediately)

**Status:** resolved

- [x] Backslash-escaped special characters in unquoted identifiers (`\>`, `\+`, `\,`, `\:`, `\~`, etc.) are recognized as part of the identifier.
- [x] The lexer automatically unescapes the escape sequences so `raw="a\\>b"` produces `value="a>b"`.
- [x] Queries using backslash-escaped identifiers match nodes with special characters via `select()`, `select_one()`, and `matches()`.
- [x] Escaped identifiers can be chained with combinators (e.g. `a\>b > c\+d`).
- [x] Escaped identifiers work inside `:not(...)` and `:has(...)`.
