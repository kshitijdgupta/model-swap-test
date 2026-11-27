"""Command line interface for the Model Swap Test."""

from __future__ import annotations

import argparse
import sys

from model_swap_test import __version__
from model_swap_test.checker import SpecError, check_path, format_report
from model_swap_test.reconcile import format_result, reconcile


def cli(argv: list[str] | None = None) -> None:
    """Entry point for the model-swap-test console script."""

    raise SystemExit(main(argv))


def main(argv: list[str] | None = None) -> int:
    """Run a subcommand and return a process exit code."""

    parser = _parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        return 0 if code is None else int(code)

    if args.command == "check":
        return _check(args.file)
    if args.command == "reconcile":
        return _reconcile(args.agent, args.certified, args.tolerance, relative=args.relative)
    parser.print_help(sys.stderr)
    return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="model-swap-test",
        description="Score metric definitions against the four Model Swap Test contracts.",
    )
    parser.add_argument("--version", action="version", version=f"model-swap-test {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser(
        "check",
        help="Score a YAML file of metric definitions.",
    )
    check.add_argument("file", help="Path to a metrics YAML file.")

    compare = subparsers.add_parser(
        "reconcile",
        help="Compare one agent answer to a certified value.",
    )
    compare.add_argument("agent", type=float, help="Value returned by the agent.")
    compare.add_argument("certified", type=float, help="Certified value.")
    compare.add_argument(
        "--tolerance",
        required=True,
        type=float,
        help="Allowed gap. Absolute by default, or a fraction with --relative.",
    )
    compare.add_argument(
        "--relative",
        action="store_true",
        help="Treat tolerance as a fraction of the certified value.",
    )
    return parser


def _check(path: str) -> int:
    try:
        report = check_path(path)
    except SpecError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    sys.stdout.write(format_report(report))
    return 0 if report.passed else 1


def _reconcile(agent: float, certified: float, tolerance: float, *, relative: bool) -> int:
    try:
        result = reconcile(agent, certified, tolerance, relative=relative)
    except (TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    sys.stdout.write(format_result(result))
    return 0 if result.passed else 1
