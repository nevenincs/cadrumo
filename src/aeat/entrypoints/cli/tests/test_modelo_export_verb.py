"""CLI surface tests for ``aeat app modelo export``."""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest
from click.testing import Result

from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....application.modelo import resolve_registry_revision_for_work_target
from ....application.user_profile._orchestration import profile_create_storage_span, set_active_fields
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....core import CasillaId, Period, validated_casilla_id
from ....domain.modelos._calculation_repository import (
    CalculationRevisionCatalogueRepository,
    upsert_calculation_revision,
)
from ....domain.modelos._calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos._codes import ModeloCode
from ....domain.modelos._repository import WorkUnitCatalogueRepository, upsert_work_unit
from ....domain.modelos._work_unit import WorkUnit, derive_work_unit_id
from ....domain.user_profile import UserProfileFact
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from .envelope_helpers import unwrap_schema_envelope as _payload

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


def _active_registry_revision_id(*, modelo: str, filing_year: int, period: str) -> str:
    return resolve_registry_revision_for_work_target(
        modelo=modelo,
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, period),
        registry_revision_id=None,
    )


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    dispose_engine()
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("operator"),
    ):
        try:
            workflow_state_repository().update(
                lambda state: register_minimal_profile(state, profile_id="operator"),
            )
            yield
        finally:
            dispose_engine()


def _seed_work_unit_only(*, modelo: str = "130", filing_year: int = 2026, period: str = "1T") -> str:
    state = workflow_state_repository().load()
    bucket_id = state.active_profile_bucket_id()
    assert bucket_id is not None
    revision_id = _active_registry_revision_id(modelo=modelo, filing_year=filing_year, period=period)
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
    )
    revision = CalculationRevision(
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        created_at=now,
        updated_at=now,
    )
    cr_repo = CalculationRevisionCatalogueRepository()
    cr_repo.save(upsert_calculation_revision(cr_repo.load(), revision))
    return work_unit_id, calculation_revision_id


def _seed_verified_revision_without_inputs(*, modelo: str, filing_year: int, period: str) -> tuple[str, str]:
    state = workflow_state_repository().load()
    bucket_id = state.active_profile_bucket_id()
    assert bucket_id is not None
    revision_id = _active_registry_revision_id(modelo=modelo, filing_year=filing_year, period=period)
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
    )
    revision = CalculationRevision(
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        created_at=now,
        updated_at=now,
        verified_at=now,
        verified_by="operator",
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
    workflow_state_repository().update(
        lambda state: set_active_fields(
            state,
            (
                UserProfileFact(path="identity.name", value="Ana"),
                UserProfileFact(path="identity.surnames", value="Export Test"),
                UserProfileFact(path="activities.description", value="Consulting"),
            ),
        ),
    )


def _clear_export_profile_surnames() -> None:
    workflow_state_repository().update(
        lambda state: set_active_fields(
            state,
            (
                UserProfileFact(path="identity.surnames", value=None),
                UserProfileFact(path="activities.description", value="Consulting"),
            ),
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
    registry_revision_id = _active_registry_revision_id(modelo="111", filing_year=filing_year, period=period)
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


def _seed_exportable_modelo_111_revision(
    *,
    modelo: str = "111",
    filing_year: int = 2026,
    period: str = "1T",
) -> tuple[str, str]:
    """Persist a verified-complete modelo-111 revision ready for export.

    The work unit carries a canonical quarterly period token and the
    revision captures a real modelo-111 casilla input snapshot so the
    registry-backed draft build produces a populated fichero-BOE file.
    """

    state = workflow_state_repository().load()
    bucket_id = state.active_profile_bucket_id()
    assert bucket_id is not None
    revision_id = _active_registry_revision_id(modelo=modelo, filing_year=filing_year, period=period)
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

    calculation_revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id=_MODELO_111_INPUTS,
        binding_overrides={},
        casilla_values={},
    )
    revision = CalculationRevision(
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        input_values_by_casilla_id=_MODELO_111_INPUTS,
        created_at=now,
        updated_at=now,
        verified_at=now,
        verified_by="operator",
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
    work_unit_id, _ = _seed_exportable_modelo_111_revision()
    out = tmp_path / "modelo-111.txt"

    result = _invoke(
        ["app", "modelo", "export", work_unit_id, "--output", str(out)],
    )

    assert result.exit_code == 0, result.output
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
    work_unit_id, _ = _seed_exportable_modelo_111_revision()
    out = tmp_path / "modelo-111.txt"

    result = _invoke(
        ["app", "modelo", "export", work_unit_id, "--output", str(out)],
    )

    assert result.exit_code != 0, result.output
    assert "surnames" in result.output.lower(), result.output
    assert not out.exists()


def test_export_modelo_390_refuses_missing_boe_layout_as_unsupported(tmp_path: Path) -> None:
    """Modelo 390 calculations may exist, but export refuses without an authored layout."""

    _set_export_profile_name()
    work_unit_id, _ = _seed_verified_revision_without_inputs(modelo="390", filing_year=2025, period="0A")
    out = tmp_path / "modelo-390.txt"

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
    assert payload["error"]["context"]["modelo"] == "390"
    assert "export_layouts" in payload["error"]["message"]
    assert payload["error"]["suggestion"] == "aeat app modelo describe 390"
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
