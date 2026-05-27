"""Example: Service config DSL validator using selectors.

Demonstrates how to build a simple validation/linting layer on top
of the selector API. Rules are defined as (selector, check, message)
tuples — the selector finds candidate nodes, and the check determines
whether they pass or fail.

Usage:
    uv run python examples/config_dsl.py
"""

from __future__ import annotations

from dataclasses import dataclass

from kdlquery import parse

# -- Sample configs -----------------------------------------------------------

VALID_CONFIG = """\
service "api" {
    server "main" port=8080 tls=#true {
        host "localhost"
    }
    server "backup" port=8081 {
        host "backup.local"
    }
    route "/health" handler="health.check"
    route "/api/users" handler="users.list" auth=#true
}
"""

INVALID_CONFIG = """\
service "api" {
    server "main" {
        host "localhost"
    }
    route "/api/users"
}
"""

# -- Rule engine --------------------------------------------------------------


@dataclass
class Violation:
    rule: str
    message: str
    node_name: str
    line: int = 0
    column: int = 0
    severity: str = "error"


def validate(source: str) -> list[Violation]:
    doc = parse(source)
    violations: list[Violation] = []

    # Rule 1: every service must have at least one child server
    for node in doc.select("service:not(:has(> server))"):
        violations.append(
            Violation(
                "required-child",
                "service must contain a server",
                node.name,
                line=node.span.start.line,
                column=node.span.start.column,
            )
        )

    # Rule 2: every server must have a port property
    for node in doc.select("server:not([port])"):
        violations.append(
            Violation(
                "required-prop",
                f"server {node.get_arg(0)!r} is missing 'port' property",
                node.name,
                line=node.span.start.line,
                column=node.span.start.column,
            )
        )

    # Rule 3: every route must have a handler property
    for node in doc.select("route:not([handler])"):
        violations.append(
            Violation(
                "required-prop",
                f"route {node.get_arg(0)!r} is missing 'handler' property",
                node.name,
                line=node.span.start.line,
                column=node.span.start.column,
            )
        )

    # Rule 4 (warning): recommend a health-check route
    if not doc.select_one('route[0~="health"]'):
        violations.append(
            Violation(
                "recommended",
                "no health-check route found",
                "",
                severity="warning",
            )
        )

    return violations


def print_report(config_name: str, source: str) -> None:
    print(f"=== {config_name} ===")
    violations = validate(source)
    if not violations:
        print("  All checks passed.\n")
        return
    for v in violations:
        tag = "WARN" if v.severity == "warning" else "ERR "
        loc = f"line {v.line}" if v.line else ""
        print(f"  [{tag}] {loc:>8}  {v.rule}: {v.message}")
    print()


def main() -> None:
    print_report("Valid config", VALID_CONFIG)
    print_report("Invalid config", INVALID_CONFIG)


if __name__ == "__main__":
    main()
