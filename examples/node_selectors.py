"""Example: Drilling into sub-trees with KdlNode selectors.

Demonstrates KdlNode.select() / select_one() — scoped selectors
that search only within a node's children subtree. Cannot access
parent or root nodes.

Usage:
    uv run python examples/node_selectors.py
"""

from kdlquery import KdlNode, parse

KDL_SOURCE = """\
app "my-service" {
    (network)server "primary" port=8080 tls=#true {
        host "localhost"
        host "127.0.0.1"
    }

    (network)server "replica" port=8081 tls=#false {
        host "replica.local"
    }

    router {
        route "GET" "/api/users" handler="users.list" auth=#true
        route "POST" "/api/users" handler="users.create" auth=#true
        route "GET" "/api/health" handler="health.check" auth=#false
    }
}
"""


def _assert_node(node: KdlNode | None, name: str) -> KdlNode:
    assert node is not None, f"Expected to find {name!r}"
    return node


def main() -> None:
    doc = parse(KDL_SOURCE)
    app = _assert_node(doc.select_one("app"), "app")

    # --- Basic: find descendants by name ---
    print("All hosts under app:")
    for host in app.select("host"):
        print(f"  {host.get_arg(0)}")

    # --- Filters + combinators within subtree ---
    print("\nTLS servers and their hosts:")
    for server in app.select("server[tls=#true]"):
        print(f"  {server.get_arg(0)!r}:")
        for host in server.select("host"):
            print(f"    {host.get_arg(0)}")

    # --- Scoped: select on a deeper node ---
    router = _assert_node(app.select_one("router"), "router")
    print("\nAuth-required routes:")
    for route in router.select("route[auth=#true]"):
        print(f"  {route.get_arg(0)} {route.get_arg(1)} -> {route.get_prop('handler')}")

    # --- :root never matches on KdlNode ---
    print(f"\napp.select('*:root') -> {app.select('*:root')}")
    print(f"doc.select('*:root') -> {[n.name for n in doc.select('*:root')]}")

    # --- select_one on a node ---
    first_route = _assert_node(router.select_one("route"), "route")
    print(f"\nFirst route: {first_route.get_arg(0)} {first_route.get_arg(1)}")


if __name__ == "__main__":
    main()
