"""Native CLI acceptance for the cross-period IVA prorrata register."""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from click.testing import Result

from ....adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from ....adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from ....adapters.persistence.profile.tests.modelo_303_filed_disposition import modelo_303_filed_disposition
from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....application.prorrata_register.registered_operations import ProrrataEntryProjection
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.modelo import Modelo
from ....core.prorrata_register import (
    ProrrataEspecialTransitionKind,
    ProrrataProvisionalProvenance,
    ProrrataRegisterRegime,
    SectorDiferenciadoLetra,
)
from ....core.type_adapters import STR_KEYED_MAPPING_ADAPTER
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.calculations.registry.tests.registry_observations import registry_grounded_modelo_observation
from ....domain.prorrata_register.register import (
    ProrrataEspecialTransitionEvidence,
    ProrrataRegister,
    ProrrataRegisterEntry,
    SectorDefinition,
)
from ....tests.cli_envelope import unwrap_cli_result
from .._prorrata_register_cli import _entry_payload
from .._prorrata_register_payloads import (
    ProrrataDeclareSectorResult,
    ProrrataElectGeneralResult,
    ProrrataEntryPayload,
    ProrrataListResult,
    ProrrataSeedResult,
    ProrrataSeedSectorResult,
    ProrrataSeedSourcePayload,
    ProrrataSettleSectorResult,
    SectorDefinitionPayload,
)
from .cli_runner import invoke_cached_cli
from .runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]

_SOURCE_KIND = "aeat_sede_justificante"
_CAPTURED_AT = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_WHOLE_SEED_CURRENT_YEAR = 2026
_WHOLE_SEED_PRIOR_YEAR = 2025
_SECTOR_PRIOR_YEAR = 2024
_SECTOR_CURRENT_YEAR = 2025
_SETTLEMENT_PERIOD = "4T"
_PRIOR_DEFINITIVE = Decimal("87")
_PORCENTAJE_ID: CasillaId = validated_casilla_id(
    "iva.prorrata-porcentaje",
    surface="native prorrata register CLI test casilla id",
)
_SECTOR_ID = "arrendamiento"
_SECTOR_AUTHORIZATION = "AEAT-PRORRATA-2024-0001"
_PROFILE_FACTS = {
    "taxpayer_type.entity_type": "natural_person",
    "identity.name": "Native",
    "identity.surnames": "Prorrata",
    "activities.description": "synthetic prorrata register profile",
    "censo.activity_start_date": "2020-01-01",
    "tax_residence.jurisdiction_scope": "common_regime",
    "iva.regime": "GENERAL",
    "iva.m303_regime_composition": "general",
    "iva.redeme_enrolled": "false",
    "iva.cash_accounting_regime_enrolled": "false",
    "iva.voluntary_sii_enrolled": "false",
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
}


@pytest.fixture
def native_prorrata_profile(tmp_path: Path) -> Iterator[NativeCliProfileFixture]:
    """Register one encrypted profile and supervise its native runtime worker."""
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-prorrata-register", facts=_PROFILE_FACTS)
        yield profile


def _invoke(profile: NativeCliProfileFixture, *command: str) -> Result:
    if profile.label is None:
        raise AssertionError("native prorrata profile must be registered before invocation")
    close_active_bucket_session()
    result = invoke_cached_cli(
        (
            "--language",
            "en",
            "--format",
            "json",
            "--profile",
            profile.label,
            "--profile-secrets-stdin",
            *command,
        ),
        input=json.dumps({"profile_passphrase": profile.passphrase}),
    )
    assert profile.passphrase not in result.output
    return result


def _error_context(result: Result) -> dict[str, object]:
    assert result.exit_code != 0, result.output
    document = STR_KEYED_MAPPING_ADAPTER.validate_python(json.loads(result.output))
    error = STR_KEYED_MAPPING_ADAPTER.validate_python(document["error"])
    return STR_KEYED_MAPPING_ADAPTER.validate_python(error["context"])


def _assert_registered_refusal(
    context: dict[str, object],
    *,
    definition_id: str,
    reason: str,
    refusal_code: str,
) -> None:
    operation_id = context["operation_id"]
    assert isinstance(operation_id, str) and len(operation_id) == 64
    assert all(character in "0123456789abcdef" for character in operation_id)
    if "definition_id" in context:
        assert context["definition_id"] == definition_id
    assert context["reason"] == reason
    assert context["effect"] == "none"
    assert context["terminal_condition"] == "refused"
    assert context["refusal_code"] == refusal_code


def _law_determined_prior_revision_id() -> str:
    snapshot = published_snapshot(
        Modelo("303").value,
        filing_year=_WHOLE_SEED_PRIOR_YEAR,
        period=_SETTLEMENT_PERIOD,
    )
    return str(snapshot.revision.id)


def _store_prior_settlement_observation() -> None:
    """Write one locally stamped, registry-grounded prior 303 settlement observation."""
    repository = CalculationObservationRepository()
    casilla_values, source_headers = modelo_303_filed_disposition(
        {_PORCENTAJE_ID: _PRIOR_DEFINITIVE},
        source_locator="native-prorrata-prior-settlement",
    )
    observation = registry_grounded_modelo_observation(
        modelo=Modelo("303").value,
        filing_year=_WHOLE_SEED_PRIOR_YEAR,
        period=_SETTLEMENT_PERIOD,
        casilla_values=casilla_values,
    )
    repository.save(
        repository.prepare_observation_envelope(
            observation,
            source_kind=_SOURCE_KIND,
            captured_at=_CAPTURED_AT,
            source_headers=source_headers,
            stamped_revision_id=_law_determined_prior_revision_id(),
        )
    )


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_native_whole_seed_projects_stamped_source_and_refuses_without_source(
    native_prorrata_profile: NativeCliProfileFixture,
) -> None:
    _store_prior_settlement_observation()
    prior_revision_id = _law_determined_prior_revision_id()

    seeded_result = _invoke(
        native_prorrata_profile,
        "app",
        "ledger",
        "prorrata",
        "seed",
        "--ejercicio",
        str(_WHOLE_SEED_CURRENT_YEAR),
    )
    seeded = ProrrataSeedResult.model_validate_json(json.dumps(unwrap_cli_result(seeded_result)))
    expected_snapshot = RegistrySnapshotRef(
        modelo=Modelo("303").value,
        revision_id=prior_revision_id,
        modelo_year=_WHOLE_SEED_PRIOR_YEAR,
        period=_SETTLEMENT_PERIOD,
    )
    expected_entry = ProrrataEntryPayload(
        ejercicio=_WHOLE_SEED_CURRENT_YEAR,
        regime=ProrrataRegisterRegime.from_registry("general").value,
        especial_transition=None,
        sector_id=None,
        interrupted=False,
        provisional_percentage=str(_PRIOR_DEFINITIVE),
        provisional_provenance=ProrrataProvisionalProvenance.from_registry("carried_prior_definitiva").value,
        authorisation_reference=None,
        definitive_percentage=None,
        definitive_volume_con_derecho=None,
        definitive_volume_sin_derecho=None,
        source_observation_ref=f"303:{_WHOLE_SEED_PRIOR_YEAR}:{_SETTLEMENT_PERIOD}",
        source_registry_snapshot_refs=(expected_snapshot,),
        schema_version="2",
    )
    expected_source = ProrrataSeedSourcePayload(
        modelo=Modelo("303").value,
        filing_year=_WHOLE_SEED_PRIOR_YEAR,
        period=_SETTLEMENT_PERIOD,
        casilla_id=str(_PORCENTAJE_ID),
        stamped_revision_id=prior_revision_id,
        authority="local_prior_observation",
    )
    assert seeded.entry == expected_entry
    assert seeded.source == expected_source
    assert seeded.findings == []
    assert seeded.count == 1

    absent = _invoke(
        native_prorrata_profile,
        "app",
        "ledger",
        "prorrata",
        "seed",
        "--ejercicio",
        str(_WHOLE_SEED_CURRENT_YEAR + 1),
    )
    absent_context = _error_context(absent)
    _assert_registered_refusal(
        absent_context,
        definition_id="ledger.prorrata.seed",
        reason="seed_source_absent",
        refusal_code="REFUSED_PROFILE_PRORRATA_WHOLE_SEED",
    )
    assert absent_context["prior_ejercicio"] == str(_WHOLE_SEED_CURRENT_YEAR)

    listed_result = _invoke(native_prorrata_profile, "app", "ledger", "prorrata", "list")
    listed = ProrrataListResult.model_validate_json(json.dumps(unwrap_cli_result(listed_result)))
    assert str(listed.bucket_id) == str(seeded.bucket_id)
    assert listed.entries == [expected_entry]
    assert listed.sectors == []
    assert listed.count == 1


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_native_sector_election_settlement_seed_and_list_preserve_full_register(
    native_prorrata_profile: NativeCliProfileFixture,
    operation: PinnedAuthorityOperation,
) -> None:
    declared_result = _invoke(
        native_prorrata_profile,
        "app",
        "ledger",
        "prorrata",
        "declare-sector",
        "--sector-id",
        _SECTOR_ID,
        "--letra",
        SectorDiferenciadoLetra.from_registry("a").value,
        "--activity-code",
        "6820",
        "--activity-code",
        "6810",
    )
    declared = ProrrataDeclareSectorResult.model_validate_json(json.dumps(unwrap_cli_result(declared_result)))
    expected_sector = SectorDefinitionPayload(
        sector_id=_SECTOR_ID,
        letra=SectorDiferenciadoLetra.from_registry("a").value,
        member_activity_codes=["6820", "6810"],
    )
    assert declared.sector == expected_sector
    assert declared.count == 1

    missing_prior = _invoke(
        native_prorrata_profile,
        "app",
        "ledger",
        "prorrata",
        "seed-sector",
        "--ejercicio",
        str(_SECTOR_CURRENT_YEAR),
        "--sector-id",
        _SECTOR_ID,
    )
    missing_context = _error_context(missing_prior)
    _assert_registered_refusal(
        missing_context,
        definition_id="ledger.prorrata.seed_sector",
        reason="sector_prior_definitive_absent",
        refusal_code="REFUSED_PROFILE_PRORRATA_SECTOR_LIFECYCLE",
    )
    assert missing_context["ejercicio"] == str(_SECTOR_CURRENT_YEAR)
    assert missing_context["sector_id"] == _SECTOR_ID

    sector_alias = _invoke(
        native_prorrata_profile,
        "app",
        "ledger",
        "prorrata",
        "seed",
        "--ejercicio",
        str(_SECTOR_CURRENT_YEAR),
        "--sector",
        _SECTOR_ID,
    )
    alias_context = _error_context(sector_alias)
    assert alias_context["reason"] == "sector_requires_seed_sector"
    assert alias_context["sector_id"] == _SECTOR_ID
    assert alias_context["ejercicio"] == str(_SECTOR_CURRENT_YEAR)
    assert "operation_id" not in alias_context

    unchanged_result = _invoke(native_prorrata_profile, "app", "ledger", "prorrata", "list")
    unchanged = ProrrataListResult.model_validate_json(json.dumps(unwrap_cli_result(unchanged_result)))
    assert unchanged.entries == []
    assert unchanged.sectors == [expected_sector]
    assert unchanged.count == 0

    elected_result = _invoke(
        native_prorrata_profile,
        "app",
        "ledger",
        "prorrata",
        "elect-general",
        "--ejercicio",
        str(_SECTOR_PRIOR_YEAR),
        "--percentage",
        "50",
        "--sector",
        _SECTOR_ID,
        "--provenance",
        ProrrataProvisionalProvenance.from_registry("aeat_autorizada").value,
        "--reference",
        _SECTOR_AUTHORIZATION,
    )
    elected = ProrrataElectGeneralResult.model_validate_json(json.dumps(unwrap_cli_result(elected_result)))
    expected_election_entry = ProrrataEntryPayload(
        ejercicio=_SECTOR_PRIOR_YEAR,
        regime=ProrrataRegisterRegime.from_registry("general").value,
        especial_transition=None,
        sector_id=_SECTOR_ID,
        interrupted=False,
        provisional_percentage="50",
        provisional_provenance=ProrrataProvisionalProvenance.from_registry("aeat_autorizada").value,
        authorisation_reference=_SECTOR_AUTHORIZATION,
        definitive_percentage=None,
        definitive_volume_con_derecho=None,
        definitive_volume_sin_derecho=None,
        source_observation_ref=None,
        source_registry_snapshot_refs=(),
        schema_version="2",
    )
    assert elected.entry == expected_election_entry
    assert elected.count == 1
    assert str(elected.bucket_id) == str(declared.bucket_id)

    settlement_snapshot = operation.snapshot(
        Modelo("303").value,
        filing_year=_SECTOR_PRIOR_YEAR,
        period=_SETTLEMENT_PERIOD,
    ).snapshot_ref
    settled_result = _invoke(
        native_prorrata_profile,
        "app",
        "ledger",
        "prorrata",
        "settle-sector",
        "--ejercicio",
        str(_SECTOR_PRIOR_YEAR),
        "--sector-id",
        _SECTOR_ID,
        "--con-derecho-volume",
        "80000.00",
        "--sin-derecho-volume",
        "20000.00",
    )
    settled = ProrrataSettleSectorResult.model_validate_json(json.dumps(unwrap_cli_result(settled_result)))
    expected_settled_entry = expected_election_entry.model_copy(
        update={
            "definitive_percentage": "80",
            "definitive_volume_con_derecho": "80000.00",
            "definitive_volume_sin_derecho": "20000.00",
            "source_registry_snapshot_refs": (settlement_snapshot,),
        }
    )
    assert settled.entry == expected_settled_entry
    assert settled.count == 1

    seeded_result = _invoke(
        native_prorrata_profile,
        "app",
        "ledger",
        "prorrata",
        "seed-sector",
        "--ejercicio",
        str(_SECTOR_CURRENT_YEAR),
        "--sector-id",
        _SECTOR_ID,
    )
    seeded = ProrrataSeedSectorResult.model_validate_json(json.dumps(unwrap_cli_result(seeded_result)))
    expected_seeded_entry = ProrrataEntryPayload(
        ejercicio=_SECTOR_CURRENT_YEAR,
        regime=ProrrataRegisterRegime.from_registry("general").value,
        especial_transition=None,
        sector_id=_SECTOR_ID,
        interrupted=False,
        provisional_percentage="80",
        provisional_provenance=ProrrataProvisionalProvenance.from_registry("carried_prior_definitiva").value,
        authorisation_reference=None,
        definitive_percentage=None,
        definitive_volume_con_derecho=None,
        definitive_volume_sin_derecho=None,
        source_observation_ref=f"prorrata-register:{_SECTOR_PRIOR_YEAR}:{_SECTOR_ID}",
        source_registry_snapshot_refs=(settlement_snapshot,),
        schema_version="2",
    )
    assert seeded.entry == expected_seeded_entry
    assert seeded.prior_ejercicio == _SECTOR_PRIOR_YEAR
    assert seeded.count == 2

    listed_result = _invoke(native_prorrata_profile, "app", "ledger", "prorrata", "list")
    listed = ProrrataListResult.model_validate_json(json.dumps(unwrap_cli_result(listed_result)))
    assert str(listed.bucket_id) == str(seeded.bucket_id)
    assert listed.entries == [expected_settled_entry, expected_seeded_entry]
    assert listed.sectors == [expected_sector]
    assert listed.count == 2


def test_upsert_entry_preserves_sector_definitions(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="ce2eee1d-3086-41f0-8c9c-bab63890f9f1"):
        repository = ProrrataRegisterRepository()
        definition = SectorDefinition(
            sector_id="comercio",
            letra=SectorDiferenciadoLetra.from_registry("a"),
            member_activity_codes=("4711",),
        )
        repository.save(
            ProrrataRegister(
                entries=(
                    ProrrataRegisterEntry(
                        ejercicio=2024,
                        regime=ProrrataRegisterRegime.from_registry("general"),
                        especial_transition=None,
                        source_registry_snapshot_refs=(),
                    ),
                ),
                sector_definitions=(definition,),
            )
        )

        repository.upsert_entry(
            ProrrataRegisterEntry(
                ejercicio=2025,
                regime=ProrrataRegisterRegime.from_registry("especial"),
                especial_transition=None,
                provisional_percentage=Decimal("60"),
                provisional_provenance=ProrrataProvisionalProvenance.from_registry("aeat_autorizada"),
                authorisation_reference="AEAT-PRORRATA-2025-0001",
                source_registry_snapshot_refs=(),
            )
        )

        reloaded = repository.load()
        assert reloaded.sector_definitions == (definition,)
        assert {entry.ejercicio for entry in reloaded.entries} == {2024, 2025}


def test_upsert_sector_definition_preserves_entries(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="77873c85-0589-4b50-b184-7e8f33dc4471"):
        repository = ProrrataRegisterRepository()
        entry = ProrrataRegisterEntry(
            ejercicio=2025,
            regime=ProrrataRegisterRegime.from_registry("especial"),
            especial_transition=None,
            provisional_percentage=Decimal("60"),
            provisional_provenance=ProrrataProvisionalProvenance.from_registry("aeat_autorizada"),
            authorisation_reference="AEAT-PRORRATA-2025-0001",
            source_registry_snapshot_refs=(),
        )
        repository.save(ProrrataRegister(entries=(entry,)))

        repository.upsert_sector_definition(
            SectorDefinition(
                sector_id="comercio",
                letra=SectorDiferenciadoLetra.from_registry("a"),
                member_activity_codes=("4711",),
            )
        )

        reloaded = repository.load()
        assert reloaded.entries == (entry,)
        assert reloaded.is_sectorized
        assert reloaded.sector_ids() == ("comercio",)


@pytest.mark.parametrize(
    ("regime", "kind", "expected_token"),
    [
        (
            ProrrataRegisterRegime.from_registry("especial"),
            ProrrataEspecialTransitionKind.from_registry("opcion"),
            "opcion",
        ),
        (
            ProrrataRegisterRegime.from_registry("general"),
            ProrrataEspecialTransitionKind.from_registry("revocacion"),
            "revocacion",
        ),
    ],
)
def test_entry_payload_round_trips_the_especial_transition_kind_as_a_stable_token(
    regime: ProrrataRegisterRegime,
    kind: ProrrataEspecialTransitionKind,
    expected_token: str,
) -> None:
    """The strict payload accepts a real entry's serialized form and re-emits the token.

    ``ProrrataEspecialTransitionPayload.kind`` is enum-typed under the strict
    :class:`OutputSchema` config, so projecting a register entry must reconstruct
    the enum member rather than hand it the bare string ``model_dump(mode='json')``
    renders. The emitted value stays the untranslated transport token.
    """
    entry = ProrrataRegisterEntry(
        ejercicio=2024,
        regime=regime,
        especial_transition=ProrrataEspecialTransitionEvidence(
            kind=kind,
            evidence_reference="acta-2024-001",
        ),
        source_registry_snapshot_refs=(),
    )

    payload = _entry_payload(ProrrataEntryProjection.from_entry(entry))

    assert payload.especial_transition is not None
    assert payload.especial_transition.kind == kind
    emitted = payload.model_dump(mode="json")["especial_transition"]
    assert emitted == {"kind": expected_token, "evidence_reference": "acta-2024-001"}
