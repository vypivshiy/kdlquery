from pathlib import Path

import pytest

from kdlquery.types import (
    CSTArgEntry,
    CSTPropEntry,
    CSTValue,
    KDLParseError,
)
from kdlquery.parser import (
    KDL2CSTParser,
    KDLLexer,
    RawToken,
    _build_line_starts,
    _offset_to_position,
    offset_to_position,
)


_ROOT = Path(__file__).parent
_ALL_KDL_FILES = list((_ROOT / "kdl_test_cases/input").glob("*.kdl"))
_VALID_KDL_FILES = [f for f in _ALL_KDL_FILES if not f.name.endswith("_fail.kdl")]
_INVALID_KDL_FILES = [f for f in _ALL_KDL_FILES if f.name.endswith("_fail.kdl")]


@pytest.mark.parametrize("file", _VALID_KDL_FILES, ids=lambda p: p.name)
def test_orig_kdl2_valid_cases(file: Path) -> None:
    parser = KDL2CSTParser()
    doc = parser.parse(file.read_text(encoding="utf-8-sig"))
    assert doc.span.end.offset >= doc.span.start.offset


@pytest.mark.parametrize("file", _INVALID_KDL_FILES, ids=lambda p: p.name)
def test_orig_kdl2_invalid_cases(file: Path) -> None:
    with pytest.raises(KDLParseError):
        KDL2CSTParser().parse(file.read_text(encoding="utf-8-sig"))


def test_kdl_parser_keeps_spans_and_entries() -> None:
    src = """
struct Main {
    item type=list {
        css "a[href]"
        attr href
        fallback #null
    }
}
"""
    doc = KDL2CSTParser().parse(src)

    assert len(doc.nodes) == 1
    root = doc.nodes[0]
    assert root.name.value == "struct"
    assert isinstance(root.entries[0], CSTArgEntry)
    assert root.entries[0].value.value == "Main"

    item = root.children[0]
    assert item.name.value == "item"

    prop_entries = [e for e in item.entries if isinstance(e, CSTPropEntry)]
    assert len(prop_entries) == 1
    assert prop_entries[0].key.value == "type"
    assert prop_entries[0].value.value == "list"

    arg_entries = [e for e in item.children[0].entries if isinstance(e, CSTArgEntry)]
    assert arg_entries[0].value.value == "a[href]"

    assert item.span.start.line > 0
    assert item.span.end.offset > item.span.start.offset


def test_kdl_parser_multiline_and_raw_strings() -> None:
    src = '''
@doc """
line1
line2
"""
define PAT=#"""
(?xs)
abc
"""#
'''
    doc = KDL2CSTParser().parse(src)

    assert len(doc.nodes) == 2
    doc_node = doc.nodes[0]
    define_node = doc.nodes[1]

    assert doc_node.name.value == "@doc"
    assert isinstance(doc_node.entries[0], CSTArgEntry)
    assert "line1" in doc_node.entries[0].value.value

    assert define_node.name.value == "define"
    assert isinstance(define_node.entries[0], CSTPropEntry)
    assert "(?xs)" in define_node.entries[0].value.value


def test_kdl_parser_accepts_dotted_bare_identifier_values() -> None:
    src = """
struct X {
    f { css-all .col-auto }
}
"""
    doc = KDL2CSTParser().parse(src)
    field = doc.nodes[0].children[0]
    css_all = field.children[0]
    assert css_all.name.value == "css-all"
    assert isinstance(css_all.entries[0], CSTArgEntry)
    assert css_all.entries[0].value.value == ".col-auto"


def test_kdl_parser_allows_string_identifier_node_name() -> None:
    src = """
repl {
    "from" "to"
}
"""
    doc = KDL2CSTParser().parse(src)
    repl_node = doc.nodes[0]
    child = repl_node.children[0]
    assert child.name.value == "from"
    assert isinstance(child.entries[0], CSTArgEntry)
    assert child.entries[0].value.value == "to"


def test_kdl_parser_parses_radix_and_keyword_numbers() -> None:
    src = """
node 0x10 0o10 0b10 #inf #-inf #nan
"""
    doc = KDL2CSTParser().parse(src)
    vals = [
        entry.value.value
        for entry in doc.nodes[0].entries
        if isinstance(entry, CSTArgEntry)
    ]
    assert vals[0] == 16
    assert vals[1] == 8
    assert vals[2] == 2
    assert isinstance(vals[3], (int, float))
    assert isinstance(vals[4], (int, float))
    assert isinstance(vals[5], (int, float))
    assert vals[3] > 0
    assert vals[4] < 0
    assert vals[5] != vals[5]


def test_kdl_parser_supports_slashdash_omission() -> None:
    src = """
/- dropped 1
kept 2
"""
    doc = KDL2CSTParser().parse(src)
    assert len(doc.nodes) == 1
    assert doc.nodes[0].name.value == "kept"
    assert doc.nodes[0].entries[0].value.value == 2


def test_kdl_parser_supports_nested_block_comments() -> None:
    src = """
/* outer
   /* inner */
*/
node 1
"""
    doc = KDL2CSTParser().parse(src)
    assert len(doc.nodes) == 1
    assert doc.nodes[0].name.value == "node"


def test_kdl_parser_raises_on_unterminated_block_comment() -> None:
    with pytest.raises(KDLParseError, match="Unterminated block comment"):
        KDL2CSTParser().parse("/* x")


def test_kdl_parser_raises_on_newline_in_quoted_string() -> None:
    bad = 'node "a\nb"'
    with pytest.raises(KDLParseError, match="Newline in quoted string"):
        KDL2CSTParser().parse(bad)


def test_kdl_parser_supports_escline_line_continuation() -> None:
    src = 'node "a" \\\n "b"'
    doc = KDL2CSTParser().parse(src)
    vals = [
        entry.value.value
        for entry in doc.nodes[0].entries
        if isinstance(entry, CSTArgEntry)
    ]
    assert vals == ["a", "b"]


def test_kdl_parser_handles_spec_like_package_example() -> None:
    src = '''
package {
  name my-pkg
  version "1.2.3"

  dependencies {
    lodash "^3.2.1" optional=#true alias=underscore
  }

  scripts {
    message """
      hello
      world
      """
    build #"""
      echo "foo"
      node -c "console.log('hello, world!');"
      echo "foo" > some-file.txt
      """#
  }

  the-matrix 1 2 3 \\
             4 5 6 \\
             7 8 9

  /-this-is-commented {
    this entire node {
      is gone
    }
  }
}
'''
    doc = KDL2CSTParser().parse(src)

    assert len(doc.nodes) == 1
    pkg = doc.nodes[0]
    assert pkg.name.value == "package"

    children = {n.name.value: n for n in pkg.children}
    assert "name" in children
    assert "version" in children
    assert "dependencies" in children
    assert "scripts" in children
    assert "the-matrix" in children
    assert "this-is-commented" not in children

    deps = children["dependencies"].children[0]
    assert deps.name.value == "lodash"
    dep_args = [e.value.value for e in deps.entries if isinstance(e, CSTArgEntry)]
    dep_props = {
        e.key.value: e.value.value for e in deps.entries if isinstance(e, CSTPropEntry)
    }
    assert dep_args == ["^3.2.1"]
    assert dep_props["optional"] is True
    assert dep_props["alias"] == "underscore"

    scripts = children["scripts"].children
    message = next(n for n in scripts if n.name.value == "message")
    build = next(n for n in scripts if n.name.value == "build")
    assert "hello" in message.entries[0].value.value
    assert "world" in message.entries[0].value.value
    assert "console.log('hello, world!');" in build.entries[0].value.value

    matrix = children["the-matrix"]
    matrix_vals = [e.value.value for e in matrix.entries if isinstance(e, CSTArgEntry)]
    assert matrix_vals == [1, 2, 3, 4, 5, 6, 7, 8, 9]


# -- Type annotation propagation --


class TestTypeAnnotationPropagation:
    def test_type_annotation_on_arg_value(self) -> None:
        doc = KDL2CSTParser().parse('node (array)"str"')
        arg = doc.nodes[0].entries[0]
        assert isinstance(arg, CSTArgEntry)
        assert isinstance(arg.value, CSTValue)
        assert arg.value.type_annotation is not None
        assert arg.value.type_annotation.raw == "(array)"

    def test_type_annotation_on_property_value(self) -> None:
        doc = KDL2CSTParser().parse("node prop=(u8)123")
        prop = doc.nodes[0].entries[0]
        assert isinstance(prop, CSTPropEntry)
        assert isinstance(prop.value, CSTValue)
        assert prop.value.type_annotation is not None
        assert prop.value.type_annotation.raw == "(u8)"

    def test_type_annotation_on_node(self) -> None:
        doc = KDL2CSTParser().parse('(published)date "1970-01-01"')
        assert doc.nodes[0].type_annotation is not None
        assert doc.nodes[0].type_annotation.raw == "(published)"

    def test_no_type_annotation(self) -> None:
        doc = KDL2CSTParser().parse('node "plain"')
        assert doc.nodes[0].type_annotation is None
        arg = doc.nodes[0].entries[0]
        assert isinstance(arg, CSTArgEntry)
        assert isinstance(arg.value, CSTValue)
        assert arg.value.type_annotation is None

    def test_typed_bare_identifier_value(self) -> None:
        doc = KDL2CSTParser().parse("node (array)str")
        arg = doc.nodes[0].entries[0]
        assert isinstance(arg, CSTArgEntry)
        assert isinstance(arg.value, CSTValue)
        assert arg.value.type_annotation is not None
        assert arg.value.type_annotation.raw == "(array)"
        assert arg.value.value == "str"


# -- Structured error codes --


class TestParseErrorCodes:
    """Every parse failure must carry a stable `code` and a non-empty `hint`."""

    def test_code_defaults_empty_for_backward_compat(self) -> None:
        # Old call form `KDLParseError(msg, line, col)` must still work.
        err = KDLParseError("legacy", line=2, col=3)
        assert err.msg == "legacy"
        assert err.line == 2
        assert err.col == 3
        assert err.code == ""
        assert err.hint == ""
        assert str(err) == "legacy: line 2 column 3"

    # One fixture per category. Each fixture is chosen to reliably land on the
    # targeted raise site.
    @pytest.mark.parametrize(
        "src,expected_code",
        [
            # --- raw strings (the motivating user case) ---
            # single-quote raw string hits a literal newline before closing #
            ('re foo #"(\\d+)"\nbar', "raw-string/newline"),
            # single-quote raw string runs to EOF without closing #
            ('re foo #"(\\d+)"', "raw-string/unterminated"),
            # multiline raw string: content not preceded by a newline
            ('x #"""body"""#', "multiline-raw-string/no-leading-newline"),
            # --- quoted strings ---
            ('x "open\n"', "quoted-string/newline"),
            ('x "open', "quoted-string/unterminated"),
            ('x "\\xZZ"', "quoted-string/decode"),
            # --- multiline (non-raw) strings ---
            ('x """body"""', "multiline-string/no-leading-newline"),
            ('x """\nbody', "multiline-string/unterminated"),
            # --- comments ---
            ("/* never closed", "block-comment/unterminated"),
            # --- disallowed code points ---
            ("x \u0001", "control-codepoint"),
            ("a\ufeff", "bom-outside-start"),
            ("x \u202a", "direction-control-codepoint"),
            # --- numbers ---
            ("x 123abc", "number/invalid-trailing"),
            ("x 0x1G", "number/invalid-trailing"),
            # --- children blocks ---
            ("x {", "children-block/unterminated"),
            ("x {} {}", "node/multiple-children-blocks"),
            # --- structural ---
            ('foo"bar"', "expected-whitespace"),
            ("true", "reserved-bare-identifier"),
            ("#$", "unexpected-character"),
            # expected-eol: two nodes on the same line, the second appears
            # right after a closing children block (no newline between).
            ("x {\n} y", "expected-eol"),
            # --- escline comment continuation ---
            ("node \\\n// comment\narg", "escline-comment-continuation"),
        ],
    )
    def test_raises_expected_code(self, src: str, expected_code: str) -> None:
        with pytest.raises(KDLParseError) as exc:
            KDL2CSTParser().parse(src)
        assert exc.value.code == expected_code, (
            f"expected code {expected_code!r}, got {exc.value.code!r} "
            f"(msg={exc.value.msg!r})"
        )
        assert exc.value.hint, f"hint empty for code {expected_code!r}"
        if expected_code == "raw-string/unterminated":
            assert "trailing #" in exc.value.hint

    def test_escline_comment_continuation_detailed(self) -> None:
        snippet = """
endpoint name="service" \\
        target="replica" \\
        // first explanatory comment
        // second explanatory comment
        "https://example.com/api"
"""
        with pytest.raises(KDLParseError) as exc:
            KDL2CSTParser().parse(snippet)
        assert exc.value.code == "escline-comment-continuation"
        assert exc.value.line == 4
        assert "/* ... */" in exc.value.hint

        # Empty lines between escline and comment should also raise
        with pytest.raises(KDLParseError) as exc2:
            KDL2CSTParser().parse("node \\\n\n    // comment\n    arg\n")
        assert exc2.value.code == "escline-comment-continuation"

        # Block comments across continuation are allowed and work as node-space
        doc_block = KDL2CSTParser().parse(
            "node \\\n    /* comment */ \\\n    arg\n"
        )
        assert len(doc_block.nodes) == 1
        assert doc_block.nodes[0].name.value == "node"
        assert len(doc_block.nodes[0].entries) == 1

        doc_block2 = KDL2CSTParser().parse(
            "node \\\n    /* comment */ arg\n"
        )
        assert len(doc_block2.nodes) == 1
        assert doc_block2.nodes[0].name.value == "node"
        assert len(doc_block2.nodes[0].entries) == 1

        # Same-line single-line comments remain valid KDL 2.0
        doc_sameline = KDL2CSTParser().parse(
            "node \\ // same-line comment\n    arg\n"
        )
        assert len(doc_sameline.nodes) == 1
        assert doc_sameline.nodes[0].name.value == "node"
        assert len(doc_sameline.nodes[0].entries) == 1


class TestPhase1Optimizations:
    def test_escape_fast_path(self) -> None:
        from kdlquery.parser import _decode_escape_body

        plain = "hello world this is a test without escapes"
        res = _decode_escape_body(plain)
        assert res is plain  # Same string object returned via fast-path

        with_escapes = "hello\\nworld"
        assert _decode_escape_body(with_escapes) == "hello\nworld"

    def test_unannotated_value_raw(self) -> None:
        doc = KDL2CSTParser().parse('node 123 "hello" #true #null')
        entries = doc.nodes[0].entries
        assert [e.value.raw for e in entries] == ["123", '"hello"', "#true", "#null"]

    def test_source_retained_slice(self) -> None:
        from kdlquery.parser import KDLLexer, _Parser

        source = 'node (my-type)"val"'
        tokens = KDLLexer(source).tokenize()
        parser_with_source = _Parser(tokens, source=source)
        doc = parser_with_source.parse_document()
        entry = doc.nodes[0].entries[0]
        assert isinstance(entry.value, CSTValue)
        assert entry.value.type_annotation is not None
        assert entry.value.type_annotation.raw == "(my-type)"

        # Fallback when source is None
        parser_no_source = _Parser(tokens)
        doc_no_source = parser_no_source.parse_document()
        entry_no_src = doc_no_source.nodes[0].entries[0]
        assert isinstance(entry_no_src.value, CSTValue)
        assert entry_no_src.value.type_annotation is not None
        assert entry_no_src.value.type_annotation.raw == "(my-type)"

    def test_radix_and_number_matching(self) -> None:
        doc = KDL2CSTParser().parse("node 0x1F 0o77 0b101 42 3.14 -10")
        values = [e.value.value for e in doc.nodes[0].entries]
        assert values == [0x1F, 0o77, 0b101, 42, 3.14, -10]


def test_build_line_starts() -> None:
    assert _build_line_starts("") == [0]
    assert _build_line_starts("node 1") == [0]
    assert _build_line_starts("a\nb\r\nc\rd") == [0, 2, 5, 7]
    assert _build_line_starts("line1\u0085line2\u000bline3\u000cline4\u2028line5\u2029line6") == [
        0, 6, 12, 18, 24, 30
    ]


def test_offset_to_position_mapping() -> None:
    source = "node {\n    sub 1\r\n    sub 2\n}"
    line_starts = _build_line_starts(source)
    # line 1: "node {\n" (0..6)
    # line 2: "    sub 1\r\n" (7..17)
    # line 3: "    sub 2\n" (18..27)
    # line 4: "}" (28..28)
    pos0 = _offset_to_position(line_starts, 0)
    assert pos0.line == 1
    assert pos0.column == 1

    pos_nl1 = _offset_to_position(line_starts, 6)
    assert pos_nl1.line == 1
    assert pos_nl1.column == 7

    pos_line2 = _offset_to_position(line_starts, 7)
    assert pos_line2.line == 2
    assert pos_line2.column == 1

    pos_line2_sub = _offset_to_position(line_starts, 11)
    assert pos_line2_sub.line == 2
    assert pos_line2_sub.column == 5

    pos_line3 = _offset_to_position(line_starts, 18)
    assert pos_line3.line == 3
    assert pos_line3.column == 1

    pos_line4 = offset_to_position(line_starts, 28)
    assert pos_line4.line == 4
    assert pos_line4.column == 1

    # KDLLexer helper method
    lexer = KDLLexer(source)
    assert lexer.offset_to_position(11) == pos_line2_sub


def test_bulk_codepoint_validation_bom() -> None:
    # BOM at offset 0 is allowed
    doc = KDL2CSTParser().parse("\ufeffnode 1")
    assert len(doc.nodes) == 1

    # BOM after offset 0 is disallowed
    with pytest.raises(KDLParseError) as exc:
        KDL2CSTParser().parse("node \ufeff1")
    assert exc.value.code == "bom-outside-start"
    assert exc.value.line == 1
    assert exc.value.col == 6


def test_bulk_codepoint_validation_disallowed() -> None:
    # Control code point
    with pytest.raises(KDLParseError) as exc:
        KDL2CSTParser().parse("first\nsecond \x08 third")
    assert exc.value.code == "control-codepoint"
    assert exc.value.line == 2
    assert exc.value.col == 8

    # Surrogate code point
    with pytest.raises(KDLParseError) as exc:
        KDL2CSTParser().parse("node \ud800")
    assert exc.value.code == "surrogate-codepoint"
    assert exc.value.line == 1
    assert exc.value.col == 6

    # Direction-control code point
    with pytest.raises(KDLParseError) as exc:
        KDL2CSTParser().parse("node\n  \u202e 1")
    assert exc.value.code == "direction-control-codepoint"
    assert exc.value.line == 2
    assert exc.value.col == 3


def test_two_tier_lexer_architecture() -> None:
    from kdlquery.types import Token, TokenType

    source = 'node key="value" 123 #true {\n    /-child;\n}\n'
    lexer = KDLLexer(source)

    # 1. Fast internal raw-offset tuple stream
    raw_tokens = lexer.tokenize_raw()
    assert len(raw_tokens) > 0
    assert all(isinstance(t, RawToken) for t in raw_tokens)
    assert all(isinstance(t, tuple) for t in raw_tokens)

    # Verify tuple unpacking
    first = raw_tokens[0]
    typ, raw, val, start, end = first
    assert typ == TokenType.IDENT
    assert raw == "node"
    assert val == "node"
    assert start == 0
    assert end == 4

    # 2. Public backward-compatible Token stream
    tokens = lexer.tokenize()
    assert len(tokens) == len(raw_tokens)
    assert all(isinstance(t, Token) for t in tokens)

    # Spans match line_starts calculation
    assert tokens[0].typ == TokenType.IDENT
    assert tokens[0].span.start.line == 1
    assert tokens[0].span.start.column == 1
    assert tokens[0].span.end.offset == 4


def test_master_regex_high_frequency_tokens() -> None:
    from kdlquery.types import TokenType

    source = 'node (my-type)foo key="str" 0x1A 0o77 0b101 42 3.14 -10 #false #null /- bar; \n'
    lexer = KDLLexer(source)
    raw_tokens = lexer.tokenize_raw()

    token_types = [t.typ for t in raw_tokens]
    assert token_types == [
        TokenType.IDENT,  # node
        TokenType.LPAREN,  # (
        TokenType.IDENT,  # my-type
        TokenType.RPAREN,  # )
        TokenType.IDENT,  # foo
        TokenType.IDENT,  # key
        TokenType.EQUAL,  # =
        TokenType.STRING,  # "str"
        TokenType.NUMBER,  # 0x1A
        TokenType.NUMBER,  # 0o77
        TokenType.NUMBER,  # 0b101
        TokenType.NUMBER,  # 42
        TokenType.NUMBER,  # 3.14
        TokenType.NUMBER,  # -10
        TokenType.BOOL,  # #false
        TokenType.NULL,  # #null
        TokenType.SLASHDASH,  # /-
        TokenType.IDENT,  # bar
        TokenType.SEMI,  # ;
        TokenType.NEWLINE,  # \n
        TokenType.EOF,
    ]


def test_multihash_raw_and_multiline_strings() -> None:
    # Multi-hash raw strings
    doc1 = KDL2CSTParser().parse('node #"single raw"# ##"double raw"## ###"triple raw"###')
    values1 = [e.value.value for e in doc1.nodes[0].entries]
    assert values1 == ["single raw", "double raw", "triple raw"]

    # Multiline raw strings
    doc2 = KDL2CSTParser().parse('node #"""\n  multiline raw\n  """# ##"""\n  double ml\n  """##')
    values2 = [e.value.value for e in doc2.nodes[0].entries]
    assert values2 == ["multiline raw", "double ml"]

    # Multiline raw string missing leading newline raises error
    with pytest.raises(KDLParseError) as exc:
        KDL2CSTParser().parse('node #"""no newline"""#')
    assert exc.value.code == "multiline-raw-string/no-leading-newline"

    # Unterminated raw string
    with pytest.raises(KDLParseError) as exc2:
        KDL2CSTParser().parse('node ##"unterminated"#')
    assert exc2.value.code == "raw-string/unterminated"


def test_nested_block_comments_depth_tracking() -> None:
    # Deeply nested block comments
    doc = KDL2CSTParser().parse("node /* outer /* mid /* inner */ mid2 */ outer2 */ 42")
    assert len(doc.nodes) == 1
    assert len(doc.nodes[0].entries) == 1
    assert doc.nodes[0].entries[0].value.value == 42

    # Unterminated nested block comment
    with pytest.raises(KDLParseError) as exc:
        KDL2CSTParser().parse("node /* outer /* inner */ missing_close 42")
    assert exc.value.code == "block-comment/unterminated"


def test_vectorized_escape_decoding() -> None:
    from kdlquery.parser import _decode_escape_body

    # Plain fast path
    assert _decode_escape_body("plain text") == "plain text"

    # All standard escapes
    assert _decode_escape_body(r"line\nbreak\r\ttab\b\f\\\"space\s") == "line\nbreak\r\ttab\b\f\\\"space "

    # Unicode scalar escapes
    assert _decode_escape_body(r"\u{41}\u{1F600}") == "A\U0001F600"

    # Whitespace escapes
    assert _decode_escape_body("hello\\\n    world") == "helloworld"

    # Invalid escapes
    with pytest.raises(ValueError, match="Surrogate code point"):
        _decode_escape_body(r"\u{D800}")
    with pytest.raises(ValueError, match="exceeds maximum"):
        _decode_escape_body(r"\u{110000}")
    with pytest.raises(ValueError, match="Unterminated"):
        _decode_escape_body(r"\u{123")
    with pytest.raises(ValueError, match="Invalid escape sequence"):
        _decode_escape_body(r"\x")

