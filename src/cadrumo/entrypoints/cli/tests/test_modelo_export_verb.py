"""CLI surface tests for ``aeat app modelo export``."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from click.testing import Result

from cadrumo.application.workflow.persistence import workflow_state_repository

from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....core import CasillaId, Period, validated_casilla_id
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionState,
    ModeloCode,
    WorkUnit,
    derive_calculation_revision_id,
    derive_work_unit_id,
    upsert_calculation_revision,
    upsert_work_unit,
)
from ....domain.user_profile.values import UserProfileFact
from ....tests.cli_envelope import unwrap_envelope_notices as _notices
from ....tests.cli_envelope import unwrap_schema_envelope as _payload
from ....tests.cli_runner import invoke_cached_cli
from ....tests.profile_capsule import set_active_test_profile_facts
from ....tests.registry_observations import registry_grounded_observations
from ....tests.registry_revision import active_registry_revision_id
from ._modelo_review_package_support import seed_exportable_modelo_revision
from ._strict_cli_fixture_support import binding_isolated_backend

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

__all__ = ["binding_isolated_backend"]


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


def _seed_work_unit_only(*, modelo: str = "130", filing_year: int = 2026, period: str = "1T") -> str:
    state = workflow_state_repository().load()
    bucket_id = state.active_profile_bucket_id()
    assert bucket_id is not None
    revision_id = active_registry_revision_id(modelo=modelo, filing_year=filing_year, period=period)
    filing_period = Period.from_year_and_code(filing_year, period)
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=filing_period,
        revision_id=revision_id,
    )
    now = datetime.now(UTC)
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode(modelo),
        filing_year=filing_year,
        period=filing_period,
        revision_id=revision_id,
        name=f"{modelo}-{filing_year}-{period}",
        created_at=now,
        updated_at=now,
    )
    repo = WorkUnitCatalogueRepository()
    repo.save(upsert_work_unit(repo.load(), work_unit))
    return work_unit_id


def _seed_work_unit_with_draft_revision() -> tuple[str, str]:
    work_unit_id = _seed_work_unit_only()
    now = datetime.now(UTC)
    calculation_revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    revision = CalculationRevision(
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        created_at=now,
        updated_at=now,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    cr_repo = CalculationRevisionCatalogueRepository()
    cr_repo.save(upsert_calculation_revision(cr_repo.load(), revision))
    return work_unit_id, calculation_revision_id


def _seed_verified_revision_without_inputs(*, modelo: str, filing_year: int, period: str) -> tuple[str, str]:
    state = workflow_state_repository().load()
    bucket_id = state.active_profile_bucket_id()
    assert bucket_id is not None
    revision_id = active_registry_revision_id(modelo=modelo, filing_year=filing_year, period=period)
    filing_period = Period.from_year_and_code(filing_year, period)
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=filing_period,
        revision_id=revision_id,
    )
    now = datetime.now(UTC)
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode(modelo),
        filing_year=filing_year,
        period=filing_period,
        revision_id=revision_id,
        name=f"{modelo}-{filing_year}-{period}",
        created_at=now,
        updated_at=now,
    )
    WorkUnitCatalogueRepository().save(upsert_work_unit(WorkUnitCatalogueRepository().load(), work_unit))
    calculation_revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    revision = CalculationRevision(
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        created_at=now,
        updated_at=now,
        verified_at=now,
        verified_by="operator",
        filing_instance_evidence=None,
        source_provenance=(),
    )
    cr_repo = CalculationRevisionCatalogueRepository()
    cr_repo.save(upsert_calculation_revision(cr_repo.load(), revision))
    return work_unit_id, calculation_revision_id


_M111_CASILLA_03: CasillaId = validated_casilla_id("03", surface="modelo 111 export test casilla")
_M111_CASILLA_06: CasillaId = validated_casilla_id("06", surface="modelo 111 export test casilla")
_M111_CASILLA_09: CasillaId = validated_casilla_id("09", surface="modelo 111 export test casilla")
_M111_CASILLA_12: CasillaId = validated_casilla_id("12", surface="modelo 111 export test casilla")
_M111_CASILLA_15: CasillaId = validated_casilla_id("15", surface="modelo 111 export test casilla")
_M111_CASILLA_18: CasillaId = validated_casilla_id("18", surface="modelo 111 export test casilla")
_M111_CASILLA_21: CasillaId = validated_casilla_id("21", surface="modelo 111 export test casilla")
_M111_CASILLA_24: CasillaId = validated_casilla_id("24", surface="modelo 111 export test casilla")
_M111_CASILLA_27: CasillaId = validated_casilla_id("27", surface="modelo 111 export test casilla")
_M111_CASILLA_29: CasillaId = validated_casilla_id("29", surface="modelo 111 export test casilla")
_M202_CASILLA_01: CasillaId = validated_casilla_id("01", surface="modelo 202 export test casilla")
_M202_2023_2024_PRIOR_PAYMENTS_BINDING = "modelo-202-2023-2024-pagos-fraccionados-anteriores"

_MODELO_111_INPUTS: dict[CasillaId, str] = {
    _M111_CASILLA_03: "180.25",
    _M111_CASILLA_06: "12.10",
    _M111_CASILLA_09: "300.00",
    _M111_CASILLA_12: "14.40",
    _M111_CASILLA_15: "25.00",
    _M111_CASILLA_18: "0.50",
    _M111_CASILLA_21: "7.00",
    _M111_CASILLA_24: "8.00",
    _M111_CASILLA_27: "9.00",
    _M111_CASILLA_29: "40.00",
}


def _set_export_profile_name() -> None:
    set_active_test_profile_facts(
        (
            UserProfileFact(path="identity.name", value="Ana"),
            UserProfileFact(path="identity.surnames", value="Export Test"),
            UserProfileFact(path="activities.description", value="Consulting"),
            # Modelo 111 declares whether the withholder is a colegio
            # concertado in its own header field; the producer refuses an
            # undeclared value rather than assume one.
            UserProfileFact(path="withholding.colegio_concertado", value=False),
        ),
    )


def _set_emilio_legal_entity_export_profile() -> None:
    set_active_test_profile_facts(
        (
            UserProfileFact(path="identity.tax_id", value="B12345674"),
            UserProfileFact(path="identity.name", value="Emilio"),
            UserProfileFact(path="identity.surnames", value="Corporate Persona"),
            UserProfileFact(path="identity.legal_name", value="Emilio Consulting Sociedad Limitada"),
            UserProfileFact(path="activities.description", value="Consulting"),
            UserProfileFact(path="withholding.colegio_concertado", value=False),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
            UserProfileFact(path="withholding.has_employees", value=True),
            UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
            UserProfileFact(path="taxpayer_type.legal_entity_form", value="sl"),
            UserProfileFact(path="taxpayer_type.irpf_income_categories", value=""),
            UserProfileFact(path="taxpayer_type.incn_prior_12_months", value="500000"),
            UserProfileFact(path="taxpayer_type.new_entity_first_two_profit_periods", value=False),
            UserProfileFact(path="taxpayer_type.tributacion_estado_porcentaje", value="100"),
        ),
    )


def _clear_export_profile_surnames() -> None:
    set_active_test_profile_facts(
        (
            UserProfileFact(path="identity.surnames", value=None),
            UserProfileFact(path="activities.description", value="Consulting"),
        ),
    )


def _seed_modelo_111_revisions(
    *,
    states: tuple[CalculationRevisionState, ...],
    current_index: int | None = None,
    filed_index: int | None = None,
    filing_year: int = 2026,
    period: str = "1T",
) -> tuple[str, tuple[str, ...]]:
    state = workflow_state_repository().load()
    bucket_id = state.active_profile_bucket_id()
    assert bucket_id is not None
    registry_revision_id = active_registry_revision_id(modelo="111", filing_year=filing_year, period=period)
    filing_period = Period.from_year_and_code(filing_year, period)
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo="111",
        filing_year=filing_year,
        period=filing_period,
        revision_id=registry_revision_id,
    )
    now = datetime.now(UTC)
    revision_ids: list[str] = []
    revisions: list[CalculationRevision] = []
    for index, state_value in enumerate(states):
        inputs = {**_MODELO_111_INPUTS, _M111_CASILLA_03: f"{180 + index}.25"}
        calculation_revision_id = derive_calculation_revision_id(
            work_unit_id=work_unit_id,
            input_values_by_casilla_id=inputs,
            binding_overrides={},
            casilla_values={},
            filing_instance_evidence=None,
            source_provenance=(),
        )
        revision_ids.append(calculation_revision_id)
        revisions.append(
            CalculationRevision(
                calculation_revision_id=calculation_revision_id,
                work_unit_id=work_unit_id,
                state=state_value,
                input_values_by_casilla_id=inputs,
                created_at=now,
                updated_at=now,
                verified_at=now
                if state_value in {CalculationRevisionState.VERIFICADO_COMPLETO, CalculationRevisionState.PRESENTADO}
                else None,
                verified_by="operator"
                if state_value in {CalculationRevisionState.VERIFICADO_COMPLETO, CalculationRevisionState.PRESENTADO}
                else None,
                filed_at=now if state_value is CalculationRevisionState.PRESENTADO else None,
                filed_by="operator" if state_value is CalculationRevisionState.PRESENTADO else None,
                filing_instance_evidence=None,
                source_provenance=(),
            ),
        )

    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode("111"),
        filing_year=filing_year,
        period=filing_period,
        revision_id=registry_revision_id,
        name=f"111-{filing_year}-{period}",
        created_at=now,
        updated_at=now,
        current_calculation_revision_id=revision_ids[current_index] if current_index is not None else None,
        filed_calculation_revision_id=revision_ids[filed_index] if filed_index is not None else None,
    )
    wu_repo = WorkUnitCatalogueRepository()
    wu_repo.save(upsert_work_unit(wu_repo.load(), work_unit))
    cr_repo = CalculationRevisionCatalogueRepository()
    catalogue = cr_repo.load()
    for revision in revisions:
        catalogue = upsert_calculation_revision(catalogue, revision)
    cr_repo.save(catalogue)
    return work_unit_id, tuple(revision_ids)


def _seed_exportable_modelo_202_2024_revision() -> tuple[str, str]:
    """Persist a verified-complete M202 2024 1P revision with the 2023-2024 binding channel."""

    state = workflow_state_repository().load()
    bucket_id = state.active_profile_bucket_id()
    assert bucket_id is not None
    revision_id = active_registry_revision_id(modelo="202", filing_year=2024, period="1P")
    filing_period = Period.from_year_and_code(2024, "1P")
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo="202",
        filing_year=2024,
        period=filing_period,
        revision_id=revision_id,
    )
    inputs = {_M202_CASILLA_01: "0"}
    binding_overrides = {_M202_2023_2024_PRIOR_PAYMENTS_BINDING: "0"}
    casilla_values = {_M202_CASILLA_01: Decimal("0")}
    calculation_revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id=inputs,
        binding_overrides=binding_overrides,
        casilla_values=casilla_values,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    now = datetime.now(UTC)
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode("202"),
        filing_year=2024,
        period=filing_period,
        revision_id=revision_id,
        name="202-2024-1P",
        created_at=now,
        updated_at=now,
        current_calculation_revision_id=calculation_revision_id,
    )
    WorkUnitCatalogueRepository().save(upsert_work_unit(WorkUnitCatalogueRepository().load(), work_unit))
    revision = CalculationRevision(
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        input_values_by_casilla_id=inputs,
        binding_overrides=binding_overrides,
        casilla_values=casilla_values,
        observations=registry_grounded_observations(
            modelo="202",
            filing_year=2024,
            period="1P",
            casilla_values=casilla_values,
        ),
        created_at=now,
        updated_at=now,
        verified_at=now,
        verified_by="Emilio",
        filing_instance_evidence=None,
        source_provenance=(),
    )
    cr_repo = CalculationRevisionCatalogueRepository()
    cr_repo.save(upsert_calculation_revision(cr_repo.load(), revision))
    return work_unit_id, calculation_revision_id


def test_export_modelo_111_end_to_end_writes_file_with_composed_headers(
    tmp_path: Path,
) -> None:
    """Exporting a verified-complete modelo-111 revision end-to-end
    writes a fichero-BOE file without a header-validation error.

    Modelo 111 declares ``declaration_type``, ``surnames``, and
    ``name`` as required export header keys. The export service must
    compose all of them — the operator name from the persisted profile
    facts — or ``_header_field_value`` raises FilingExportValidationError.
    This locks the header-composition contract: a real registry-backed
    export of a non-130 modelo succeeds.
    """

    _set_export_profile_name()
    work_unit_id, _ = seed_exportable_modelo_revision(input_values_by_casilla_id=_MODELO_111_INPUTS)
    out = tmp_path / "modelo-111.txt"

    result = _invoke(
        ["app", "modelo", "export", work_unit_id, "--output", str(out)],
    )

    assert result.exit_code == 0, result.output
    assert "evidence_status\tlocal_export_not_official_aeat_filing_evidence" in result.output
    assert "not official AEAT filing evidence" in result.output
    assert "justificante" in result.output
    assert "consulta de declaraciones presentadas" in result.output
    assert "CSV cotejo" in result.output
    assert "aeat app modelo reconcile pull --modelo 111 --year 2026 --period 1T" in result.output
    assert out.exists()
    assert out.stat().st_size > 0


def test_export_modelo_111_emilio_legal_entity_uses_profile_identity_name(
    tmp_path: Path,
) -> None:
    _set_emilio_legal_entity_export_profile()
    _, (calculation_revision_id,) = _seed_modelo_111_revisions(
        states=(CalculationRevisionState.VERIFICADO_COMPLETO,),
        current_index=0,
        filing_year=2024,
        period="1T",
    )
    out = tmp_path / "modelo-111-2024-1T.boe"

    result = _invoke(
        [
            "app",
            "modelo",
            "export",
            "--modelo",
            "111",
            "--year",
            "2024",
            "--period",
            "1T",
            "--output",
            str(out),
            "--by",
            "Emilio",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "operation\tmodelo.export" in result.output
    assert f"calculation_revision_id\t{calculation_revision_id}" in result.output
    assert "modelo\t111" in result.output
    assert "filing_year\t2024" in result.output
    assert "period\t2024 1T" in result.output
    assert out.exists()
    assert out.stat().st_size > 0


def test_export_modelo_202_2024_emilio_uses_verified_revision_snapshot(
    tmp_path: Path,
) -> None:
    _set_emilio_legal_entity_export_profile()
    _, calculation_revision_id = _seed_exportable_modelo_202_2024_revision()
    out = tmp_path / "modelo-202-2024-1P.boe"

    result = _invoke(
        [
            "app",
            "modelo",
            "export",
            "--modelo",
            "202",
            "--year",
            "2024",
            "--period",
            "1P",
            "--output",
            str(out),
            "--by",
            "Emilio",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "operation\tmodelo.export" in result.output
    assert f"calculation_revision_id\t{calculation_revision_id}" in result.output
    assert "modelo\t202" in result.output
    assert "filing_year\t2024" in result.output
    assert "period\t2024 1P" in result.output
    assert out.exists()
    assert out.stat().st_size > 0


def test_export_resolves_visible_target_to_current_verified_revision(
    tmp_path: Path,
) -> None:
    """Natural-key export defaults to the current verified-complete revision."""

    _set_export_profile_name()
    _, (calculation_revision_id,) = _seed_modelo_111_revisions(
        states=(CalculationRevisionState.VERIFICADO_COMPLETO,),
        current_index=0,
    )
    out = tmp_path / "modelo-111-current.txt"

    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "export",
            "--modelo",
            "111",
            "--year",
            "2026",
            "--period",
            "1T",
            "--output",
            str(out),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = _payload(result.output)
    assert payload["calculation_revision_id"] == calculation_revision_id
    notices = _notices(result.output)
    notice = next(notice for notice in notices if notice["code"] == "modelo.export.local_export_not_official_evidence")
    assert notice["severity"] == "warning"
    assert notice["context"]["evidence_status"] == "local_export_not_official_aeat_filing_evidence"
    assert notice["context"]["modelo"] == "111"
    assert notice["context"]["filing_year"] == "2026"
    assert notice["context"]["period"] == "1T"
    assert notice["message"] == "The local export is not official filing evidence."
    assert notice["action"] is None
    assert out.exists()


def test_export_prefers_filed_pointer_over_current_verified_revision(
    tmp_path: Path,
) -> None:
    """Natural-key export prefers filed pointer before current verified pointer."""

    _set_export_profile_name()
    _, revision_ids = _seed_modelo_111_revisions(
        states=(CalculationRevisionState.VERIFICADO_COMPLETO, CalculationRevisionState.PRESENTADO),
        current_index=0,
        filed_index=1,
    )
    out = tmp_path / "modelo-111-filed.txt"

    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "export",
            "--modelo",
            "111",
            "--year",
            "2026",
            "--period",
            "1T",
            "--output",
            str(out),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = _payload(result.output)
    assert payload["calculation_revision_id"] == revision_ids[1]
    assert out.exists()


def test_export_refuses_ambiguous_verified_revisions_without_pointer(
    tmp_path: Path,
) -> None:
    """Natural-key export refuses multiple verified candidates without a pointer."""

    _seed_modelo_111_revisions(
        states=(CalculationRevisionState.VERIFICADO_COMPLETO, CalculationRevisionState.VERIFICADO_COMPLETO),
    )
    out = tmp_path / "modelo-111-ambiguous.txt"

    result = _invoke(
        [
            "app",
            "modelo",
            "export",
            "--modelo",
            "111",
            "--year",
            "2026",
            "--period",
            "1T",
            "--output",
            str(out),
        ],
    )

    assert result.exit_code != 0, result.output
    assert "ambiguous" in result.output.lower() or "more than one" in result.output.lower()
    assert not out.exists()


def test_export_modelo_111_refuses_when_profile_name_missing(
    tmp_path: Path,
) -> None:
    """When the active profile lacks ``identity.surnames`` the export
    must refuse with a clear error naming the missing profile fact
    rather than fabricating a placeholder name."""

    _clear_export_profile_surnames()
    work_unit_id, _ = seed_exportable_modelo_revision(input_values_by_casilla_id=_MODELO_111_INPUTS)
    out = tmp_path / "modelo-111.txt"

    result = _invoke(
        ["app", "modelo", "export", work_unit_id, "--output", str(out)],
    )

    assert result.exit_code != 0, result.output
    assert "surnames" in result.output.lower(), result.output
    assert not out.exists()


def test_export_modelo_121_refuses_missing_boe_layout_as_unsupported(tmp_path: Path) -> None:
    """Modelo 121 calculations may exist, but export refuses without an authored layout."""

    _set_export_profile_name()
    work_unit_id, _ = _seed_verified_revision_without_inputs(modelo="121", filing_year=2025, period="0A")
    out = tmp_path / "modelo-121.txt"

    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "export",
            work_unit_id,
            "--output",
            str(out),
        ],
    )

    assert result.exit_code == 2, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "REFUSED_MODELO_EXPORT_UNSUPPORTED"
    assert payload["error"]["category"] == "REFUSED"
    assert payload["error"]["context"]["modelo"] == "121"
    assert "export_layouts" in payload["error"]["message"]
    assert "suggestion" not in payload["error"]
    assert not out.exists()
    assert "Traceback" not in result.output


def test_export_modelo_303_cli_refuses_revision_without_filing_evidence(tmp_path: Path) -> None:
    work_unit_id, _ = _seed_verified_revision_without_inputs(modelo="303", filing_year=2026, period="1T")
    out = tmp_path / "modelo-303.txt"

    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "export",
            work_unit_id,
            "--output",
            str(out),
        ],
    )

    assert result.exit_code == 5, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "FAIL_MODELO_EXPORT"
    # The envelope identifies the cause by its registered error type. The
    # producer carries a declared precondition failure now, so there is no
    # English sentence here for a consumer to match on.
    assert payload["error"]["context"]["cause_type"] == "M303FilingEvidenceError"
    assert not out.exists()
    assert not out.with_name(out.name + ".tmp").exists()
    assert "Traceback" not in result.output


def test_export_modelo_100_reaches_xml_dictionary_path_before_cross_period_gate(tmp_path: Path) -> None:
    work_unit_id, _ = _seed_verified_revision_without_inputs(modelo="100", filing_year=2025, period="0A")
    out = tmp_path / "modelo-100.xml"

    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "export",
            work_unit_id,
            "--output",
            str(out),
        ],
    )

    assert result.exit_code == 2, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "REFUSED_MODELO_CROSS_PERIOD_CLEAN_STATE"
    assert payload["error"]["category"] == "REFUSED"
    assert "fixed_width" not in result.output
    assert "xml_dictionary" not in payload["error"]["message"]
    assert not out.exists()
    assert "Traceback" not in result.output


def test_export_requires_output_flag() -> None:
    """``--output`` is required; missing it surfaces as Typer usage error."""

    work_unit_id = _seed_work_unit_only()

    result = _invoke(["app", "modelo", "export", work_unit_id])
    assert result.exit_code != 0, result.output


def test_export_refuses_unknown_work_unit(tmp_path: Path) -> None:
    """A work unit id that resolves to no exportable revision must
    refuse rather than write an empty file."""

    out = tmp_path / "out.txt"
    result = _invoke(
        ["app", "modelo", "export", "0" * 64, "--output", str(out)],
    )
    assert result.exit_code != 0, result.output
    assert not out.exists()


def test_export_refuses_work_unit_with_no_exportable_revision(
    tmp_path: Path,
) -> None:
    """A work unit whose only revision is in DRAFT state must refuse;
    only verified-complete or filed revisions are exportable."""

    work_unit_id, _ = _seed_work_unit_with_draft_revision()
    out = tmp_path / "out.txt"

    result = _invoke(
        ["app", "modelo", "export", work_unit_id, "--output", str(out)],
    )
    assert result.exit_code != 0, result.output
    assert not out.exists()


def test_export_help_advertises_local_only() -> None:
    """The export verb help string must state ``Local-only`` so the
    operator cannot mistake the verb for an AEAT-contacting submit."""

    result = _invoke(["app", "modelo", "export", "--help"])
    assert result.exit_code == 0, result.output
    assert "modelo" in result.output.lower()
    assert any(token in result.output.lower() for token in ("local-only", "local;", "local.", "nunca")), result.output
    assert "--refund-election" in result.output
    assert "--payment-election" in result.output
    assert "--disposition" not in result.output


def test_export_refuses_explicit_revision_in_draft_state(
    tmp_path: Path,
) -> None:
    """When --revision targets a DRAFT revision explicitly, the service
    raises CalculationRevisionStateError; the CLI surfaces it as a
    refusal."""

    work_unit_id, calc_rev_id = _seed_work_unit_with_draft_revision()
    out = tmp_path / "out.txt"

    result = _invoke(
        [
            "app",
            "modelo",
            "export",
            work_unit_id,
            "--output",
            str(out),
            "--revision",
            calc_rev_id,
        ],
    )
    assert result.exit_code != 0, result.output
    assert not out.exists()
