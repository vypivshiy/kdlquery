# Adopt CSS3 Selectors Due to Unfinalized Official KQL Specification

The official KDL 2.0 release finalized only the document format; the query specification (`QUERY-SPEC.md`, KQL) remains an unreleased, actively contested draft without community consensus or implementation in reference parsers. We decided to adopt a battle-tested CSS3 selector dialect as `kdlquery`'s query language, resolving conflicts with KDL 2.0 identifier characters (`>`, `<`, `+`, `,`) through quoted strings (`"..."`, `'...'`) and backslash escaping (`\>`).

## Considered Options

- **Implement draft KQL (`QUERY-SPEC.md`)**: Rejected because KQL is unreleased, actively changing, lacks pseudo-classes (`:has()`, `:not()`, `:nth-child()`), and has documented syntactic ambiguities with KDL 2.0 identifiers (`[a>b>c]`, `lorem+ipsum`).
- **CSS3 without escaping/quotes**: Rejected because valid KDL 2.0 node names and property keys containing `>`, `<`, `+`, or `,` could not be selected.
- **CSS3 with quotes and backslash disambiguation (Chosen)**: Combinators (`>`, `+`, `~`, `,`, whitespace) retain standard CSS semantics, while node names, property keys, and type annotations containing special characters can be specified via quotes (`"a>b"`, `'foo,bar'`) or backslash escaping (`a\>b`).
