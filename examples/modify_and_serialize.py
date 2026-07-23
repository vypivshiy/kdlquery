"""Example: Modify a parsed KDL document and serialize it back to KDL 2.0.

Demonstrates the mutation API (KdlNode/KdlDocument mutators and the
KdlNode.create / KdlValue.create factories) together with to_kdl()
serialization.

Usage:
    uv run python examples/modify_and_serialize.py
"""

from kdlquery import KdlNode, KdlValue, parse

KDL_SOURCE = """\
app "my-service" version="1.0.0" {
    server "primary" port=8080
    server "replica" port=8081
}
"""


def main() -> None:
    doc = parse(KDL_SOURCE)
    app = doc.select_one("app")
    assert app is not None

    print("=== Original document ===")
    print(doc.to_kdl())

    # --- Mutate properties and arguments on an existing node ---
    app.set_prop("version", KdlValue.create("2.0.0"))
    app.set_prop("migrated", KdlValue.create(True))

    # --- Insert a brand-new child at the top of the children block ---
    app.insert_child(
        0,
        KdlNode.create(
            "metadata",
            properties={
                "owner": KdlValue.create("infra-team"),
                "ticket": KdlValue.create("OPS-1234"),
            },
        ),
    )

    # --- Append a child via add_child (parent + document wired automatically) ---
    app.add_child(
        KdlNode.create(
            "healthcheck",
            args=[KdlValue.create("/healthz")],
            children=[
                KdlNode.create(
                    "interval", args=[KdlValue.create(30, type_annotation="(u32)")]
                ),
                KdlNode.create(
                    "timeout", args=[KdlValue.create(5, type_annotation="(u32)")]
                ),
            ],
        )
    )

    # --- Add a top-level node to the document ---
    doc.add_node(KdlNode.create("footer", args=[KdlValue.keyword("#null")]))

    # --- Serialize back ---
    print("=== After mutation ===")
    print(doc.to_kdl())

    # --- Round-trip check: re-parse and verify ---
    reparsed = parse(doc.to_kdl())
    new_app = reparsed.select_one("app")
    assert new_app is not None
    assert new_app.get_prop("version") == "2.0.0"
    assert new_app.get_prop("migrated") is True
    assert new_app.children[0].name == "metadata"
    assert reparsed.nodes[-1].name == "footer"

    print("Round-trip OK - reparsed document matches expected structure.")

    # --- Single node serialization with options ---
    metadata = app.children[0]
    print("\n=== Single node via to_kdl(indent_str='\\t') ===")
    print(metadata.to_kdl(indent_str="\t"))

    # --- force_children_block for empty nodes ---
    empty = KdlNode.create("placeholder")
    print("\n=== force_children_block ===")
    print(empty.to_kdl(), "<- default (no block)")
    print(empty.to_kdl(force_children_block=True), "<- forced empty block")


if __name__ == "__main__":
    main()
