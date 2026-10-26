"""Finite export selectors must describe the receipt's canonical work identity."""

from __future__ import annotations

import pytest

from cadrumo.application.modelo.export_projection import ModeloPriorDomiciliationPublicProvenance
from cadrumo.application.operations.public_period import PublicPeriod
from cadrumo.core.prior_domiciliation_election import PriorDomiciliationElection
from cadrumo.domain.modelos.work_unit import derive_work_unit_id

from ..export_evidence import _modelo_export_selector_matches, _ModeloExportEvidence

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_PROFILE = "99999999-9999-4999-8999-999999999999"
_REGISTRY_REVISION = "2026"
_PERIOD = PublicPeriod(filing_year=2026, code="1T")
_CALCULATION_REVISION = "b" * 64
_WORK_UNIT = derive_work_unit_id(
    bucket_id=_PROFILE, modelo="303", filing_year=2026, period=_PERIOD.to_period(), revision_id=_REGISTRY_REVISION
)
_COORDINATES = ("aeat", "app", "modelo", "export", "--modelo", "303", "--year", "2026", "--period", "1T")
_EXACT = ("aeat", "--format", "json", "app", "modelo", "export", _WORK_UNIT, "--revision", _CALCULATION_REVISION)


def _evidence(**changes: object) -> _ModeloExportEvidence:
    receipt = _ModeloExportEvidence(
        operation="modelo.export",
        bucket_id=_PROFILE,
        work_unit_id=_WORK_UNIT,
        calculation_revision_id=_CALCULATION_REVISION,
        modelo="303",
        filing_year=2026,
        period=_PERIOD,
        output_path="unused.boe",
        byte_size=0,
        file_sha256="c" * 64,
        format="fichero-boe",
        bucket_event_id="d" * 64,
        resolved_result_disposition=None,
        payment_election=None,
        refund_election=None,
        prior_domiciliation_election=ModeloPriorDomiciliationPublicProvenance(election=PriorDomiciliationElection.KEEP),
    )
    return receipt.model_copy(update=changes)


@pytest.mark.parametrize("argv", [_COORDINATES, _EXACT, (*_COORDINATES, "--revision", _CALCULATION_REVISION)])
def test_complete_export_selector_matches_canonical_receipt(argv: tuple[str, ...]) -> None:
    assert _modelo_export_selector_matches(
        _evidence(), argv=argv, profile_id=_PROFILE, registry_revision_id=_REGISTRY_REVISION
    )


@pytest.mark.parametrize(
    "argv",
    [
        _COORDINATES[:-2],
        (*_COORDINATES[:-1], "2T"),
        (*_COORDINATES, "--revision", "a" * 64),
        (*_EXACT[:-1], "a" * 64),
        (*_EXACT[:6], "a" * 64, *_EXACT[7:]),
        _EXACT[:-2],
        (*_EXACT, "--modelo", "303"),
        (*_EXACT, "--year", "2026", "--period", "1T"),
        (*_EXACT, "--registry-revision", _REGISTRY_REVISION),
    ],
)
def test_incomplete_contradictory_or_mixed_export_selector_is_refused(argv: tuple[str, ...]) -> None:
    assert not _modelo_export_selector_matches(
        _evidence(), argv=argv, profile_id=_PROFILE, registry_revision_id=_REGISTRY_REVISION
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"modelo": "130"},
        {"filing_year": 2025},
        {"period": PublicPeriod(filing_year=2026, code="2T")},
        {"work_unit_id": "a" * 64},
        {"calculation_revision_id": "a" * 64},
    ],
)
def test_exact_selector_cannot_relabel_the_filing_target(changes: dict[str, object]) -> None:
    assert not _modelo_export_selector_matches(
        _evidence(**changes), argv=_EXACT, profile_id=_PROFILE, registry_revision_id=_REGISTRY_REVISION
    )


@pytest.mark.parametrize("revision", [None, "2025"])
def test_exact_selector_requires_the_selected_registry_revision(revision: str | None) -> None:
    assert not _modelo_export_selector_matches(
        _evidence(), argv=_EXACT, profile_id=_PROFILE, registry_revision_id=revision
    )


def test_exact_selector_is_bound_to_the_profile_even_when_public_bucket_is_redacted() -> None:
    receipt = _evidence(bucket_id="<bucket-id>")
    assert _modelo_export_selector_matches(
        receipt, argv=_EXACT, profile_id=_PROFILE, registry_revision_id=_REGISTRY_REVISION
    )
    assert not _modelo_export_selector_matches(
        receipt, argv=_EXACT, profile_id="88888888-8888-4888-8888-888888888888", registry_revision_id=_REGISTRY_REVISION
    )
