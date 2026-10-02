---
title: "Selector Identifier Disambiguation (Quotes and Escapes for KDL 2.0 Characters)"
labels:
  - ready-for-agent
---

# Spec: Selector Identifier Disambiguation

## Problem Statement

In KDL 2.0, bare identifiers allow characters such as `>`, `<`, `+`, and `,`. Furthermore, node names, type annotations, and property keys can be arbitrary quoted strings. However, `kdlquery`'s CSS3 Node Selector parser treats these characters strictly as combinators (`>`, `+`), list separators (`,`), or invalid identifier characters, and raises syntax errors when quoted strings or backslash escapes appear in selector node positions (`SelectorError: Expected node selector, got '"foo"'`).

As a result, users cannot query valid KDL 2.0 documents when nodes, type annotations, or property keys contain any of these characters.

## Solution

Implement **Selector Identifier Disambiguation** within the CSS3 Node Selector engine:
1. Support both double (`"..."`) and single (`'...'`) quoted strings for node names, type annotations, and property filter keys.
2. Support CSS-style backslash escaping (`\>`, `\+`, `\,`, `\:`, `\~`) within unquoted identifiers.
3. Automatically unescape backslash escapes during lexing so that AST nodes store literal, unescaped strings matching `KdlNode` properties.
4. Distinguish positional arguments from numeric property keys in attribute filters: unquoted numbers (`[0="val"]`) target positional arguments, while quoted numbers (`["0"="val"]` / `['0'="val"]`) target properties with string keys.

## User Stories

1. As a developer querying a KDL 2.0 document with node names containing `>`, I want to query `doc.select('"a>b"')` or `doc.select(r"a\>b")`, so that I can select nodes named `a>b` without triggering the child combinator.
2. As a developer querying a KDL 2.0 document with node names containing `+`, I want to query `doc.select('"a+b"')` or `doc.select(r"a\+b")`, so that I can select nodes named `a+b` without triggering the adjacent sibling combinator.
3. As a developer querying a KDL 2.0 document with node names containing `~`, I want to query `doc.select('"a~b"')` or `doc.select(r"a\~b")`, so that I can select nodes named `a~b` without triggering the general sibling combinator.
4. As a developer querying a KDL 2.0 document with node names containing `,`, I want to query `doc.select('"a,b"')` or `doc.select(r"a\,b")`, so that I can select nodes named `a,b` without triggering the selector list separator.
5. As a Python developer writing queries in double-quoted strings, I want to use single quotes inside selectors like `doc.select("server['app.name']")`, so that I do not have to escape quotes in Python source code.
6. As a Python developer writing queries in single-quoted strings, I want to use double quotes inside selectors like `doc.select('server["app.name"]')`, so that I can use standard double quotes naturally.
7. As a developer working with type annotations containing special characters, I want to query `doc.select('("my/custom:type")node')` or `doc.select(r'(my\/custom\:type)node')`, so that I can filter by complex type annotations.
8. As a developer working with type-annotated properties, I want to query `doc.select('node[("u:16")port=8080]')`, so that type annotations with special characters inside property filters work seamlessly.
9. As a developer querying a node with numeric string property keys, I want `doc.select('item["0"="value"]')` to match the property `"0"`, so that string property keys are not confused with positional argument indices.
10. As a developer querying a node with positional arguments, I want `doc.select('item[0="value"]')` to match the first positional argument, so that existing positional argument filters remain backward-compatible.
11. As a developer querying properties whose keys contain special characters, I want to use `doc.select('node["api.version"="v1"]')` or `doc.select(r'node[api\.version="v1"]')`, so that dots and punctuation in property keys are supported.
12. As a developer combining disambiguated node selectors, I want `doc.select('"parent>node" > "child+node"')` to select `child+node` directly inside `parent>node`, so that combinations of combinators and disambiguated names function reliably.
13. As a developer using pseudo-classes, I want `doc.select('"service:web":not("service:api")')` or `doc.select('node:has("child>item")')`, so that disambiguated identifiers work inside `:not()`, `:has()`, and other pseudo-classes.
14. As a developer writing malformed selectors with unterminated quotes, I want to receive an informative `SelectorError`, so that I can quickly diagnose syntax errors in queries.

## Implementation Decisions

- **Selector Dialect**: Retain the CSS3 Node Selector dialect and do not adopt the unreleased KQL draft, in accordance with ADR-0002.
- **Lexer Tokenization**:
  - Add support for single-quoted strings (`'...'`) in addition to double-quoted strings (`"..."`).
  - Extend identifier scanning to support backslash escaping of special characters (`()[]{}=^$~*+>:#"/,`).
  - Automatically unescape escaped characters in the lexer so the token value is the literal unescaped string.
- **Parser Grammar**:
  - Update `_node_selector` to accept `STRING` tokens in addition to `IDENT` and `STAR`.
  - Update `_type_annotation` to accept `STRING` tokens as well as `IDENT` tokens inside `(...)`.
  - Update `_filter_inner` to accept `STRING` tokens for property keys.
  - When the key token is `NUMBER`, treat it as a positional argument index; when it is `STRING` or `IDENT`, treat it as a property key.
- **Combinator Precedence**:
  - Unquoted `>` and `+` tokens always represent combinators; whitespace around combinators remains optional in accordance with standard CSS rules.

## Testing Decisions

- **Test Seam**: Tests will be conducted strictly against `KdlDocument.select()`, `KdlDocument.select_one()`, `KdlNode.select()`, and `KdlNode.matches()`. No internal lexer/parser unit tests will be created.
- **Scope of Tests**:
  - Documents with KDL 2.0 nodes having names `a>b`, `foo+bar`, `x~y`, `a,b`, and `ns:item`.
  - Matching using double quotes, single quotes, and backslash escapes.
  - Property filters with dots, colons, and numeric string keys (`["0"=...]` vs `[0=...]`).
  - Combinator chains between nodes with special names (e.g. `"a>b" > "c+d"`).
  - Pseudo-classes `:not(...)` and `:has(...)` containing disambiguated identifiers.
- **Prior Art**: `tests/test_selector.py` serves as the test style and structure reference.

## Out of Scope

- Adopting the official unreleased KQL syntax (`>>`, `++`, `||`, `[]`).
- XPath or JSONPath selector syntax.
- Raw multiline strings inside selector queries (`#"""..."""#`).
- Dynamic selector interpolation or regex node name matching.

## Further Notes

- Aligns directly with [`docs/adr/0002-css3-selectors-over-unfinalized-kql.md`](docs/adr/0002-css3-selectors-over-unfinalized-kql.md) and [`CONTEXT.md`](CONTEXT.md).
