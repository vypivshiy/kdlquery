# 03: Disambiguated type annotations with quotes and escapes

**What to build:**
Support quoted strings (`("type")`, `('type')`) and backslash escapes (`(my\/type)`, `(ns\:type)`) within type annotations on node selectors and within property filters (e.g. `("my/custom:type")node`, `node[("u:16")port=8080]`). Unescape escaped characters so the AST type annotation stores the literal type string.

**Blocked by:** 01-quoted-node-selectors, 02-backslash-escaped-identifiers

**Status:** resolved

- [x] Type annotations on node selectors accept double-quoted and single-quoted strings (e.g. `("my/type")node`, `('custom:v1')node`).
- [x] Type annotations accept backslash-escaped identifiers without quotes (e.g. `(my\/type)node`, `(custom\:v1)node`).
- [x] Type annotations within attribute filters accept quotes and backslash escapes (e.g. `node[("u:16")port=8080]`, `node[(u\:16)port=8080]`).
- [x] Matching correctly compares against `KdlNode.type_annotation` and property value type annotations.
