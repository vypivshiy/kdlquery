import pytest

from kdlquery import (
    KDL2CSTParser,
    KdlDocument,
    KdlNode,
    KdlValue,
    DictReader,
    parse,
    parse_into,
)


# ---------------------------------------------------------------------------
# KdlValue
# ---------------------------------------------------------------------------


class TestKdlValue:
    def test_construction(self):
        from kdlquery.types import Position, Span

        span = Span(Position(0, 1, 1), Position(2, 1, 3))
        v = KdlValue(value=42, span=span)
        assert v.value == 42
        assert v.span == span
        assert v.type_annotation is None

    def test_with_type_annotation(self):
        from kdlquery.types import Position, Span

        span = Span(Position(0, 1, 1), Position(5, 1, 6))
        v = KdlValue(value=42, span=span, type_annotation="(u8)")
        assert v.type_annotation == "(u8)"

    def test_frozen(self):
        from kdlquery.types import Position, Span

        span = Span(Position(0, 1, 1), Position(1, 1, 2))
        v = KdlValue(value="x", span=span)
        with pytest.raises(AttributeError):
            v.value = "y"


# ---------------------------------------------------------------------------
# KdlNode.from_cst
# ---------------------------------------------------------------------------


class TestKdlNodeFromCst:
    def test_simple_node(self):
        doc = KDL2CSTParser().parse('item "hello" count=5')
        node = KdlNode.from_cst(doc.nodes[0])
        assert node.name == "item"
        assert node.args[0].value == "hello"
        assert node.properties["count"].value == 5
        assert node.type_annotation is None
        assert node.children == ()

    def test_node_with_type_annotation(self):
        doc = KDL2CSTParser().parse('(published)date "1970-01-01"')
        node = KdlNode.from_cst(doc.nodes[0])
        assert node.type_annotation == "(published)"
        assert node.args[0].value == "1970-01-01"

    def test_nested_children(self):
        doc = KDL2CSTParser().parse(
            """
package {
  name my-pkg
  version "1.0"
}
"""
        )
        node = KdlNode.from_cst(doc.nodes[0])
        assert node.name == "package"
        assert len(node.children) == 2
        assert node.children[0].name == "name"
        assert node.children[1].name == "version"

    def test_arg_type_annotation_preserved(self):
        doc = KDL2CSTParser().parse('node (array)"str"')
        node = KdlNode.from_cst(doc.nodes[0])
        assert node.args[0].type_annotation == "(array)"
        assert node.args[0].value == "str"


# ---------------------------------------------------------------------------
# KdlNode convenience methods
# ---------------------------------------------------------------------------


class TestKdlNodeMethods:
    @pytest.fixture()
    def node(self):
        doc = KDL2CSTParser().parse('item "hello" 42 count=5 active=#true')
        return KdlNode.from_cst(doc.nodes[0])

    def test_get_arg(self, node):
        assert node.get_arg(0) == "hello"
        assert node.get_arg(1) == 42
        assert node.get_arg(2) is None
        assert node.get_arg(2, "default") == "default"

    def test_get_prop(self, node):
        assert node.get_prop("count") == 5
        assert node.get_prop("active") is True
        assert node.get_prop("missing") is None
        assert node.get_prop("missing", 0) == 0

    def test_has_prop(self, node):
        assert node.has_prop("count") is True
        assert node.has_prop("active") is True
        assert node.has_prop("missing") is False

    def test_iter_args(self, node):
        assert list(node.iter_args()) == ["hello", 42]

    def test_iter_props(self, node):
        props = dict(node.iter_props())
        assert props == {"count": 5, "active": True}


# ---------------------------------------------------------------------------
# KdlDocument
# ---------------------------------------------------------------------------


class TestKdlDocument:
    @pytest.fixture()
    def document(self):
        return parse(
            """
root {
    child-a {
        grandchild 1
    }
    child-b "val"
}
top-level 42
"""
        )

    def test_from_cst_nodes(self, document):
        assert len(document.nodes) == 2
        assert document.nodes[0].name == "root"
        assert document.nodes[1].name == "top-level"

    def test_parent_of_root_is_none(self, document):
        assert document.parent_of(document.nodes[0]) is None
        assert document.parent_of(document.nodes[1]) is None

    def test_parent_of_child(self, document):
        root = document.nodes[0]
        child_a = root.children[0]
        assert document.parent_of(child_a) is root

    def test_parent_of_grandchild(self, document):
        root = document.nodes[0]
        grandchild = root.children[0].children[0]
        assert document.parent_of(grandchild) is root.children[0]
        assert document.parent_of(document.parent_of(grandchild)) is root

    def test_depth_of(self, document):
        root = document.nodes[0]
        child = root.children[0]
        grandchild = child.children[0]
        assert document.depth_of(root) == 0
        assert document.depth_of(child) == 1
        assert document.depth_of(grandchild) == 2

    def test_depth_of_top_level(self, document):
        assert document.depth_of(document.nodes[1]) == 0

    def test_index_of(self, document):
        root = document.nodes[0]
        assert document.index_of(root) == 0
        assert document.index_of(document.nodes[1]) == 1
        assert document.index_of(root.children[0]) == 0
        assert document.index_of(root.children[1]) == 1

    def test_siblings_of(self, document):
        root = document.nodes[0]
        child_a = root.children[0]
        child_b = root.children[1]
        assert document.siblings_of(child_a) == (child_a, child_b)
        assert document.siblings_of(root) == document.nodes

    def test_iter_nodes(self, document):
        names = [n.name for n in document.iter_nodes()]
        assert names == ["root", "child-a", "grandchild", "child-b", "top-level"]

    def test_select_not_implemented(self, document):
        with pytest.raises(NotImplementedError, match="CSS3"):
            document.select("root")


# ---------------------------------------------------------------------------
# Walker + Reader with new API
# ---------------------------------------------------------------------------


class TestReaderNewApi:
    def test_on_node_receives_kdlnode(self):
        received: list[KdlNode] = []

        class Collector(DictReader):
            def on_node(self, node, ctx):
                received.append(node)
                return super().on_node(node, ctx)

        src = 'a "x"\nb "y"'
        cst = KDL2CSTParser().parse(src)
        parse_into(cst, Collector())
        assert len(received) == 2
        assert received[0].name == "a"
        assert received[1].name == "b"

    def test_walk_context_depth(self):
        depths: list[int] = []

        class DepthReader(DictReader):
            def on_node(self, node, ctx):
                depths.append(ctx.depth)
                return super().on_node(node, ctx)

        src = "root { child { grand } }"
        cst = KDL2CSTParser().parse(src)
        parse_into(cst, DepthReader())
        assert depths == [0, 1, 2]

    def test_walk_context_parent(self):
        parents: list[str | None] = []

        class ParentReader(DictReader):
            def on_node(self, node, ctx):
                parents.append(ctx.parent.name if ctx.parent else None)
                return super().on_node(node, ctx)

        src = "root { child }"
        cst = KDL2CSTParser().parse(src)
        parse_into(cst, ParentReader())
        assert parents == [None, "root"]

    def test_walk_context_index(self):
        indices: list[int] = []

        class IndexReader(DictReader):
            def on_node(self, node, ctx):
                indices.append(ctx.index)
                return super().on_node(node, ctx)

        src = "root { a; b; c }"
        cst = KDL2CSTParser().parse(src)
        parse_into(cst, IndexReader())
        assert indices == [0, 0, 1, 2]


# ---------------------------------------------------------------------------
# parse() convenience function
# ---------------------------------------------------------------------------


class TestParse:
    def test_simple(self):
        doc = parse('item "hello" count=5')
        assert isinstance(doc, KdlDocument)
        assert len(doc.nodes) == 1
        assert doc.nodes[0].name == "item"
        assert doc.nodes[0].get_arg(0) == "hello"
        assert doc.nodes[0].get_prop("count") == 5

    def test_nested(self):
        doc = parse(
            """
package {
    name my-pkg
    version "1.2.3"
}
"""
        )
        pkg = doc.nodes[0]
        assert pkg.name == "package"
        assert len(pkg.children) == 2
        assert doc.parent_of(pkg.children[0]) is pkg

    def test_empty_document(self):
        doc = parse("")
        assert isinstance(doc, KdlDocument)
        assert len(doc.nodes) == 0

    def test_span_preserved(self):
        doc = parse("node 42")
        assert doc.nodes[0].span.start.line >= 1


# ---------------------------------------------------------------------------
# DictReader with new API
# ---------------------------------------------------------------------------


class TestDictReader:
    def test_produces_dict_tree(self):
        src = """
root {
    child "arg" key="val"
}
"""
        cst = KDL2CSTParser().parse(src)
        result, diags = parse_into(cst, DictReader())
        assert len(result) == 1
        root = result[0]
        assert root["name"] == "root"
        assert len(root["children"]) == 1
        child = root["children"][0]
        assert child["name"] == "child"
        assert child["args"] == ("arg",)
        assert child["props"] == {"key": "val"}
        assert child["children"] == []
