# Prohibit Escline Comment Continuation

In standard KDL 2.0, single-line comments `//` following an escline (`\`) on subsequent lines silently terminate the node, turning subsequent arguments into new nodes. We decided to explicitly prohibit this pattern and raise `KDLParseError` with code `escline-comment-continuation`. Users should instead use block comments (`/* ... */`) or place comments before or after the node.

## Considered Options

- **Permissive continuation (Lenient mode)**: Transparently continue the node across single-line comments. Rejected because it violates official KDL grammar compatibility and parses differently across other KDL parsers.
- **Silent acceptance (Raw KDL 2.0)**: Allow standard behavior where the node silently breaks. Rejected because it causes subtle, catastrophic semantic bugs in DSLs.
- **Syntax error on comment continuation (Chosen)**: Reject the ambiguous syntax at parse time with an informative message and suggestions (`/* ... */` or moving comments outside the node). All 403 official KDL 2.0 compliance test cases continue to pass.
