"""Score metric definitions against the four Model Swap Test contracts."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import yaml

CONTRACTS: tuple[str, ...] = ("meaning", "grain", "access", "reconciliation")

CONTRACT_TITLES: dict[str, str] = {
    "meaning": "Meaning",
    "grain": "Grain and freshness",
    "access": "Access",
    "reconciliation": "Reconciliation",
}

_CHECK_ORDER: dict[str, dict[str, int]] = {
    "meaning": {
        "no_metrics": 0,
        "not_a_mapping": 1,
        "missing_name": 2,
        "name_type": 2,
        "meaning_type": 3,
        "ambiguous_unlabeled": 3,
        "ambiguous_label": 4,
        "missing_owner": 5,
        "owner_type": 6,
        "missing_formula": 7,
        "formula_type": 8,
        "missing_certified_source": 9,
        "certified_source_type": 10,
        "bad_aliases": 11,
    },
    "grain": {
        "no_metrics": 0,
        "not_a_mapping": 1,
        "missing_grain": 2,
        "grain_type": 3,
        "missing_clock": 4,
        "clock_type": 5,
        "missing_freshness": 6,
        "freshness_type": 7,
    },
    "access": {
        "no_metrics": 0,
        "not_a_mapping": 1,
        "missing_access": 2,
        "access_not_inherited": 3,
    },
    "reconciliation": {
        "no_metrics": 0,
        "not_a_mapping": 1,
        "missing_reconciliation": 2,
        "reconciliation_shape": 3,
        "reconciliation_certified_value": 4,
        "reconciliation_tolerance": 5,
        "reconciliation_tolerance_negative": 6,
    },
}

_ASKING_USER = "asking_user"


class SpecError(Exception):
    """The file is not a usable metric spec."""


@dataclass(frozen=True, slots=True)
class Finding:
    """One gap in a metric definition."""

    contract: str
    code: str
    metric: str
    message: str
    metric_index: int


@dataclass(frozen=True, slots=True)
class Report:
    """Pass or fail result for one metric file."""

    source: str
    metric_count: int
    findings: tuple[Finding, ...]

    @property
    def passed(self) -> bool:
        return self.contracts_passed == len(CONTRACTS)

    @property
    def contracts_passed(self) -> int:
        failed = {finding.contract for finding in self.findings}
        return sum(1 for contract in CONTRACTS if contract not in failed)

    @property
    def score(self) -> float:
        """Share of the four contracts that passed. Range is 0 to 1."""

        return self.contracts_passed / len(CONTRACTS)


def check_path(path: str | Path) -> Report:
    """Load a YAML spec from disk and score it."""

    spec_path = Path(path)
    display = spec_path.as_posix()
    if not spec_path.is_file():
        raise SpecError(f"{display}: file not found")
    try:
        text = spec_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SpecError(f"{display}: {exc.strerror or exc}") from exc
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        detail = str(exc).strip().splitlines()
        reason = detail[0] if detail else exc.__class__.__name__
        raise SpecError(f"{display}: invalid YAML ({reason})") from exc
    metrics = coerce_metrics(data, display)
    return check_metrics(metrics, source=display)


def check_metrics(metrics: list, *, source: str = "(input)") -> Report:
    """Score an in-memory list of metric mappings."""

    if not isinstance(metrics, list):
        raise SpecError("metrics must be a list")

    labels = _metric_labels(metrics)
    findings: list[Finding] = []
    if not metrics:
        for contract in CONTRACTS:
            findings.append(
                Finding(
                    contract=contract,
                    code="no_metrics",
                    metric="-",
                    message="no metrics to check",
                    metric_index=0,
                )
            )
        return _report(source, 0, findings)

    named: list[tuple[int, dict, str]] = []
    for index, raw in enumerate(metrics):
        label = labels[index]
        if not isinstance(raw, dict):
            for contract in CONTRACTS:
                findings.append(
                    Finding(
                        contract=contract,
                        code="not_a_mapping",
                        metric=label,
                        message="metric is not a mapping",
                        metric_index=index,
                    )
                )
            continue
        findings.extend(_check_meaning_fields(raw, label, index))
        findings.extend(_check_grain(raw, label, index))
        findings.extend(_check_access(raw, label, index))
        findings.extend(_check_reconciliation(raw, label, index))
        named.append((index, raw, label))

    findings.extend(_check_ambiguity(named))
    return _report(source, len(metrics), findings)


def coerce_metrics(data: object, source: str) -> list:
    """Accept a metrics list, or a mapping that holds one."""

    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "metrics" in data:
        metrics = data["metrics"]
        if not isinstance(metrics, list):
            raise SpecError(f"{source}: metrics must be a list")
        return metrics
    raise SpecError(f"{source}: expected a mapping with a metrics list")


def format_report(report: Report) -> str:
    """Render a contract report as plain text."""

    status = "PASS" if report.passed else "FAIL"
    header = [
        f"Model Swap Test: {status}",
        f"File: {report.source}",
        f"Metrics checked: {report.metric_count}",
    ]
    blocks: list[str] = []
    for contract in CONTRACTS:
        title = CONTRACT_TITLES[contract]
        group = [finding for finding in report.findings if finding.contract == contract]
        if not group:
            blocks.append(f"{title}: PASS")
            continue
        noun = "finding" if len(group) == 1 else "findings"
        block = [f"{title}: FAIL ({len(group)} {noun})"]
        block.extend(f"- {finding.metric}: {finding.message}" for finding in group)
        blocks.append("\n".join(block))
    summary = [
        f"Contracts passed: {report.contracts_passed}/{len(CONTRACTS)}",
        f"Overall score: {report.score:.2f}",
    ]
    return "\n\n".join(["\n".join(header), *blocks, "\n".join(summary)]) + "\n"


def _report(source: str, metric_count: int, findings: list[Finding]) -> Report:
    ordered = tuple(
        sorted(
            findings,
            key=lambda finding: (
                finding.metric_index,
                CONTRACTS.index(finding.contract),
                _CHECK_ORDER[finding.contract].get(finding.code, 99),
            ),
        )
    )
    return Report(source=source, metric_count=metric_count, findings=ordered)


def _metric_labels(metrics: list) -> list[str]:
    bases: list[str] = []
    for index, raw in enumerate(metrics, start=1):
        if not isinstance(raw, dict):
            bases.append(f"metric {index}")
            continue
        name = _text(raw.get("name")) if "name" in raw else None
        meaning = _text(raw.get("meaning")) if "meaning" in raw else None
        if not name:
            bases.append(f"metric {index}")
        elif meaning:
            bases.append(f"{name} ({meaning})")
        else:
            bases.append(name)

    counts: dict[str, int] = {}
    for base in bases:
        counts[base] = counts.get(base, 0) + 1
    seen: dict[str, int] = {}
    labels: list[str] = []
    for base in bases:
        if counts[base] > 1:
            seen[base] = seen.get(base, 0) + 1
            labels.append(f"{base} #{seen[base]}")
        else:
            labels.append(base)
    return labels


def _check_meaning_fields(metric: dict, label: str, index: int) -> list[Finding]:
    findings: list[Finding] = []
    findings.extend(
        _require_text(
            metric,
            "name",
            contract="meaning",
            label=label,
            index=index,
            missing_code="missing_name",
            missing_message="missing name",
            type_code="name_type",
            type_message="name must be text",
        )
    )
    findings.extend(
        _require_text(
            metric,
            "owner",
            contract="meaning",
            label=label,
            index=index,
            missing_code="missing_owner",
            missing_message="missing owner",
            type_code="owner_type",
            type_message="owner must be text",
        )
    )
    findings.extend(
        _require_text(
            metric,
            "formula",
            contract="meaning",
            label=label,
            index=index,
            missing_code="missing_formula",
            missing_message="missing formula",
            type_code="formula_type",
            type_message="formula must be text",
        )
    )
    findings.extend(
        _require_text(
            metric,
            "certified_source",
            contract="meaning",
            label=label,
            index=index,
            missing_code="missing_certified_source",
            missing_message="missing certified source",
            type_code="certified_source_type",
            type_message="certified source must be text",
        )
    )
    if "meaning" in metric and metric["meaning"] is not None and not isinstance(metric["meaning"], str):
        findings.append(
            Finding(
                contract="meaning",
                code="meaning_type",
                metric=label,
                message="meaning must be text",
                metric_index=index,
            )
        )
    if "aliases" in metric and metric["aliases"] is not None:
        aliases = metric["aliases"]
        if not isinstance(aliases, list) or not all(isinstance(item, str) and item.strip() for item in aliases):
            findings.append(
                Finding(
                    contract="meaning",
                    code="bad_aliases",
                    metric=label,
                    message="aliases must be a list of text",
                    metric_index=index,
                )
            )
    return findings


def _check_ambiguity(named: list[tuple[int, dict, str]]) -> list[Finding]:
    groups: dict[str, list[tuple[int, dict, str]]] = {}
    for index, metric, label in named:
        name = _text(metric.get("name")) if "name" in metric else None
        if not name:
            continue
        groups.setdefault(name.casefold(), []).append((index, metric, label))

    findings: list[Finding] = []
    for members in groups.values():
        if len(members) < 2:
            continue
        by_meaning: dict[str, list[tuple[int, dict, str, str]]] = {}
        for index, metric, label in members:
            meaning = _text(metric.get("meaning")) if "meaning" in metric else None
            display_name = _text(metric.get("name")) or label
            if meaning is None:
                findings.append(
                    Finding(
                        contract="meaning",
                        code="ambiguous_unlabeled",
                        metric=label,
                        message=(
                            f'ambiguous name "{display_name}" has a second meaning '
                            "that is not labeled"
                        ),
                        metric_index=index,
                    )
                )
                continue
            by_meaning.setdefault(meaning.casefold(), []).append((index, metric, label, meaning))
        for group in by_meaning.values():
            if len(group) < 2:
                continue
            for index, _metric, label, meaning in group:
                findings.append(
                    Finding(
                        contract="meaning",
                        code="ambiguous_label",
                        metric=label,
                        message=(
                            f'ambiguous name shares the meaning label "{meaning}"'
                        ),
                        metric_index=index,
                    )
                )
    return findings


def _check_grain(metric: dict, label: str, index: int) -> list[Finding]:
    findings: list[Finding] = []
    findings.extend(
        _require_text(
            metric,
            "grain",
            contract="grain",
            label=label,
            index=index,
            missing_code="missing_grain",
            missing_message="missing grain",
            type_code="grain_type",
            type_message="grain must be text",
        )
    )
    findings.extend(
        _require_text(
            metric,
            "clock",
            contract="grain",
            label=label,
            index=index,
            missing_code="missing_clock",
            missing_message="missing clock",
            type_code="clock_type",
            type_message="clock must be text",
        )
    )
    findings.extend(_freshness_findings(metric, label, index))
    return findings


def _freshness_findings(metric: dict, label: str, index: int) -> list[Finding]:
    if "freshness" not in metric or metric["freshness"] is None:
        return [_freshness_missing(label, index)]
    freshness = metric["freshness"]
    if isinstance(freshness, str):
        if freshness.strip():
            return []
        return [_freshness_missing(label, index)]
    if isinstance(freshness, dict):
        as_of = freshness.get("as_of")
        if isinstance(as_of, str) and as_of.strip():
            return []
        return [_freshness_missing(label, index)]
    return [
        Finding(
            contract="grain",
            code="freshness_type",
            metric=label,
            message="freshness must be text or a mapping with as_of",
            metric_index=index,
        )
    ]


def _freshness_missing(label: str, index: int) -> Finding:
    return Finding(
        contract="grain",
        code="missing_freshness",
        metric=label,
        message="missing freshness",
        metric_index=index,
    )


def _check_access(metric: dict, label: str, index: int) -> list[Finding]:
    if "access" not in metric or metric["access"] is None:
        return [_access_finding("missing_access", "no access policy", label, index)]
    access = metric["access"]
    if isinstance(access, str):
        if access.strip() == _ASKING_USER:
            return []
        if not access.strip():
            return [_access_finding("missing_access", "no access policy", label, index)]
        return [
            _access_finding(
                "access_not_inherited",
                "access is not inherited from the asking user",
                label,
                index,
            )
        ]
    if isinstance(access, dict):
        if not access or "inherit_from" not in access or access.get("inherit_from") is None:
            return [_access_finding("missing_access", "no access policy", label, index)]
        inherit = access.get("inherit_from")
        if isinstance(inherit, str) and not inherit.strip():
            return [_access_finding("missing_access", "no access policy", label, index)]
        if isinstance(inherit, str) and inherit.strip() == _ASKING_USER:
            return []
        return [
            _access_finding(
                "access_not_inherited",
                "access is not inherited from the asking user",
                label,
                index,
            )
        ]
    return [
        _access_finding(
            "access_not_inherited",
            "access is not inherited from the asking user",
            label,
            index,
        )
    ]


def _access_finding(code: str, message: str, label: str, index: int) -> Finding:
    return Finding(
        contract="access",
        code=code,
        metric=label,
        message=message,
        metric_index=index,
    )


def _check_reconciliation(metric: dict, label: str, index: int) -> list[Finding]:
    if "reconciliation" not in metric or metric["reconciliation"] in (None, {}, []):
        return [
            Finding(
                contract="reconciliation",
                code="missing_reconciliation",
                metric=label,
                message="no reconciliation test",
                metric_index=index,
            )
        ]
    reconciliation = metric["reconciliation"]
    tests = reconciliation if isinstance(reconciliation, list) else [reconciliation]
    findings: list[Finding] = []
    for test_index, test in enumerate(tests, start=1):
        prefix = f"reconciliation test {test_index}" if isinstance(reconciliation, list) else "reconciliation test"
        if not isinstance(test, dict):
            findings.append(
                Finding(
                    contract="reconciliation",
                    code="reconciliation_shape",
                    metric=label,
                    message=f"{prefix} must be a mapping",
                    metric_index=index,
                )
            )
            continue
        findings.extend(_reconciliation_test_findings(test, prefix, label, index))
    return findings


def _reconciliation_test_findings(test: dict, prefix: str, label: str, index: int) -> list[Finding]:
    findings: list[Finding] = []
    if "certified_value" not in test or test["certified_value"] is None:
        findings.append(
            Finding(
                contract="reconciliation",
                code="reconciliation_certified_value",
                metric=label,
                message=f"{prefix} is missing a certified value",
                metric_index=index,
            )
        )
    elif not _is_finite_number(test["certified_value"]):
        findings.append(
            Finding(
                contract="reconciliation",
                code="reconciliation_certified_value",
                metric=label,
                message=f"{prefix} certified value must be a finite number",
                metric_index=index,
            )
        )

    if "tolerance" not in test or test["tolerance"] is None:
        findings.append(
            Finding(
                contract="reconciliation",
                code="reconciliation_tolerance",
                metric=label,
                message=f"{prefix} is missing a tolerance",
                metric_index=index,
            )
        )
    elif not _is_finite_number(test["tolerance"]):
        findings.append(
            Finding(
                contract="reconciliation",
                code="reconciliation_tolerance",
                metric=label,
                message=f"{prefix} tolerance must be a finite number",
                metric_index=index,
            )
        )
    elif float(test["tolerance"]) < 0:
        findings.append(
            Finding(
                contract="reconciliation",
                code="reconciliation_tolerance_negative",
                metric=label,
                message=f"{prefix} tolerance must be zero or greater",
                metric_index=index,
            )
        )
    return findings


def _require_text(
    metric: dict,
    key: str,
    *,
    contract: str,
    label: str,
    index: int,
    missing_code: str,
    missing_message: str,
    type_code: str,
    type_message: str,
) -> list[Finding]:
    if key not in metric or metric[key] is None:
        return [_finding(contract, missing_code, label, missing_message, index)]
    value = metric[key]
    if isinstance(value, str):
        if value.strip():
            return []
        return [_finding(contract, missing_code, label, missing_message, index)]
    return [_finding(contract, type_code, label, type_message, index)]


def _finding(contract: str, code: str, label: str, message: str, index: int) -> Finding:
    return Finding(
        contract=contract,
        code=code,
        metric=label,
        message=message,
        metric_index=index,
    )


def _text(value: object) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _is_finite_number(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(float(value))
