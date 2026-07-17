"""Real terminal-boundary coverage for ``aeat app modelo work amend-wizard``.

Seeds a real AEAT-attested baseline (via ``filing-record import``, the same
production path an operator uses before amending) and drives the wizard's prompt
sequence end to end against the real registry engine and the real bucket-scoped
storage the CLI runs against in every other integration test.

The prompts are driven through ``prompt_toolkit``'s own IO-injection contract:
:func:`~prompt_toolkit.input.create_pipe_input` supplies the keystrokes and
:func:`~prompt_toolkit.application.current.create_app_session` declares that pipe
as the ambient session's IO, which is what the production
:meth:`~cadrumo.application.wizard.QuestionaryPrompter.from_ambient_app_session`
construction reads. Nothing is mocked, stubbed, or patched -- the keystrokes are
the only thing supplied, exactly what an operator would type.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from io import StringIO
from pathlib import Path

import pytest
from prompt_toolkit.application.current import create_app_session
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output.plain_text import PlainTextOutput
from pydantic import AnyHttpUrl, TypeAdapter

from ....adapters.persistence.profile.justificante import JustificanteRepository
from ....application.user_profile import profile_storage_session
from ....core import Period, resolve_active_bucket_id
from ....domain.justificante import Justificante
from ....tests.aeat_literal_fixtures import justificante_cotejo_url
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_cli_backend as _isolated_cli_backend  # noqa: F401
from ._modelo_work_ux_support import _create_m130_work_unit
from .envelope_helpers import unwrap_schema_envelope as _payload

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_TAX_ID = "12345678Z"

# M130 1T has no required-manual casillas (casilla 02 is `required = true` but
# `input_kind = "bound"`, so it is excluded from the amend completeness gate --
# see `required_input_casilla_ids_for_revision`). A baseline carrying only
# casillas 01 (ingresos) and 02 (gastos) is a legitimate amendable
# AEAT-attested filing.
_BASELINE_INGRESOS = Decimal("1000.00")
_BASELINE_GASTOS = Decimal("250.00")
_CORRECTED_INGRESOS = Decimal("1100.00")


def _invoke(args: list[str]):
    return invoke_cached_cli(args)


def _invoke_with_typed_answers(args: list[str], answers: tuple[str, ...]):
    """Run the CLI with ``answers`` queued as real keystrokes on a pipe.

    The whole answer sequence is buffered up front because the CLI call is
    synchronous: each ``questionary`` prompt reads up to its Enter and leaves the
    remainder for the next one.
    """
    with create_pipe_input() as pipe:
        pipe.send_text("".join(f"{answer}\r" for answer in answers))
        with create_app_session(input=pipe, output=PlainTextOutput(StringIO())):
            return _invoke(args)


def _create_profile() -> None:
    result = _invoke(
        [
            "config",
            "profile",
            "create",
            "operator",
            "--quiet",
            "--accept-defaults",
            "--entity-type",
            "natural_person",
            "--irpf-income-categories",
            "actividad_economica",
            "--tax-id",
            _TAX_ID,
            "--name",
            "Operator",
            "--surnames",
            "Amend",
            "--activity",
            "design",
        ],
    )
    assert result.exit_code == 0, result.output


def _seed_justificante(*, csv: str, period: str = "1T") -> None:
    """Persist the stored receipt metadata a justificante-bound evidence import requires.

    ``import_external_filing_evidence`` refuses a justificante-bound evidence
    kind unless the reference id resolves to real stored receipt metadata
    matching the taxpayer, modelo, filing year, and period -- so a real receipt
    is seeded here rather than mocked or bypassed.
    """
    body = f"{csv}-pdf".encode()
    receipt = Justificante(
        csv=csv,
        modelo="130",
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
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    with profile_storage_session(bucket_id):
        JustificanteRepository(bucket_id=bucket_id).save(receipt)


def _import_external_baseline(
    work_unit_id: str, *, csv: str = "JUST-2025-130-1T-AMEND-WIZARD", period: str = "1T"
) -> str:
    """Import an AEAT-attested baseline filing and return its filing_record_id."""
    _seed_justificante(csv=csv, period=period)
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
    return _payload(result.output)["filing_record_id"]


def test_amend_wizard_drives_full_prompt_sequence_and_files_correction() -> None:
    """The wizard walks selection, one corrected value, kind, and reason, then files.

    The typed answers drive: (1) which casilla numbers changed ("01"), (2) the
    corrected value for casilla 01, (3) the amendment kind, (4) the free-text
    reason. The resulting filing record supersedes the imported baseline and
    carries the corrected casilla value.
    """
    _create_profile()
    work_unit_id = _create_m130_work_unit()
    baseline_filing_id = _import_external_baseline(work_unit_id)

    result = _invoke_with_typed_answers(
        ["--format", "json", "app", "modelo", "work", "amend-wizard", work_unit_id],
        ("01", str(_CORRECTED_INGRESOS), "complementaria", "under-reported turnover"),
    )
    assert result.exit_code == 0, result.output
    assert "Traceback" not in result.output
    # Prompt copy renders on the prompter's own device, never stdout.
    assert result.output.lstrip().startswith("{"), result.output

    payload = _payload(result.output)
    assert payload["work_unit_id"] == work_unit_id
    assert payload["amendment_kind"] == "complementaria"
    assert payload["amendment_reason"] == "under-reported turnover"
    assert payload["status"] == "vigente"
    # The new record is an internal filing envelope, not an AEAT-attested one.
    assert payload["external_evidence"] is None
    assert payload["amends_filing_record_id"] == baseline_filing_id

    corrected = payload["corrected_casillas"]
    assert len(corrected) == 1
    assert corrected[0]["number"] == "01"
    assert corrected[0]["previous_value"] == str(_BASELINE_INGRESOS)
    assert corrected[0]["corrected_value"] == str(_CORRECTED_INGRESOS)
    assert corrected[0]["legal_refs"], "corrected casilla must carry legal_refs"

    assert "export" in payload["export_next_action"]
    assert work_unit_id in payload["export_next_action"]

    # The correction is persisted, not merely reported: the filed revision
    # carries the corrected figure.
    revision = _payload(
        _invoke(
            ["--format", "json", "app", "modelo", "work", "revision", payload["calculation_revision_id"]],
        ).output,
    )
    assert Decimal(revision["casilla_values"]["01"]) == _CORRECTED_INGRESOS


def test_amend_wizard_composes_shared_amend_path_not_a_parallel_one() -> None:
    """A wizard-built amendment and a hand-built ``work amend`` amendment agree exactly.

    Two independently-seeded baselines (different quarters, same modelo/year)
    are amended identically: one through the guided wizard, one through the raw
    ``work amend`` flag grammar. Both must resolve to the same corrected casilla
    01 value -- proof the wizard is a guided front end over the existing
    ``amend_modelo_revision`` path
    (``composition-service-no-parallel-write-path``), not a second,
    independently-derived amendment surface.
    """
    _create_profile()

    wizard_unit_id = _create_m130_work_unit(period="1T")
    _import_external_baseline(wizard_unit_id, csv="JUST-2025-130-1T-WIZARD", period="1T")
    wizard_result = _invoke_with_typed_answers(
        ["--format", "json", "app", "modelo", "work", "amend-wizard", wizard_unit_id],
        ("01", str(_CORRECTED_INGRESOS), "complementaria", "wizard-driven correction"),
    )
    assert wizard_result.exit_code == 0, wizard_result.output
    wizard_payload = _payload(wizard_result.output)

    hand_unit_id = _create_m130_work_unit(period="2T")
    hand_baseline_filing_id = _import_external_baseline(
        hand_unit_id,
        csv="JUST-2025-130-2T-HANDBUILT",
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
        == str(_CORRECTED_INGRESOS)
    )
    assert wizard_payload["amendment_kind"] == hand_built_payload["amendment_kind"] == "complementaria"


def test_amend_wizard_no_selection_refuses_instructively() -> None:
    """A blank answer to 'which casillas changed' refuses with no amendment filed."""
    _create_profile()
    work_unit_id = _create_m130_work_unit()
    _import_external_baseline(work_unit_id)

    result = _invoke_with_typed_answers(
        ["--format", "json", "app", "modelo", "work", "amend-wizard", work_unit_id],
        ("",),
    )
    assert result.exit_code != 0
    assert "Traceback" not in result.output


def test_amend_wizard_refuses_without_evidence_baseline() -> None:
    """A local work unit cannot enter the external-filing amendment path."""
    _create_profile()
    work_unit_id = _create_m130_work_unit()

    result = _invoke(["--format", "json", "app", "modelo", "work", "amend-wizard", work_unit_id])

    assert result.exit_code != 0
    assert "Traceback" not in result.output


def test_amend_wizard_non_interactive_host_refuses_with_instructive_message() -> None:
    """A real non-TTY invocation refuses before attempting an interactive prompt."""
    _create_profile()
    work_unit_id = _create_m130_work_unit()
    _import_external_baseline(work_unit_id)

    result = _invoke(["--format", "json", "app", "modelo", "work", "amend-wizard", work_unit_id])

    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert "interactive" in result.output.lower() or "console" in result.output.lower()
