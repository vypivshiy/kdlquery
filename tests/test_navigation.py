import pytest

from kdlquery import KDL2CSTParser, KdlDocument, KdlNode, parse


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def doc() -> KdlDocument:
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


NAVIGATION_DOC = """\
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
    }

    plugins {
        plugin "auth" enabled=#true {
            (jwt)secret "hs256" key=(regex)"hs(256|512)"
            expires (i32)3600
        }
        plugin "debug" enabled=#false
    }
}
"""


@pytest.fixture()
def nav_doc() -> KdlDocument:
    return parse(NAVIGATION_DOC)


# ---------------------------------------------------------------------------
# KdlNode.parent
# ---------------------------------------------------------------------------


class TestNodeParent:
    def test_root_parent_is_none(self, doc: KdlDocument) -> None:
        assert doc.nodes[0].parent is None
        assert doc.nodes[1].parent is None

    def test_child_parent(self, doc: KdlDocument) -> None:
        root = doc.nodes[0]
        child_a = root.children[0]
        assert child_a.parent is root

    def test_grandchild_parent(self, doc: KdlDocument) -> None:
        root = doc.nodes[0]
        child_a = root.children[0]
        grandchild = child_a.children[0]
        assert grandchild.parent is child_a
        assert child_a.parent is root

    def test_standalone_from_cst_wires_parents(self) -> None:
        cst = KDL2CSTParser().parse('package {\n  name my-pkg\n  version "1.0"\n}')
        node = KdlNode.from_cst(cst.nodes[0])
        assert node.parent is None
        assert node.children[0].parent is node
        assert node.children[1].parent is node


# ---------------------------------------------------------------------------
# KdlNode.root
# ---------------------------------------------------------------------------


class TestNodeRoot:
    def test_root_of_root_is_self(self, doc: KdlDocument) -> None:
        root = doc.nodes[0]
        assert root.root is root

    def test_root_of_deep_node(self, doc: KdlDocument) -> None:
        root = doc.nodes[0]
        grandchild = root.children[0].children[0]
        assert grandchild.root is root

    def test_root_of_top_level(self, doc: KdlDocument) -> None:
        top = doc.nodes[1]
        assert top.root is top


# ---------------------------------------------------------------------------
# KdlNode.document
# ---------------------------------------------------------------------------


class TestNodeDocument:
    def test_document_owned(self, doc: KdlDocument) -> None:
        assert doc.nodes[0].document is doc
        assert doc.nodes[0].children[0].document is doc

    def test_standalone_has_no_document(self) -> None:
        cst = KDL2CSTParser().parse("item 42")
        node = KdlNode.from_cst(cst.nodes[0])
        assert node.document is None


# ---------------------------------------------------------------------------
# KdlNode.depth()
# ---------------------------------------------------------------------------


class TestNodeDepth:
    def test_root_depth(self, doc: KdlDocument) -> None:
        assert doc.nodes[0].depth() == 0
        assert doc.nodes[1].depth() == 0

    def test_child_depth(self, doc: KdlDocument) -> None:
        root = doc.nodes[0]
        assert root.children[0].depth() == 1
        assert root.children[1].depth() == 1

    def test_grandchild_depth(self, doc: KdlDocument) -> None:
        root = doc.nodes[0]
        assert root.children[0].children[0].depth() == 2

    def test_agrees_with_document_depth_of(self, doc: KdlDocument) -> None:
        for node in doc.iter_nodes():
            assert node.depth() == doc.depth_of(node)


# ---------------------------------------------------------------------------
# KdlNode.index()
# ---------------------------------------------------------------------------


class TestNodeIndex:
    def test_root_index(self, doc: KdlDocument) -> None:
        assert doc.nodes[0].index() == 0
        assert doc.nodes[1].index() == 1

    def test_child_index(self, doc: KdlDocument) -> None:
        root = doc.nodes[0]
        assert root.children[0].index() == 0
        assert root.children[1].index() == 1

    def test_agrees_with_document_index_of(self, doc: KdlDocument) -> None:
        for node in doc.iter_nodes():
            assert node.index() == doc.index_of(node)

    def test_standalone_root_index(self) -> None:
        cst = KDL2CSTParser().parse("item 42")
        node = KdlNode.from_cst(cst.nodes[0])
        assert node.index() == 0


# ---------------------------------------------------------------------------
# KdlNode.siblings()
# ---------------------------------------------------------------------------


class TestNodeSiblings:
    def test_root_siblings(self, doc: KdlDocument) -> None:
        assert doc.nodes[0].siblings() == doc.nodes
        assert doc.nodes[1].siblings() == doc.nodes

    def test_child_siblings(self, doc: KdlDocument) -> None:
        root = doc.nodes[0]
        child_a = root.children[0]
        child_b = root.children[1]
        assert child_a.siblings() == (child_a, child_b)
        assert child_b.siblings() == (child_a, child_b)

    def test_agrees_with_document_siblings_of(self, doc: KdlDocument) -> None:
        for node in doc.iter_nodes():
            assert node.siblings() == doc.siblings_of(node)


# ---------------------------------------------------------------------------
# KdlNode.iter_descendants()
# ---------------------------------------------------------------------------


class TestNodeIterDescendants:
    def test_iter_descendants_order(self, doc: KdlDocument) -> None:
        root = doc.nodes[0]
        names = [n.name for n in root.iter_descendants()]
        assert names == ["child-a", "grandchild", "child-b"]

    def test_empty_children(self, doc: KdlDocument) -> None:
        grandchild = doc.nodes[0].children[0].children[0]
        assert list(grandchild.iter_descendants()) == []

    def test_agrees_with_document_iter_nodes_subtree(self, doc: KdlDocument) -> None:
        root = doc.nodes[0]
        doc_nodes = [
            n
            for n in doc.iter_nodes()
            if n is not root and doc.parent_of(n) is not None
        ]
        # All descendants of root
        subtree = list(root.iter_descendants())
        assert set(id(n) for n in subtree) == set(id(n) for n in doc_nodes)


# ---------------------------------------------------------------------------
# KdlNode.parents()
# ---------------------------------------------------------------------------


class TestNodeParents:
    def test_root_parents_empty(self, doc: KdlDocument) -> None:
        assert doc.nodes[0].parents() == []

    def test_child_parents(self, doc: KdlDocument) -> None:
        root = doc.nodes[0]
        child_a = root.children[0]
        assert child_a.parents() == [root]

    def test_grandchild_parents(self, doc: KdlDocument) -> None:
        root = doc.nodes[0]
        child_a = root.children[0]
        grandchild = child_a.children[0]
        assert grandchild.parents() == [child_a, root]


# ---------------------------------------------------------------------------
# KdlNode.matches()
# ---------------------------------------------------------------------------


class TestNodeMatches:
    def test_matches_by_name(self, nav_doc: KdlDocument) -> None:
        server = nav_doc.select_one("server")
        assert server is not None
        assert server.matches("server")
        assert not server.matches("host")

    def test_matches_by_type(self, nav_doc: KdlDocument) -> None:
        server = nav_doc.select_one("(network)server")
        assert server is not None
        assert server.matches("(network)server")
        # "server" without type annotation matches any node named "server"
        assert server.matches("server")
        # A non-matching type annotation does NOT match
        assert not server.matches("(i32)server")

    def test_matches_wildcard(self, nav_doc: KdlDocument) -> None:
        server = nav_doc.select_one("server")
        assert server is not None
        assert server.matches("*")

    def test_matches_filter(self, nav_doc: KdlDocument) -> None:
        server = nav_doc.select_one("server[tls=#true]")
        assert server is not None
        assert server.matches("server[tls=#true]")
        assert not server.matches("server[tls=#false]")

    def test_matches_pseudo(self, nav_doc: KdlDocument) -> None:
        app = nav_doc.select_one("app")
        assert app is not None
        assert app.matches("*:root")

    def test_matches_with_combinator(self, nav_doc: KdlDocument) -> None:
        server = nav_doc.select_one("server")
        assert server is not None
        assert server.matches("app > server")
        assert not server.matches("router > server")

    def test_matches_descendant_combinator(self, nav_doc: KdlDocument) -> None:
        host = nav_doc.select_one("host")
        assert host is not None
        assert host.matches("app host")

    def test_no_match(self, nav_doc: KdlDocument) -> None:
        debug = nav_doc.select_one('plugin[0="debug"]')
        assert debug is not None
        assert not debug.matches("plugin[enabled=#true]")
        assert not debug.matches("nonexistent")


# ---------------------------------------------------------------------------
# KdlNode.closest()
# ---------------------------------------------------------------------------


class TestNodeClosest:
    def test_closest_returns_self(self, nav_doc: KdlDocument) -> None:
        server = nav_doc.select_one("server")
        assert server is not None
        assert server.closest("server") is server

    def test_closest_walks_to_parent(self, nav_doc: KdlDocument) -> None:
        host = nav_doc.select_one("host")
        assert host is not None
        # host -> server -> app
        assert host.closest("server") is not None
        assert host.closest("server").name == "server"  # type: ignore[union-attr]

    def test_closest_walks_to_grandparent(self, nav_doc: KdlDocument) -> None:
        host = nav_doc.select_one("host")
        assert host is not None
        assert host.closest("app") is nav_doc.nodes[0]

    def test_closest_returns_none(self, nav_doc: KdlDocument) -> None:
        host = nav_doc.select_one("host")
        assert host is not None
        assert host.closest("nonexistent") is None

    def test_closest_with_filter(self, nav_doc: KdlDocument) -> None:
        host = nav_doc.select_one('host[0="localhost"]')
        assert host is not None
        result = host.closest("server[tls=#true]")
        assert result is not None
        assert result.get_arg(0) == "primary"

    def test_closest_with_type(self, nav_doc: KdlDocument) -> None:
        host = nav_doc.select_one('host[0="localhost"]')
        assert host is not None
        # host -> server (has type annotation) -> app
        result = host.closest("(network)server")
        assert result is not None
        assert result.name == "server"
        assert result.type_annotation == "(network)"

    def test_closest_root_node(self, nav_doc: KdlDocument) -> None:
        app = nav_doc.nodes[0]
        assert app.closest("app") is app
        assert app.closest("nonexistent") is None


# ---------------------------------------------------------------------------
# KdlDocument backward compat
# ---------------------------------------------------------------------------


class TestDocumentBackwardCompat:
    def test_parent_of_agrees_with_node_parent(self, doc: KdlDocument) -> None:
        for node in doc.iter_nodes():
            assert doc.parent_of(node) is node.parent

    def test_depth_of_agrees_with_node_depth(self, doc: KdlDocument) -> None:
        for node in doc.iter_nodes():
            assert doc.depth_of(node) == node.depth()

    def test_index_of_agrees_with_node_index(self, doc: KdlDocument) -> None:
        for node in doc.iter_nodes():
            assert doc.index_of(node) == node.index()

    def test_siblings_of_agrees_with_node_siblings(self, doc: KdlDocument) -> None:
        for node in doc.iter_nodes():
            assert doc.siblings_of(node) == node.siblings()
