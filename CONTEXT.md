# kdlquery

A pure Python KDL 2.0 lossless CST parser, AST query engine, and serializer.

## Language

**Escline**:
An escape line starting with a backslash `\` that allows continuing a node across lines.
_Avoid_: Line break escape, backslash continuation

**Escline Comment Continuation**:
The prohibited pattern where an escline `\` is followed on a subsequent line by a single-line comment `//`, which would otherwise silently terminate the node in standard KDL.
_Avoid_: Multiline comment break, dangling comment

**Node Space**:
Whitespace, block comments, or esclines that separate arguments and properties within a node.
_Avoid_: Entry separator, node whitespace

**CSS3 Node Selector**:
The query selector dialect used by `kdlquery` to traverse and filter KDL nodes, based on CSS3 syntax rather than the unfinalized official KQL draft.
_Avoid_: KQL selector, KDL query path

**Selector Identifier Disambiguation**:
The syntax convention allowing node names, property keys, or type annotations with KDL 2.0 special characters (`>`, `<`, `+`, `,`) to be wrapped in quotes (`"..."`, `'...'`) or backslash-escaped (`\>`).
_Avoid_: Operator escaping, quoted selector
