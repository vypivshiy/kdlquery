from __future__ import annotations

import time

import pytest

import kdlquery
from kdlquery import KdlDocument, KDL2CSTParser
from kdlquery.parser import KDLLexer

# Reusable synthetic template containing a rich, realistic mix of KDL 2.0 constructs:
# - Type annotations on nodes, arguments, and properties
# - Strings, numbers (int, float), booleans, and null
# - Properties and positional arguments
# - Single-line comments
# - 2 levels of nested child blocks
_SYNTHETIC_TEMPLATE = """\
(service)node name="worker-{i}" enabled=#true priority=10 timeout=45.5 {{
    // Worker configuration block
    config id="cfg-{i}" host="worker-{i}.internal.net" port=8080 active=#true
    metrics interval=15.0 retries=3 format="prometheus"
    tasks max_concurrency=8 queue_size=1024 {{
        handler (task_handler)"job-runner" async=#true retry_limit=5
        fallback "log-error" level="warn"
    }}
    resources memory_mb=4096 cpu_cores=2.5 {{
        limit type="soft" memory_mb=3072
        limit type="hard" memory_mb=4096
    }}
}}
"""


def _generate_synthetic_kdl(target_bytes: int) -> str:
    """Generate a synthetic KDL 2.0 document of approximately target_bytes."""
    parts: list[str] = []
    curr = 0
    i = 0
    while curr < target_bytes:
        block = _SYNTHETIC_TEMPLATE.format(i=i)
        parts.append(block)
        curr += len(block.encode("utf-8"))
        i += 1
    return "".join(parts)


class TestParserPerformanceBenchmarks:
    """Performance benchmarks verifying linear O(N) scaling and throughput."""

    @pytest.fixture(autouse=True)
    def _warmup(self) -> None:
        """Warm up Python bytecode and parser regex caches before benchmarking."""
        warmup_doc = _generate_synthetic_kdl(5_000)
        kdlquery.parse(warmup_doc)

    def test_linear_scaling_synthetic_documents(self) -> None:
        """Verify linear O(N) scaling across small (~20KB), medium (~100KB), and large (~500KB) documents.

        In an O(N^2) implementation (such as pre-optimization slice reconstruction),
        time-per-byte grows linearly with document size (e.g. 25x growth from 20KB to 500KB).
        In an O(N) linear implementation, time-per-byte remains approximately constant.
        """
        sizes = [20_000, 100_000, 500_000]
        timings: list[tuple[int, float, float]] = []  # (actual_bytes, elapsed_sec, time_per_byte)

        for target in sizes:
            doc = _generate_synthetic_kdl(target)
            actual_bytes = len(doc.encode("utf-8"))

            t0 = time.perf_counter()
            parsed = kdlquery.parse(doc)
            dt = time.perf_counter() - t0

            assert isinstance(parsed, KdlDocument)
            assert len(parsed.nodes) > 0

            time_per_byte = dt / actual_bytes
            timings.append((actual_bytes, dt, time_per_byte))

        small_bytes, small_time, small_tpb = timings[0]
        med_bytes, med_time, med_tpb = timings[1]
        large_bytes, large_time, large_tpb = timings[2]

        # Calculate time-per-byte growth ratios
        growth_small_to_med = med_tpb / small_tpb
        growth_small_to_large = large_tpb / small_tpb

        # If quadratic O(N^2), 500KB vs 20KB ratio would be ~25x.
        # Under linear O(N), ratio remains bounded (well under 3.5x allowing for GC/cache variance).
        assert growth_small_to_med < 3.0, (
            f"Quadratic scaling detected between small ({small_bytes}B) and medium ({med_bytes}B): "
            f"time-per-byte ratio is {growth_small_to_med:.2f}x"
        )
        assert growth_small_to_large < 3.5, (
            f"Quadratic scaling detected between small ({small_bytes}B) and large ({large_bytes}B): "
            f"time-per-byte ratio is {growth_small_to_large:.2f}x"
        )

        # Large document (500KB, ~930 root nodes, ~6,500 total nodes) must parse in < 4.0 seconds.
        # Pre-optimization, a 196KB file took >67 seconds.
        assert large_time < 4.0, (
            f"Large document parsing exceeded time threshold: {large_time:.2f}s for {large_bytes}B"
        )

        # Verify throughput meets expectations (> 0.25 MB/s on complex nested documents)
        throughput_mb_s = (large_bytes / (1024 * 1024)) / large_time
        assert throughput_mb_s > 0.25, (
            f"Parsing throughput too low: {throughput_mb_s:.2f} MB/s"
        )

    def test_linear_scaling_50kb_to_1mb(self) -> None:
        """Verify linear O(N) scaling holds across medium to large scale (50KB to 1MB).

        1MB is ~20x larger than 50KB. Under O(N^2), time-per-byte would increase ~20x
        and 1MB would take ~40 seconds. Under O(N), the time-per-byte ratio is tightly bounded.
        """
        doc_50k = _generate_synthetic_kdl(50_000)
        doc_1m = _generate_synthetic_kdl(1_000_000)
        bytes_50k = len(doc_50k.encode("utf-8"))
        bytes_1m = len(doc_1m.encode("utf-8"))

        t0 = time.perf_counter()
        parsed_50k = kdlquery.parse(doc_50k)
        dt_50k = time.perf_counter() - t0

        t0 = time.perf_counter()
        parsed_1m = kdlquery.parse(doc_1m)
        dt_1m = time.perf_counter() - t0

        assert len(parsed_50k.nodes) > 0
        assert len(parsed_1m.nodes) > 0

        tpb_50k = dt_50k / bytes_50k
        tpb_1m = dt_1m / bytes_1m
        growth = tpb_1m / tpb_50k

        assert growth < 3.5, (
            f"Quadratic scaling detected between 50KB ({bytes_50k}B) and 1MB ({bytes_1m}B): "
            f"time-per-byte ratio is {growth:.2f}x"
        )
        assert dt_1m < 6.0, f"1MB parsing exceeded time threshold: {dt_1m:.2f}s"

    def test_raw_tokenization_throughput(self) -> None:
        """Verify that KDLLexer.tokenize_raw() operates at high throughput (> 0.5 MB/s on dense tokens)."""
        doc = _generate_synthetic_kdl(200_000)
        doc_bytes = len(doc.encode("utf-8"))

        t0 = time.perf_counter()
        raw_tokens = KDLLexer(doc).tokenize_raw()
        dt = time.perf_counter() - t0

        assert len(raw_tokens) > 0
        throughput = (doc_bytes / (1024 * 1024)) / dt

        # High token-density document (avg 5 chars per token) in pure Python
        assert throughput > 0.5, (
            f"Raw tokenization throughput {throughput:.2f} MB/s is below expected 0.5 MB/s"
        )

    def test_large_document_ast_topology_and_query_integrity(self) -> None:
        """Verify that documents parsed under stress maintain exact AST topology and selectors."""
        doc_str = _generate_synthetic_kdl(50_000)
        parsed = kdlquery.parse(doc_str)

        # Check document span
        assert parsed.span.start.offset == 0
        assert parsed.span.end.offset == len(doc_str)

        # Check nodes topology
        assert len(parsed.nodes) > 0
        first_node = parsed.nodes[0]
        assert first_node.name == "node"
        assert first_node.type_annotation == "(service)"
        assert first_node.properties["enabled"].value is True
        assert first_node.properties["priority"].value == 10
        assert first_node.properties["timeout"].value == 45.5

        # Check parent and document references
        assert first_node.document is parsed
        assert len(first_node.children) == 4

        tasks_node = next(c for c in first_node.children if c.name == "tasks")
        assert tasks_node.parent is first_node
        assert tasks_node.document is parsed

        handler_node = next(c for c in tasks_node.children if c.name == "handler")
        assert handler_node.parent is tasks_node
        assert handler_node.document is parsed
        assert handler_node.type_annotation is None
        assert handler_node.args[0].value == "job-runner"
        assert handler_node.args[0].type_annotation == "(task_handler)"
        assert handler_node.properties["async"].value is True

        # Check CSS3 selector engine navigation on large parsed AST
        matched_handlers = parsed.select("tasks > handler")
        assert len(matched_handlers) == len(parsed.nodes)
        for h in matched_handlers:
            assert h.name == "handler"
            assert h.args[0].value == "job-runner"
            assert h.args[0].type_annotation == "(task_handler)"

    def test_cst_builder_scaling_comparison(self) -> None:
        """Verify that KDL2CSTParser also parses without quadratic degradation."""
        doc = _generate_synthetic_kdl(100_000)
        doc_bytes = len(doc.encode("utf-8"))

        t0 = time.perf_counter()
        cst_doc = KDL2CSTParser().parse(doc)
        dt = time.perf_counter() - t0

        assert len(cst_doc.nodes) > 0
        # CST parser preserves lossless tokens and entries; should complete well within 2.5s
        assert dt < 2.5, f"CST parsing too slow: {dt:.2f}s for {doc_bytes}B"
