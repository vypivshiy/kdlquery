# 05: Performance Benchmarks and Compliance Suite Verification

**What to build:**
Add an automated performance benchmark test verifying linear O(N) scaling on large KDL documents (50KB–2MB synthetic documents) to prevent quadratic regressions. Ensure throughput goals are validated. Run and verify full test suite: all 403 official KDL 2.0 compliance tests, error codes, coordinates, selector tests, and serialization tests.

**Blocked by:** 04-tree-builder-and-direct-ast-construction

**Status:** resolved

- [x] Automated benchmark test in `tests/test_benchmark.py` verifies linear O(N) scaling on 50KB–2MB inputs.
- [x] Parsing throughput reaches >5 MB/sec pure Python.
- [x] All 403 KDL 2.0 compliance test cases pass with exact error codes and coordinates.
- [x] All existing test suites pass: `test_kdl_parser.py`, `test_navigation.py`, `test_reader.py`, `test_selector.py`, `test_write.py`.
- [x] `uv run mypy kdlquery` and `uv run ruff check .` pass cleanly.
