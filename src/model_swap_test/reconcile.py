"""Compare an agent answer to a certified value."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReconcileResult:
    """Outcome of one reconciliation."""

    passed: bool
    agent_value: float
    certified_value: float
    tolerance: float
    relative: bool
    delta: float
    limit: float


def reconcile(
    agent_value: float,
    certified_value: float,
    tolerance: float,
    *,
    relative: bool = False,
) -> ReconcileResult:
    """Return whether agent_value is within tolerance of certified_value.

    Absolute tolerance is the default: the absolute gap must be less than or
    equal to tolerance. With relative=True, tolerance is a fraction of the
    certified value. A gap equal to the limit passes. Certified value 0 with
    a relative tolerance passes only when the agent value is also 0.
    """

    agent = _finite_number(agent_value, "agent value")
    certified = _finite_number(certified_value, "certified value")
    allowed = _finite_number(tolerance, "tolerance")
    if allowed < 0:
        raise ValueError("tolerance must be zero or greater")

    delta = abs(agent - certified)
    limit = abs(certified) * allowed if relative else allowed
    return ReconcileResult(
        passed=delta <= limit,
        agent_value=agent,
        certified_value=certified,
        tolerance=allowed,
        relative=relative,
        delta=delta,
        limit=limit,
    )


def format_result(result: ReconcileResult) -> str:
    """Render a reconciliation result as plain text."""

    mode = "relative" if result.relative else "absolute"
    status = "PASS" if result.passed else "FAIL"
    lines = [
        f"Reconciliation: {status}",
        f"Agent value: {format_number(result.agent_value)}",
        f"Certified value: {format_number(result.certified_value)}",
        f"Mode: {mode}",
        f"Tolerance: {format_number(result.tolerance)}",
        f"Delta: {format_number(result.delta)}",
        f"Limit: {format_number(result.limit)}",
        "",
    ]
    return "\n".join(lines)


def format_number(value: float) -> str:
    """Render a finite number without trailing zeros."""

    if value == 0:
        return "0"
    if math.isfinite(value) and value == math.trunc(value) and abs(value) < 1e15:
        return str(int(value))
    rendered = f"{value:.8f}".rstrip("0").rstrip(".")
    return rendered or "0"


def _finite_number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be a finite number")
    return number
