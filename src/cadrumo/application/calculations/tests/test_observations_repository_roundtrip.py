"""Strict roundtrip across the CalculationObservationRepository boundary.

Persists :class:`RegistryModeloObservation` records at
``SensitivityClass.AUDIT`` keyed by ``(modelo, filing_year, period)``.

Anti-tautology: the populated observation carries two
``CasillaObservation`` entries with full provenance (formula_id,
operand_refs, operand_casilla_refs, operand_values, legal_refs,
source_refs). A
save-drops-grounding regression would surface as inequality on the
loaded observation tuple.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....adapters.persistence.storage import Envelope, EnvelopeVersionError
from ....core import (
    CasillaId,
    Period,
    SecureObjectWrite,
    validated_casilla_id,
)
from cadrumo.domain.calculations.registry.bindings import CasillaObservation, RegistryModeloObservation
from ....domain.iva_compensation import (
    IvaCompensationAuthoritySource,
    IvaCompensationDecisionReason,
    IvaCompensationReconciliationDecision,
)
from ....tests.secure_sql import (
    isolated_runtime_profile,
    mutate_encrypted_secure_object_json,
    read_db_at_rest_bytes,
)
from ..errors import ObservationCasillaReferenceError
from .._observations_repository import (
    CalculationObservationRepository,
    IvaWalletDecisionEnvelopePayload,
    IvaWalletDecisionRepository,
    ObservationEnvelopePayload,
    ObservationSourceKind,
    iva_wallet_decision_event_key,
    iva_wallet_decision_key,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_IVA_DEVENGADO_CASILLA: CasillaId = validated_casilla_id("iva.cuota-devengada-total")
_IVA_DEDUCIBLE_CASILLA: CasillaId = validated_casilla_id("iva.cuota-deducible-total")
_IVA_RESULTADO_CASILLA: CasillaId = validated_casilla_id("iva.resultado")
_M303_PRINTED_RESULT_REFERENCE_CASILLA: CasillaId = validated_casilla_id("69")
_M130_ABSENT_BY_DESIGN_CASILLA: CasillaId = validated_casilla_id("15")
_M130_PAYMENT_BASE_CASILLA: CasillaId = validated_casilla_id("14")
_M303_PERIOD_CASILLA: CasillaId = validated_casilla_id("decl.periodo")
_CAPTURED_AT = datetime(2026, 5, 28, 11, 35, 0, tzinfo=UTC)


def _populated_observation() -> RegistryModeloObservation:
    return RegistryModeloObservation(
        modelo="303",
        filing_year=2025,
        period="1T",
        observations=(
            CasillaObservation(
                casilla_id=_IVA_DEVENGADO_CASILLA,
                value=Decimal("20000.00"),
                formula_id=None,  # input casilla — no formula
                operand_refs=(),
                operand_casilla_refs=(),
                operand_values=(),
                legal_refs=("ley-37-1992:art-21",),
                source_refs=("aeat-iva-2025",),
            ),
            CasillaObservation(
                casilla_id=_M303_PERIOD_CASILLA,
                value_kind="text",
                value="1T",
                legal_refs=("rd-1624-1992:art-71", "orden-eha-3786-2008:art-1"),
                source_refs=("boe-modelo-303-2008-form", "aeat-modelo-303-procedure"),
            ),
            CasillaObservation(
                casilla_id=_IVA_RESULTADO_CASILLA,
                value=Decimal("12345.67"),
                formula_id="iva.formula.resultado",
                operand_refs=(_IVA_DEVENGADO_CASILLA, _IVA_DEDUCIBLE_CASILLA),
                operand_casilla_refs=(_IVA_DEVENGADO_CASILLA, _IVA_DEDUCIBLE_CASILLA),
                operand_values=(Decimal("20000.00"), Decimal("7654.33")),
                legal_refs=("ley-37-1992:art-94",),
                source_refs=("aeat-iva-2025",),
            ),
        ),
    )


def test_calculation_observation_survives_encrypted_storage_roundtrip(
    tmp_path: Path,
) -> None:
    """A RegistryModeloObservation roundtrips through the encrypted observation repo."""

    with isolated_runtime_profile(tmp_path=tmp_path):
        original = _populated_observation()
        repo = CalculationObservationRepository()
        repo.save(
            repo.prepare_observation_envelope(
                original,
                source_kind="aeat_sede_justificante",
                captured_at=_CAPTURED_AT,
                source_metadata={
                    "aeat_register_status": "ALTA",
                    "aeat_expediente_id": "202530300000001Z",
                },
            )
        )
        loaded = repo.load_observation("303", Period.from_year_and_code(2025, "1T"))

        assert loaded is not None
        assert loaded.observation == original
        assert loaded.source_kind == "aeat_sede_justificante"
        assert loaded.captured_at == _CAPTURED_AT
        assert loaded.source_metadata == {
            "aeat_register_status": "ALTA",
            "aeat_expediente_id": "202530300000001Z",
        }
        assert len(loaded.observation.observations) == 3
        loaded_computed = next(
            observation
            for observation in loaded.observation.observations
            if observation.casilla_id == _IVA_RESULTADO_CASILLA
        )
        assert loaded_computed.formula_id == "iva.formula.resultado"
        assert loaded_computed.operand_refs == (_IVA_DEVENGADO_CASILLA, _IVA_DEDUCIBLE_CASILLA)
        assert loaded_computed.operand_casilla_refs == (_IVA_DEVENGADO_CASILLA, _IVA_DEDUCIBLE_CASILLA)
        assert loaded_computed.operand_values == (
            Decimal("20000.00"),
            Decimal("7654.33"),
        )
        assert loaded_computed.legal_refs == ("ley-37-1992:art-94",)
        loaded_period = next(
            observation
            for observation in loaded.observation.observations
            if observation.casilla_id == _M303_PERIOD_CASILLA
        )
        assert loaded_period.value == "1T"
        assert _M303_PERIOD_CASILLA not in loaded.observation.casilla_values


def test_encrypted_observation_roundtrip_detects_a_dropped_text_value(tmp_path: Path) -> None:
    """Anti-tautology: changing the persisted text scalar changes the loaded envelope."""
    from sqlalchemy import select

    from ....adapters.persistence.storage.sql import SecureObjectRow
    from .._observations_repository import observation_key

    period = Period.from_year_and_code(2025, "1T")
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        original = _populated_observation()
        repo = CalculationObservationRepository()
        repo.save(
            repo.prepare_observation_envelope(
                original,
                source_kind="aeat_sede_justificante",
                captured_at=_CAPTURED_AT,
            )
        )
        stmt = select(SecureObjectRow).where(
            SecureObjectRow.namespace == repo.namespace,
            SecureObjectRow.object_key == observation_key("303", period),
        )

        def replace_text_scalar(envelope):
            rows = envelope["payload"]["observation"]["observations"]
            period_row = next(row for row in rows if row["casilla_id"] == _M303_PERIOD_CASILLA)
            assert period_row["value_kind"] == "text" and period_row["value"] == "1T"
            period_row["value"] = "0"

        mutate_encrypted_secure_object_json(
            profile.repository._engine,
            row_statement=stmt,
            mutate=replace_text_scalar,
        )

        loaded = repo.load_observation("303", period)
        assert loaded is not None
        assert loaded.observation != original
        loaded_period = next(
            observation
            for observation in loaded.observation.observations
            if observation.casilla_id == _M303_PERIOD_CASILLA
        )
        assert loaded_period.value == "0"
        assert loaded_period.value_kind == "text"


def test_calculation_observation_repository_rejects_printed_number_reference(
    tmp_path: Path,
) -> None:
    """Persisting calculation history must reject printed-number casilla references."""

    observation = RegistryModeloObservation(
        modelo="303",
        filing_year=2025,
        period="1T",
        observations=(
            CasillaObservation(
                casilla_id=_M303_PRINTED_RESULT_REFERENCE_CASILLA,
                value=Decimal("1.00"),
                legal_refs=("ley-37-1992:art-94",),
                source_refs=("aeat-iva-2025",),
            ),
        ),
    )

    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        with pytest.raises(ObservationCasillaReferenceError) as raised:
            repo.save(
                repo.prepare_observation_envelope(
                    observation,
                    source_kind="aeat_sede_justificante",
                    captured_at=_CAPTURED_AT,
                )
            )

        assert str(raised.value) == "application.calculations.observations.errors.casilla_ids_noncanonical"
        assert raised.value.context is not None
        assert raised.value.context["modelo"] == "303"
        assert raised.value.context["filing_year"] == 2025
        assert raised.value.context["period"] == "1T"
        assert raised.value.context["casilla_ids"] == (_M303_PRINTED_RESULT_REFERENCE_CASILLA,)
        assert repo.load_observation("303", Period.from_year_and_code(2025, "1T")) is None


def test_calculation_observation_repository_rejects_printed_operand_casilla_ref(
    tmp_path: Path,
) -> None:
    observation = RegistryModeloObservation(
        modelo="303",
        filing_year=2025,
        period="1T",
        observations=(
            CasillaObservation(
                casilla_id=_IVA_RESULTADO_CASILLA,
                value=Decimal("1.00"),
                formula_id="iva.formula.resultado",
                operand_refs=(_M303_PRINTED_RESULT_REFERENCE_CASILLA,),
                operand_casilla_refs=(_M303_PRINTED_RESULT_REFERENCE_CASILLA,),
                operand_values=(Decimal("1.00"),),
                legal_refs=("ley-37-1992:art-94",),
                source_refs=("aeat-iva-2025",),
            ),
        ),
    )

    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        with pytest.raises(ObservationCasillaReferenceError) as raised:
            repo.save(
                repo.prepare_observation_envelope(
                    observation,
                    source_kind="aeat_sede_justificante",
                    captured_at=_CAPTURED_AT,
                )
            )

        assert raised.value.context is not None
        assert raised.value.context["modelo"] == "303"
        assert raised.value.context["filing_year"] == 2025
        assert raised.value.context["period"] == "1T"
        assert raised.value.context["casilla_ids"] == (_M303_PRINTED_RESULT_REFERENCE_CASILLA,)
        assert raised.value.context["observation_casilla_ids"] == ()
        assert raised.value.context["operand_casilla_refs"] == (_M303_PRINTED_RESULT_REFERENCE_CASILLA,)
        assert repo.load_observation("303", Period.from_year_and_code(2025, "1T")) is None


def test_calculation_observation_repository_rejects_unregistered_m303_annual_ingress(
    tmp_path: Path,
) -> None:
    """M303 ``0A`` cannot enter encrypted history without a registry revision.

    The ingress request intentionally has no casilla values: without a
    Modelo 303 ``0A`` snapshot there is no legal provenance from which to
    construct them. The production repository must reject the request before
    writing an encrypted observation, retaining the established ``4T``
    lifecycle as the only registry-supported annual settlement ingress.
    """

    annual_ingress = RegistryModeloObservation(
        modelo="303",
        filing_year=2025,
        period="0A",
    )

    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        with pytest.raises(ObservationCasillaReferenceError) as raised:
            repo.save(repo.prepare_observation_envelope(annual_ingress, source_kind="aeat_sede_justificante"))

        assert str(raised.value) == "application.calculations.observations.errors.registry_snapshot_missing"
        assert raised.value.context == {
            "modelo": "303",
            "filing_year": 2025,
            "period": "0A",
        }
        assert repo.load_observation("303", Period.from_year_and_code(2025, "0A")) is None


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
                    casilla_id=_M130_ABSENT_BY_DESIGN_CASILLA,
                    value=Decimal("0"),
                    absent_by_design=True,
                    legal_refs=("rd-439-2007:art-110",),
                    source_refs=("aeat-modelo-130-instructions",),
                ),
                CasillaObservation(
                    casilla_id=_M130_PAYMENT_BASE_CASILLA,
                    value=Decimal("500.00"),
                    absent_by_design=False,
                    legal_refs=("rd-439-2007:art-110",),
                    source_refs=("aeat-modelo-130-instructions",),
                ),
            ),
        )

        repo = CalculationObservationRepository()
        repo.save(
            repo.prepare_observation_envelope(
                absent_by_design_observation,
                source_kind="aeat_sede_justificante",
                captured_at=_CAPTURED_AT,
            )
        )
        loaded = repo.load_observation("130", Period.from_year_and_code(2026, "1T"))

        assert loaded is not None
        assert loaded.observation == absent_by_design_observation

        casilla_15 = next(
            obs for obs in loaded.observation.observations if obs.casilla_id == _M130_ABSENT_BY_DESIGN_CASILLA
        )
        casilla_14 = next(
            obs for obs in loaded.observation.observations if obs.casilla_id == _M130_PAYMENT_BASE_CASILLA
        )

        # The absent_by_design discrimination must survive the
        # encrypted-storage roundtrip. A regression that dropped
        # the field would collapse both observations to False.
        assert casilla_15.absent_by_design is True
        assert casilla_14.absent_by_design is False


def test_second_observation_under_one_natural_key_leaves_the_first_unreachable(
    tmp_path: Path,
) -> None:
    """A second write to one (modelo, period) slot replaces the first irrecoverably.

    Observations are keyed naturally by modelo and filing period, so there is
    exactly one slot per period and a later write is an update of that row. This
    measures what a second write COSTS, which decides whether displacing an
    official observation is shadowing (the earlier payload survives and the
    wrong one is selected) or destruction (the earlier payload is gone).

    The claim is bounded to what this repository exposes: after the second
    write, no read surface it offers returns the first payload. It is not a
    claim that no trace exists anywhere in the substrate.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        period = Period.from_year_and_code(2025, "1T")

        repo.save(
            repo.prepare_observation_envelope(
                _populated_observation(),
                source_kind="aeat_sede_justificante",
                captured_at=_CAPTURED_AT,
                source_metadata={
                    "aeat_register_status": "ALTA",
                    "aeat_expediente_id": "202530300000001Z",
                },
            )
        )
        repo.save(
            repo.prepare_observation_envelope(
                _populated_observation(),
                source_kind="operator_manual",
                captured_at=_CAPTURED_AT + timedelta(days=1),
                source_metadata={"local_observation_kind": "operator_supplied"},
                # This displacement is now refused by default. The intent is stated
                # explicitly because what this test measures is the COST of
                # displacing official evidence, not whether it is permitted -- the
                # refusal is measured separately. Removing this argument would turn
                # a cost measurement into a duplicate of the guard's own test.
                replace_official_evidence=True,
            )
        )

        loaded = repo.load_observation("303", period)
        assert loaded is not None
        assert loaded.source_kind == "operator_manual", (
            "the later write did not take the slot, so this measurement does not describe the code"
        )

        scanned = [row for row in repo.iter_modelo("303") if row.observation.period == "1T"]
        assert len(scanned) == 1, (
            f"expected one row per natural key, found {len(scanned)} -- if the substrate keeps prior "
            "payloads reachable through the modelo scan, displacing an official observation is "
            "shadowing rather than destruction and the remedy is selection, not a write guard"
        )
        assert scanned[0].source_kind == "operator_manual"
        assert "aeat_expediente_id" not in dict(scanned[0].source_metadata), (
            "the displaced AEAT provenance is still reachable, so this is not destruction"
        )


def test_calculation_observation_iter_modelo_enumerates_decrypted_records(
    tmp_path: Path,
) -> None:
    """Modelo scans must enumerate through decrypted records, not raw HMAC keys."""

    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        target = _populated_observation()
        other = RegistryModeloObservation(modelo="130", filing_year=2025, period="2T")
        repo.save(
            repo.prepare_observation_envelope(
                target,
                source_kind="aeat_sede_justificante",
                captured_at=datetime(2026, 5, 21, 12, 0, tzinfo=UTC),
            )
        )
        repo.save(
            repo.prepare_observation_envelope(
                other,
                source_kind="aeat_sede_justificante",
                captured_at=datetime(2026, 5, 21, 12, 1, tzinfo=UTC),
            )
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

    from sqlalchemy import select

    from ....adapters.persistence.storage.sql import SecureObjectRow
    from .._observations_repository import observation_key

    observation_namespace = CalculationObservationRepository.namespace

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        original = _populated_observation()
        repo = CalculationObservationRepository()
        repo.save(
            repo.prepare_observation_envelope(
                original,
                source_kind="aeat_sede_justificante",
                captured_at=_CAPTURED_AT,
            )
        )

        object_key = observation_key("303", Period.from_year_and_code(2025, "1T"))
        stmt = select(SecureObjectRow).where(
            SecureObjectRow.namespace == observation_namespace,
            SecureObjectRow.object_key == object_key,
        )

        def mutate(envelope):
            casillas = envelope["payload"]["observation"]["observations"]
            assert casillas and casillas[1]["legal_refs"], (
                "fixture must serialise legal_refs onto the computed casilla for this proof test to be meaningful"
            )
            casillas[1]["legal_refs"] = []

        mutate_encrypted_secure_object_json(
            profile.repository._engine,
            row_statement=stmt,
            mutate=mutate,
        )

        with pytest.raises(ValidationError, match="legal_refs"):
            repo.load_observation("303", Period.from_year_and_code(2025, "1T"))


def test_iva_wallet_reconciliation_decision_v2_roundtrip_preserves_reason_identity_and_operator_explanation(
    tmp_path: Path,
) -> None:
    """An IVA wallet reconciliation decision round-trips as AUDIT state."""

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repo = IvaWalletDecisionRepository()
        decided_at = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)
        decision = IvaCompensationReconciliationDecision(
            taxpayer_nif="12345678Z",
            target_year=2026,
            target_period=Period.from_year_and_code(2026, "2T"),
            selected_authority="taxpayer_override",
            selected_amount=Decimal("1100"),
            wallet_amount=Decimal("1200"),
            local_recurrence_amount=Decimal("1000"),
            override_amount=Decimal("1100"),
            divergence="override",
            blocked=False,
            stale_wallet=False,
            reason_identity=IvaCompensationDecisionReason.TAXPAYER_OVERRIDE,
            operator_explanation="Operator reviewed the filed return and AEAT wallet evidence.",
            # Populated NON-default on purpose: it defaults to False, so a
            # save-drops-field / load-re-defaults-field regression would be
            # invisible if the fixture left it alone. It is the only field
            # distinguishing a prior record that could not be read from one that
            # was never stored, so losing it silently returns the operator to
            # being told nothing exists.
            local_evidence_found_but_unusable=True,
            wallet_captured_at=decided_at,
            decided_at=decided_at,
        )

        latest_key = iva_wallet_decision_key("12345678Z", Period.from_year_and_code(2026, "2T"))
        event_key = iva_wallet_decision_event_key(decision)

        repo.save_decision(decision)
        latest_record = repo.secure_object_repository.load(
            repo.namespace,
            latest_key,
            expected_class=repo.sensitivity,
            max_supported_version=repo.schema_version,
        )
        event_record = repo.secure_object_repository.load(
            repo.history_namespace,
            event_key,
            expected_class=repo.sensitivity,
            max_supported_version=repo.schema_version,
        )
        cleartext_key_record = repo.secure_object_repository.load(
            repo.namespace,
            "12345678Z:2026:2T",
            expected_class=repo.sensitivity,
            max_supported_version=repo.schema_version,
        )
        loaded = repo.load_decision("12345678Z", Period.from_year_and_code(2026, "2T"))

        assert latest_record is not None
        assert event_record is not None
        assert cleartext_key_record is None
        assert loaded == decision
        assert loaded is not None
        assert loaded.selected_authority == "taxpayer_override"
        assert loaded.selected_amount == Decimal("1100")
        assert loaded.reason_identity is IvaCompensationDecisionReason.TAXPAYER_OVERRIDE
        assert loaded.operator_explanation == "Operator reviewed the filed return and AEAT wallet evidence."
        assert loaded.blocked is False
        assert repo.load_decision_history("12345678Z", Period.from_year_and_code(2026, "2T")) == (decision,)
        latest_envelope = Envelope[IvaWalletDecisionEnvelopePayload].model_validate_json(latest_record.payload)
        event_envelope = Envelope[IvaWalletDecisionEnvelopePayload].model_validate_json(event_record.payload)
        assert latest_record.schema_version == repo.schema_version == 2
        assert event_record.schema_version == repo.history_schema_version == 2
        assert latest_envelope.schema_version == repo.schema_version
        assert event_envelope.schema_version == repo.history_schema_version
        assert latest_key.startswith("iva-wallet-decision:")
        assert event_key.startswith("iva-wallet-decision-event:")
        database_bytes = read_db_at_rest_bytes(profile.paths.database_file)
        assert b"12345678Z" not in database_bytes
        assert b"12345678Z:2026:2T" not in database_bytes
        assert b"Operator reviewed the filed return" not in database_bytes


def test_a_decision_payload_missing_the_unreadable_evidence_flag_reloads_unequal(
    tmp_path: Path,
) -> None:
    """Anti-tautology: prove the roundtrip above would notice this field being dropped.

    The flag carries a default, so a payload that omits it does NOT raise -- it
    silently re-defaults to False, which is the save-drops-field regression in
    its quietest form and would return the operator to being told no prior
    record exists. The sanctioned proof for a defaultable field is therefore
    strict INEQUALITY rather than a refusal, and this asserts it.

    Limit, stated rather than implied: this drops the key from the validated
    payload, so it proves the value cannot be reconstructed from a payload that
    omits it. It does not tamper with ciphertext at rest, so it does not prove
    the encrypted envelope would surface the same difference.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = IvaWalletDecisionRepository()
        decided_at = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)
        original = IvaCompensationReconciliationDecision(
            taxpayer_nif="12345678Z",
            target_year=2026,
            target_period=Period.from_year_and_code(2026, "2T"),
            selected_authority="missing",
            selected_amount=None,
            divergence="missing",
            blocked=True,
            stale_wallet=False,
            reason_identity=IvaCompensationDecisionReason.LOCAL_EVIDENCE_UNREADABLE,
            local_evidence_found_but_unusable=True,
            decided_at=decided_at,
        )
        repo.save_decision(original)
        assert repo.load_decision("12345678Z", Period.from_year_and_code(2026, "2T")) == original

        # Feed the strict model its Python-shaped contract. JSON mode also turns
        # Period/authority tuples and datetimes into wire strings/lists, making
        # validation fail before the deliberately omitted flag is exercised.
        payload = original.model_dump(mode="python")
        # Assert the field was THERE before dropping it. Without this, a model
        # that never serialised it at all would satisfy every assertion below
        # while proving the opposite defect: the drop would be a no-op and the
        # inequality would never be tested.
        assert "local_evidence_found_but_unusable" in payload, (
            "the serialized decision does not carry the field at all, so this proof would pass "
            "vacuously and the roundtrip above asserts nothing about it"
        )
        del payload["local_evidence_found_but_unusable"]
        reloaded = IvaCompensationReconciliationDecision.model_validate(payload)

        assert reloaded.local_evidence_found_but_unusable is False
        assert reloaded != original, (
            "a payload that dropped the unreadable-evidence flag reloaded EQUAL to the original, so "
            "the roundtrip above cannot detect this field being lost and every assertion about it is "
            "tautological"
        )


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
            target_period=Period.from_year_and_code(2026, "2T"),
            selected_authority="aeat_wallet",
            selected_amount=Decimal("1200"),
            wallet_amount=Decimal("1200"),
            local_recurrence_amount=Decimal("1200"),
            override_amount=None,
            divergence="match",
            blocked=False,
            stale_wallet=False,
            reason_identity=IvaCompensationDecisionReason.AEAT_WALLET_VALIDATED,
            wallet_captured_at=first_at,
            decided_at=first_at,
        )
        second = first.model_copy(
            update={
                "selected_amount": Decimal("1300"),
                "wallet_amount": Decimal("1300"),
                "local_recurrence_amount": None,
                "divergence": "wallet_only",
                "reason_identity": IvaCompensationDecisionReason.AEAT_WALLET_UNCROSSCHECKED,
                "wallet_captured_at": second_at,
                "decided_at": second_at,
            },
        )

        repo.save_decision(first)
        repo.save_decision(second)

        assert repo.load_decision("12345678Z", Period.from_year_and_code(2026, "2T")) == second
        assert repo.load_decision_history("12345678Z", Period.from_year_and_code(2026, "2T")) == (first, second)
        database_bytes = read_db_at_rest_bytes(profile.paths.database_file)
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
                source_periods=(Period.from_year_and_code(2025, "4T"),),
            ),
            IvaCompensationAuthoritySource(
                source_kind="filed_history_observation",
                amount=Decimal("800"),
                source_locator="binding:modelo-303-compensacion-pendiente-anteriores",
                captured_at=decided_at,
                source_modelo="303",
                source_filing_year=2025,
                source_periods=(Period.from_year_and_code(2025, "4T"),),
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
            target_period=Period.from_year_and_code(2026, "2T"),
            selected_authority="taxpayer_override",
            selected_amount=Decimal("1000"),
            wallet_amount=Decimal("1200"),
            local_recurrence_amount=Decimal("800"),
            override_amount=Decimal("1000"),
            divergence="override",
            blocked=False,
            stale_wallet=False,
            reason_identity=IvaCompensationDecisionReason.TAXPAYER_OVERRIDE,
            operator_explanation="Operator reviewed separate AEAT, filed-history, local, and override evidence.",
            wallet_captured_at=wallet_captured_at,
            authority_sources=authority_sources,
            decided_at=decided_at,
        )

        repo.save_decision(decision)
        loaded = repo.load_decision("12345678Z", Period.from_year_and_code(2026, "2T"))

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
        assert repo.load_decision_history("12345678Z", Period.from_year_and_code(2026, "2T")) == (decision,)
        assert repo.list_decisions() == (decision,)
        database_bytes = read_db_at_rest_bytes(profile.paths.database_file)
        assert b"12345678Z" not in database_bytes
        assert b"operator-note:iva-wallet-review-2026-2T" not in database_bytes


class TestCaptureInstantContract:
    """Every persisted observation envelope carries a UTC-aware capture instant."""

    @staticmethod
    def _canonical_fields() -> dict[str, object]:
        return {
            "observation": _populated_observation(),
            "captured_at": datetime(2024, 4, 15, 10, 30, tzinfo=UTC),
            "source_kind": ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
            "stamped_revision_id": "revision-for-envelope-roundtrip",
        }

    def test_utc_aware_capture_instant_is_accepted(self) -> None:
        """The positive control for the refusals below."""
        payload = ObservationEnvelopePayload.model_validate(self._canonical_fields())

        assert payload.captured_at.tzinfo is not None
        assert payload.captured_at.utcoffset() == timedelta(0)

    @pytest.mark.parametrize(
        "captured_at",
        [
            datetime(2024, 4, 15, 10, 30),
            datetime(2024, 4, 15, 10, 30, tzinfo=timezone(timedelta(hours=2))),
        ],
    )
    def test_naive_and_offset_capture_instants_are_refused(self, captured_at: datetime) -> None:
        """A capture instant with no zone, or a non-UTC zone, never reaches persistence.

        ``captured_at`` was a bare ``datetime``, so a naive value was persisted
        as if it were an instant. Every later comparison against a UTC-aware
        instant then silently answered a different question than it appeared to,
        and the stored evidence could not say which zone it meant.
        """
        fields = self._canonical_fields()
        fields["captured_at"] = captured_at

        with pytest.raises(ValidationError):
            ObservationEnvelopePayload.model_validate(fields)


def _wallet_decision() -> IvaCompensationReconciliationDecision:
    decided_at = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)
    return IvaCompensationReconciliationDecision(
        taxpayer_nif="12345678Z",
        target_year=2026,
        target_period=Period.from_year_and_code(2026, "2T"),
        selected_authority="aeat_wallet",
        selected_amount=Decimal("1200"),
        wallet_amount=Decimal("1200"),
        local_recurrence_amount=Decimal("1200"),
        override_amount=None,
        divergence="match",
        blocked=False,
        stale_wallet=False,
        reason_identity=IvaCompensationDecisionReason.AEAT_WALLET_VALIDATED,
        wallet_captured_at=decided_at,
        decided_at=decided_at,
    )


def _restamp_wallet_decision_row_as_v1(
    repo: IvaWalletDecisionRepository,
    *,
    namespace: str,
    object_key: str,
) -> None:
    """Turn one real encrypted v2 row into a self-consistent historical v1 row."""
    import json

    from sqlalchemy import select

    from ....adapters.persistence.storage.crypto import (
        encrypt_secure_object_payload,
        secure_object_payload_aad,
    )
    from ....adapters.persistence.storage.sql import SecureObjectRow
    from ....adapters.persistence.storage.sql._secure_object_crypto import derive_revision_id
    from ....adapters.persistence.storage.sql.session import session_scope
    from ....core.hashing import sha256_hex

    current = repo.secure_object_repository.load(
        namespace,
        object_key,
        expected_class=repo.sensitivity,
        max_supported_version=2,
    )
    assert current is not None
    legacy_envelope = json.loads(current.payload.decode("utf-8"))
    legacy_envelope["schema_version"] = 1
    legacy_decision = legacy_envelope["payload"]["decision"]
    legacy_decision["reason"] = "Using latest valid AEAT wallet observation for Modelo 303 prior compensation."
    del legacy_decision["reason_identity"]
    legacy_decision.pop("operator_explanation", None)
    legacy_payload = json.dumps(legacy_envelope, separators=(",", ":")).encode("utf-8")

    with session_scope(repo.secure_object_repository.engine) as session:
        row = session.execute(
            select(SecureObjectRow).where(
                SecureObjectRow.namespace == namespace,
                SecureObjectRow.object_key == object_key,
            ),
        ).scalar_one()
        legacy_payload_wire = encrypt_secure_object_payload(
            legacy_payload,
            associated_data=secure_object_payload_aad(namespace, bytes(row.object_key), 1),
        )
        legacy_payload_hash = sha256_hex(legacy_payload)
        legacy_ciphertext_hash = sha256_hex(legacy_payload_wire)
        row.schema_version = 1
        row.payload = legacy_payload_wire
        row.payload_hash = legacy_payload_hash
        row.ciphertext_hash = legacy_ciphertext_hash
        row.revision_id = derive_revision_id(
            namespace=namespace,
            object_key=bytes(row.object_key),
            schema_version=1,
            written_at=row.written_at,
            payload_hash=legacy_payload_hash,
            ciphertext_hash=legacy_ciphertext_hash,
            previous_revision_id=row.previous_revision_id,
            previous_payload_hash=row.previous_payload_hash,
        )


@pytest.mark.parametrize("surface", ["latest", "history"])
def test_iva_wallet_reconciliation_decision_namespaces_refuse_v1_rows(
    tmp_path: Path,
    surface: str,
) -> None:
    """Both changed encrypted namespaces refuse the exact pre-current version."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = IvaWalletDecisionRepository()
        decision = _wallet_decision()
        repo.save_decision(decision)
        period = Period.from_year_and_code(2026, "2T")
        if surface == "latest":
            _restamp_wallet_decision_row_as_v1(
                repo,
                namespace=repo.namespace,
                object_key=iva_wallet_decision_key(decision.taxpayer_nif, period),
            )
            with pytest.raises(EnvelopeVersionError) as raised:
                repo.load_decision(decision.taxpayer_nif, period)
        else:
            _restamp_wallet_decision_row_as_v1(
                repo,
                namespace=repo.history_namespace,
                object_key=iva_wallet_decision_event_key(decision),
            )
            with pytest.raises(EnvelopeVersionError) as raised:
                repo.secure_object_repository.load(
                    repo.history_namespace,
                    iva_wallet_decision_event_key(decision),
                    expected_class=repo.sensitivity,
                    max_supported_version=repo.history_schema_version,
                )
        assert raised.value.context is not None
        assert raised.value.context["schema_version"] == 1
        assert raised.value.context["expected"] == 2


def test_wallet_decision_latest_and_history_commit_together(tmp_path: Path) -> None:
    """A failed decision write leaves neither a latest row nor an audit event.

    The latest state and the immutable audit event used to be two independent
    writes, so a failure between them persisted a decision the history has no
    record of. The history exists precisely to explain how the latest state was
    reached, so a latest row with no event is a decision that cannot be audited.

    The refusal here is the substrate's own registered write policy: an event
    payload addressed at a schema version the namespace does not accept is
    refused, and because both rows now ride one transaction the latest row must
    not survive it either.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = IvaWalletDecisionRepository()
        decision = _wallet_decision()
        latest_key = iva_wallet_decision_key("12345678Z", Period.from_year_and_code(2026, "2T"))

        # Positive control: the real save persists both rows.
        repo.save_decision(decision)
        assert repo.load_decision("12345678Z", Period.from_year_and_code(2026, "2T")) is not None
        assert len(repo.load_decision_history("12345678Z", Period.from_year_and_code(2026, "2T"))) == 1

        # A second decision whose history write is refused must not land its latest row.
        replacement = _wallet_decision().model_copy(update={"decided_at": decision.decided_at + timedelta(seconds=1)})
        latest_write = repo.to_secure_object_write(IvaWalletDecisionEnvelopePayload(decision=replacement))
        refused_history_write = SecureObjectWrite(
            namespace=repo.history_namespace,
            object_key=iva_wallet_decision_event_key(replacement),
            classification=repo.sensitivity,
            # A version the namespace's registered write policy does not accept.
            schema_version=repo.schema_version + 99,
            written_at=latest_write.written_at,
            payload=latest_write.payload,
        )
        with pytest.raises(EnvelopeVersionError):
            repo.secure_object_repository.apply_batch((latest_write, refused_history_write))

        # The prior decision is intact and the replacement never landed.
        surviving = repo.load_decision("12345678Z", Period.from_year_and_code(2026, "2T"))
        assert surviving is not None
        assert surviving.reason_identity is decision.reason_identity
        assert (
            repo.secure_object_repository.load(
                repo.namespace,
                latest_key,
                expected_class=repo.sensitivity,
                max_supported_version=repo.schema_version,
            )
            is not None
        )
        assert len(repo.load_decision_history("12345678Z", Period.from_year_and_code(2026, "2T"))) == 1
