"""Strict roundtrip across the CalculationObservationRepository boundary.

Persists :class:`RegistryModeloObservation` records at
``SensitivityClass.AUDIT`` keyed by ``(modelo, filing_year, period)``.

Anti-tautology: the populated observation carries two
``CasillaObservation`` entries with full provenance (formula_id,
operand_refs, operand_values, legal_refs, source_refs). A
save-drops-grounding regression would surface as inequality on the
loaded observation tuple.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....domain.calculations.registry import (
    CasillaObservation,
    RegistryModeloObservation,
)
from ....domain.iva_compensation._reconciliation import (
    IvaCompensationAuthoritySource,
    IvaCompensationReconciliationDecision,
)
from ....tests.secure_sql import isolated_runtime_profile
from .._observations_repository import (
    CalculationObservationRepository,
    IvaWalletDecisionRepository,
    iva_wallet_decision_event_key,
    iva_wallet_decision_key,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _populated_observation() -> RegistryModeloObservation:
    return RegistryModeloObservation(
        modelo="303",
        filing_year=2025,
        period="1T",
        observations=(
            CasillaObservation(
                casilla_id="iva.devengado",
                value=Decimal("20000.00"),
                formula_id=None,  # input casilla — no formula
                operand_refs=(),
                operand_values=(),
                legal_refs=("liva.art-21",),
                source_refs=("aeat.iva.2025",),
            ),
            CasillaObservation(
                casilla_id="iva.resultado",
                value=Decimal("12345.67"),
                formula_id="iva.formula.resultado",
                operand_refs=("iva.devengado", "iva.deducible"),
                operand_values=(Decimal("20000.00"), Decimal("7654.33")),
                legal_refs=("liva.art-94",),
                source_refs=("aeat.iva.2025",),
            ),
        ),
    )


def test_calculation_observation_survives_encrypted_storage_roundtrip(
    tmp_path: Path,
) -> None:
    """A RegistryModeloObservation roundtrips through the encrypted observation repo."""

    with isolated_runtime_profile(tmp_path=tmp_path):
        original = _populated_observation()
        captured_at = datetime.now(UTC).replace(microsecond=0)
        repo = CalculationObservationRepository()
        repo.save_observation(
            original,
            source_kind="aeat_sede_justificante",
            captured_at=captured_at,
        )
        loaded = repo.load_observation("303", 2025, "1T")

        assert loaded is not None
        assert loaded.observation == original
        assert loaded.source_kind == "aeat_sede_justificante"
        assert loaded.captured_at == captured_at
        assert len(loaded.observation.observations) == 2
        loaded_computed = loaded.observation.observations[1]
        assert loaded_computed.formula_id == "iva.formula.resultado"
        assert loaded_computed.operand_refs == ("iva.devengado", "iva.deducible")
        assert loaded_computed.operand_values == (
            Decimal("20000.00"),
            Decimal("7654.33"),
        )
        assert loaded_computed.legal_refs == ("liva.art-94",)


def test_calculation_observation_absent_by_design_flag_survives_encrypted_storage_roundtrip(
    tmp_path: Path,
) -> None:
    """CasillaObservation.absent_by_design survives encrypted storage.

    The pydantic-roundtrip test pinned the model_dump_json round trip.
    The production persistence path goes through SecureObjectRepository
    + encrypted SQLite + envelope, which adds serialization layers the
    pydantic gate doesn't exercise.
    This test exercises the full path: construct an observation
    with absent_by_design=True (e.g., M130 C15 at 1T), persist via
    CalculationObservationRepository, reload, assert the flag
    survives verbatim.
    """

    with isolated_runtime_profile(tmp_path=tmp_path):
        absent_by_design_observation = RegistryModeloObservation(
            modelo="130",
            filing_year=2026,
            period="1T",
            observations=(
                CasillaObservation(
                    casilla_id="15",
                    value=Decimal("0"),
                    absent_by_design=True,
                    legal_refs=("rd-439-2007:art-110",),
                    source_refs=("aeat-modelo-130-instructions",),
                ),
                CasillaObservation(
                    casilla_id="14",
                    value=Decimal("500.00"),
                    absent_by_design=False,
                    legal_refs=("rd-439-2007:art-110",),
                    source_refs=("aeat-modelo-130-instructions",),
                ),
            ),
        )

        captured_at = datetime.now(UTC).replace(microsecond=0)
        repo = CalculationObservationRepository()
        repo.save_observation(
            absent_by_design_observation,
            source_kind="aeat_sede_justificante",
            captured_at=captured_at,
        )
        loaded = repo.load_observation("130", 2026, "1T")

        assert loaded is not None
        assert loaded.observation == absent_by_design_observation

        casilla_15 = next(obs for obs in loaded.observation.observations if obs.casilla_id == "15")
        casilla_14 = next(obs for obs in loaded.observation.observations if obs.casilla_id == "14")

        # The absent_by_design discrimination must survive the
        # encrypted-storage roundtrip. A regression that dropped
        # the field would collapse both observations to False.
        assert casilla_15.absent_by_design is True
        assert casilla_14.absent_by_design is False


def test_calculation_observation_iter_modelo_enumerates_decrypted_records(
    tmp_path: Path,
) -> None:
    """Modelo scans must enumerate through decrypted records, not raw HMAC keys."""

    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        target = _populated_observation()
        other = target.model_copy(update={"modelo": "130", "period": "2T"})
        repo.save_observation(
            target,
            source_kind="aeat_sede_justificante",
            captured_at=datetime(2026, 5, 21, 12, 0, tzinfo=UTC),
        )
        repo.save_observation(
            other,
            source_kind="aeat_sede_justificante",
            captured_at=datetime(2026, 5, 21, 12, 1, tzinfo=UTC),
        )

        loaded = tuple(repo.iter_modelo("303"))

        assert len(loaded) == 1
        assert loaded[0].observation == target


def test_calculation_observation_dropped_legal_refs_surfaces_at_load(
    tmp_path: Path,
) -> None:
    """Anti-tautology proof: deleting ``legal_refs`` on a casilla must surface.

    The whole point of persisting :class:`RegistryModeloObservation` is
    the regulatory grounding (legal_refs, source_refs, formula_id) it
    carries through the AUDIT-class boundary. A save-drops-grounding
    drift is the highest-stakes regression this codebase can have: a
    persisted observation with no legal_refs would silently feed
    unsupported numbers into amendment / verification flows.

    Persists a populated observation, reaches into ``SecureObjectRow``
    via ``session_scope``, surgically deletes the ``legal_refs`` tuple
    from one casilla in the encrypted JSON envelope, and asserts the
    load path catches the drift (either ValidationError on the typed
    record's min_length=1 invariant, or strict inequality on the
    loaded observation).
    """

    import json as _json

    from sqlalchemy import select

    from ....adapters.persistence.storage.sql._orm import SecureObjectRow
    from ....adapters.persistence.storage.sql.session import session_scope
    from .._observations_repository import observation_key

    observation_namespace = CalculationObservationRepository.namespace

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        original = _populated_observation()
        captured_at = datetime.now(UTC).replace(microsecond=0)
        repo = CalculationObservationRepository()
        repo.save_observation(
            original,
            source_kind="aeat_sede_justificante",
            captured_at=captured_at,
        )

        object_key = observation_key("303", 2025, "1T")
        with session_scope(profile.repository._engine) as session:
            stmt = select(SecureObjectRow).where(
                SecureObjectRow.namespace == observation_namespace,
                SecureObjectRow.object_key == object_key,
            )
            row = session.execute(stmt).scalar_one()
            envelope = _json.loads(row.payload.decode("utf-8"))
            casillas = envelope["payload"]["observation"]["observations"]
            assert casillas and casillas[1]["legal_refs"], (
                "fixture must serialise legal_refs onto the computed casilla for this proof test to be meaningful"
            )
            casillas[1]["legal_refs"] = []
            row.payload = _json.dumps(envelope).encode("utf-8")

        loaded = repo.load_observation("303", 2025, "1T")
        assert loaded is not None
        assert loaded.observation != original, (
            "anti-tautology proof failed: deleting legal_refs from a "
            "persisted casilla did NOT surface as strict inequality "
            "on the loaded observation. The grounding boundary is "
            "tautological and every observation roundtrip in the "
            "suite is suspect."
        )


def test_iva_wallet_reconciliation_decision_survives_encrypted_storage_roundtrip(
    tmp_path: Path,
) -> None:
    """An IVA wallet reconciliation decision round-trips as AUDIT state."""

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repo = IvaWalletDecisionRepository()
        decided_at = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)
        decision = IvaCompensationReconciliationDecision(
            taxpayer_nif="12345678Z",
            target_year=2026,
            target_period="2T",
            selected_authority="aeat_wallet",
            selected_amount=Decimal("1200"),
            wallet_amount=Decimal("1200"),
            local_recurrence_amount=Decimal("1200"),
            override_amount=None,
            divergence="match",
            blocked=False,
            stale_wallet=False,
            reason="Using latest valid AEAT wallet observation for Modelo 303 prior compensation.",
            wallet_captured_at=decided_at,
            decided_at=decided_at,
        )

        repo.save_decision(decision)
        loaded = repo.load_decision("12345678Z", 2026, "2T")

        assert loaded == decision
        assert loaded is not None
        assert loaded.selected_authority == "aeat_wallet"
        assert loaded.selected_amount == Decimal("1200")
        assert loaded.blocked is False
        assert repo.load_decision_history("12345678Z", 2026, "2T") == (decision,)
        assert iva_wallet_decision_key("12345678Z", 2026, "2T").startswith("iva-wallet-decision:")
        assert iva_wallet_decision_event_key(decision).startswith("iva-wallet-decision-event:")
        database_bytes = (profile.paths.db_dir / "aeat.db").read_bytes()
        assert b"12345678Z" not in database_bytes
        assert b"12345678Z:2026:2T" not in database_bytes


def test_iva_wallet_reconciliation_decisions_keep_immutable_history(
    tmp_path: Path,
) -> None:
    """Later decisions update latest lookup without deleting prior audit events."""

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repo = IvaWalletDecisionRepository()
        first_at = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)
        second_at = datetime(2026, 5, 20, 12, 0, 0, tzinfo=UTC)
        first = IvaCompensationReconciliationDecision(
            taxpayer_nif="12345678Z",
            target_year=2026,
            target_period="2T",
            selected_authority="aeat_wallet",
            selected_amount=Decimal("1200"),
            wallet_amount=Decimal("1200"),
            local_recurrence_amount=Decimal("1200"),
            override_amount=None,
            divergence="match",
            blocked=False,
            stale_wallet=False,
            reason="Using first valid AEAT wallet observation for Modelo 303 prior compensation.",
            wallet_captured_at=first_at,
            decided_at=first_at,
        )
        second = first.model_copy(
            update={
                "selected_amount": Decimal("1300"),
                "wallet_amount": Decimal("1300"),
                "local_recurrence_amount": None,
                "divergence": "wallet_only",
                "reason": "Using later valid AEAT wallet observation without local recurrence.",
                "wallet_captured_at": second_at,
                "decided_at": second_at,
            },
        )

        repo.save_decision(first)
        repo.save_decision(second)

        assert repo.load_decision("12345678Z", 2026, "2T") == second
        assert repo.load_decision_history("12345678Z", 2026, "2T") == (first, second)
        database_bytes = (profile.paths.db_dir / "aeat.db").read_bytes()
        assert b"12345678Z" not in database_bytes
        assert b"12345678Z:2026:2T" not in database_bytes


def test_iva_wallet_reconciliation_decision_roundtrip_preserves_separate_authority_sources(
    tmp_path: Path,
) -> None:
    """A persisted override decision keeps wallet, local, filed-history, and override sources distinct."""

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repo = IvaWalletDecisionRepository()
        decided_at = datetime(2026, 5, 21, 12, 0, 0, tzinfo=UTC)
        wallet_captured_at = datetime(2026, 5, 21, 9, 0, 0, tzinfo=UTC)
        authority_sources = (
            IvaCompensationAuthoritySource(
                source_kind="aeat_wallet",
                amount=Decimal("1200"),
                source_locator="https://example.test/wallet",
                captured_at=wallet_captured_at,
            ),
            IvaCompensationAuthoritySource(
                source_kind="local_recurrence",
                amount=Decimal("800"),
                source_locator="local-recurrence:modelo-303-compensacion-pendiente-anteriores",
                captured_at=decided_at,
                source_modelo="303",
                source_filing_year=2025,
                source_periods=("4T",),
            ),
            IvaCompensationAuthoritySource(
                source_kind="filed_history_observation",
                amount=Decimal("800"),
                source_locator="binding:modelo-303-compensacion-pendiente-anteriores",
                captured_at=decided_at,
                source_modelo="303",
                source_filing_year=2025,
                source_periods=("4T",),
            ),
            IvaCompensationAuthoritySource(
                source_kind="taxpayer_override",
                amount=Decimal("1000"),
                source_locator="operator-note:iva-wallet-review-2026-2T",
                captured_at=decided_at,
            ),
        )
        decision = IvaCompensationReconciliationDecision(
            taxpayer_nif="12345678Z",
            target_year=2026,
            target_period="2T",
            selected_authority="taxpayer_override",
            selected_amount=Decimal("1000"),
            wallet_amount=Decimal("1200"),
            local_recurrence_amount=Decimal("800"),
            override_amount=Decimal("1000"),
            divergence="override",
            blocked=False,
            stale_wallet=False,
            reason="Operator reviewed separate AEAT, filed-history, local, and override evidence.",
            wallet_captured_at=wallet_captured_at,
            authority_sources=authority_sources,
            decided_at=decided_at,
        )

        repo.save_decision(decision)
        loaded = repo.load_decision("12345678Z", 2026, "2T")

        assert loaded == decision
        assert loaded is not None
        assert loaded.selected_authority == "taxpayer_override"
        assert loaded.selected_amount == Decimal("1000")
        assert loaded.wallet_amount == Decimal("1200")
        assert loaded.local_recurrence_amount == Decimal("800")
        assert loaded.override_amount == Decimal("1000")
        assert tuple(source.source_kind for source in loaded.authority_sources) == (
            "aeat_wallet",
            "local_recurrence",
            "filed_history_observation",
            "taxpayer_override",
        )
        assert tuple(source.amount for source in loaded.authority_sources) == (
            Decimal("1200"),
            Decimal("800"),
            Decimal("800"),
            Decimal("1000"),
        )
        assert repo.load_decision_history("12345678Z", 2026, "2T") == (decision,)
        assert repo.list_decisions() == (decision,)
        database_bytes = (profile.paths.db_dir / "aeat.db").read_bytes()
        assert b"12345678Z" not in database_bytes
        assert b"operator-note:iva-wallet-review-2026-2T" not in database_bytes
