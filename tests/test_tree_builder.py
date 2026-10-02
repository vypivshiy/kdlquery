from __future__ import annotations

import math
from typing import Any

from kdlquery import (
    AstBuilder,
    CSTArgEntry,
    CSTDocument,
    CSTIdentifier,
    CSTNode,
    CSTPropEntry,
    CSTTypeAnnotation,
    CSTValue,
    CstBuilder,
    KDL2CSTParser,
    KdlDocument,
    KdlNode,
    Span,
    TreeBuilder,
    parse,
)
from kdlquery.parser import KDLLexer, _Parser


class TestTreeBuilderProtocol:
    def test_protocol_conformance(self) -> None:
        assert isinstance(AstBuilder(), TreeBuilder)
        assert isinstance(CstBuilder(), TreeBuilder)

    def test_custom_tree_builder(self) -> None:
        class EventRecordingBuilder:
            def __init__(self) -> None:
                self.events: list[str] = []

            def start_node(
                self,
                name: str,
                type_annotation: str | None,
                span: Span,
                **kwargs: Any,
            ) -> None:
                self.events.append(f"start_node:{name}:{type_annotation}")

            def add_arg(
                self,
                value: Any,
                type_annotation: str | None,
                span: Span,
                **kwargs: Any,
            ) -> None:
                self.events.append(f"arg:{value}:{type_annotation}")

            def add_prop(
                self,
                key: str,
                value: Any,
                type_annotation: str | None,
                span: Span,
                **kwargs: Any,
            ) -> None:
                self.events.append(f"prop:{key}={value}:{type_annotation}")

            def start_children(self, span: Span) -> None:
                self.events.append("start_children")

            def end_children(self, span: Span) -> None:
                self.events.append("end_children")

            def end_node(self, span: Span) -> None:
                self.events.append("end_node")

            def finish_document(self, span: Span) -> list[str]:
                return self.events

        builder = EventRecordingBuilder()
        assert isinstance(builder, TreeBuilder)

        src = '(pub)parent "arg1" key="val" {\n    child 42\n}'
        tokens = KDLLexer(src).tokenize()
        parser = _Parser(tokens, source=src, builder=builder)
        events = parser.parse_document()

        assert events == [
            "start_node:parent:(pub)",
            "arg:arg1:None",
            "prop:key=val:None",
            "start_children",
            "start_node:child:None",
            "arg:42:None",
            "end_node",
            "end_children",
            "end_node",
        ]


class TestAstBuilderDirectConstruction:
    def test_direct_ast_construction_without_cst_allocations(self) -> None:
        src = """\
(service)database "postgres" port=5432 active=#true {
    (cluster)node "db-1" primary=#true
    (cluster)node "db-2" primary=#false
}
"""
        doc = parse(src)
        assert isinstance(doc, KdlDocument)
        assert len(doc.nodes) == 1

        db = doc.nodes[0]
        assert db.name == "database"
        assert db.type_annotation == "(service)"
        assert len(db.args) == 1
        assert db.args[0].value == "postgres"
        assert db.properties["port"].value == 5432
        assert db.properties["active"].value is True
        assert db.parent is None
        assert db.document is doc

        # Verify child nodes and in-flight references
        assert len(db.children) == 2
        child1 = db.children[0]
        assert child1.name == "node"
        assert child1.type_annotation == "(cluster)"
        assert child1.args[0].value == "db-1"
        assert child1.properties["primary"].value is True
        assert child1.parent is db
        assert child1.document is doc
        assert child1.depth() == 1

        child2 = db.children[1]
        assert child2.name == "node"
        assert child2.args[0].value == "db-2"
        assert child2.properties["primary"].value is False
        assert child2.parent is db
        assert child2.document is doc
        assert child2.depth() == 1

        # Sibling queries
        siblings = doc.siblings_of(child1)
        assert siblings == [child1, child2]

    def test_slashdash_discarding_in_ast_builder(self) -> None:
        src = """\
/- discarded_node 1
real_node 10 /- "dropped_arg" 20 /- dropped_prop="foo" kept_prop="bar" {
    /- discarded_child
    real_child 30
}
"""
        doc = parse(src)
        assert len(doc.nodes) == 1
        node = doc.nodes[0]
        assert node.name == "real_node"
        assert [a.value for a in node.args] == [10, 20]
        assert list(node.properties.keys()) == ["kept_prop"]
        assert node.properties["kept_prop"].value == "bar"
        assert len(node.children) == 1
        assert node.children[0].name == "real_child"
        assert node.children[0].args[0].value == 30
        assert node.children[0].parent is node
        assert node.children[0].document is doc

    def test_empty_document_ast_builder(self) -> None:
        doc = parse("")
        assert isinstance(doc, KdlDocument)
        assert len(doc.nodes) == 0
        assert doc.span.start.offset == 0
        assert doc.span.end.offset == 0


class TestCstBuilderStructureFidelity:
    def test_cst_builder_produces_identical_cst(self) -> None:
        src = '(app)web-server "primary" port=(u16)8080 {\n    endpoint "/health"\n}'
        cst = KDL2CSTParser().parse(src)

        assert isinstance(cst, CSTDocument)
        assert len(cst.nodes) == 1
        node = cst.nodes[0]
        assert isinstance(node, CSTNode)
        assert node.has_children_block is True
        assert node.children_block_span is not None

        # Name
        assert isinstance(node.name, CSTIdentifier)
        assert node.name.value == "web-server"
        assert node.name.raw == "web-server"

        # Type annotation
        assert isinstance(node.type_annotation, CSTTypeAnnotation)
        assert node.type_annotation.raw == "(app)"

        # Entries
        assert len(node.entries) == 2
        arg_entry = node.entries[0]
        assert isinstance(arg_entry, CSTArgEntry)
        assert isinstance(arg_entry.value, CSTValue)
        assert arg_entry.value.value == "primary"
        assert arg_entry.value.raw == '"primary"'

        prop_entry = node.entries[1]
        assert isinstance(prop_entry, CSTPropEntry)
        assert isinstance(prop_entry.key, CSTIdentifier)
        assert prop_entry.key.value == "port"
        assert isinstance(prop_entry.value, CSTValue)
        assert prop_entry.value.value == 8080
        assert prop_entry.value.type_annotation is not None
        assert prop_entry.value.type_annotation.raw == "(u16)"

        # Children
        assert len(node.children) == 1
        child = node.children[0]
        assert child.name.value == "endpoint"
        assert child.has_children_block is False
        assert child.children_block_span is None


def _assert_ast_trees_equal(actual: KdlNode, expected: KdlNode) -> None:
    assert actual.name == expected.name
    assert actual.type_annotation == expected.type_annotation
    assert actual.span == expected.span

    # Args
    assert len(actual.args) == len(expected.args)
    for a_act, a_exp in zip(actual.args, expected.args):
        if isinstance(a_act.value, float) and math.isnan(a_act.value):
            assert isinstance(a_exp.value, float) and math.isnan(a_exp.value)
        else:
            assert a_act.value == a_exp.value
        assert a_act.type_annotation == a_exp.type_annotation
        assert a_act.span == a_exp.span

    # Properties
    assert set(actual.properties.keys()) == set(expected.properties.keys())
    for k in actual.properties:
        p_act = actual.properties[k]
        p_exp = expected.properties[k]
        if isinstance(p_act.value, float) and math.isnan(p_act.value):
            assert isinstance(p_exp.value, float) and math.isnan(p_exp.value)
        else:
            assert p_act.value == p_exp.value
        assert p_act.type_annotation == p_exp.type_annotation
        assert p_act.span == p_exp.span

    # Children
    assert len(actual.children) == len(expected.children)
    for c_act, c_exp in zip(actual.children, expected.children):
        assert c_act.parent is actual
        assert c_exp.parent is expected
        _assert_ast_trees_equal(c_act, c_exp)


class TestDirectAstAndCstEquivalence:
    def test_various_documents_equivalence(self) -> None:
        snippets = [
            'node "arg" prop=123',
            '(pub)item "str" (u8)42 key=(bool)#true',
            'empty_node',
            'parent {\n    child-a 1\n    child-b key="val" {\n        grandchild\n    }\n}',
            'node 0x1F 0b101 #-inf #null #nan',
            '/- discarded\nnode /- "arg" 123 /- prop="bad" good="yes" {\n    /- { sub }\n    child\n}',
        ]
        for src in snippets:
            direct_doc = parse(src)
            cst_doc = KDL2CSTParser().parse(src)
            adapted_doc = KdlDocument.from_cst(cst_doc)

            assert len(direct_doc.nodes) == len(adapted_doc.nodes)
            assert direct_doc.span == adapted_doc.span

            for n_dir, n_adp in zip(direct_doc.nodes, adapted_doc.nodes):
                assert n_dir.parent is None
                assert n_adp.parent is None
                assert n_dir.document is direct_doc
                assert n_adp.document is adapted_doc
                _assert_ast_trees_equal(n_dir, n_adp)


class TestDirectAstNavigationAndSelectors:
    def test_navigation_methods_on_direct_ast(self) -> None:
        src = """\
root {
    child1 "first"
    child2 "second" {
        grandchild "deep"
    }
    child3 "third"
}
"""
        doc = parse(src)
        root = doc.nodes[0]
        c1, c2, c3 = root.children
        gc = c2.children[0]

        assert doc.parent_of(c1) is root
        assert doc.parent_of(root) is None
        assert doc.depth_of(root) == 0
        assert doc.depth_of(c2) == 1
        assert doc.depth_of(gc) == 2

        assert doc.index_of(c1) == 0
        assert doc.index_of(c2) == 1
        assert doc.index_of(c3) == 2
        assert doc.index_of(gc) == 0

        assert doc.siblings_of(c1) == [c1, c2, c3]
        assert doc.siblings_of(gc) == [gc]

        # iter_nodes pre-order
        all_nodes = list(doc.iter_nodes())
        assert all_nodes == [root, c1, c2, gc, c3]

    def test_css3_selectors_on_direct_ast(self) -> None:
        src = """\
app "my-service" version="1.0" {
    server "web" port=8080 active=#true {
        route "/api"
    }
    server "worker" port=9000 active=#false {
        queue "jobs"
    }
}
"""
        doc = parse(src)

        # Type selector
        servers = doc.select("server")
        assert len(servers) == 2
        assert [s.args[0].value for s in servers] == ["web", "worker"]

        # Child combinator
        routes = doc.select("server > route")
        assert len(routes) == 1
        assert routes[0].args[0].value == "/api"

        # Descendant combinator
        queues = doc.select("app queue")
        assert len(queues) == 1
        assert queues[0].args[0].value == "jobs"

        # Attribute selector
        active = doc.select("server[active=#true]")
        assert len(active) == 1
        assert active[0].args[0].value == "web"

        # select_one
        first_server = doc.select_one("server")
        assert first_server is not None
        assert first_server.args[0].value == "web"


class TestCodeReviewFixes:
    def test_exports(self) -> None:
        import kdlquery

        assert "offset_to_position" in kdlquery.__all__
        assert "TreeBuilder" in kdlquery.__all__
        assert "AstBuilder" in kdlquery.__all__
        assert "CstBuilder" in kdlquery.__all__
        assert "_Parser" not in kdlquery.__all__
        assert callable(kdlquery.offset_to_position)

    def test_no_is_cst_builder_attribute_on_parser(self) -> None:
        src = 'node 123 key="val"'
        tokens = KDLLexer(src).tokenize_raw()
        parser = _Parser(tokens, source=src, builder=AstBuilder())
        assert not hasattr(parser, "_is_cst_builder")
        doc = parser.parse_document()
        assert len(doc.nodes) == 1

    def test_uniform_tree_builder_kwargs_received(self) -> None:
        received_kwargs: dict[str, Any] = {}

        class SpyBuilder:
            def start_node(
                self,
                name: str,
                type_annotation: str | None,
                span: Span,
                *,
                name_raw: str,
                name_span: Span,
                type_span: Span | None,
            ) -> None:
                received_kwargs["start_node"] = {
                    "name": name,
                    "type_annotation": type_annotation,
                    "span": span,
                    "name_raw": name_raw,
                    "name_span": name_span,
                    "type_span": type_span,
                }

            def add_arg(
                self,
                value: Any,
                type_annotation: str | None,
                span: Span,
                *,
                raw: str,
                value_span: Span,
                type_span: Span | None,
                is_bare_ident: bool = False,
            ) -> None:
                received_kwargs["add_arg"] = {
                    "value": value,
                    "type_annotation": type_annotation,
                    "span": span,
                    "raw": raw,
                    "value_span": value_span,
                    "type_span": type_span,
                    "is_bare_ident": is_bare_ident,
                }

            def add_prop(
                self,
                key: str,
                value: Any,
                type_annotation: str | None,
                span: Span,
                *,
                key_raw: str,
                key_span: Span,
                value_raw: str,
                value_span: Span,
                type_span: Span | None,
                is_bare_ident: bool = False,
            ) -> None:
                received_kwargs["add_prop"] = {
                    "key": key,
                    "value": value,
                    "type_annotation": type_annotation,
                    "span": span,
                    "key_raw": key_raw,
                    "key_span": key_span,
                    "value_raw": value_raw,
                    "value_span": value_span,
                    "type_span": type_span,
                    "is_bare_ident": is_bare_ident,
                }

            def start_children(self, span: Span) -> None:
                pass

            def end_children(self, span: Span) -> None:
                pass

            def end_node(self, span: Span) -> None:
                pass

            def finish_document(self, span: Span) -> None:
                pass

        spy = SpyBuilder()
        assert isinstance(spy, TreeBuilder)

        src = '(my-type)"my-name" (arg-type)42 key=(prop-type)"prop-val"'
        parser = _Parser(KDLLexer(src).tokenize_raw(), source=src, builder=spy)
        parser.parse_document()

        assert received_kwargs["start_node"]["name"] == "my-name"
        assert received_kwargs["start_node"]["name_raw"] == '"my-name"'
        assert received_kwargs["start_node"]["type_annotation"] == "(my-type)"
        assert received_kwargs["start_node"]["type_span"] is not None

        assert received_kwargs["add_arg"]["value"] == 42
        assert received_kwargs["add_arg"]["raw"] == "(arg-type)42"
        assert received_kwargs["add_arg"]["type_annotation"] == "(arg-type)"
        assert received_kwargs["add_arg"]["is_bare_ident"] is False

        assert received_kwargs["add_prop"]["key"] == "key"
        assert received_kwargs["add_prop"]["key_raw"] == "key"
        assert received_kwargs["add_prop"]["value"] == "prop-val"
        assert received_kwargs["add_prop"]["value_raw"] == '(prop-type)"prop-val"'
        assert received_kwargs["add_prop"]["type_annotation"] == "(prop-type)"
        assert received_kwargs["add_prop"]["is_bare_ident"] is False

    def test_bypassing_cst_allocations_in_ast_mode(self) -> None:
        from unittest.mock import patch

        src = '(my-type)"node-name" (arg-type)100 prop=(prop-type)"val" {\n    child bare_ident\n}'
        with patch("kdlquery.builder.CSTIdentifier", wraps=CSTIdentifier) as mock_id:
            with patch("kdlquery.builder.CSTTypeAnnotation", wraps=CSTTypeAnnotation) as mock_ty:
                doc = parse(src)
                assert isinstance(doc, KdlDocument)
                assert mock_id.call_count == 0
                assert mock_ty.call_count == 0

    def test_cst_builder_allocations_intact(self) -> None:
        src = '(my-type)"node-name" (arg-type)100 prop=(prop-type)"val" {\n    child bare_ident\n}'
        cst = KDL2CSTParser().parse(src)
        assert isinstance(cst, CSTDocument)
        assert isinstance(cst.nodes[0].name, CSTIdentifier)
        assert isinstance(cst.nodes[0].type_annotation, CSTTypeAnnotation)

    def test_parser_accepts_tokens_and_raw_tokens(self) -> None:
        src = "node 123"
        # 1. Native raw token stream
        raw_tokens = KDLLexer(src).tokenize_raw()
        p1 = _Parser(raw_tokens, source=src, builder=AstBuilder())
        doc1 = p1.parse_document()
        assert len(doc1.nodes) == 1

        # 2. Materialized Token stream (backward compatibility)
        tokens = KDLLexer(src).tokenize()
        p2 = _Parser(tokens, source=src, builder=AstBuilder())
        doc2 = p2.parse_document()
        assert len(doc2.nodes) == 1

        # 3. Materialized Token stream with source=None
        p3 = _Parser(tokens, source=None, builder=AstBuilder())
        doc3 = p3.parse_document()
        assert len(doc3.nodes) == 1
        assert doc3.nodes[0].span.start.line == 1

    def test_build_cst_value_helper(self) -> None:
        from kdlquery.builder import _build_cst_value
        from kdlquery import Position

        dummy_span = Span(Position(0, 1, 1), Position(3, 1, 4))
        # Bare identifier
        val1 = _build_cst_value(
            value="foo",
            raw="foo",
            span=dummy_span,
            type_annotation=None,
            type_span=None,
            is_bare_ident=True,
        )
        assert isinstance(val1, CSTIdentifier)
        assert val1.value == "foo"

        # Value with type annotation
        val2 = _build_cst_value(
            value=42,
            raw="(u8)42",
            span=dummy_span,
            type_annotation="(u8)",
            type_span=dummy_span,
            is_bare_ident=False,
        )
        assert isinstance(val2, CSTValue)
        assert val2.value == 42
        assert val2.type_annotation is not None
        assert val2.type_annotation.raw == "(u8)"
