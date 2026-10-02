# 04: Disambiguated property filter keys and positional argument differentiation

**What to build:**
Allow property keys in attribute filters to be specified using double-quoted (`["foo.bar"="val"]`), single-quoted (`['foo.bar'="val"]`), or backslash-escaped (`[foo\.bar="val"]`) strings. Distinguish between positional argument index filters and string property keys: unquoted integer numbers (`[0="val"]`) target positional argument index 0, whereas quoted numbers (`["0"="val"]`, `['0'="val"]`) target properties with string key `"0"`.

**Blocked by:** 01-quoted-node-selectors, 02-backslash-escaped-identifiers

**Status:** ready-for-agent

- [ ] Quoted strings (both `"` and `'`) can be used as attribute filter keys (e.g. `["app.name"="api"]`, `['foo:bar'="baz"]`).
- [ ] Unquoted property keys with backslash escapes work (e.g. `[app\.name="api"]`).
- [ ] Unquoted number in key position (`[0="val"]`) matches the positional argument at index 0.
- [ ] Quoted number in key position (`["0"="val"]`, `['0'="val"]`) matches the property with string key `"0"`.
- [ ] Backward compatibility is preserved for existing positional argument filters and property filters.
