"""Reconciliation helper."""

import pytest

from model_swap_test.reconcile import format_number, reconcile


def test_absolute_tolerance_includes_the_limit():
    inside = reconcile(12, 10, 2)
    assert inside.passed
    assert inside.delta == 2
    assert inside.limit == 2
    assert inside.relative is False

    outside = reconcile(12.01, 10, 2)
    assert outside.passed is False
    assert outside.delta == pytest.approx(2.01)


def test_relative_tolerance_uses_the_certified_value():
    inside = reconcile(12, 8, 0.5, relative=True)
    assert inside.passed
    assert inside.limit == 4

    outside = reconcile(12.1, 8, 0.5, relative=True)
    assert outside.passed is False


def test_relative_tolerance_with_certified_zero_needs_an_exact_agent_value():
    assert reconcile(0, 0, 0.01, relative=True).passed
    assert reconcile(0.01, 0, 0.01, relative=True).passed is False


def test_negative_and_non_finite_inputs_are_rejected():
    with pytest.raises(ValueError, match="zero or greater"):
        reconcile(1, 1, -0.1)
    with pytest.raises(ValueError, match="finite"):
        reconcile(float("inf"), 1, 1)
    with pytest.raises(TypeError, match="number"):
        reconcile(True, 1, 1)


def test_format_number_trims_integers():
    assert format_number(1842000.0) == "1842000"
    assert format_number(0.0) == "0"
    assert format_number(1.25) == "1.25"
