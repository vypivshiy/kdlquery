# kdlquery

A pure Python [KDL 2.0](https://kdl.dev/spec) parser with a CSS3-like selector API.

kdlquery provides a lossless CST parser, an immutable node tree with parent/sibling navigation, a Reader API for transforming KDL documents into arbitrary Python objects, and a selector engine for querying nodes by name, type annotation, properties, arguments, combinators, and pseudo-classes.

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

`parse()` returns a `KdlDocument` — an immutable tree of `KdlNode` objects with parent, depth, sibling, and index maps pre-built.

### Node access

```python
# Top-level nodes
app = doc.nodes[0]
app.name                          # "app"
app.get_arg(0)                    # "my-service"
app.get_prop("version")           # "1.0.0"

# Children
for server in app.children:
    print(server.get_arg(0), server.get_prop("port"))

# Tree navigation
doc.parent_of(app.children[0]) is app   # True
doc.depth_of(app)                        # 0
doc.index_of(app.children[1])            # 1
doc.siblings_of(app.children[0])         # (child_0, child_1, ...)
```

### Selector API

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

# Argument filters
doc.select('route[0="GET"]')
# → [route "GET" "/api/users", route "GET" "/api/health", route "GET" "/static/*"]

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

>[!NOTE]
> This selector implementation intentionally diverges from the [official KDL Query draft](https://github.com/kdl-org/kdl/blob/main/QUERY-SPEC.md) and closely mirrors CSS3 syntax.  
> Should the official query language be finalized and stabilized, a compatibility port to this project may be considered.

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

### Reader API

The Reader API lets you transform a KDL document into arbitrary Python objects by walking the node tree.

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

### CST parser

For cases where you need the raw parse tree with full source spans:

```python
from kdlquery import KDL2CSTParser

cst = KDL2CSTParser().parse('node "value" key=42')
# cst.nodes[0].entries — raw CST entries with exact positions
```

## Selector reference

```
# Node
name                    # by name
*                       # any node
(type)                  # by type annotation on node
(type)name              # type annotation + name

# Properties
[key]                   # property exists
[key=val]               # equals
[key^=val]              # starts with
[key$=val]              # ends with
[key~=val]              # contains
[(type)key]             # property with type-annotated value
[(type)key=val]         # type-annotated + value match

# Arguments
[N]                     # argument at position N exists
[N=val]                 # equals
[N^=val]                # starts with
[N$=val]                # ends with
[N~=val]                # contains
[(type)N]               # argument with type annotation
[*=val]                 # any argument equals val

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
:not(compound)
:has(complex)
:has(> complex)
```

## License

MIT
