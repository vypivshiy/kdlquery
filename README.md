# kdlquery

A pure Python [KDL 2.0](https://kdl.dev/spec) parser with a CSS3-like selector API.

kdlquery provides a lossless CST parser and a mutable node tree with parent/sibling navigation. It includes a CSS3-like selector engine for querying nodes, a Reader API for transforming documents into Python objects with source-span diagnostics, and a spec-compliant serializer for emitting KDL 2.0 text from any tree.

Designed as a foundation for building DSLs — KDL is a good fit for configuration, schemas, and structured data. The parser and selector API together cover the common cases of parsing, validating, and linting KDL documents.

Parser test cases are borrowed from the [official KDL test suite](https://github.com/kdl-org/kdl/tree/main/tests/test_cases).

## Requirements

Python 3.10+, no external dependencies.

## Installation

```bash
pip install kdlquery
```

## Quick start

### Parsing

```python
from kdlquery import parse

doc = parse("""
app "my-service" version="1.0.0" {
    (network)server "primary" port=8080 tls=#true {
        host "localhost"
        host "127.0.0.1"
        timeout idle=30 connect=5
    }

    (network)server "replica" port=8081 tls=#false {
        host "replica.local"
        timeout idle=60 connect=5
    }

    router {
        route "GET" "/api/users" handler="users.list" auth=#true
        route "POST" "/api/users" handler="users.create" auth=#true
        route "GET" "/api/health" handler="health.check" auth=#false
        route "GET" "/static/*" handler="static.serve" auth=#false
    }

    plugins {
        plugin "auth" enabled=#true {
            (jwt)secret "hs256" key=(regex)"hs(256|512)"
            expires (i32)3600
        }
        plugin "cache" enabled=#true {
            backend "redis" host="cache.local" port=(u16)6379
        }
        plugin "debug" enabled=#false
    }

    (i32)workers 4
    (i32)timeout 30
    limits max-conn=(u32)1000 max-req=(u32)500
}
""")
```

`parse()` returns a `KdlDocument` — a tree of `KdlNode` objects with parent references wired automatically.

### Node access

```python
# Top-level nodes
app = doc.nodes[0]
app.name                          # "app"
app.get_arg(0)                    # "my-service"
app.get_prop("version")           # "1.0.0"

# Children
for child in app.children:
    print(child.name, child.get_arg(0))

# Or query specific children directly
for server in app.select("server"):
    print(server.get_arg(0), server.get_prop("port"))

# Tree navigation via KdlDocument (backward-compatible)
doc.parent_of(app.children[0]) is app   # True
doc.depth_of(app)                        # 0
doc.index_of(app.children[1])            # 1
doc.siblings_of(app.children[0])         # [child_0, child_1, ...]
```

### Selector API

>[!NOTE]
> This selector implementation intentionally diverges from the [official KDL Query draft](https://github.com/kdl-org/kdl/blob/main/QUERY-SPEC.md) and closely mirrors CSS3 syntax.
> Should the official query language be finalized and stabilized, a compatibility port to this project may be considered.


CSS3-like selectors for querying the node tree.

```python
# By name
doc.select("server")
# → [server "primary", server "replica"]

# By type annotation
doc.select("(network)")
# → [server "primary", server "replica"]

# Property filters
doc.select("server[tls=#true]")
# → [server "primary"]

doc.select('route[handler^="users"]')
# → [route "GET" "/api/users", route "POST" "/api/users"]

# Argument filters (select first arg)
doc.select('route[0="GET"]')
# → [route "GET" "/api/users", route "GET" "/api/health", route "GET" "/static/*"]

# select all args
doc.select('route[*="POST"]')
# → [route "POST" "/api/users"]

# Type-annotated properties
doc.select("backend[(u16)port]")
# → [backend "redis"]

# Type-annotated arguments
doc.select("expires[(i32)0]")
# → [expires (i32)3600]

# Combinators: child (>), descendant (space), adjacent sibling (+), general sibling (~)
doc.select("app > server")
# → [server "primary", server "replica"]

doc.select("app route")
# → all four routes

doc.select('route[0="GET"] + route')
# → [route "POST" ..., route "GET" ...]

# Pseudo-classes
doc.select("route:first-child")
# → [route "GET" "/api/users"]

doc.select("(i32):last-child")
# → [timeout 30]

doc.select("host:only-child")
# → [host "replica.local"]

doc.select("app:root")
# → [app]

# :not()
doc.select("server:not([port=8080])")
# → [server "replica"]

doc.select("plugin:not(:empty)")
# → [plugin "auth", plugin "cache"]

# :has()
doc.select("plugin:has(backend)")
# → [plugin "cache"]

doc.select("app:has(> router)")
# → [app]

doc.select("plugin:has(> secret[(regex)key])")
# → [plugin "auth"]

# Comma (union) — deduplicates by node identity
doc.select("app, router")
# → [app, router]

doc.select("server, server")
# → [server "primary", server "replica"]  (no duplicates)

# select_one — lazy, returns first match or None
doc.select_one("server[tls=#true]")
# → server "primary"
```

### Node selectors

`KdlNode` also has `select()` and `select_one()` for querying within a node's children subtree. This is useful when you already have a reference to a specific node and want to drill down.

Selectors on `KdlNode` are scoped to descendants — they cannot access parent or root nodes.

```python
app = doc.nodes[0]

# Query descendants of app
app.select("server")
# → [server "primary", server "replica"]

app.select("server > host")
# → [host "localhost", host "127.0.0.1", host "replica.local"]

app.select("route:first-child")
# → [route "GET" "/api/users"]

# All selectors work — filters, combinators, pseudo-classes
app.select('plugin:has(> backend)')
# → [plugin "cache"]

app.select_one("host")
# → host "localhost"

# Scoped to subtree — won't escape the node
primary = doc.select_one("server[tls=#true]")
primary.select("host")
# → [host "localhost", host "127.0.0.1"]

# :root never matches on KdlNode — there is no root concept in a subtree
app.select("*:root")
# → []
```

### Selector identifier disambiguation

KDL 2.0 identifiers allow characters that CSS3 selectors treat as combinators or syntax tokens (`>`, `<`, `+`, `,`, `:`, `~`, `.`, whitespace). To query nodes, properties, or type annotations containing these characters, use double quotes (`"..."`), single quotes (`'...'`), or backslash escaping (`\`):

```python
# Quoted node names (avoids combinator and separator collisions)
doc.select('"a>b"')
doc.select('"service:web"')
doc.select("'c+d'")

# Backslash-escaped identifiers (CSS-style)
doc.select(r"a\>b")
doc.select(r"ns\:service")
doc.select(r"hello\ world")

# Quoted or escaped type annotations
doc.select('("my/custom:type")service')
doc.select(r"(my\/custom\:type)service")
doc.select('service[("u:16")port=8080]')
doc.select('app[("u:16")1=100]')

# Quoted or escaped property keys (supports dots, colons, brackets, spaces)
doc.select('service["app.name"="api-gateway"]')
doc.select(r'service[app\.name="api-gateway"]')
doc.select('service["foo:bar"="baz"]')
doc.select('service["a>b"="gt_val"]')

# Positional arguments vs numeric property keys
doc.select('route[0="GET"]')       # unquoted integer: positional argument at index 0
doc.select('route["0"="GET"]')     # quoted string: property with string key "0"
doc.select("worker[0]")            # positional argument at index 0 exists
doc.select('worker["0"]')          # property with string key "0" exists

# Combinators and pseudo-classes with disambiguated selectors
doc.select('"parent>node" > "child+node"')
doc.select('"service:web":not("service:api")')
doc.select('service:has(> route["api.version"="v2"])')
```

### Navigation API

DOM-like methods for traversing the node tree. Inspired by `Element.closest()`, `Element.matches()`, and `Node.parentElement` from the browser DOM.

```python
app = doc.nodes[0]
server = app.children[0]
host = server.children[0]

# Direct parent access
host.parent is server                 # True
server.parent is app                  # True
app.parent is None                    # True — root node

# Walk to root
host.root is app                      # True

# Owning document
host.document is doc                  # True

# Depth in tree
app.depth()                           # 0
server.depth()                        # 1
host.depth()                          # 2

# Position among siblings
server.index()                        # 0
host.siblings()                       # [host, host, timeout]

# Iterate descendants
list(app.iter_descendants())          # all nodes under app

# All ancestors, bottom-up
host.parents()                        # [server, app]

# Check if node matches a selector
host.matches("host")                  # True
host.matches("server > host")         # True
host.matches("server[tls=#false]")    # False

# Find nearest ancestor matching a selector (checks self first)
host.closest("server")                # server node
host.closest("(network)server[tls=#true]")  # server "primary"
host.closest("nonexistent")           # None
```

### Reader API

The Reader API transforms a KDL document into domain objects while collecting source-span diagnostics. While `parse()` constructs a queryable `KdlDocument` directly, `parse_into()` walks a `CSTDocument` from `KDL2CSTParser` to preserve exact source positions for validation errors.

```python
from kdlquery import KDL2CSTParser, DictReader, parse_into

cst = KDL2CSTParser().parse("""
database "primary" {
    host "db.example.com"
    port 5432
}
database "replica" {
    host "db-replica.example.com"
    port 5433
}
""")

result, diagnostics = parse_into(cst, DictReader())

# result is a list of plain dicts
# [
#   {
#     "name": "database",
#     "args": ("primary",),
#     "props": {},
#     "children": [
#       {"name": "host", "args": ("db.example.com",), "props": {}, "children": []},
#       {"name": "port", "args": (5432,), "props": {}, "children": []},
#     ],
#   },
#   ...
# ]
```

`DictReader` is a built-in reader that produces nested dicts. To build a custom reader, subclass `Reader` and implement `on_node`:

```python
from kdlquery import KdlNode, Reader, WalkContext

class ConfigReader(Reader[dict, dict]):
    def on_node(self, node: KdlNode, ctx: WalkContext[dict]) -> dict:
        if node.name == "server":
            children = ctx.walk_children()
            return {
                "id": node.get_arg(0),
                "port": node.get_prop("port"),
                "tls": node.get_prop("tls", False),
                "hosts": [c["host"] for c in children if "host" in c],
            }
        if node.name == "host":
            return {"host": node.get_arg(0)}
        return ctx.walk_children()  # recurse by default

    def finalize(self, nodes, diagnostics):
        return {n["id"]: n for n in nodes if "id" in n}
```

### Mutation and serialization

`KdlNode`, `KdlValue`, and `KdlDocument` are mutable. Node containers (`args`, `properties`, `children`, `nodes`) are plain Python `list`/`dict` — you can build, edit, and re-emit any KDL tree without going through the parser.

**Building nodes from scratch:**

```python
from kdlquery import KdlNode, KdlValue

node = KdlNode.create(
    "@check",
    args=[KdlValue.create("exists")],
    children=[
        KdlNode.create("css", args=[KdlValue.create(".foo")]),
        KdlNode.create("to-bool"),
        KdlNode.create("fallback", args=[KdlValue.create(False)]),
    ],
)
```

`KdlValue.create()` accepts Python primitives (`bool`, `None`, `int`, `float`, `str`) and infers the KDL literal at serialization time. For raw passthrough of an arbitrary keyword (`#true`, `#null`, `#inf`, or implementation-defined), use `KdlValue.keyword("#custom")` — the string is emitted verbatim.

**Mutating an existing tree:**

```python
doc = parse(source)
struct = doc.select_one("struct")

# Insert children — parent and document back-refs are wired automatically.
struct.insert_child(0, KdlNode.create("@request", args=[KdlValue.create("GET /")]))
struct.add_child(KdlNode.create("note", args=[KdlValue.create("added")]))

# Properties and arguments
struct.set_prop("migrated", KdlValue.create(True))
struct.add_arg(KdlValue.create(42))
struct.remove_prop("legacy")

# Top-level nodes
doc.add_node(KdlNode.create("footer"))
doc.remove_node(0)
```

Mutation methods: `KdlNode.add_child` / `insert_child` / `remove_child` / `add_arg` / `set_prop` / `remove_prop`; `KdlDocument.add_node` / `insert_node` / `remove_node`. Each mutator propagates `parent` and `document` back-references to the inserted subtree.

**Serializing back to KDL 2.0:**

```python
node.to_kdl()                  # single node → str
doc.to_kdl()                   # whole document → str (trailing newline)

# Options
node.to_kdl(indent_str="\t")                  # custom indent (default 4 spaces)
node.to_kdl(force_children_block=True)        # emit `name {}` when no children
```

The serializer is KDL 2.0 spec-compliant:

- Booleans / null → `#true` / `#false` / `#null`; floats handle `#inf` / `#-inf` / `#nan`.
- Bare identifier detection per §3.10 (reserved keywords, digit-leading, sign rules).
- Quoted strings escape `\\ \" \n \r \t \b \f` and `\u{XXXX}` for disallowed code points; lone surrogates raise `ValueError`.
- Multi-line strings (`"""..."""`) for any value containing `\n`, with depth-aware reindentation.
- Type annotations on nodes and values (`(u8) 123`, `(published)date`).
- Round-trip safe: `parse(doc.to_kdl())` produces a semantically equivalent tree (not byte-identical — comments, raw-string variants, and hex/octal/binary number formats are normalized away).

**Migration example:**

```python
from kdlquery import parse, KdlNode, KdlValue

doc = parse('struct "old" {}')
struct = doc.nodes[0]
struct.insert_child(0, KdlNode.create("@request", args=[KdlValue.create("GET /")]))
struct.insert_child(1, KdlNode.create("@check", args=[KdlValue.create("exists")], children=[
    KdlNode.create("css", args=[KdlValue.create(".foo")]),
    KdlNode.create("to-bool"),
    KdlNode.create("fallback", args=[KdlValue.create(False)]),
]))
result = doc.to_kdl()
```

### CST parser

For cases where you need the raw parse tree with full source spans:

```python
from kdlquery import KDL2CSTParser

cst = KDL2CSTParser().parse('node "value" key=42')
# cst.nodes[0].entries — raw CST entries with exact positions
```

### Structured parse errors

`KDLParseError` carries a stable machine-readable `code` and a human-readable `hint`, so downstream tools can branch on the category instead of pattern-matching error text.

```python
from kdlquery import parse, KDLParseError

try:
    parse(r'foo re #"(\d+)"')          # missing trailing #
except KDLParseError as e:
    e.code   # "raw-string/unterminated"
    e.hint   # actionable, non-empty string
```

`PARSE_ERROR_CODES` (a `frozenset[str]`) enumerates all 26 categories. See `llm.txt` for the full code → hint table.

## Selector reference

```
# Node
name                    # by bare identifier
"name" or 'name'        # quoted node name (handles >, +, ~, ,, :, spaces)
\>name or a\>b          # backslash-escaped identifier (CSS-style)
*                       # any node
(type)                  # by type annotation on node
("type") or (t\:ype)    # quoted or escaped type annotation
(type)name              # type annotation + name

# Properties
[key]                   # property exists
["key"] or ['key']      # quoted property key (handles ., :, >, spaces)
[key\.name]             # backslash-escaped property key
["0"]                   # property with string key "0" (distinguished from arg 0)
[key=val]               # equals
[key^=val]              # starts with
[key$=val]              # ends with
[key~=val]              # contains
[(type)key]             # property with type-annotated value
[("type")key=val]       # type-annotated (quoted/escaped type) + value match

# Arguments
[N]                     # positional argument at index N exists (unquoted integer)
[N=val]                 # positional argument at index N equals val
[N^=val]                # starts with
[N$=val]                # ends with
[N~=val]                # contains
[(type)N]               # positional argument with type annotation
[("type")N=val]         # positional argument with quoted/escaped type annotation
[*=val]                 # any positional argument equals val

# Combinators
A B                     # descendant
A > B                   # direct child
A + B                   # adjacent sibling
A ~ B                   # general sibling
A, B                    # union (deduplicated)

# Pseudo-classes
:root
:first-child
:last-child
:nth-child(n)
:nth-child(2n)
:nth-child(2n+1)
:only-child
:empty
:not(selector)
:has(selector)
:has(> selector)
```

## License

MIT
