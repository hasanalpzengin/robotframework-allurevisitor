"""Allure 2 / Allure 3 report generators and normalised report-data readers.

Each generator knows how to resolve itself (an ``allure`` executable on PATH of
the right major version, else ``npx`` with a pinned package version), how to run
``generate`` with its own CLI syntax, and how to read its report's
machine-readable data into one shape so tests can assert identically on both.

Resolution failures make tests skip (or fail when ``ALLURE_REQUIRE_GENERATORS=1``,
as in CI); a resolved generator that then fails makes tests fail, so a broken
generator integration is never hidden.
"""

from __future__ import annotations

import functools
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

ALLURE2_VERSION = os.environ.get("ALLURE2_VERSION", "2.46.1")
ALLURE3_VERSION = os.environ.get("ALLURE3_VERSION", "3.20.1")
GENERATORS = ("allure2", "allure3")
STATUSES = ("passed", "failed", "broken", "skipped", "unknown")


def _major_version(cmd: list[str]) -> int | None:
    """Run ``<cmd> --version`` and return the major version, or None on failure."""
    try:
        completed = subprocess.run([*cmd, "--version"], capture_output=True, text=True, timeout=300)
    except (subprocess.TimeoutExpired, OSError):
        return None
    match = re.search(r"\b(\d+)\.\d+\.\d+\b", completed.stdout)
    if completed.returncode != 0 or match is None:
        return None
    return int(match.group(1))


@functools.cache
def resolve_command(name: str) -> tuple[str, ...] | None:
    """Return a command prefix running the given generator, or None if unavailable."""
    major = 2 if name == "allure2" else 3
    if shutil.which("allure") and _major_version(["allure"]) == major:
        return ("allure",)
    if not shutil.which("npx"):
        return None
    if major == 2:
        if not shutil.which("java"):
            return None
        cmd = ["npx", "--yes", f"allure-commandline@{ALLURE2_VERSION}"]
    else:
        cmd = ["npx", "--yes", f"allure@{ALLURE3_VERSION}"]
    return tuple(cmd) if _major_version(cmd) == major else None


@dataclass
class Report:
    """A generated report plus a reader for its generator's data layout."""

    generator: str
    path: Path

    # ------------------------------------------------------------- statistics
    def stats(self) -> dict[str, int]:
        if self.generator == "allure2":
            raw = _read_json(self.path / "widgets" / "summary.json")["statistic"]
        else:
            raw = _read_json(self.path / "summary.json")["stats"]
        stats = {status: int(raw.get(status, 0)) for status in STATUSES}
        stats["total"] = int(raw.get("total", sum(stats.values())))
        return stats

    # ------------------------------------------------------------- test cases
    def test_cases(self) -> list[dict]:
        """Headline test cases; earlier attempts are counted in each case's ``retries``."""
        folder = "test-cases" if self.generator == "allure2" else "test-results"
        files = sorted((self.path / "data" / folder).glob("*.json"))
        reader = _allure2_case if self.generator == "allure2" else _allure3_case
        # Allure 2 marks earlier attempts "retry"; Allure 3 marks them "isRetry" (its own
        # "retry" key is set on every attempt of a retried test).
        flag = "retry" if self.generator == "allure2" else "isRetry"
        raws = [_read_json(f) for f in files]
        return [reader(raw) for raw in raws if not raw.get(flag)]

    def test_case(self, name: str) -> dict:
        matches = [case for case in self.test_cases() if case["name"] == name]
        assert len(matches) == 1, f"expected one test case named {name!r}, got {len(matches)}"
        return matches[0]

    # ------------------------------------------------------------ environment
    def environment(self) -> dict[str, list[str]]:
        if self.generator == "allure2":
            items = _read_json(self.path / "widgets" / "environment.json")
            return {item["name"]: list(item["values"]) for item in items}
        items = _read_json(self.path / "widgets" / "allure_environment.json")
        return {item["name"]: list(item["values"]) for item in items}


def generate_report(generator: str, results_dir: Path, report_dir: Path) -> Report:
    """Generate a report with ``generator``; skip if unavailable, fail if it breaks."""
    cmd = resolve_command(generator)
    if cmd is None:
        message = f"{generator} report generator is not available"
        # CI sets this so an unavailable generator cannot turn into a silent skip.
        if os.environ.get("ALLURE_REQUIRE_GENERATORS") == "1":
            pytest.fail(message)
        pytest.skip(message)
    if generator == "allure2":
        args = [*cmd, "generate", "--clean", "-o", str(report_dir), str(results_dir)]
    else:
        args = [*cmd, "generate", str(results_dir), "-o", str(report_dir)]
    # Run from the report's parent so no unrelated allurerc/config is picked up.
    completed = subprocess.run(
        args, capture_output=True, text=True, timeout=600, cwd=report_dir.parent
    )
    if completed.returncode != 0 or not (report_dir / "index.html").is_file():
        pytest.fail(
            f"{generator} failed to generate a report (exit {completed.returncode}):\n"
            f"{completed.stdout[-2000:]}\n{completed.stderr[-2000:]}"
        )
    return Report(generator, report_dir)


# ----------------------------------------------------------------- readers
def _read_json(path: Path):  # noqa: ANN202
    return json.loads(path.read_text(encoding="utf-8"))


def _labels(raw: dict) -> list[tuple[str, str]]:
    return [(label["name"], label["value"]) for label in raw.get("labels", [])]


def _links(raw: dict) -> list[dict]:
    return [
        {"name": link.get("name"), "url": link.get("url"), "type": link.get("type")}
        for link in raw.get("links", [])
    ]


def _params(raw: dict) -> dict[str, str]:
    return {p["name"]: p["value"] for p in raw.get("parameters", [])}


def _allure2_node(raw: dict) -> dict:
    return {
        "name": raw.get("name"),
        "status": raw.get("status"),
        "parameters": _params(raw),
        "attachments": [
            {"name": a.get("name"), "type": a.get("type")} for a in raw.get("attachments", [])
        ],
        "steps": [_allure2_node(step) for step in raw.get("steps", [])],
    }


def _allure2_case(raw: dict) -> dict:
    stage = _allure2_node(raw.get("testStage") or {})
    return {
        "name": raw["name"],
        "status": raw["status"],
        "labels": _labels(raw),
        "links": _links(raw),
        "description": raw.get("description") or raw.get("descriptionHtml"),
        "setup": [_allure2_node(stage) for stage in raw.get("beforeStages", [])],
        "teardown": [_allure2_node(stage) for stage in raw.get("afterStages", [])],
        "steps": stage["steps"],
        "attachments": stage["attachments"],
        "retries": len((raw.get("extra") or {}).get("retries") or []),
    }


def _allure3_node(raw: dict) -> dict:
    children = raw.get("steps", [])
    return {
        "name": raw.get("name"),
        "status": raw.get("status"),
        "parameters": _params(raw),
        "attachments": [
            {"name": c["link"].get("name"), "type": c["link"].get("contentType")}
            for c in children
            if c.get("type") == "attachment"
        ],
        "steps": [_allure3_node(c) for c in children if c.get("type") != "attachment"],
    }


def _allure3_case(raw: dict) -> dict:
    body = _allure3_node(raw)
    return {
        "name": raw["name"],
        "status": raw["status"],
        "labels": _labels(raw),
        "links": _links(raw),
        "description": raw.get("description") or raw.get("descriptionHtml"),
        "setup": [_allure3_node(item) for item in raw.get("setup", [])],
        "teardown": [_allure3_node(item) for item in raw.get("teardown", [])],
        "steps": body["steps"],
        "attachments": body["attachments"],
        "retries": len(raw.get("retries") or []),
    }


def walk(nodes: list[dict]):  # noqa: ANN201
    """Yield every node in a normalised step tree, depth-first."""
    for node in nodes:
        yield node
        yield from walk(node["steps"])
