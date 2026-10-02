# 01: Quoted node selectors and descendant combinators

**What to build:**
Enable selecting KDL nodes using double (`"..."`) and single (`'...'`) quoted strings in node selector positions, allowing node names containing special characters (`>`, `<`, `+`, `,`, `~`, `:`, etc.) to be selected without triggering combinators or syntax errors. Ensure combinators (child `>`, adjacent `+`, general sibling `~`, and descendant whitespace) work seamlessly with quoted node selectors (e.g., `"a>b" > "c+d"`, `"parent" "child"`), and that quoted node selectors work inside pseudo-classes (`:not("service:api")`, `:has("child>item")`).

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Both `"name"` and `'name'` match nodes with exact name `name`.
- [ ] Node names containing combinator characters like `"a>b"`, `'a+b'`, `"a~b"`, `"a,b"` match their corresponding nodes without parser errors or triggering combinators.
- [ ] Descendant combinators work when either ancestor or descendant node selector is quoted (e.g. `"parent" "child"`, `app "server"`).
- [ ] Explicit combinators (`>`, `+`, `~`) connect quoted node selectors (e.g. `"a>b" > "c+d"`).
- [ ] Quoted node selectors work inside `:not(...)` and `:has(...)`.
- [ ] Unterminated single or double quotes raise an informative `SelectorError`.
