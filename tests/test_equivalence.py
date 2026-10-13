"""The listener and the converter produce equivalent results for the same run.

Both are driven by one mapping; this test guards that promise. The capability
suite is run once with the listener, and the run's output.xml is converted with
``generate()``. After normalising uuids (to stable keys), attachment sources (to
content hashes), and the per-process ``thread`` label, the result sets are equal.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys

from test_e2e_capabilities import CAPABILITY_SUITE, PNG

from robotframework_allurevisitor.visitor import generate


def _load(results_dir, pattern):
    return [json.loads(f.read_text()) for f in sorted(results_dir.glob(pattern))]


def _normalise(results_dir):
    """Results and containers with uuids replaced by stable keys, sorted."""
    results = _load(results_dir, "*-result.json")
    containers = _load(results_dir, "*-container.json")
    keys = {r["uuid"]: f"result:{r['fullName']}" for r in results}

    # Containers may reference containers: resolve until every child has a key.
    unresolved = list(containers)
    while unresolved:
        progress = False
        for container in list(unresolved):
            if all(child in keys for child in container.get("children", [])):
                children = sorted(keys[child] for child in container.get("children", []))
                keys[container["uuid"]] = f"container:{container['name']}:{children}"
                unresolved.remove(container)
                progress = True
        assert progress, "container children reference unknown uuids"

    def clean(node):
        if isinstance(node, list):
            return [clean(item) for item in node]
        if not isinstance(node, dict):
            return node
        node = dict(node)
        node.pop("uuid", None)
        if "children" in node:
            node["children"] = sorted(keys[child] for child in node["children"])
        if "labels" in node:
            node["labels"] = sorted(
                (label["name"], label["value"])
                for label in node["labels"]
                if label["name"] != "thread"
            )
        if "source" in node and "type" in node:  # attachment -> content hash
            content = (results_dir / node["source"]).read_bytes()
            node["source"] = hashlib.sha256(content).hexdigest()
        return {key: clean(value) for key, value in node.items()}

    def canonical(items):
        return sorted(json.dumps(clean(item), sort_keys=True) for item in items)

    return canonical(results), canonical(containers)


def test_listener_and_converter_agree(tmp_path):
    (tmp_path / "suite.robot").write_text(CAPABILITY_SUITE)
    (tmp_path / "shot.png").write_bytes(PNG)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "robot",
            "--outputdir",
            str(tmp_path),
            "--listener",
            f"robotframework_allurevisitor.Listener:{tmp_path / 'live'}",
            str(tmp_path / "suite.robot"),
        ],
        cwd=tmp_path,
        capture_output=True,
        check=False,
    )
    generate(tmp_path / "output.xml", tmp_path / "converted", clean=True)

    live_results, live_containers = _normalise(tmp_path / "live")
    converted_results, converted_containers = _normalise(tmp_path / "converted")

    assert len(live_results) == 1 and len(live_containers) == 2
    assert live_results == converted_results
    assert live_containers == converted_containers
