"""CLI surface tests for ``aeat app modelo export``."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_cli_backend
from cadrumo.application.modelo.export_m202_profile import (
    MARK_FACT_BY_PRODUCER_KEY,
    PRINCIPAL_CNAE_CLASSIFICATION_PATH,
    PRINCIPAL_CNAE_PATH,
)
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.filing.software_identity import development_mock_software_identity
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevisionState,
)
from cadrumo.entrypoints.cli.tests.modelo_review_package_support import seed_exportable_modelo_revision

from .modelo_export_verb_support import (
    MODELO_111_INPUTS,
    PRE_B2_LAST_EXERCISE,
    export_operator,
    invoke,
    seed_exportable_modelo_202_pre_b2_revision,
    seed_modelo_111_revisions,
    seed_work_unit_only,
    seed_work_unit_with_draft_revision,
    set_emilio_legal_entity_export_profile,
    set_export_profile_name,
)
from .modelo_profile_seed import seed_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

__all__ = ["export_operator", "isolated_cli_backend", "seed_profile"]


def test_export_modelo_111_end_to_end_writes_file_with_composed_headers(
    tmp_path: Path,
    *,
    operation: PinnedAuthorityOperation,
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

    set_export_profile_name()
    work_unit_id, _ = seed_exportable_modelo_revision(input_values_by_casilla_id=MODELO_111_INPUTS, operation=operation)
    out = tmp_path / "modelo-111.txt"

    result = invoke(
        ["app", "modelo", "export", work_unit_id, "--output", str(out)],
    )

    assert result.exit_code == 0, result.output
    assert "evidence_status\tlocal_export_not_official_aeat_filing_evidence" in result.output
    assert "not official AEAT filing evidence" in result.output
    assert "justificante" in result.output
    assert "consulta de declaraciones presentadas" in result.output
    assert "CSV cotejo" in result.output
    assert out.exists()
    assert out.stat().st_size > 0
    # The seeded box 03 of 180.25 euros, written in cents as the fixed-width design carries amounts.
    assert b"18025" in out.read_bytes()


def test_export_modelo_111_emilio_legal_entity_uses_profile_identity_name(
    tmp_path: Path,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    set_emilio_legal_entity_export_profile()
    _, (calculation_revision_id,) = seed_modelo_111_revisions(
        states=(CalculationRevisionState.VERIFICADO_COMPLETO,),
        current_index=0,
        filing_year=2024,
        period="1T",
        operation=operation,
    )
    out = tmp_path / "modelo-111-2024-1T.boe"

    result = invoke(
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


def test_export_refuses_output_path_with_missing_parent_directory(
    tmp_path: Path,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """A relative-shaped ``--output`` whose parent directory is missing carries a typed reason.

    The refusal must not be laundered into a bare, contextless CLI usage
    error: the operator needs the stable reason and the exact path that was
    refused, machine-readably.
    """
    set_emilio_legal_entity_export_profile()
    seed_modelo_111_revisions(
        states=(CalculationRevisionState.VERIFICADO_COMPLETO,),
        current_index=0,
        filing_year=2024,
        period="1T",
        operation=operation,
    )
    out = tmp_path / "missing-parent" / "modelo-111-2024-1T.boe"

    result = invoke(
        [
            "--format",
            "json",
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

    assert result.exit_code != 0, result.output
    error = json.loads(result.output)["error"]
    assert error["code"] == "REFUSED_MODELO_EXPORT_OUTPUT_PATH"
    context = error["context"]
    assert isinstance(context, dict)
    assert context["output_path"] == str(out)
    assert context["reason"] == "parent directory does not exist"
    assert not out.exists()


def test_export_refuses_an_existing_output_path_without_replace(
    tmp_path: Path,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """A pre-existing ``--output`` file without ``--replace`` carries a typed reason too."""
    set_emilio_legal_entity_export_profile()
    seed_modelo_111_revisions(
        states=(CalculationRevisionState.VERIFICADO_COMPLETO,),
        current_index=0,
        filing_year=2024,
        period="1T",
        operation=operation,
    )
    out = tmp_path / "modelo-111-2024-1T.boe"
    out.write_bytes(b"already here")

    result = invoke(
        [
            "--format",
            "json",
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

    assert result.exit_code != 0, result.output
    error = json.loads(result.output)["error"]
    assert error["code"] == "REFUSED_MODELO_EXPORT_OUTPUT_PATH"
    context = error["context"]
    assert isinstance(context, dict)
    assert context["output_path"] == str(out)
    assert context["reason"] == "path is an existing file"
    assert out.read_bytes() == b"already here"


def test_export_modelo_202_without_page_01_entity_facts_refuses_with_the_door_to_state_them(
    tmp_path: Path,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """The development identity clears the envelope header; unstated page 01 entity facts still refuse.

    The profile states its ejercicio, so the devengo resolves, but no principal
    CNAE and none of the datos adicionales the official design asks for, so the
    export stops before any byte is written, names every missing profile fact
    and opens the first one.
    """

    # The company started after the periodo impositivo the 1P art. 40.2 base reads, so that
    # instalment has no earlier Modelo 200 to take a base from and the export reaches the producer.
    started = date(PRE_B2_LAST_EXERCISE - 1, 1, 1)
    # The sociedad persona states its page 01 entity facts; this profile leaves them unstated.
    set_emilio_legal_entity_export_profile(
        activity_start_date=started,
        constitution_date=started,
        without=(PRINCIPAL_CNAE_PATH, PRINCIPAL_CNAE_CLASSIFICATION_PATH, *MARK_FACT_BY_PRODUCER_KEY.values()),
    )
    _, calculation_revision_id = seed_exportable_modelo_202_pre_b2_revision(operation=operation)
    out = tmp_path / f"modelo-202-{PRE_B2_LAST_EXERCISE}-1P.boe"

    result = invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "export",
            "--modelo",
            "202",
            "--year",
            str(PRE_B2_LAST_EXERCISE),
            "--period",
            "1P",
            "--output",
            str(out),
            "--by",
            "Emilio",
        ],
    )

    assert result.exit_code != 0, result.output
    error = json.loads(result.output)["error"]
    assert error["code"] == "REFUSED_MODELO_PROFILE_READINESS"
    context = error["context"]
    assert context["calculation_revision_id"] == calculation_revision_id
    assert context["cause_type"] == "FilingProducerSnapshotError"
    assert context["reason"] == "m202_profile_facts_missing"
    missing = str(context["missing_profile_paths"]).split(", ")
    # The code is a code of one classification, so the classification is asked for first.
    assert missing[:2] == ["taxpayer_type.principal_cnae_classification", "taxpayer_type.principal_cnae"]
    assert "taxpayer_type.regimen_ley_49_2002" in missing
    assert context["profile_path"] == "taxpayer_type.principal_cnae_classification"
    assert not out.exists()


def test_a_fixed_record_envelope_reports_the_development_identity_it_stamps(
    tmp_path: Path,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """Modelo 111 authors its envelope as a fixed record whose EEDD slots take the development mock identity.

    The file carries the all-zero identity, so the operator must be told it is
    not presentable at AEAT exactly as for an envelope-prefix layout.
    """
    set_emilio_legal_entity_export_profile()
    seed_modelo_111_revisions(
        states=(CalculationRevisionState.VERIFICADO_COMPLETO,),
        current_index=0,
        filing_year=2024,
        period="1T",
        operation=operation,
    )
    out = tmp_path / "modelo-111-2024-1T.boe"

    result = invoke(
        [
            "--format",
            "json",
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
    envelope = json.loads(result.output)
    assert envelope["result"]["software_identity_grade"] == "development_mock"
    assert "modelo.export.development_software_identity" in {notice["code"] for notice in envelope["notices"]}
    written = out.read_bytes()
    assert written[92:96] == b"0000"
    assert written[100:109] == development_mock_software_identity().developer_tax_id.encode("ascii")


def test_export_requires_output_flag(*, operation: PinnedAuthorityOperation) -> None:
    """``--output`` is required; missing it surfaces as Typer usage error."""

    work_unit_id = seed_work_unit_only(operation=operation)

    result = invoke(["app", "modelo", "export", work_unit_id])
    assert result.exit_code != 0, result.output


def test_export_refuses_unknown_work_unit(tmp_path: Path) -> None:
    """A work unit id that resolves to no exportable revision must
    refuse rather than write an empty file."""

    out = tmp_path / "out.txt"
    result = invoke(
        ["app", "modelo", "export", "0" * 64, "--output", str(out)],
    )
    assert result.exit_code != 0, result.output
    assert not out.exists()


def test_export_refuses_work_unit_with_no_exportable_revision(
    tmp_path: Path,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """A work unit whose only revision is in DRAFT state must refuse;
    only verified-complete or filed revisions are exportable."""

    work_unit_id, _ = seed_work_unit_with_draft_revision(operation=operation)
    out = tmp_path / "out.txt"

    result = invoke(
        ["app", "modelo", "export", work_unit_id, "--output", str(out)],
    )
    assert result.exit_code != 0, result.output
    assert not out.exists()


def test_export_help_advertises_local_only() -> None:
    """The export verb help string must state ``Local-only`` so the
    operator cannot mistake the verb for an AEAT-contacting submit."""

    result = invoke(["app", "modelo", "export", "--help"])
    assert result.exit_code == 0, result.output
    assert "modelo" in result.output.lower()
    assert any(token in result.output.lower() for token in ("local-only", "local;", "local.", "nunca")), result.output
    assert "--refund-election" in result.output
    assert "--payment-election" in result.output
    assert "--disposition" not in result.output


def test_export_refuses_explicit_revision_in_draft_state(
    tmp_path: Path,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """When --revision targets a DRAFT revision explicitly, the service
    raises CalculationRevisionStateError; the CLI surfaces it as a
    refusal."""

    work_unit_id, calc_rev_id = seed_work_unit_with_draft_revision(operation=operation)
    out = tmp_path / "out.txt"

    result = invoke(
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
