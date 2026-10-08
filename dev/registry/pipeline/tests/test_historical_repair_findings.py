"""A reviewed stale-target repair cannot absorb extra or substituted defects."""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ..historical_static_repair import _REVIEWED_TARGETS, _validate_repair_findings, validated_historical_repair_source

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_M720_TARGET = (
    "720",
    "2013-y-siguientes",
    "aeat-dr-720",
    2024,
    "0A",
    "83c26f2c7c2848ec9544889d070b071d69d24608f48bd52782a6d608039d23b9",
)
_M720_PRODUCER_TARGET = (
    *_M720_TARGET[:-1],
    "1217b488e839465f1499fba090eeab3faa1e39e83068d7447de68467427f398d",
)


def test_m720_exact_findings_cover_both_retired_constant_pairs_and_owned_companions() -> None:
    target = _REVIEWED_TARGETS[_M720_TARGET]
    assert target.exact_findings is not None
    findings = tuple(sorted(target.exact_findings))
    assert len(findings) == 6
    assert sum("references unknown binding" in finding for finding in findings) == 4
    assert sum("form layout is stale" in finding for finding in findings) == 1
    assert sum("2 design record(s)" in finding for finding in findings) == 1
    _validate_repair_findings(target, findings)


def test_m720_producer_findings_cover_only_the_five_duplicate_inputs_and_form() -> None:
    target = _REVIEWED_TARGETS[_M720_PRODUCER_TARGET]
    assert target.exact_findings is not None
    findings = tuple(sorted(target.exact_findings))
    assert len(findings) == 9
    assert sum("references unknown binding" in finding for finding in findings) == 5
    assert sum("form layout is stale" in finding for finding in findings) == 1
    assert sum("shows binding" in finding for finding in findings) == 3
    assert all("design record(s)" not in finding for finding in findings)
    _validate_repair_findings(target, findings)


@pytest.mark.parametrize("target_key", [_M720_TARGET, _M720_PRODUCER_TARGET])
@pytest.mark.parametrize("change", ["missing", "extra", "duplicate", "wrong_record", "another_modelo"])
def test_m720_findings_refuse_every_unreviewed_change(
    change: str, target_key: tuple[str, str, str, int, str, str]
) -> None:
    target = _REVIEWED_TARGETS[target_key]
    assert target.exact_findings is not None
    findings = list(sorted(target.exact_findings))
    if change == "missing":
        findings.pop()
    elif change == "extra":
        findings.append("modelo 303 revision 2022: another failure")
    elif change == "duplicate":
        findings[-1] = findings[0]
    elif change == "wrong_record":
        index = next(index for index, finding in enumerate(findings) if "references unknown binding" in finding)
        findings[index] = findings[index].replace("type_1", "type_3")
    else:
        findings[0] = findings[0].replace("modelo 720", "modelo 714")
    with pytest.raises(RegistryValidationError, match="beyond the reviewed target defects"):
        _validate_repair_findings(target, tuple(findings))


@pytest.mark.parametrize("digest", [None, "0" * 64])
def test_m720_repair_refuses_unreviewed_manifest_before_source_access(digest: str | None) -> None:
    with pytest.raises(RegistryValidationError, match="exact reviewed"):
        validated_historical_repair_source(
            modelo="720",
            revision="2013-y-siguientes",
            source_ref="aeat-dr-720",
            filing_year=2024,
            period="0A",
            expected_manifest_sha256=digest,
        )
