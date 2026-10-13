"""Shared test helpers: run a Robot suite and load generated Allure results."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


def run_robot(
    suite_text: str,
    work_dir: Path,
    *,
    output: str = "output.xml",
    env: dict[str, str] | None = None,
    args: list[str] | None = None,
) -> Path:
    """Write ``suite_text`` to a .robot file, run it, and return the output.xml path.

    ``args`` are extra Robot options (e.g. ``--listener``). Robot runs with
    ``work_dir`` as the working directory, so relative listener paths land there.
    """
    suite = work_dir / "suite.robot"
    suite.write_text(suite_text)
    run_env = None
    if env is not None:
        import os

        run_env = {**os.environ, **env}
    # Robot exits non-zero on test failure; that is expected in several fixtures.
    cmd = [
        sys.executable,
        "-m",
        "robot",
        "--output",
        output,
        "--outputdir",
        str(work_dir),
        *(args or []),
        str(suite),
    ]
    subprocess.run(cmd, check=False, env=run_env, cwd=work_dir)
    return work_dir / output


def load_results(results_dir: Path) -> list[dict]:
    return [json.loads(f.read_text()) for f in sorted(results_dir.glob("*-result.json"))]


def load_containers(results_dir: Path) -> list[dict]:
    return [json.loads(f.read_text()) for f in sorted(results_dir.glob("*-container.json"))]


def step_names(steps: list[dict]) -> list[str]:
    return [s["name"] for s in steps]


def find_step(steps: list[dict], name: str) -> dict | None:
    """Depth-first search for the first step whose name startswith ``name``."""
    for step in steps:
        if step["name"].startswith(name):
            return step
        nested = find_step(step.get("steps", []), name)
        if nested is not None:
            return nested
    return None


@pytest.fixture
def robot(tmp_path):
    return lambda text, **kw: run_robot(text, tmp_path, **kw)
