"""Command line entry point for the Allure result visitor."""

from __future__ import annotations

import argparse
import glob
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from robotframework_allurevisitor.visitor import generate


def _expand(sources: list[str]) -> list[str]:
    """Expand glob patterns, keeping literal paths that match nothing."""
    expanded: list[str] = []
    for source in sources:
        matches = glob.glob(source)
        expanded.extend(matches or [source])
    return expanded


def _environment_entry(text: str) -> tuple[str, str]:
    key, separator, value = text.partition("=")
    if not separator or not key:
        raise argparse.ArgumentTypeError(f"expected KEY=VALUE, got {text!r}")
    return key, value


def _executor(text: str) -> dict:
    """Parse ``--executor`` as inline JSON or as a path to a JSON file."""
    try:
        raw = text if text.lstrip().startswith("{") else Path(text).read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, ValueError) as error:
        raise argparse.ArgumentTypeError(f"invalid executor JSON ({error})") from error
    if not isinstance(data, dict):
        raise argparse.ArgumentTypeError("executor JSON must be an object")
    return data


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="rf-allure",
        description="Generate Allure input files from Robot Framework output.xml file(s).",
    )
    parser.add_argument("sources", nargs="+", help="output.xml file(s) or glob(s)")
    parser.add_argument(
        "-o",
        "--output",
        default="allure-results",
        help="Directory to write Allure result files into (default: allure-results).",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove existing files in the output directory before writing.",
    )
    parser.add_argument(
        "--thread",
        default=None,
        help="Thread label for the results (e.g. a pabot worker id).",
    )
    parser.add_argument("--issue-pattern", default=None, help="Pattern for issue links.")
    parser.add_argument("--link-pattern", default=None, help="Pattern for generic links.")
    parser.add_argument(
        "--merge",
        action="store_true",
        help=(
            "Merge the sources like `rebot --merge` (last wins) into one result per test. "
            "Without it, tests repeated across sources become Allure retries."
        ),
    )
    parser.add_argument(
        "--broken-heuristic",
        action="store_true",
        help="Report library/syntax/import/timeout failures as broken instead of failed.",
    )
    parser.add_argument(
        "--environment",
        action="append",
        type=_environment_entry,
        default=[],
        metavar="KEY=VALUE",
        help="Environment entry for the report (repeatable); written to environment.properties.",
    )
    parser.add_argument(
        "--executor",
        type=_executor,
        default=None,
        help="Executor info as inline JSON or a JSON file path; written to executor.json.",
    )
    args = parser.parse_args(argv)

    generate(
        _expand(args.sources),
        args.output,
        clean=args.clean,
        thread=args.thread,
        issue_pattern=args.issue_pattern,
        link_pattern=args.link_pattern,
        broken_heuristic=args.broken_heuristic,
        environment=dict(args.environment),
        executor=args.executor,
        merge=args.merge,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
