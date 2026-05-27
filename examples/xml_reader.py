"""Example: KDL to XML converter using a custom Reader.

Demonstrates how to subclass Reader to transform a KDL document
into a different representation — in this case, XML via
xml.etree.ElementTree from the standard library.

Usage:
    uv run python examples/xml_reader.py
"""

from __future__ import annotations

from xml.etree.ElementTree import Element, tostring

from kdlquery import KDL2CSTParser, KdlNode, Reader, WalkContext, parse_into

KDL_SOURCE = """\
database "myapp" driver="postgres" {
    host "localhost"
    port 5432
    credentials {
        user "admin"
        password "secret"
    }
    pool min=2 max=10
}
"""


class XmlReader(Reader[Element, str]):
    """Converts a KDL document tree into an XML string.

    Mapping rules:
        node.name          -> XML tag name
        node.properties    -> XML attributes
        node.get_arg(0)    -> element text content
        node.children      -> child XML elements
    """

    def on_node(self, node: KdlNode, ctx: WalkContext[Element]) -> Element:
        el = Element(node.name)

        # Source location as attributes
        el.set("xml:line", str(node.span.start.line))
        el.set("xml:col", str(node.span.start.column))

        # Properties become XML attributes
        for key, val in node.properties.items():
            el.set(key, str(val.value))

        # First positional argument becomes text content
        if node.args:
            el.text = str(node.args[0].value)

        # Children become nested XML elements
        for child_el in ctx.walk_children():
            el.append(child_el)

        return el

    def error_node(
        self, node: KdlNode, message: str, ctx: WalkContext[Element]
    ) -> Element:
        el = Element(node.name)
        el.set("_error", message)
        return el

    def finalize(
        self,
        nodes: list[Element],
        diagnostics: list[object],
    ) -> str:
        # Wrap in a root <document> element
        root = Element("document")
        for el in nodes:
            root.append(el)
        return tostring(root, encoding="unicode", xml_declaration=True)


def main() -> None:
    cst = KDL2CSTParser().parse(KDL_SOURCE)
    xml_output, diagnostics = parse_into(cst, XmlReader())

    print("=== KDL input ===")
    print(KDL_SOURCE)

    print("=== XML output ===")
    print(xml_output)

    if diagnostics:
        print(f"\n{len(diagnostics)} diagnostic(s)")


if __name__ == "__main__":
    main()
