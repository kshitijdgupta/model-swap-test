"""CLI exit codes and module entry."""

import os
import subprocess
import sys
from pathlib import Path

from model_swap_test import __version__
from model_swap_test.cli import main

ROOT = Path(__file__).resolve().parents[1]
GOOD = str(ROOT / "examples" / "good_metrics.yaml")
BAD = str(ROOT / "examples" / "bad_metrics.yaml")


def test_check_exit_codes(capsys):
    assert main(["check", GOOD]) == 0
    good_out = capsys.readouterr().out
    assert good_out.startswith("Model Swap Test: PASS")

    assert main(["check", BAD]) == 1
    bad_out = capsys.readouterr().out
    assert "Model Swap Test: FAIL" in bad_out
    assert "Overall score: 0.00" in bad_out

    assert main(["check", str(ROOT / "examples" / "missing.yaml")]) == 2
    error = capsys.readouterr().err
    assert error.startswith("error:")


def test_reconcile_exit_codes(capsys):
    assert main(["reconcile", "12", "10", "--tolerance", "2"]) == 0
    passed = capsys.readouterr().out
    assert "Reconciliation: PASS" in passed
    assert "Mode: absolute" in passed

    assert main(["reconcile", "13", "10", "--tolerance", "2"]) == 1
    failed = capsys.readouterr().out
    assert "Reconciliation: FAIL" in failed

    assert main(["reconcile", "12", "8", "--tolerance", "0.5", "--relative"]) == 0
    relative = capsys.readouterr().out
    assert "Mode: relative" in relative

    assert main(["reconcile", "1", "1", "--tolerance", "-1"]) == 2
    assert "tolerance" in capsys.readouterr().err


def test_version_matches_pyproject():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert f'version = "{__version__}"' in text


def test_help_and_version(capsys):
    assert main(["--help"]) == 0
    assert "model-swap-test" in capsys.readouterr().out
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == "model-swap-test 0.1.0"
    assert main([]) == 2


def test_module_entrypoint():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    completed = subprocess.run(
        [sys.executable, "-m", "model_swap_test", "check", GOOD],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert completed.returncode == 0
    assert "Model Swap Test: PASS" in completed.stdout
