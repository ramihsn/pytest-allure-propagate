from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List


def _collect_step(step: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": step.get("name"),
        "status": step.get("status"),
        "steps": [_collect_step(s) for s in step.get("steps", [])],
    }


def parse_allure_results(alluredir: str) -> Dict[str, Any]:
    directory = Path(alluredir)
    tests: List[Dict[str, Any]] = []
    for path in sorted(directory.glob("*-result.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        tests.append(
            {
                "name": data.get("name"),
                "status": data.get("status"),
                "statusDetails": data.get("statusDetails", {}),
                "steps": [_collect_step(s) for s in data.get("steps", [])],
            }
        )
    return {"tests": tests}


def run_pytest_and_collect(code: str) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        tests_dir = td_path / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        test_file = tests_dir / "test_generated.py"
        test_file.write_text(code, encoding="utf-8")

        allure_out = td_path / "allure"
        allure_out.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        # Ensure our plugin/package is importable and auto-loaded
        project_root = str(Path(__file__).resolve().parents[1])
        env["PYTHONPATH"] = os.pathsep.join([project_root, env.get("PYTHONPATH", "")])
        env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "0"

        cmd = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "allure_pytest",
            "-p",
            "allure_pytest_ext.plugin",
            f"--alluredir={str(allure_out)}",
            str(tests_dir),
        ]
        proc = subprocess.run(cmd, cwd=str(td_path), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        results = parse_allure_results(str(allure_out))
        return {
            "exit_code": proc.returncode,
            "stdout": proc.stdout.decode("utf-8", errors="replace"),
            "stderr": proc.stderr.decode("utf-8", errors="replace"),
            "results": results,
        }
