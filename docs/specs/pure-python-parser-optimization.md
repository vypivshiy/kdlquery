# Specification: Pure Python KDL 2.0 Parser Optimization & Deepening

## Problem Statement

Parsing KDL documents in `kdlquery` currently exhibits critical performance bottlenecks in pure Python, preventing its practical use on medium-to-large documents (50KB–5MB+):

1. **Quadratic Complexity in Token Reconstruction**: When resolving raw slices for type annotations and values, the parser performs a linear token scan from index 0 across the entire token list. On a 196KB file with 4,000 nodes, this results in over 1.1 billion loop iterations, causing parsing to stall for over 67 seconds ($O(N^2)$ runtime).
2. **Interpreter Overhead in Character Cursor**: The lexer steps through source code character-by-character via a shallow cursor module. For each code point, multiple Python function calls execute to advance the index, allocate single-character lists, recalculate line/column numbers, validate disallowed unicode ranges through compound conditionals, and slice entire file tails to test numeric regular expressions. In a 50KB input, over 1.25 million Python calls occur during tokenization alone.
3. **Triple Tree Traversal and CST Object Churn**: The high-level entry point `kdlquery.parse(source)` constructs thousands of temporary immutable `CSTNode` and `CSTEntry` NamedTuples, only to immediately unpack them into mutable `KdlNode` and `KdlValue` instances. It then performs two additional full recursive tree traversals to wire parent pointers and document back-references.
4. **Bytecode-Bound String Decoding**: Escapes are decoded via a character-by-character `while` loop across all strings (even those containing zero escape characters), and multiline prefix stripping instantiates generator expressions on every line.

Users require fast, native-speed pure Python parsing without installing C or Rust binary extensions, while maintaining 100% compliance with KDL 2.0 and retaining the existing lossless CST capabilities.

## Solution

Restructure and deepen the parsing subsystem in three distinct phases:

1. **Phase 1 (Immediate Algorithmic Hotfixes)**: Eliminate the quadratic token search by localizing slice reconstruction to the current token cursor or source slice, eliminate buffer-copying file tail slices in numeric matching, and introduce a zero-copy fast path for unescaped strings.
2. **Phase 2 (Deep Regex Lexer Module)**: Replace the shallow per-character cursor with a compiled regex scanner operating at C-speed in CPython (`re.Pattern.match(..., pos)`). Codepoint validation is performed in bulk, line and column numbers are computed lazily via `bisect` on a line-starts offset table, and escape decoding is vectorized using `re.sub()`. A two-tier lexer architecture provides internal raw-offset tuples for parsing performance while preserving the public `KDLLexer.tokenize() -> list[Token]` interface.
3. **Phase 3 (Direct Single-Pass AST Construction)**: Introduce a Tree Builder seam (`AstBuilder` / `CstBuilder`). High-level parsing directly constructs `KdlDocument` and `KdlNode` trees with parent and document references wired in-flight during the single parse pass, cutting object allocations by ~60%. `KDL2CSTParser` remains fully supported as a CST-producing adapter.

## User Stories

1. As a developer parsing large KDL 2.0 configuration files (>100KB), I want parsing time to scale linearly $O(N)$ with document size, so that configuration loading does not block application startup.
2. As a library consumer, I want `kdlquery.parse(source)` to execute at high throughput in pure Python, so that I do not need a C compiler or Rust toolchain in restricted runtime environments (e.g., PyPy, AWS Lambda, WASM, minimal containers).
3. As a developer, I want all 403 official KDL 2.0 compliance test cases to pass unchanged, so that parsing semantics remain strictly compliant with the KDL 2.0 specification.
4. As a tooling author performing lossless source transformations, I want access to `KDL2CSTParser`, so that I can inspect and mutate CST structures with preserved spans and raw tokens.
5. As an API user inspecting nodes, I want `node.span.start.line` and `node.span.start.column` to accurately reflect 1-based source coordinates, so that error messages and linter warnings point to exact source locations.
6. As a consumer relying on structured diagnostics, I want `KDLParseError` to emit the exact same error codes (`PARSE_ERROR_CODES`), messages, and hints, so that automated error reporting and diagnostic integrations continue to function seamlessly.
7. As a developer querying KDL documents, I want parent and document back-references (`node.parent`, `node.document`) to be immediately available upon calling `parse()`, so that CSS3 node selector queries work instantly without manual wiring.
8. As a developer processing documents with thousands of plain strings without escape characters, I want string decoding to bypass regex and loops entirely, so that standard string values load with near-zero overhead.
9. As a developer embedding `kdlquery` in memory-constrained environments, I want memory allocations during parsing to be minimized, so that garbage collection pauses remain imperceptible.
10. As a maintainer of `kdlquery`, I want grammar rules, Escline handling, and Node Space validation to be concentrated in a single unified parsing module, so that future grammar fixes do not require duplicate maintenance across AST and CST parsers.

## Implementation Decisions

### Phase 1: Algorithmic Hotfixes & Localized Seams

1. **$O(1)$ Token Slice Reconstruction**:
   - In `_Parser`, anchor `_slice(start, end)` to a narrow window around `self.i` (or directly slice the original `source` string `source[start:end]` if retained).
   - Completely eliminate the global loop `for t in self.tokens:` from index 0.
   - For values without type annotations, return `tok.raw` directly without invoking slicing logic.

2. **Zero-Copy Numeric Matching**:
   - In `_try_read_number`, replace `rem = self.c.src[self.c.i :]` with `rx.match(self.c.src, pos=self.c.i)`.
   - Gate radix regex matching (`0x`, `0o`, `0b`) behind a single-character lookahead check (`ch == '0' and peek in 'xXoObB'`), skipping radix attempts for base-10 numbers and identifiers.

3. **Fast-Path String Escape Decoding**:
   - In `_decode_escape_body`, add an immediate fast path: `if "\\" not in body: return body`.
   - Skip all list allocations and character traversal when no backslashes exist.

### Phase 2: Deep Regex Lexer Module

4. **Regex-Driven Token Scanning**:
   - Implement a unified master regex using named groups for high-frequency tokens: whitespace, newlines, delimiters (`(`, `)`, `{`, `}`, `=`, `;`), slashdash (`/-`), numeric literals, standard quoted strings (`"(?:[^"\\]|\\.)*"`), and valid bare identifiers.
   - Execute token scanning via `master_pattern.match(source, pos)` in a loop, moving the scanning pointer in native C without per-character Python dispatch.

5. **Specialized Delimiter and Continuation Handlers**:
   - Multi-hash raw strings (`#"..."#`, `##"..."##`, `#"""..."""#`) and multiline blocks are handled by targeted sub-routines triggered when `#` or `"""` is matched.
   - Nested block comments (`/* ... */`) are tracked via a dedicated scanner loop with depth counting.
   - Escline handling retains strict detection of prohibited single-line comments (`//`) across newlines to enforce the `escline-comment-continuation` rule per ADR-0001.

6. **Deferred Position and Line Calculation**:
   - Build a `line_starts` array (a list of byte offsets where each line begins) using `[0] + [m.end() for m in re.finditer(r"\r\n|[\n\r\u0085\u000b\u000c\u2028\u2029]", source)]`.
   - Provide a helper function `offset_to_position(offset: int) -> Position`:
     - `line_idx = bisect_right(line_starts, offset) - 1`
     - `line = line_idx + 1`
     - `col = offset - line_starts[line_idx] + 1`
   - Calculate `Position` and `Span` only when constructing concrete AST/CST nodes or raising `KDLParseError`.

7. **Bulk Codepoint and BOM Validation**:
   - Replace character-by-character codepoint validation with a single compiled regex search:
     `_DISALLOWED_RE = re.compile(r"[\x00-\x08\x0e-\x1f\x7f\ud800-\udfff\u200e\u200f\u202a-\u202e\u2066-\u2069]")`.
   - Check BOM constraints (`\ufeff` outside offset 0) via `"\ufeff" in source[1:]`.

8. **Two-Tier Lexer Seam**:
   - Internal scanning yields a fast tuple stream: `(TokenType, raw, value, start_offset, end_offset)`.
   - The public class `KDLLexer` wraps the internal scanner and materializes standard `Token(typ, raw, value, Span(start, end))` instances on `.tokenize()`, preserving full backward compatibility.

9. **Vectorized Escape and Multiline Decoding**:
   - Replace the character-by-character state machine in `_decode_escape_body` with `re.sub(r'\\([nrtbf"\\s]|u\{[0-9a-fA-F]+\}|\s+)', _replace_escape, body)`.
   - In `_multiline_extract_prefix`, check whitespace without generator expressions, using string methods (`line.lstrip()`).

### Phase 3: Direct Single-Pass AST Construction

10. **Tree Builder Seam**:
    - Define a generic parsing core that consumes the token stream and drives a builder interface:
      - `builder.start_node(name, type_annotation, span)`
      - `builder.add_arg(value, type_annotation, span)`
      - `builder.add_prop(key, value, type_annotation, span)`
      - `builder.start_children(span)`
      - `builder.end_children(span)`
      - `builder.end_node(span)`
      - `builder.finish_document(span)`

11. **`AstBuilder` (Default Direct AST Adapter)**:
    - Directly constructs mutable `KdlNode` and `KdlValue` instances.
    - Wires child-parent relationships (`node.parent = parent`) on the fly when parsing child blocks.
    - Attaches document back-references (`node._document = doc`) in a single pass.
    - Completely bypasses creation of `CSTNode`, `CSTArgEntry`, `CSTPropEntry`, and `CSTIdentifier`.

12. **`CstBuilder` (Lossless CST Adapter)**:
    - Produces the full, immutable `CSTDocument` with `CSTNode`, `CSTEntry`, and exact token slices.
    - Used by `KDL2CSTParser.parse(source)` to ensure 100% compatibility with existing CST mutation and serialization workflows.

## Testing Decisions

### Seam Discipline & Test Strategy

- **Highest Seam Testing**: Tests should exercise external behavior through `kdlquery.parse(source)` and `KDL2CSTParser().parse(source)`. No tests should mock or assert on internal private scanner state.
- **KDL 2.0 Compliance Suite**: All 403 test files in `tests/kdl_test_cases/input/*.kdl` (both valid and invalid cases) must pass with zero modifications.
- **Error Code and Coordinate Fidelity**: Verify that invalid cases raise `KDLParseError` with exact `line`, `col`, and `code` matching the official compliance specifications and existing test suite.
- **AST Navigation & Selector Integrity**: Run the entire existing test suite (`test_navigation.py`, `test_selector.py`, `test_reader.py`, `test_write.py`) to confirm that direct AST construction produces trees identical in topology, properties, and queries to the previous CST-converted trees.
- **Performance Regression Benchmarks**: Add automated performance tests comparing throughput on large inputs (e.g. 500KB–2MB synthetic documents) to enforce linear $O(N)$ scaling and prevent quadratic regressions in future PRs.

## Out of Scope

- Native compiled C/C++ or Rust accelerator modules (e.g., CFFI, PyO3, Cython) — all optimizations must remain 100% pure Python.
- Altering the CSS3 node selector engine or selector syntax (governed by ADR-0002).
- Changing the public data model of `KdlNode`, `KdlValue`, `KdlDocument`, or `CSTDocument`.
- Modifying KDL 2.0 grammar rules or relaxing escline comment prohibitions (governed by ADR-0001).

## Further Notes

- Target performance goals:
  - Phase 1: 50x–70x speedup on inputs >100KB (eliminating $O(N^2)$ quadratic bottleneck).
  - Phase 2: 25x–35x speedup in raw tokenization throughput.
  - Phase 3: 2x–3x additional speedup in document construction, with a 60% reduction in peak memory and GC pause times.
- Combined overall expected throughput: ~5–10 MB/sec in pure Python (up from ~0.15 MB/sec).
