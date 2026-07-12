"""Real-behavior coverage for the guided ``aeat app modelo work amend-wizard`` command.

Seeds a real AEAT-attested baseline (via ``filing-record import``, the same
production path an operator uses before amending) and drives the wizard's
scripted prompt sequence end to end against the real registry engine and the
real bucket-scoped storage the CLI runs against in every other integration
test -- no mocks, stubs, or patches. Every assertion compares the wizard's
persisted amendment against ``work amend``'s hand-built equivalent
(``composition-service-no-parallel-write-path``): both must call the exact
same :func:`~cadrumo.application.modelo.amend_modelo_revision` composition path,
never a parallel one.
"""

from __future__ import annotations

import hashlib
from collections import deque
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, TypeAdapter

from ....adapters.persistence.profile.justificante import JustificanteRepository
from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....application.user_profile import profile_storage_session
from ....core import Period, resolve_active_bucket_id
from ....core.config import override_settings
from ....domain.justificante import Justificante
from ....tests.aeat_literal_fixtures import justificante_cotejo_url
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from .._modelo_amend_wizard_cli import override_amend_wizard_prompter
from .._modelo_work_wizard_cli import _ScriptedTextPrompter
from .envelope_helpers import unwrap_schema_envelope as _payload

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

# M130 1T has no required-manual casillas (casilla 02 is `required = true`
# but `input_kind = "bound"`, so it is excluded from the amend completeness
# gate -- see `required_input_casilla_ids_for_revision`). A baseline carrying
# only casillas 01 (ingresos) and 02 (gastos) is a legitimate amendable
# AEAT-attested filing, matching the pattern the application-layer
# `test_amend_flow.py` fixture already proves.
_BASELINE_INGRESOS = Decimal("1000.00")
_BASELINE_GASTOS = Decimal("250.00")
_CORRECTED_INGRESOS = Decimal("1100.00")
_TAX_ID = "12345678Z"


def _justificante_metadata(*, csv: str, modelo: str, period: str) -> Justificante:
    """Seed the stored :class:`Justificante` metadata ``filing-record import`` requires.

    ``import_external_filing_evidence`` refuses a justificante-bound evidence
    kind (the only kinds the CLI ``--evidence-kind`` accepts) unless the
    reference id resolves to real stored receipt metadata matching the
    taxpayer, modelo, filing year, and period -- so a real receipt is seeded
    here rather than mocked or bypassed.
    """
    body = f"{csv}-pdf".encode()
    return Justificante(
        csv=csv,
        modelo=modelo,
        period=Period.from_year_and_code(2025, period),
        ejercicio="2025",
        presentation_id=None,
        presented_at=datetime(2025, 4, 15, 9, 30, tzinfo=UTC),
        tax_id=_TAX_ID,
        total_a_ingresar=None,
        total_a_devolver=None,
        verification_url=TypeAdapter(AnyHttpUrl).validate_python(justificante_cotejo_url(csv)),
        source_pdf_path=Path("var") / "justificantes" / f"{csv}.pdf",
        source_pdf_sha256=hashlib.sha256(body).hexdigest(),
        parsed_at=datetime(2025, 4, 16, 12, 0, tzinfo=UTC),
    )


@pytest.fixture(autouse=True)
def _isolated_cli_backend(tmp_path: Path) -> Iterator[None]:
    dispose_engine()
    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_output_language="en"),
        isolated_profile_storage_root(tmp_path=tmp_path),
    ):
        try:
            yield
        finally:
            dispose_engine()


def _invoke(args: list[str]):
    return invoke_cached_cli(args)


def _create_profile() -> None:
    result = _invoke(
        [
            "config", "profile", "create", "operator",
            "--quiet", "--accept-defaults",
            "--entity-type", "natural_person",
            "--irpf-income-categories", "actividad_economica",
            "--tax-id", "12345678Z",
            "--name", "Operator",
            "--surnames", "Amend",
            "--activity", "design",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output


def _seed_justificante(*, csv: str, modelo: str, period: str) -> None:
    """Persist the stored receipt metadata a justificante-bound evidence import requires."""
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None, "test profile must install an active bucket pointer"
    with profile_storage_session(bucket_id):
        JustificanteRepository(bucket_id=bucket_id).save(
            _justificante_metadata(csv=csv, modelo=modelo, period=period),
        )


def _create_m130_work_unit() -> str:
    result = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "130", "--year", "2025", "--period", "1T",
            "--revision", "2019-y-siguientes",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    return _payload(result.output)["work_unit_id"]


def _import_external_baseline(work_unit_id: str) -> None:
    """Import an AEAT-attested baseline filing -- the gate ``amend`` requires."""
    csv = "JUST-2025-130-1T-AMEND-WIZARD"
    _seed_justificante(csv=csv, modelo="130", period="1T")
    result = _invoke(
        [
            "--format", "json",
            "app", "modelo", "filing-record", "import", work_unit_id,
            "--evidence-kind", "aeat_justificante_pdf",
            "--evidence-id", csv,
            "--set", f"01={_BASELINE_INGRESOS}",
            "--set", f"02={_BASELINE_GASTOS}",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output


def test_amend_wizard_drives_full_prompt_sequence_and_files_correction() -> None:
    """The wizard walks selection, one corrected value, kind, and reason, then files.

    The scripted answer queue drives: (1) which casilla numbers changed
    ("01"), (2) the corrected value for casilla 01, (3) the amendment kind,
    (4) the free-text reason. The resulting filing record supersedes the
    imported baseline and carries the corrected casilla_values.
    """
    _create_profile()
    work_unit_id = _create_m130_work_unit()
    _import_external_baseline(work_unit_id)

    prompter = _ScriptedTextPrompter(
        deque(["01", str(_CORRECTED_INGRESOS), "complementaria", "under-reported turnover"]),
    )
    with override_amend_wizard_prompter(prompter):
        result = _invoke(["--format", "json", "app", "modelo", "work", "amend-wizard", work_unit_id])
    assert result.exit_code == 0, result.output
    assert "Traceback" not in result.output

    payload = _payload(result.output)
    assert payload["work_unit_id"] == work_unit_id
    assert payload["amendment_kind"] == "complementaria"
    assert payload["amendment_reason"] == "under-reported turnover"
    assert payload["status"] == "vigente"
    assert payload["external_evidence"] is None  # new record is an internal filing envelope
    assert payload["amends_filing_record_id"]

    corrected = payload["corrected_casillas"]
    assert len(corrected) == 1
    assert corrected[0]["number"] == "01"
    assert corrected[0]["previous_value"] == str(_BASELINE_INGRESOS)
    assert corrected[0]["corrected_value"] == str(_CORRECTED_INGRESOS)
    assert corrected[0]["legal_refs"], "corrected casilla must carry legal_refs"

    assert "export" in payload["export_next_action"]
    assert work_unit_id in payload["export_next_action"]

    # Every scripted answer was consumed.
    assert len(prompter.asked_prompts) == 4
    from ....application.wizard import WizardScriptUnderflowError

    with pytest.raises(WizardScriptUnderflowError):
        prompter.ask_text("extra question nobody scripted", help_text=None)


def _create_m130_work_unit_for_period(period: str) -> str:
    result = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "130", "--year", "2025", "--period", period,
            "--revision", "2019-y-siguientes",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    return _payload(result.output)["work_unit_id"]


def _import_external_baseline_for_unit(work_unit_id: str, *, evidence_id: str, period: str) -> str:
    """Import a baseline for ``work_unit_id`` and return its filing_record_id."""
    _seed_justificante(csv=evidence_id, modelo="130", period=period)
    result = _invoke(
        [
            "--format", "json",
            "app", "modelo", "filing-record", "import", work_unit_id,
            "--evidence-kind", "aeat_justificante_pdf",
            "--evidence-id", evidence_id,
            "--set", f"01={_BASELINE_INGRESOS}",
            "--set", f"02={_BASELINE_GASTOS}",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    return _payload(result.output)["filing_record_id"]


def test_amend_wizard_composes_shared_amend_path_not_a_parallel_one() -> None:
    """A wizard-built amendment and a hand-built ``work amend`` amendment agree exactly.

    Two independently-seeded baselines (different quarters, same modelo/year)
    are amended identically: one through the guided wizard, one through the
    raw ``work amend`` flag grammar. Both must resolve to the same corrected
    casilla 01 value -- proof the wizard is a guided front end over the
    existing ``amend_modelo_revision`` path
    (composition-service-no-parallel-write-path), not a second,
    independently-derived amendment surface.
    """
    _create_profile()

    wizard_unit_id = _create_m130_work_unit_for_period("1T")
    wizard_baseline_filing_id = _import_external_baseline_for_unit(
        wizard_unit_id,
        evidence_id="JUST-2025-130-1T-WIZARD",
        period="1T",
    )
    prompter = _ScriptedTextPrompter(
        deque(["01", str(_CORRECTED_INGRESOS), "complementaria", "wizard-driven correction"]),
    )
    with override_amend_wizard_prompter(prompter):
        wizard_result = _invoke(
            ["--format", "json", "app", "modelo", "work", "amend-wizard", wizard_unit_id],
        )
    assert wizard_result.exit_code == 0, wizard_result.output
    wizard_payload = _payload(wizard_result.output)

    hand_unit_id = _create_m130_work_unit_for_period("2T")
    hand_baseline_filing_id = _import_external_baseline_for_unit(
        hand_unit_id,
        evidence_id="JUST-2025-130-2T-HANDBUILT",
        period="2T",
    )
    hand_built_result = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "amend",
            "--from-filing-record", hand_baseline_filing_id,
            "--kind", "complementaria",
            "--reason", "hand-built parity check",
            "--set", f"01={_CORRECTED_INGRESOS}",
        ],
    )  # fmt: skip
    assert hand_built_result.exit_code == 0, hand_built_result.output
    hand_built_payload = _payload(hand_built_result.output)

    assert wizard_payload["amends_filing_record_id"] == wizard_baseline_filing_id
    assert hand_built_payload["amends_filing_record_id"] == hand_baseline_filing_id

    wizard_revision = _payload(
        _invoke(
            ["--format", "json", "app", "modelo", "work", "revision", wizard_payload["calculation_revision_id"]],
        ).output,
    )
    hand_built_revision = _payload(
        _invoke(
            [
                "--format", "json",
                "app", "modelo", "work", "revision", hand_built_payload["calculation_revision_id"],
            ],
        ).output,
    )  # fmt: skip
    assert (
        wizard_revision["casilla_values"]["01"]
        == hand_built_revision["casilla_values"]["01"]
        == str(
            _CORRECTED_INGRESOS,
        )
    )
    assert wizard_payload["amendment_kind"] == hand_built_payload["amendment_kind"] == "complementaria"


def test_amend_wizard_no_selection_refuses_instructively() -> None:
    """A blank answer to 'which casillas changed' refuses with no amendment filed."""
    _create_profile()
    work_unit_id = _create_m130_work_unit()
    _import_external_baseline(work_unit_id)

    prompter = _ScriptedTextPrompter(deque([""]))
    with override_amend_wizard_prompter(prompter):
        result = _invoke(["--format", "json", "app", "modelo", "work", "amend-wizard", work_unit_id])
    assert result.exit_code != 0
    assert "Traceback" not in result.output


def test_amend_wizard_refuses_without_evidence_baseline() -> None:
    """A work unit with no imported external-evidence baseline refuses cleanly.

    Mirrors ``work amend``'s own ``AmendmentEvidenceMissingError`` gate: a
    locally-filed (never externally imported) work unit cannot enter the
    amendment wizard.
    """
    _create_profile()
    work_unit_id = _create_m130_work_unit()

    result = _invoke(["--format", "json", "app", "modelo", "work", "amend-wizard", work_unit_id])
    assert result.exit_code != 0
    assert "Traceback" not in result.output


def test_amend_wizard_non_interactive_host_refuses_with_instructive_message() -> None:
    """Without a scripted prompter injected, a non-TTY host refuses instructively."""
    _create_profile()
    work_unit_id = _create_m130_work_unit()
    _import_external_baseline(work_unit_id)

    result = _invoke(["--format", "json", "app", "modelo", "work", "amend-wizard", work_unit_id])
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert "interactive" in result.output.lower() or "console" in result.output.lower()


def test_amend_wizard_kind_prompt_restricts_choices_to_period_permitted_set() -> None:
    """The kind prompt offers and accepts only the resolved period's legally
    permitted amendment kinds -- it never offers rectificativa for a
    pre-boundary M303 period, matching the period-aware guard
    ``amend_modelo_revision`` re-asserts downstream."""
    import typer

    from ....domain.modelos import CalculationRevisionAmendmentKind
    from .._modelo_amend_wizard_cli import _prompt_amendment_kind

    pre_boundary_period = Period.from_year_and_code(2024, "2T")
    prompter = _ScriptedTextPrompter(deque(["complementaria"]))
    kind = _prompt_amendment_kind(prompter, modelo="303", period=pre_boundary_period)
    assert kind is CalculationRevisionAmendmentKind.COMPLEMENTARIA
    assert "rectificativa" not in prompter.asked_prompts[0]

    rejecting_prompter = _ScriptedTextPrompter(deque(["rectificativa"]))
    with pytest.raises(typer.BadParameter):
        _prompt_amendment_kind(rejecting_prompter, modelo="303", period=pre_boundary_period)

    post_boundary_period = Period.from_year_and_code(2024, "3T")
    post_prompter = _ScriptedTextPrompter(deque(["rectificativa"]))
    post_kind = _prompt_amendment_kind(post_prompter, modelo="303", period=post_boundary_period)
    assert post_kind is CalculationRevisionAmendmentKind.RECTIFICATIVA
    assert "complementaria" not in post_prompter.asked_prompts[0]
