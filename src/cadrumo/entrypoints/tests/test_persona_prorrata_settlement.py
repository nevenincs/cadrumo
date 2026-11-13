"""A verified last Modelo 303 of the year exports before it is filed, and filing leaves the register it exported.

LIVA art. 105.Cuatro settles the definitive prorrata in the year's last return and art. 105.Uno
reads the filed definitive as the next year's provisional one; RIVA art. 28.1.2º keeps an especial
option for at least three years. The persona's fourth quarter is taken through the registered
operations in the order an operator runs them: calculate, verify, export, file. The export must
write the file with the register as filing will leave it, and must write nothing to the register.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Final

import pytest

from ...application.modelo.export_projection import ModeloExportPublicResultV3
from ...application.modelo.m303_attestation_operation import (
    MODELO_WORK_M303_ATTESTATION_OPERATION_DEFINITION_ID,
    ModeloWorkM303AttestationPublicResultV2,
    ModeloWorkM303AttestationRequest,
)
from ...application.modelo.operation_shared import (
    MODELO_EXPORT_OPERATION_DEFINITION_ID,
    MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
    MODELO_WORK_FILE_OPERATION_DEFINITION_ID,
    MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
)
from ...application.modelo.work_calculation_contracts import (
    ModeloWorkCalculateOrdinaryM303EvidenceRequestV2,
    ModeloWorkCalculatePublicResultV3,
    ModeloWorkCalculateRequest,
)
from ...application.modelo.work_create_operation import (
    MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
    ModeloWorkCreateRequest,
    ModeloWorkCreateSuccess,
)
from ...application.modelo.work_export_contracts import ModeloExportRequest
from ...application.modelo.work_filing_contracts import (
    ModeloWorkFileApproval,
    ModeloWorkFilePublicResultV2,
    ModeloWorkFileRequest,
)
from ...application.modelo.work_verification_contracts import ModeloWorkVerifyPublicResultV2, ModeloWorkVerifyRequest
from ...application.operations.public_period import PublicPeriod
from ...application.operations.public_scalar import PublicDecimal, restore_scalar
from ...application.prorrata_register.operation_requests import (
    PRORRATA_DECLARE_SECTOR_OPERATION_DEFINITION_ID,
    PRORRATA_ELECT_ESPECIAL_OPERATION_DEFINITION_ID,
    PRORRATA_LIST_OPERATION_DEFINITION_ID,
    PRORRATA_SEED_OPERATION_DEFINITION_ID,
    ProrrataDeclareSectorRequest,
    ProrrataElectEspecialRequest,
    ProrrataListRequest,
    ProrrataSeedRequest,
)
from ...application.prorrata_register.projection_contracts import (
    ProrrataEntryProjection,
    ProrrataListProjection,
    ProrrataMutationProjection,
)
from ...application.prorrata_register.settlement import (
    PRORRATA_PORCENTAJE_CASILLA,
    PRORRATA_SETTLEMENT_ESPECIAL_CONTINUATION_LOCALE_KEY,
)
from ...core.modelo_export_artefact import ModeloExportArtefact
from ...domain.calculations.registry.authority import bundled_indexed_authority
from ...domain.calculations.registry.export_parse import parse_export_payload
from ...domain.calculations.registry.schema_form_layouts import FormContextFieldBlock
from ...tests.personas import YearEnvelope, read_persona
from .persona_materialisation import (
    PERSONA_ACTOR,
    PersonaMaterialisationError,
    PersonaWorld,
    ReplayScope,
    attest_before_first_calculation,
    materialised_persona,
    run_operation,
    settle_operation,
    year_envelope,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PERSONA: Final = "intracomunitario-desarrollador"
#: A persona with no operation exempt without the right to deduct, whose year has no prorrata to apportion.
_PERSONA_WITHOUT_PRORRATA: Final = "autonomo-electricista"
_FIRST_THREE: Final = ("1T", "2T", "3T")
_LAST: Final = "4T"
_ESPECIAL_REFERENCE: Final = "test:persona-prorrata-settlement"
_ESPECIAL_PROVENANCE: Final = "aeat_autorizada"


def _envelope() -> YearEnvelope:
    with bundled_indexed_authority().operation() as operation:
        return year_envelope(operation)


def _horizons() -> list[int]:
    """Every horizon of the registry's envelope whose previous year is supported, the registry's own included."""
    envelope = _envelope()
    return list(range(envelope.floor + 1, envelope.horizon + 1))


def _persona_for(persona_id: str, horizon: int) -> None:
    """Read the persona as the replay will, so a horizon below the floor fails here and not in the middle of a run."""
    envelope = replace(_envelope(), horizon=horizon)
    read_persona(persona_id, envelope=envelope, omit_below_floor=horizon != _envelope().horizon)


def _calculate(world: PersonaWorld, year: int, period: str) -> tuple[str, str, Mapping[str, object]]:
    """Create and calculate one Modelo 303 quarter as an ordinary filer; return its work unit, revision and casillas."""
    created = settle_operation(
        world,
        MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
        ModeloWorkCreateRequest(
            profile_id=world.profile_id,
            modelo="303",
            period=PublicPeriod(filing_year=year, code=period),
            actor=PERSONA_ACTOR,
        ),
    )
    outcome = getattr(created, "outcome", None)
    assert isinstance(outcome, ModeloWorkCreateSuccess), outcome
    work_unit_id = outcome.unit.work_unit_id
    attest_before_first_calculation(world, modelo="303", year=year, period=period, work_unit_id=work_unit_id)
    evidence = ModeloWorkCalculateOrdinaryM303EvidenceRequestV2(joint_return_elected=False)
    if period == _LAST:
        attestation = ModeloWorkM303AttestationRequest(
            profile_id=world.profile_id,
            work_unit_id=work_unit_id,
            observed_at=datetime(year, 12, 31, 12, tzinfo=UTC),
            actor=PERSONA_ACTOR,
        )
        attested = run_operation(
            world,
            MODELO_WORK_M303_ATTESTATION_OPERATION_DEFINITION_ID,
            attestation,
            ModeloWorkM303AttestationPublicResultV2,
            subject=attestation.subject_ref,
        )
        evidence = ModeloWorkCalculateOrdinaryM303EvidenceRequestV2(
            joint_return_elected=False,
            m303_exonerado_390_attachment_id=attested.attachment_id,
            m303_exonerado_390_sha256=attested.sha256,
        )
    calculated = run_operation(
        world,
        MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
        ModeloWorkCalculateRequest(
            work_unit_id=work_unit_id, actor=PERSONA_ACTOR, ordinary_m303_filing_evidence=evidence
        ),
        ModeloWorkCalculatePublicResultV3,
        subject=work_unit_id,
    )
    values = {item.key: restore_scalar(item.value) for item in calculated.calculation.casilla_values}
    return work_unit_id, calculated.calculation_revision_id, values


def _verify(world: PersonaWorld, work_unit_id: str, revision_id: str) -> ModeloWorkVerifyPublicResultV2:
    return run_operation(
        world,
        MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
        ModeloWorkVerifyRequest(calculation_revision_id=revision_id, actor=PERSONA_ACTOR),
        ModeloWorkVerifyPublicResultV2,
        subject=work_unit_id,
    )


def _file(world: PersonaWorld, work_unit_id: str, revision_id: str, report_id: str) -> None:
    run_operation(
        world,
        MODELO_WORK_FILE_OPERATION_DEFINITION_ID,
        ModeloWorkFileRequest(
            approval=ModeloWorkFileApproval(calculation_revision_id=revision_id, verification_report_id=report_id),
            actor=PERSONA_ACTOR,
        ),
        ModeloWorkFilePublicResultV2,
        subject=work_unit_id,
    )


def _published_export(world: PersonaWorld, work_unit_id: str, revision_id: str, output: Path) -> object:
    """Export the revision and return whatever the operation published, a refusal included."""
    return settle_operation(
        world,
        MODELO_EXPORT_OPERATION_DEFINITION_ID,
        ModeloExportRequest(
            calculation_revision_id=revision_id,
            output_path=str(output),
            artefact=ModeloExportArtefact.FICHERO_BOE,
            actor=PERSONA_ACTOR,
        ),
        subject=work_unit_id,
    )


def _export(world: PersonaWorld, work_unit_id: str, revision_id: str, output: Path) -> ModeloExportPublicResultV3:
    exported = _published_export(world, work_unit_id, revision_id, output)
    assert isinstance(exported, ModeloExportPublicResultV3), exported
    return exported


def _entry(world: PersonaWorld, year: int, sector_id: str | None = None) -> ProrrataEntryProjection | None:
    listed = run_operation(
        world,
        PRORRATA_LIST_OPERATION_DEFINITION_ID,
        ProrrataListRequest(profile_id=world.profile_id),
        ProrrataListProjection,
    )
    return next((entry for entry in listed.entries if (entry.ejercicio, entry.sector_id) == (year, sector_id)), None)


def _file_the_first_three_quarters(world: PersonaWorld, year: int) -> None:
    for period in _FIRST_THREE:
        work_unit_id, revision_id, _values = _calculate(world, year, period)
        verified = _verify(world, work_unit_id, revision_id)
        assert verified.granted_verificado_completo, f"{period}: {verified.completeness_status}"
        _file(world, work_unit_id, revision_id, verified.verification_report_id)


def _exported_election_fields(year: int, payload: bytes) -> dict[str, str]:
    """The raw option and revocation fields of the exported fichero, by their form context ids."""
    with bundled_indexed_authority().operation() as operation:
        snapshot = operation.reading_snapshot("303", filing_year=year, period=_LAST)
        form_layout = operation.form_layout("303", snapshot.revision.id)
        assert form_layout is not None
        blocks = {
            block.id: block
            for page in form_layout.pages
            for section in page.sections
            for block in section.blocks
            if isinstance(block, FormContextFieldBlock)
        }
        layout = operation.revision_with_export_layouts("303", snapshot.revision.id).export_layouts[0]
        parsed = parse_export_payload(layout, payload).fields
    wanted = {name: blocks[name].export_field_id for name in ("opcion-prorrata", "revocacion-prorrata")}
    return {
        name: next(field.raw for field in parsed if field.field_id == field_id) for name, field_id in wanted.items()
    }


@pytest.mark.parametrize("horizon", _horizons())
def test_the_last_return_exports_before_filing_and_filing_leaves_the_register_it_exported(
    tmp_path: Path, horizon: int
) -> None:
    _export_then_file_the_last_return(tmp_path, _PERSONA, horizon)


def test_a_persona_without_prorrata_exports_before_filing_and_files_the_ninguna_entry(tmp_path: Path) -> None:
    entry = _export_then_file_the_last_return(tmp_path, _PERSONA_WITHOUT_PRORRATA, _top_horizon())

    assert entry.regime == "ninguna"
    assert entry.definitive_percentage is not None
    assert Decimal(entry.definitive_percentage.decimal) == Decimal("100")


def _export_then_file_the_last_return(tmp_path: Path, persona_id: str, horizon: int) -> ProrrataEntryProjection:
    _persona_for(persona_id, horizon)
    year = horizon - 1
    with materialised_persona(persona_id, tmp_path / "world", ReplayScope.RECORDS, horizon=horizon) as materialised:
        world = materialised.world
        _file_the_first_three_quarters(world, year)
        assert _entry(world, year) is None

        work_unit_id, revision_id, values = _calculate(world, year, _LAST)
        definitive = values[str(PRORRATA_PORCENTAJE_CASILLA)]
        assert isinstance(definitive, Decimal)
        verified = _verify(world, work_unit_id, revision_id)
        assert verified.granted_verificado_completo, verified.completeness_status

        output = tmp_path / "m303-4t.txt"
        _export(world, work_unit_id, revision_id, output)

        assert _entry(world, year) is None, "export must write nothing to the register"
        assert _exported_election_fields(year, output.read_bytes()) == {
            "opcion-prorrata": "2",
            "revocacion-prorrata": "2",
        }

        _file(world, work_unit_id, revision_id, verified.verification_report_id)

        entry = _entry(world, year)
        assert entry is not None
        assert entry.definitive_percentage is not None
        assert Decimal(entry.definitive_percentage.decimal) == definitive
        assert entry.especial_transition is None

        seeded = settle_operation(
            world,
            PRORRATA_SEED_OPERATION_DEFINITION_ID,
            ProrrataSeedRequest(profile_id=world.profile_id, ejercicio=year + 1),
        )
        assert isinstance(seeded, ProrrataMutationProjection)
        assert seeded.outcome == "success"
        assert seeded.entry is not None
        assert seeded.entry.provisional_percentage is not None
        assert Decimal(seeded.entry.provisional_percentage.decimal) == definitive
        return entry


def _declare_prior_year_especial(world: PersonaWorld, year: int) -> None:
    elected = settle_operation(
        world,
        PRORRATA_ELECT_ESPECIAL_OPERATION_DEFINITION_ID,
        ProrrataElectEspecialRequest(
            profile_id=world.profile_id,
            ejercicio=year - 1,
            percentage=PublicDecimal(decimal="100"),
            provenance=_ESPECIAL_PROVENANCE,
            reference=_ESPECIAL_REFERENCE,
        ),
    )
    assert isinstance(elected, ProrrataMutationProjection)
    assert elected.outcome == "success", elected.refusal


def _declare_sector(world: PersonaWorld) -> None:
    declared = settle_operation(
        world,
        PRORRATA_DECLARE_SECTOR_OPERATION_DEFINITION_ID,
        ProrrataDeclareSectorRequest(
            profile_id=world.profile_id, sector_id="software", letra="a", member_activity_codes=("763",)
        ),
    )
    assert isinstance(declared, ProrrataMutationProjection)
    assert declared.outcome == "success", declared.refusal


def _top_horizon() -> int:
    return _envelope().horizon


def _refused_export(world: PersonaWorld, work_unit_id: str, revision_id: str, output: Path) -> str:
    """The text of the refusal the export of the revision publishes; the file must not exist."""
    try:
        published = _published_export(world, work_unit_id, revision_id, output)
    except PersonaMaterialisationError as error:
        text = str(error)
    else:
        assert not isinstance(published, ModeloExportPublicResultV3), "the export succeeded"
        text = repr(published)
    assert not output.exists(), text
    return text


def _export_refuses_a_register_declared_after_verification(
    tmp_path: Path, declare: Callable[[PersonaWorld, int], None], export_code: str
) -> None:
    """The export of a verified revision refuses the register declared after it and writes nothing."""
    horizon = _top_horizon()
    year = horizon - 1
    with materialised_persona(_PERSONA, tmp_path / "world", ReplayScope.RECORDS, horizon=horizon) as materialised:
        world = materialised.world
        _file_the_first_three_quarters(world, year)
        work_unit_id, revision_id, _values = _calculate(world, year, _LAST)
        verified = _verify(world, work_unit_id, revision_id)
        assert verified.granted_verificado_completo, verified.completeness_status

        declare(world, year)

        refused = _refused_export(world, work_unit_id, revision_id, tmp_path / "refused.txt")
        assert export_code in refused, refused
        assert _entry(world, year) is None


def _verify_refuses_a_register_declared_before_calculation(
    tmp_path: Path, declare: Callable[[PersonaWorld, int], None], finding_key: str | None
) -> None:
    """A last return calculated under a register that cannot cover the year does not verify.

    A register the calculation itself already refuses never reaches verification, so ``finding_key``
    is only asserted for the register the calculation accepts.
    """
    horizon = _top_horizon()
    year = horizon - 1
    with materialised_persona(_PERSONA, tmp_path / "world", ReplayScope.RECORDS, horizon=horizon) as materialised:
        world = materialised.world
        _file_the_first_three_quarters(world, year)
        declare(world, year)
        try:
            work_unit_id, revision_id, _values = _calculate(world, year, _LAST)
        except PersonaMaterialisationError:
            assert finding_key is None
            return
        verified = _verify(world, work_unit_id, revision_id)
        assert not verified.granted_verificado_completo
        if finding_key is not None:
            assert finding_key in verified.verification.model_dump_json()


def test_an_especial_year_before_the_last_return_without_a_declaration_is_refused_at_export(tmp_path: Path) -> None:
    _export_refuses_a_register_declared_after_verification(
        tmp_path, _declare_prior_year_especial, "REFUSED_PROFILE_PRORRATA_SETTLEMENT_ESPECIAL_CONTINUATION"
    )


def test_an_especial_year_before_the_last_return_without_a_declaration_is_refused_at_verify(tmp_path: Path) -> None:
    _verify_refuses_a_register_declared_before_calculation(
        tmp_path, _declare_prior_year_especial, PRORRATA_SETTLEMENT_ESPECIAL_CONTINUATION_LOCALE_KEY
    )


def test_a_declared_sector_without_its_entry_is_refused_at_export(tmp_path: Path) -> None:
    _export_refuses_a_register_declared_after_verification(
        tmp_path, lambda world, _year: _declare_sector(world), "REFUSED_MODELO_PROFILE_READINESS"
    )


def test_a_declared_sector_without_its_entry_is_refused_at_verify(tmp_path: Path) -> None:
    _verify_refuses_a_register_declared_before_calculation(tmp_path, lambda world, _year: _declare_sector(world), None)
