"""Tests for KDL 2.0 serialization (write support)."""

from __future__ import annotations

import pytest

from kdlquery import KdlNode, KdlValue, parse
from kdlquery.reader import _EMPTY_SPAN, _Keyword


# ---------------------------------------------------------------------------
# KdlValue factories
# ---------------------------------------------------------------------------


class TestKdlValueCreate:
    def test_create_int(self) -> None:
        v = KdlValue.create(42)
        assert v.value == 42
        assert v.type_annotation is None
        assert v.span == _EMPTY_SPAN

    def test_create_with_type_annotation(self) -> None:
        v = KdlValue.create("x", type_annotation="(u8)")
        assert v.value == "x"
        assert v.type_annotation == "(u8)"

    def test_create_preserves_python_types(self) -> None:
        assert KdlValue.create(True).value is True
        assert KdlValue.create(None).value is None
        assert KdlValue.create(3.14).value == 3.14

    def test_keyword_wraps_raw_literal(self) -> None:
        v = KdlValue.keyword("#null")
        assert isinstance(v.value, _Keyword)
        assert v.value.raw == "#null"

    def test_keyword_arbitrary_string(self) -> None:
        v = KdlValue.keyword("#custom-foo")
        assert v.value.raw == "#custom-foo"


# ---------------------------------------------------------------------------
# KdlNode.create + mutation API
# ---------------------------------------------------------------------------


class TestKdlNodeCreate:
    def test_create_minimal(self) -> None:
        n = KdlNode.create("foo")
        assert n.name == "foo"
        assert n.args == []
        assert n.properties == {}
        assert n.children == []
        assert n.type_annotation is None

    def test_create_with_args(self) -> None:
        n = KdlNode.create("foo", args=[KdlValue.create(1), KdlValue.create("x")])
        assert [a.value for a in n.args] == [1, "x"]

    def test_create_with_properties(self) -> None:
        n = KdlNode.create(
            "foo",
            properties={"count": KdlValue.create(5), "flag": KdlValue.create(True)},
        )
        assert n.get_prop("count") == 5
        assert n.get_prop("flag") is True

    def test_create_with_children_wires_parent(self) -> None:
        child = KdlNode.create("c")
        parent = KdlNode.create("p", children=[child])
        assert child.parent is parent
        assert parent.children == [child]

    def test_create_with_type_annotation(self) -> None:
        n = KdlNode.create("date", type_annotation="(published)")
        assert n.type_annotation == "(published)"

    def test_create_copies_inputs(self) -> None:
        args = [KdlValue.create(1)]
        n = KdlNode.create("foo", args=args)
        n.add_arg(KdlValue.create(2))
        assert len(args) == 1
        assert len(n.args) == 2


class TestMutation:
    def test_add_child_wires_parent(self) -> None:
        parent = KdlNode.create("p")
        child = KdlNode.create("c")
        ret = parent.add_child(child)
        assert ret is child
        assert child.parent is parent
        assert parent.children == [child]

    def test_add_child_propagates_document(self) -> None:
        doc = parse("root { a }")
        root = doc.nodes[0]
        new_child = KdlNode.create("new")
        root.add_child(new_child)
        assert new_child.document is doc
        # nested descendants also get document ref
        grand = KdlNode.create("g", children=[KdlNode.create("gg")])
        root.add_child(grand)
        assert grand.children[0].document is doc

    def test_insert_child(self) -> None:
        parent = KdlNode.create(
            "p", children=[KdlNode.create("a"), KdlNode.create("c")]
        )
        parent.insert_child(1, KdlNode.create("b"))
        assert [c.name for c in parent.children] == ["a", "b", "c"]
        assert parent.children[1].parent is parent

    def test_insert_child_negative_index(self) -> None:
        parent = KdlNode.create(
            "p", children=[KdlNode.create("a"), KdlNode.create("b")]
        )
        parent.insert_child(-1, KdlNode.create("z"))
        assert [c.name for c in parent.children] == ["a", "z", "b"]

    def test_remove_child(self) -> None:
        parent = KdlNode.create(
            "p", children=[KdlNode.create("a"), KdlNode.create("b")]
        )
        removed = parent.remove_child(0)
        assert removed.name == "a"
        assert removed.parent is None
        assert len(parent.children) == 1

    def test_add_arg(self) -> None:
        n = KdlNode.create("x")
        n.add_arg(KdlValue.create(True))
        assert n.get_arg(0) is True

    def test_set_prop_add_and_replace(self) -> None:
        n = KdlNode.create("x")
        n.set_prop("k", KdlValue.create(1))
        assert n.get_prop("k") == 1
        n.set_prop("k", KdlValue.create(2))
        assert n.get_prop("k") == 2

    def test_remove_prop(self) -> None:
        n = KdlNode.create("x")
        n.set_prop("k", KdlValue.create(1))
        assert n.remove_prop("k") is True
        assert n.has_prop("k") is False
        assert n.remove_prop("k") is False


class TestDocumentMutation:
    def test_add_node(self) -> None:
        doc = parse("a")
        doc.add_node(KdlNode.create("b"))
        assert [n.name for n in doc.nodes] == ["a", "b"]
        assert doc.nodes[1].document is doc

    def test_insert_node(self) -> None:
        doc = parse("a\nc")
        doc.insert_node(1, KdlNode.create("b"))
        assert [n.name for n in doc.nodes] == ["a", "b", "c"]

    def test_remove_node(self) -> None:
        doc = parse("a\nb")
        removed = doc.remove_node(0)
        assert removed.name == "a"
        assert removed.document is None
        assert len(doc.nodes) == 1


# ---------------------------------------------------------------------------
# Value serialization
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        (True, "#true"),
        (False, "#false"),
        (None, "#null"),
        (42, "42"),
        (-1, "-1"),
        (0, "0"),
        (3.14, "3.14"),
        (1.0, "1.0"),
        (-0.5, "-0.5"),
        ("hello", "hello"),
        ("foo_bar", "foo_bar"),
        ("foo-bar", "foo-bar"),
        ("--foo", "--foo"),
        (".md", ".md"),
        ("true", '"true"'),
        ("null", '"null"'),
        ("inf", '"inf"'),
        ("with space", '"with space"'),
        ("123", '"123"'),
        ("-1foo", '"-1foo"'),
        (".5", '".5"'),
        ("", '""'),
        (" ", '" "'),
        ("\t", '"\\t"'),
        ("\n", '"""\n\n\n"""'),
        ("a\nb", '"""\n    a\n    b\n"""'),
    ],
)
def test_value_to_kdl(value: object, expected: str) -> None:
    v = KdlValue.create(value)
    assert v.to_kdl() == expected


def test_value_to_kdl_special_floats() -> None:
    assert KdlValue.create(float("inf")).to_kdl() == "#inf"
    assert KdlValue.create(float("-inf")).to_kdl() == "#-inf"
    # NaN cannot be compared via ==; check textual form directly.
    nan_text = KdlValue.create(float("nan")).to_kdl()
    assert nan_text == "#nan"


def test_value_keyword_passthrough() -> None:
    assert KdlValue.keyword("#custom").to_kdl() == "#custom"
    assert KdlValue.keyword("#true").to_kdl() == "#true"


def test_value_type_annotation_prefix() -> None:
    v = KdlValue.create(123, type_annotation="(u8)")
    assert v.to_kdl() == "(u8) 123"


@pytest.mark.parametrize(
    "value,expected",
    [
        ("\u0008", '"\\b"'),
        ("\u000c", '"\\f"'),
        ("\\", '"\\\\"'),
        ('"', '"\\""'),
        ("\u0007", '"\\u{7}"'),
        ("\u007f", '"\\u{7F}"'),
        ("\u202e", '"\\u{202E}"'),
        ("\u200e", '"\\u{200E}"'),
        ("a\\b", '"a\\\\b"'),
    ],
)
def test_escape_quoted(value: str, expected: str) -> None:
    assert KdlValue.create(value).to_kdl() == expected


def test_escape_unicode_printable_literal() -> None:
    # Printable non-ASCII stays literal.
    assert KdlValue.create("café").to_kdl() == "café"
    assert KdlValue.create("日本語").to_kdl() == "日本語"


def test_escape_surrogate_raises() -> None:
    with pytest.raises(ValueError, match="surrogate"):
        KdlValue.create("\ud800").to_kdl()


def test_serialize_unsupported_type_raises() -> None:
    v = KdlValue.create(object())
    with pytest.raises(TypeError):
        v.to_kdl()


# ---------------------------------------------------------------------------
# Node serialization
# ---------------------------------------------------------------------------


class TestNodeSerialize:
    def test_bare_name(self) -> None:
        n = KdlNode.create("foo")
        assert n.to_kdl() == "foo"

    def test_reserved_name_quoted(self) -> None:
        n = KdlNode.create("true")
        assert n.to_kdl() == '"true"'

    def test_name_with_args(self) -> None:
        n = KdlNode.create("foo", args=[KdlValue.create(1), KdlValue.create("x")])
        assert n.to_kdl() == "foo 1 x"

    def test_name_with_properties(self) -> None:
        n = KdlNode.create(
            "foo",
            properties={"count": KdlValue.create(5), "flag": KdlValue.create(True)},
        )
        # dict preserves insertion order
        assert n.to_kdl() == "foo count=5 flag=#true"

    def test_reserved_property_key_quoted(self) -> None:
        n = KdlNode.create("foo", properties={"true": KdlValue.create(1)})
        assert n.to_kdl() == 'foo "true"=1'

    def test_node_type_annotation(self) -> None:
        n = KdlNode.create("date", type_annotation="(published)")
        assert n.to_kdl() == "(published) date"

    def test_node_type_annotation_with_value_type(self) -> None:
        n = KdlNode.create(
            "foo",
            args=[KdlValue.create(1, type_annotation="(u8)")],
            type_annotation="(published)",
        )
        assert n.to_kdl() == "(published) foo (u8) 1"

    def test_children_block(self) -> None:
        n = KdlNode.create(
            "parent",
            children=[
                KdlNode.create("a"),
                KdlNode.create("b", args=[KdlValue.create(1)]),
            ],
        )
        assert n.to_kdl() == "parent {\n    a\n    b 1\n}"

    def test_force_children_block_empty(self) -> None:
        n = KdlNode.create("empty")
        assert n.to_kdl() == "empty"
        assert n.to_kdl(force_children_block=True) == "empty {}"

    def test_force_children_block_not_propagated(self) -> None:
        n = KdlNode.create(
            "p",
            children=[KdlNode.create("c")],
        )
        out = n.to_kdl(force_children_block=True)
        assert out == "p {\n    c\n}"

    def test_nested_children(self) -> None:
        n = KdlNode.create(
            "a",
            children=[
                KdlNode.create(
                    "b",
                    children=[KdlNode.create("c")],
                ),
            ],
        )
        assert n.to_kdl() == "a {\n    b {\n        c\n    }\n}"

    def test_custom_indent(self) -> None:
        n = KdlNode.create("p", children=[KdlNode.create("c")])
        assert n.to_kdl(indent_str="\t") == "p {\n\tc\n}"


# ---------------------------------------------------------------------------
# Document serialization
# ---------------------------------------------------------------------------


class TestDocSerialize:
    def test_single_node(self) -> None:
        doc = parse("a")
        assert doc.to_kdl() == "a\n"

    def test_multiple_nodes(self) -> None:
        doc = parse("a\nb 1")
        assert doc.to_kdl() == "a\nb 1\n"

    def test_empty_document(self) -> None:
        doc = parse("")
        assert doc.to_kdl() == ""

    def test_round_trip_preserves_structure(self) -> None:
        src = "parent {\n    a 1\n    b key=val\n    nested {\n        c\n    }\n}\n"
        doc = parse(src)
        out = doc.to_kdl()
        doc2 = parse(out)
        assert [n.name for n in doc.nodes] == [n.name for n in doc2.nodes]
        # The exact structure should match too.
        parent = doc2.nodes[0]
        assert [c.name for c in parent.children] == ["a", "b", "nested"]
        assert parent.children[1].get_prop("key") == "val"
        assert [c.name for c in parent.children[2].children] == ["c"]


# ---------------------------------------------------------------------------
# Migration example from the user's original plan
# ---------------------------------------------------------------------------


class TestMigrationExample:
    def test_struct_migration(self) -> None:
        doc = parse('struct "old" {}')
        struct = doc.nodes[0]
        struct.insert_child(
            0,
            KdlNode.create("@request", args=[KdlValue.create("GET /")]),
        )
        struct.insert_child(
            1,
            KdlNode.create(
                "@check",
                args=[KdlValue.create("exists")],
                children=[
                    KdlNode.create("css", args=[KdlValue.create(".foo")]),
                    KdlNode.create("to-bool"),
                    KdlNode.create("fallback", args=[KdlValue.create(False)]),
                ],
            ),
        )
        out = doc.to_kdl()
        assert '@request "GET /"' in out
        assert "@check exists" in out
        assert "css .foo" in out
        assert "to-bool" in out
        assert "#false" in out
        # Re-parse the output and verify semantics.
        reparsed = parse(out).nodes[0]
        assert reparsed.children[0].name == "@request"
        assert reparsed.children[1].name == "@check"
        assert reparsed.children[1].children[2].get_arg(0) is False
