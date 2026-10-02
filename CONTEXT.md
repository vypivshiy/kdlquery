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
