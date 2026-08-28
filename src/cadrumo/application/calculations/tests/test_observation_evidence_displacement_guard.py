"""A non-official write must not displace captured AEAT evidence.

A ``(modelo, filing_year, period)`` slot holds exactly one observation, and a
companion measurement in ``test_observations_repository_roundtrip.py`` establishes
by execution what a second write costs: after it, no read surface this repository
exposes returns the earlier payload. That makes displacing official AEAT evidence
with a locally-sourced figure an irrecoverable loss rather than a shadowing.

These tests pin the guard that refuses it, over real encrypted storage. Both
non-official provenances are refused and both permitted directions are asserted,
because a guard that refused every second write would satisfy the refusal cases
while breaking correction of a taxpayer's own manual entry and re-capture from
AEAT. The permitted cases are what make the refusals meaningful.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from ....core import Period, validated_casilla_id
from ....domain.calculations.registry.bindings import CasillaObservation, RegistryModeloObservation
from ....tests.secure_sql import isolated_runtime_profile
from ..errors import ObservationEvidenceDisplacementError
from ..observations_repository import CalculationObservationRepository

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CAPTURED_AT = datetime(2026, 4, 1, 9, 30, tzinfo=UTC)
_OFFICIAL_METADATA = {"aeat_register_status": "ALTA", "aeat_expediente_id": "202530300000001Z"}


def _observation() -> RegistryModeloObservation:
    """One minimal registry-valid M303 observation; provenance is what varies."""
    return RegistryModeloObservation(
        modelo="303",
        filing_year=2025,
        period="1T",
        observations=(
            CasillaObservation(
                casilla_id=validated_casilla_id("iva.repercutido.general"),
                value=Decimal("20000.00"),
                formula_id=None,
                operand_refs=(),
                operand_casilla_refs=(),
                operand_values=(),
                legal_refs=("ley-37-1992:art-21",),
                source_refs=("aeat-iva-2025",),
            ),
        ),
    )


def _save_official(repo: CalculationObservationRepository) -> None:
    """Seed the slot with captured AEAT evidence."""
    repo.save(
        repo.prepare_observation_envelope(
            _observation(),
            source_kind="aeat_sede_justificante",
            captured_at=_CAPTURED_AT,
            source_metadata=_OFFICIAL_METADATA,
        )
    )


def _assert_slot_still_official(repo: CalculationObservationRepository) -> None:
    """The refusal must leave the stored evidence exactly as it was."""
    loaded = repo.load_observation("303", Period.from_year_and_code(2025, "1T"))
    assert loaded is not None
    assert loaded.source_kind == "aeat_sede_justificante"
    assert dict(loaded.source_metadata).get("aeat_expediente_id") == "202530300000001Z"


@pytest.mark.parametrize("source_kind", ["operator_manual", "app_filing"])
def test_a_non_official_write_over_captured_evidence_is_refused(tmp_path: Path, source_kind: str) -> None:
    """Both ruled edges refuse, and the stored evidence is untouched afterwards.

    Parametrised rather than split because the two edges must not drift apart:
    a guard covering only the operator verb would pass a single-edge test while
    leaving the local filing flow able to overwrite silently.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        _save_official(repo)

        with pytest.raises(ObservationEvidenceDisplacementError):
            repo.save(
                repo.prepare_observation_envelope(
                    _observation(),
                    source_kind=source_kind,
                    captured_at=_CAPTURED_AT + timedelta(days=1),
                )
            )

        _assert_slot_still_official(repo)


@pytest.mark.parametrize("source_kind", ["operator_manual", "app_filing"])
def test_the_refusal_happens_before_any_write_is_prepared(tmp_path: Path, source_kind: str) -> None:
    """Preparing an envelope refuses on its own, with nothing persisted.

    The batch writers never call ``save_observation``: they prepare an envelope
    and persist it alongside IVA history in one transaction. If the guard sat on
    the save, this call would return a payload happily and the batch would write
    it. That it raises here is what makes the guard cover the batch path, and it
    raises before the transaction exists, so no staged work has to be unwound.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        _save_official(repo)

        with pytest.raises(ObservationEvidenceDisplacementError):
            repo.prepare_observation_envelope(
                _observation(),
                source_kind=source_kind,
                captured_at=_CAPTURED_AT + timedelta(days=1),
            )

        _assert_slot_still_official(repo)


def test_the_operator_can_displace_evidence_deliberately(tmp_path: Path) -> None:
    """The override is what makes the refusal a gate rather than a wall.

    Without this the guard would be indistinguishable from removing the ability
    to correct a slot at all, and the escape hatch the cost asymmetry assumed
    would not exist.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        _save_official(repo)

        repo.save(
            repo.prepare_observation_envelope(
                _observation(),
                source_kind="operator_manual",
                captured_at=_CAPTURED_AT + timedelta(days=1),
                source_metadata={"local_observation_kind": "operator_supplied"},
                replace_official_evidence=True,
            )
        )

        loaded = repo.load_observation("303", Period.from_year_and_code(2025, "1T"))
        assert loaded is not None
        assert loaded.source_kind == "operator_manual"


def test_official_evidence_may_replace_official_evidence(tmp_path: Path) -> None:
    """Re-capturing from AEAT is not a downgrade and must not need an override.

    This is the anti-over-reach half. A guard written as "refuse any write onto
    an occupied slot" would pass every refusal test above and break re-capture,
    which is a normal operation on the live path.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        _save_official(repo)

        repo.save(
            repo.prepare_observation_envelope(
                _observation(),
                source_kind="aeat_sede_live_capture",
                captured_at=_CAPTURED_AT + timedelta(days=2),
                source_metadata=_OFFICIAL_METADATA,
            )
        )

        loaded = repo.load_observation("303", Period.from_year_and_code(2025, "1T"))
        assert loaded is not None
        assert loaded.source_kind == "aeat_sede_live_capture"


def test_a_manual_row_may_be_corrected_by_another_manual_row(tmp_path: Path) -> None:
    """Nothing official is at stake, so the guard must stay out of the way."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save(
            repo.prepare_observation_envelope(
                _observation(),
                source_kind="operator_manual",
                captured_at=_CAPTURED_AT,
                source_metadata={"local_observation_kind": "operator_supplied"},
            )
        )

        repo.save(
            repo.prepare_observation_envelope(
                _observation(),
                source_kind="app_filing",
                captured_at=_CAPTURED_AT + timedelta(days=1),
            )
        )

        loaded = repo.load_observation("303", Period.from_year_and_code(2025, "1T"))
        assert loaded is not None
        assert loaded.source_kind == "app_filing"


def test_an_empty_slot_accepts_a_non_official_write(tmp_path: Path) -> None:
    """The guard reads occupancy, not provenance alone.

    Without this an implementation that refused every non-official write would
    satisfy both refusal cases and make the local filing flow unusable on a
    period AEAT holds nothing for.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()

        repo.save(
            repo.prepare_observation_envelope(
                _observation(),
                source_kind="app_filing",
                captured_at=_CAPTURED_AT,
            )
        )

        loaded = repo.load_observation("303", Period.from_year_and_code(2025, "1T"))
        assert loaded is not None
        assert loaded.source_kind == "app_filing"
