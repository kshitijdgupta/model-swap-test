"""Checker coverage for the four contracts."""

from pathlib import Path

import pytest

from model_swap_test.checker import SpecError, check_metrics, check_path, format_report

ROOT = Path(__file__).resolve().parents[1]


class Delete:
    """Sentinel: remove a key from the valid metric."""


DELETE = Delete()


def valid(**overrides):
    metric = {
        "name": "orders",
        "owner": "operations",
        "formula": "count(order_id)",
        "certified_source": "ops.mart.orders",
        "grain": "one row per order",
        "clock": "calendar",
        "freshness": {"as_of": "previous_calendar_day", "max_lag": "1d"},
        "access": {"inherit_from": "asking_user"},
        "reconciliation": {
            "question": "Orders yesterday",
            "certified_value": 10,
            "tolerance": 0,
        },
    }
    for key, value in overrides.items():
        if value is DELETE:
            metric.pop(key, None)
        else:
            metric[key] = value
    return metric


def codes(report, contract):
    return [finding.code for finding in report.findings if finding.contract == contract]


def test_valid_metric_passes_every_contract():
    report = check_metrics([valid()])
    assert report.passed
    assert report.contracts_passed == 4
    assert report.score == 1
    assert report.findings == ()


def test_name_must_be_text():
    report = check_metrics([valid(name=1)])
    assert codes(report, "meaning") == ["name_type"]
    assert report.findings[0].metric == "metric 1"


def test_missing_owner_fails_meaning_only():
    report = check_metrics([valid(owner=DELETE)])
    assert codes(report, "meaning") == ["missing_owner"]
    assert report.contracts_passed == 3
    assert report.score == 0.75
    assert "Overall score: 0.75" in format_report(report)
    assert "Meaning: FAIL (1 finding)" in format_report(report)


def test_blank_owner_is_missing():
    report = check_metrics([valid(owner="  ")])
    assert codes(report, "meaning") == ["missing_owner"]


def test_owner_must_be_text():
    report = check_metrics([valid(owner=12)])
    assert codes(report, "meaning") == ["owner_type"]


def test_missing_formula_and_certified_source():
    report = check_metrics([valid(formula=DELETE, certified_source=DELETE)])
    assert codes(report, "meaning") == ["missing_formula", "missing_certified_source"]


def test_missing_formula_alone():
    report = check_metrics([valid(formula="")])
    assert codes(report, "meaning") == ["missing_formula"]


def test_missing_certified_source_alone():
    report = check_metrics([valid(certified_source=None)])
    assert codes(report, "meaning") == ["missing_certified_source"]


def test_missing_grain_or_clock_and_freshness():
    report = check_metrics([valid(grain=DELETE, clock=DELETE, freshness=DELETE)])
    assert codes(report, "grain") == ["missing_grain", "missing_clock", "missing_freshness"]


def test_freshness_accepts_text_or_as_of_mapping():
    assert check_metrics([valid(freshness="previous business day")]).passed
    assert check_metrics([valid(freshness={"as_of": "load time"})]).passed
    mapping_gap = check_metrics([valid(freshness={"max_lag": "1d"})])
    assert codes(mapping_gap, "grain") == ["missing_freshness"]
    wrong_type = check_metrics([valid(freshness=1)])
    assert codes(wrong_type, "grain") == ["freshness_type"]


def test_shared_name_without_meaning_labels_is_ambiguous():
    report = check_metrics(
        [
            valid(name="revenue"),
            valid(name="Revenue", owner="sales-operations"),
        ]
    )
    assert codes(report, "meaning") == ["ambiguous_unlabeled", "ambiguous_unlabeled"]
    assert report.findings[0].message.startswith('ambiguous name "revenue"')
    assert 'ambiguous name "Revenue"' in report.findings[1].message


def test_shared_name_with_distinct_meanings_passes():
    report = check_metrics(
        [
            valid(name="revenue", meaning="finance"),
            valid(name="revenue", meaning="sales"),
        ]
    )
    assert report.passed
    assert [finding.metric for finding in report.findings] == []


def test_one_unlabeled_meaning_is_the_finding():
    report = check_metrics(
        [
            valid(name="revenue", meaning="finance"),
            valid(name="revenue"),
        ]
    )
    unlabeled = [finding for finding in report.findings if finding.code == "ambiguous_unlabeled"]
    assert len(unlabeled) == 1
    assert unlabeled[0].metric == "revenue"


def test_repeated_meaning_label_is_still_ambiguous():
    report = check_metrics(
        [
            valid(name="revenue", meaning="Finance"),
            valid(name="revenue", meaning="finance"),
        ]
    )
    assert codes(report, "meaning") == ["ambiguous_label", "ambiguous_label"]


def test_meaning_must_be_text_when_set():
    report = check_metrics([valid(meaning=1)])
    assert codes(report, "meaning") == ["meaning_type"]


def test_unique_name_does_not_need_a_meaning_label():
    report = check_metrics([valid(name="orders")])
    assert report.passed


def test_aliases_must_be_text_when_present():
    report = check_metrics([valid(aliases=["ok", 3])])
    assert codes(report, "meaning") == ["bad_aliases"]
    assert check_metrics([valid(aliases=["net_revenue"])]).passed
    assert check_metrics([valid()]).passed


def test_missing_access_policy():
    report = check_metrics([valid(access=DELETE)])
    assert codes(report, "access") == ["missing_access"]
    assert report.findings[0].message == "no access policy"


def test_blank_access_policy():
    assert codes(check_metrics([valid(access={})]), "access") == ["missing_access"]
    assert codes(check_metrics([valid(access={"inherit_from": "  "})]), "access") == ["missing_access"]
    assert codes(check_metrics([valid(access="")]), "access") == ["missing_access"]


def test_access_must_be_inherited_from_the_asking_user():
    report = check_metrics([valid(access={"inherit_from": "warehouse_admin"})])
    assert codes(report, "access") == ["access_not_inherited"]
    shorthand = check_metrics([valid(access="asking_user")])
    assert shorthand.passed
    spaced = check_metrics([valid(access={"inherit_from": " asking_user "})])
    assert spaced.passed


def test_missing_reconciliation_test():
    report = check_metrics([valid(reconciliation=DELETE)])
    assert codes(report, "reconciliation") == ["missing_reconciliation"]
    assert check_metrics([valid(reconciliation={})]).findings[0].code == "missing_reconciliation"
    assert check_metrics([valid(reconciliation=[])]).findings[0].code == "missing_reconciliation"


def test_incomplete_reconciliation_test():
    report = check_metrics([valid(reconciliation={"question": "Orders yesterday"})])
    assert codes(report, "reconciliation") == [
        "reconciliation_certified_value",
        "reconciliation_tolerance",
    ]


def test_negative_tolerance_fails_the_contract():
    report = check_metrics(
        [
            valid(
                reconciliation={
                    "question": "Orders yesterday",
                    "certified_value": 10,
                    "tolerance": -1,
                }
            )
        ]
    )
    assert codes(report, "reconciliation") == ["reconciliation_tolerance_negative"]


def test_reconciliation_list_names_the_broken_test():
    report = check_metrics(
        [
            valid(
                reconciliation=[
                    {"certified_value": 1, "tolerance": 0},
                    {"certified_value": "n/a", "tolerance": 0},
                ]
            )
        ]
    )
    assert codes(report, "reconciliation") == ["reconciliation_certified_value"]
    assert "reconciliation test 2" in report.findings[0].message


def test_non_numeric_reconciliation_values():
    report = check_metrics(
        [
            valid(
                reconciliation={
                    "certified_value": True,
                    "tolerance": "1",
                }
            )
        ]
    )
    assert codes(report, "reconciliation") == [
        "reconciliation_certified_value",
        "reconciliation_tolerance",
    ]


def test_empty_file_fails_every_contract():
    report = check_metrics([])
    assert report.score == 0
    assert report.contracts_passed == 0
    assert {finding.contract for finding in report.findings} == {
        "meaning",
        "grain",
        "access",
        "reconciliation",
    }


def test_metric_that_is_not_a_mapping_fails_every_contract():
    report = check_metrics(["revenue"])
    assert codes(report, "meaning") == ["not_a_mapping"]
    assert report.contracts_passed == 0


def test_metrics_argument_must_be_a_list():
    with pytest.raises(SpecError):
        check_metrics({"name": "orders"})


def test_top_level_list_is_accepted(tmp_path):
    path = tmp_path / "metrics.yaml"
    path.write_text("- name: orders\n", encoding="utf-8")
    report = check_path(path)
    assert "missing_owner" in codes(report, "meaning")


def test_invalid_yaml_and_shape(tmp_path):
    broken = tmp_path / "broken.yaml"
    broken.write_text("metrics: [\n", encoding="utf-8")
    with pytest.raises(SpecError, match="invalid YAML"):
        check_path(broken)

    wrong = tmp_path / "wrong.yaml"
    wrong.write_text("name: orders\n", encoding="utf-8")
    with pytest.raises(SpecError, match="metrics list"):
        check_path(wrong)

    missing = tmp_path / "missing.yaml"
    with pytest.raises(SpecError, match="file not found"):
        check_path(missing)


def test_example_files_and_sample_output(monkeypatch):
    monkeypatch.chdir(ROOT)
    good = check_path(Path("examples/good_metrics.yaml"))
    bad = check_path(Path("examples/bad_metrics.yaml"))
    assert good.passed
    assert good.metric_count == 3
    assert bad.passed is False
    assert bad.score == 0
    assert codes(bad, "meaning") == [
        "ambiguous_unlabeled",
        "ambiguous_unlabeled",
        "missing_owner",
        "missing_formula",
        "missing_certified_source",
    ]
    assert codes(bad, "grain") == ["missing_freshness", "missing_grain", "missing_clock"]
    assert codes(bad, "access") == ["missing_access", "access_not_inherited"]
    assert codes(bad, "reconciliation") == ["missing_reconciliation"]

    good_text = format_report(good)
    bad_text = format_report(bad)
    assert good_text == (ROOT / "examples" / "sample_output_good.txt").read_text(encoding="utf-8")
    assert bad_text == (ROOT / "examples" / "sample_output_bad.txt").read_text(encoding="utf-8")
    assert "File: examples/good_metrics.yaml" in good_text
    assert "File: examples/bad_metrics.yaml" in bad_text
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert good_text.strip() in readme
    assert bad_text.strip() in readme
