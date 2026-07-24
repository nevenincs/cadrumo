"""Contract coverage for ``aeat app modelo work amend-wizard``.

The amend wizard is a guided front end over the flow substrate: it asks
which casillas changed through a CHECKBOX page, then a second definition
of one DECIMAL page per selected casilla plus the amendment-kind SELECT
and the required reason, and files through the exact same
:func:`~application.modelo.amend_modelo_revision` composition path
``work amend`` uses. On a real terminal it renders the full-screen or
line-mode frontend; a non-interactive host refuses with the substrate's
typed unsupported-console error rather than blocking. So these tests
exercise the wizard at the surfaces a non-terminal test process can
honestly reach:

* the substrate's scripted driver
  (:func:`~cadrumo.application.flows.run_scripted_flow`) walking the
  wizard's own projected selection and values/kind/reason definitions,
  then feeding those answers through the identical ``work amend``
  composition the wizard uses, and
* the non-interactive refusal (a piped caller with an amendable baseline),
  plus the period-awareness of the amendment-kind SELECT.

Nothing is mocked, stubbed, or patched: the real registry engine, the real
AEAT-attested baseline (imported through ``filing-record import``, the same
production path an operator uses before amending), and the real
bucket-scoped storage answer behind the scripted drive and the CLI amend.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, TypeAdapter

from ....adapters.persistence.profile.justificante import JustificanteRepository
from ....application.flows import FlowAnswerError, FlowPage, run_scripted_flow
from ....application.modelo import get_filing_record
from ....application.user_profile import profile_storage_session
from ....core import Period, resolve_active_bucket_id
from ....core.flows import FlowMode
from ....domain.justificante import Justificante
from ....tests.aeat_literal_fixtures import justificante_cotejo_url
from ....tests.cli_runner import invoke_cached_cli
from ....tests.modelo_cli import create_modelo_work_unit_via_cli
from ....tests.secure_sql import isolated_cli_backend as _isolated_cli_backend  # noqa: F401
from .._modelo import _resolve_work_unit_for_cli
from .._modelo_amend_wizard_cli import (
    _ACTIVE_RUNS,
    _KIND_PAGE_ID,
    _REASON_PAGE_ID,
    _amendable_rows,
    _baseline_casilla_rows,
    _selected_rows,
    _selection_definition,
    _value_page_id,
    _values_kind_reason_definition,
)
from .._modelo_cli_support import load_calculation_revision
from ._modelo_work_ux_support import _create_m130_work_unit, _create_m303_work_unit
from .envelope_helpers import unwrap_schema_envelope as _payload

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_TAX_ID = "12345678Z"

# M130 1T has no required-manual casillas (casilla 02 is `required = true` but
# `input_kind = "bound"`); a baseline carrying only casillas 01 (ingresos) and
# 02 (gastos) is a legitimate amendable AEAT-attested filing.
_BASELINE_INGRESOS = Decimal("1000.00")
_BASELINE_GASTOS = Decimal("250.00")
_CORRECTED_INGRESOS = Decimal("1100.00")

# M303 casilla 07 is the régimen-general 21% base imponible; the 2023-y-siguientes
# revision declares no required-manual casillas, so a baseline carrying 07 alone is
# a legitimate amendable AEAT-attested filing. The correction LOWERS the declared
# base: under the pre-rectificativa dual regime that direction is a solicitud de
# rectificación (LGT art. 120.3) that a self-filed complementaria cannot carry, so
# only the unified rectificativa mechanism can file it.
_M303_BASELINE_BASE_GENERAL = Decimal("10000.00")
_M303_CORRECTED_BASE_GENERAL = Decimal("9000.00")

# The fields whose values must be identical for the same amendment expressed
# through either surface (the wizard-derived inputs and a hand-built ``work
# amend``). Deliberately excluded: the fields that identify the individual
# filing and so differ by construction (`amends_filing_record_id`,
# `filing_record_id`, `work_unit_id`, `calculation_revision_id`, `period`,
# `filed_at`) -- each asserted separately.
_AMEND_PARITY_SPINE = (
    "amendment_kind",
    "status",
    "external_evidence",
    "kind",
    "live_submission",
    "aeat_accepted",
    "modelo",
    "filing_year",
    "bucket_id",
    "filed_by",
    "notes",
    "superseded_at",
    "superseded_by_filing_record_id",
)


def _invoke(args: list[str]):
    return invoke_cached_cli(args)


def _casilla_observation(revision_payload, casilla_id: str):
    """Return the single persisted observation for ``casilla_id``."""
    rows = [row for row in revision_payload["observations"] if row["casilla_id"] == casilla_id]
    assert len(rows) == 1, f"expected exactly one observation for casilla {casilla_id}, got {len(rows)}"
    return rows[0]


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


def _seed_justificante(*, csv: str, period: str = "1T", modelo: str = "130", filing_year: int = 2025) -> None:
    """Persist the stored receipt metadata a justificante-bound evidence import requires."""
    body = f"{csv}-pdf".encode()
    receipt = Justificante(
        csv=csv,
        modelo=modelo,
        period=Period.from_year_and_code(filing_year, period),
        ejercicio=str(filing_year),
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
    """Import an AEAT-attested M130 baseline filing and return its filing_record_id."""
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


def _import_external_m303_baseline(
    work_unit_id: str,
    *,
    csv: str = "JUST-2025-303-1T-AMEND-WIZARD",
    period: str = "1T",
) -> str:
    """Import an AEAT-attested M303 baseline filing and return its filing_record_id."""
    _seed_justificante(csv=csv, period=period, modelo="303")
    result = _invoke(
        [
            "--format", "json",
            "app", "modelo", "filing-record", "import", work_unit_id,
            "--evidence-kind", "aeat_justificante_pdf",
            "--evidence-id", csv,
            "--set", f"07={_M303_BASELINE_BASE_GENERAL}",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    return _payload(result.output)["filing_record_id"]


def _scripted_amend(
    work_unit_id: str,
    *,
    change_numbers: list[str],
    corrected_by_number: dict[str, str],
    kind: str,
    reason: str,
) -> tuple[dict[str, str], str, str]:
    """Drive the wizard's own two-round definitions through the scripted substrate.

    Reproduces exactly what the wizard does -- resolve the unit and its
    AEAT-attested baseline, discover the amendable casilla rows, project the
    selection and values/kind/reason definitions -- then walks them through
    :func:`run_scripted_flow` (the substrate's frontend-free scripted driver)
    instead of the interactive frontend a non-terminal test process cannot
    host. Returns the ``{casilla_id: corrected_value}`` override map plus the
    kind and reason, read back off the engine state exactly as the wizard
    reads them.
    """
    run_token = "test-amend-scripted"  # noqa: S105 - a copy-table run token, not a credential
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    with profile_storage_session(bucket_id):
        unit = _resolve_work_unit_for_cli(work_unit_id=work_unit_id)
        assert unit.current_filing_record_id is not None
        baseline = get_filing_record(unit.current_filing_record_id)
        casilla_rows = _baseline_casilla_rows(unit)
        baseline_revision = load_calculation_revision(baseline.calculation_revision_id)
        amendable = _amendable_rows(casilla_rows, baseline_revision)
        by_number = {row.number: row for row in amendable}
        selected_ids = [by_number[number].casilla_id for number in change_numbers]
        _ACTIVE_RUNS[run_token] = {}
        try:
            selection_definition = _selection_definition(
                amendable=amendable,
                baseline_revision=baseline_revision,
                unit=unit,
                run_token=run_token,
            )
            selection_state, selection_projection = run_scripted_flow(
                selection_definition,
                [",".join(selected_ids)],
                mode=FlowMode.CREATE,
            )
            assert selection_projection.submit_eligible
            selected = _selected_rows(amendable=amendable, unit=unit, state=selection_state)

            corrections_definition = _values_kind_reason_definition(
                selected=selected,
                baseline_revision=baseline_revision,
                modelo=str(baseline.modelo),
                period=baseline.period,
                run_token=run_token,
            )
            tokens = [corrected_by_number[row.number] for row in selected] + [kind, reason]
            corrections_state, corrections_projection = run_scripted_flow(
                corrections_definition,
                tokens,
                mode=FlowMode.CREATE,
            )
            assert corrections_projection.submit_eligible
            overrides = {
                row.casilla_id: (corrections_state.answers.get(_value_page_id(row.casilla_id)) or "").strip()
                for row in selected
            }
            derived_kind = (corrections_state.answers.get(_KIND_PAGE_ID) or "").strip()
            derived_reason = (corrections_state.answers.get(_REASON_PAGE_ID) or "").strip()
            return overrides, derived_kind, derived_reason
        finally:
            _ACTIVE_RUNS.pop(run_token, None)


def _amend_via_shared_path(
    *,
    from_filing_record_id: str,
    overrides: dict[str, str],
    kind: str,
    reason: str,
):
    """Invoke ``work amend`` -- the shared composition path the wizard delegates to."""
    set_flags: list[str] = []
    for casilla_id, value in overrides.items():
        set_flags += ["--set", f"{casilla_id}={value}"]
    return _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "amend",
            "--from-filing-record", from_filing_record_id,
            "--kind", kind,
            "--reason", reason,
            *set_flags,
        ],
    )  # fmt: skip


def _permitted_kind_choice_values(
    work_unit_id: str,
    *,
    change_numbers: list[str],
) -> tuple[str, ...]:
    """Return the amendment-kind SELECT's offered choice values for a baseline.

    Projects the wizard's own second-round definition and reads the kind
    page's closed choice set, so the test asserts period-awareness against
    the exact choices an operator is offered.
    """
    run_token = "test-amend-kind-choices"  # noqa: S105 - a copy-table run token, not a credential
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    with profile_storage_session(bucket_id):
        unit = _resolve_work_unit_for_cli(work_unit_id=work_unit_id)
        assert unit.current_filing_record_id is not None
        baseline = get_filing_record(unit.current_filing_record_id)
        casilla_rows = _baseline_casilla_rows(unit)
        baseline_revision = load_calculation_revision(baseline.calculation_revision_id)
        amendable = _amendable_rows(casilla_rows, baseline_revision)
        by_number = {row.number: row for row in amendable}
        selected = tuple(by_number[number] for number in change_numbers)
        _ACTIVE_RUNS[run_token] = {}
        try:
            definition = _values_kind_reason_definition(
                selected=selected,
                baseline_revision=baseline_revision,
                modelo=str(baseline.modelo),
                period=baseline.period,
                run_token=run_token,
            )
            kind_page = next(
                page for section in definition.sections for page in section.items if page.id == _KIND_PAGE_ID
            )
            assert isinstance(kind_page, FlowPage)
            return tuple(choice.value for choice in kind_page.choices)
        finally:
            _ACTIVE_RUNS.pop(run_token, None)


def test_amend_wizard_scripted_sequence_files_m130_complementaria() -> None:
    """The wizard's scripted definitions, fed to the shared amend path, file the correction.

    The substrate's scripted driver walks the wizard's own selection CHECKBOX
    (casilla 01) and its values/kind/reason round (corrected value, kind,
    reason), and those exact answers -- fed through the identical
    ``work amend`` composition the wizard uses -- supersede the imported
    AEAT-attested baseline with the corrected casilla value.
    """
    _create_profile()
    work_unit_id = _create_m130_work_unit()
    baseline_filing_id = _import_external_baseline(work_unit_id)

    overrides, kind, reason = _scripted_amend(
        work_unit_id,
        change_numbers=["01"],
        corrected_by_number={"01": str(_CORRECTED_INGRESOS)},
        kind="complementaria",
        reason="under-reported turnover",
    )
    assert kind == "complementaria"
    assert reason == "under-reported turnover"
    assert overrides == {"01": str(_CORRECTED_INGRESOS)}

    result = _amend_via_shared_path(
        from_filing_record_id=baseline_filing_id,
        overrides=overrides,
        kind=kind,
        reason=reason,
    )
    assert result.exit_code == 0, result.output
    assert "Traceback" not in result.output

    payload = _payload(result.output)
    assert payload["work_unit_id"] == work_unit_id
    assert payload["amendment_kind"] == "complementaria"
    assert payload["status"] == "vigente"
    # The new record is an internal filing envelope, not an AEAT-attested one.
    assert payload["external_evidence"] is None
    assert payload["amends_filing_record_id"] == baseline_filing_id

    # The correction is persisted, not merely reported.
    revision = _payload(
        _invoke(
            ["--format", "json", "app", "modelo", "work", "revision", payload["calculation_revision_id"]],
        ).output,
    )
    assert Decimal(revision["casilla_values"]["01"]) == _CORRECTED_INGRESOS


def test_amend_wizard_scripted_sequence_files_m303_rectificativa() -> None:
    """An Autoliquidación Rectificativa on M303 files through the wizard's scripted drive.

    Modelo 303 adopts the unified ``autoliquidación rectificativa`` (LGT art.
    120.4, Orden HAC/819/2024) from 2024 periods 09/3T onward, so 2025 1T is
    rectificativa-effective. The correction LOWERS the declared base imponible
    -- a direction a self-filed complementaria could not lawfully carry -- so a
    rectificativa is the only mechanism that can file it. The wizard's scripted
    selection + values/kind/reason answers file it through the shared amend
    path.
    """
    _create_profile()
    work_unit_id = _create_m303_work_unit()
    baseline_filing_id = _import_external_m303_baseline(work_unit_id)

    overrides, kind, reason = _scripted_amend(
        work_unit_id,
        change_numbers=["07"],
        corrected_by_number={"07": str(_M303_CORRECTED_BASE_GENERAL)},
        kind="rectificativa",
        reason="overstated base imponible",
    )
    assert kind == "rectificativa"

    result = _amend_via_shared_path(
        from_filing_record_id=baseline_filing_id,
        overrides=overrides,
        kind=kind,
        reason=reason,
    )
    assert result.exit_code == 0, result.output
    assert "Traceback" not in result.output

    payload = _payload(result.output)
    assert payload["amendment_kind"] == "rectificativa"
    assert payload["status"] == "vigente"
    assert payload["external_evidence"] is None
    assert payload["amends_filing_record_id"] == baseline_filing_id

    revision = _payload(
        _invoke(
            ["--format", "json", "app", "modelo", "work", "revision", payload["calculation_revision_id"]],
        ).output,
    )
    assert Decimal(revision["casilla_values"]["07"]) == _M303_CORRECTED_BASE_GENERAL


def test_amend_wizard_scripted_inputs_match_hand_built_work_amend() -> None:
    """Wizard-derived amend inputs and a hand-built ``work amend`` agree exactly.

    Two independently-seeded M303 2025 baselines (different quarters, both
    rectificativa-effective) are amended identically: one through the wizard's
    scripted-derived inputs, one through the raw ``work amend`` flag grammar.
    Both must resolve to the same persisted outcome -- proof the wizard is a
    guided front end over the one ``amend_modelo_revision`` path
    (``composition-service-no-parallel-write-path``), not a second,
    independently-derived amendment surface.
    """
    _create_profile()

    wizard_unit_id = _create_m303_work_unit()
    wizard_baseline_filing_id = _import_external_m303_baseline(
        wizard_unit_id,
        csv="JUST-2025-303-1T-RECT-WIZARD",
        period="1T",
    )
    overrides, kind, reason = _scripted_amend(
        wizard_unit_id,
        change_numbers=["07"],
        corrected_by_number={"07": str(_M303_CORRECTED_BASE_GENERAL)},
        kind="rectificativa",
        reason="wizard-driven rectificativa",
    )
    wizard_result = _amend_via_shared_path(
        from_filing_record_id=wizard_baseline_filing_id,
        overrides=overrides,
        kind=kind,
        reason=reason,
    )
    assert wizard_result.exit_code == 0, wizard_result.output
    wizard_payload = _payload(wizard_result.output)

    hand_unit_id = create_modelo_work_unit_via_cli(
        modelo="303",
        filing_year=2025,
        period="2T",
        revision="2023-y-siguientes",
    )
    hand_baseline_filing_id = _import_external_m303_baseline(
        hand_unit_id,
        csv="JUST-2025-303-2T-RECT-HANDBUILT",
        period="2T",
    )
    hand_built_result = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "amend",
            "--from-filing-record", hand_baseline_filing_id,
            "--kind", "rectificativa",
            "--reason", "hand-built rectificativa",
            "--set", f"07={_M303_CORRECTED_BASE_GENERAL}",
        ],
    )  # fmt: skip
    assert hand_built_result.exit_code == 0, hand_built_result.output
    hand_built_payload = _payload(hand_built_result.output)

    # The wizard-derived override set is exactly the hand-typed one.
    assert overrides == {"07": str(_M303_CORRECTED_BASE_GENERAL)}

    assert wizard_payload["amendment_kind"] == hand_built_payload["amendment_kind"] == "rectificativa"
    assert wizard_payload["amends_filing_record_id"] == wizard_baseline_filing_id
    assert hand_built_payload["amends_filing_record_id"] == hand_baseline_filing_id
    for field in _AMEND_PARITY_SPINE:
        assert wizard_payload[field] == hand_built_payload[field], field

    # The persisted revisions agree -- the parity claim is about stored state.
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
        wizard_revision["casilla_values"]["07"]
        == hand_built_revision["casilla_values"]["07"]
        == str(_M303_CORRECTED_BASE_GENERAL)
    )

    # The corrected casilla carries identical legal grounding through both
    # surfaces -- the persisted observation is where that grounding actually
    # has to survive (``aeat-calculation-grounding``).
    wizard_obs = _casilla_observation(wizard_revision, "07")
    hand_built_obs = _casilla_observation(hand_built_revision, "07")
    assert wizard_obs["value"] == hand_built_obs["value"] == str(_M303_CORRECTED_BASE_GENERAL)
    assert wizard_obs["legal_refs"], "corrected casilla must carry legal_refs"
    assert wizard_obs["legal_refs"] == hand_built_obs["legal_refs"]
    assert wizard_obs["source_refs"] == hand_built_obs["source_refs"]


def test_amend_wizard_kind_select_offers_only_period_permitted_kinds() -> None:
    """The amendment-kind SELECT is period-aware: it offers only the legally-available kinds.

    M303 2025 1T is post-unification, so the kind SELECT offers ``rectificativa``
    and NOT ``complementaria`` (the rectificativa has replaced it for ordinary
    corrections); M130 has no rectificativa regime, so its SELECT offers
    ``complementaria`` and NOT ``rectificativa``. Asserted on the projected
    choice set the operator is actually offered, not on any localized prose.
    """
    _create_profile()

    m303_unit_id = _create_m303_work_unit()
    _import_external_m303_baseline(m303_unit_id)
    m303_kinds = _permitted_kind_choice_values(m303_unit_id, change_numbers=["07"])
    assert "rectificativa" in m303_kinds
    assert "complementaria" not in m303_kinds

    m130_unit_id = _create_m130_work_unit(period="2T")
    _import_external_baseline(m130_unit_id, csv="JUST-2025-130-2T-KINDS", period="2T")
    m130_kinds = _permitted_kind_choice_values(m130_unit_id, change_numbers=["01"])
    assert "complementaria" in m130_kinds
    assert "rectificativa" not in m130_kinds


def test_amend_wizard_scripting_a_non_permitted_kind_is_refused() -> None:
    """Scripting a kind the SELECT does not offer is refused by the substrate, nothing filed.

    ``complementaria`` is not a permitted M303 2025 kind, so it is not a choice
    on the amendment-kind SELECT; the scripted driver rejects the unknown token
    with the substrate's typed answer-rejected error rather than filing it.
    """
    _create_profile()
    work_unit_id = _create_m303_work_unit()
    _import_external_m303_baseline(work_unit_id)

    with pytest.raises(FlowAnswerError):
        _scripted_amend(
            work_unit_id,
            change_numbers=["07"],
            corrected_by_number={"07": str(_M303_CORRECTED_BASE_GENERAL)},
            kind="complementaria",
            reason="should not file",
        )


def test_amend_wizard_blank_selection_yields_no_corrections() -> None:
    """A blank CHECKBOX selection reads back as no selected casillas.

    The selection page is optional, so a scripted blank answer submits with an
    empty selection -- the wizard turns that into the no-corrections refusal
    before any value is asked. Proven at the substrate level the wizard reads.
    """
    _create_profile()
    work_unit_id = _create_m130_work_unit()
    _import_external_baseline(work_unit_id)

    run_token = "test-amend-blank"  # noqa: S105 - a copy-table run token, not a credential
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    with profile_storage_session(bucket_id):
        unit = _resolve_work_unit_for_cli(work_unit_id=work_unit_id)
        assert unit.current_filing_record_id is not None
        baseline = get_filing_record(unit.current_filing_record_id)
        casilla_rows = _baseline_casilla_rows(unit)
        baseline_revision = load_calculation_revision(baseline.calculation_revision_id)
        amendable = _amendable_rows(casilla_rows, baseline_revision)
        _ACTIVE_RUNS[run_token] = {}
        try:
            definition = _selection_definition(
                amendable=amendable,
                baseline_revision=baseline_revision,
                unit=unit,
                run_token=run_token,
            )
            state, projection = run_scripted_flow(definition, [""], mode=FlowMode.CREATE)
            assert projection.submit_eligible
            assert _selected_rows(amendable=amendable, unit=unit, state=state) == ()
        finally:
            _ACTIVE_RUNS.pop(run_token, None)


def test_amend_wizard_non_interactive_host_refuses_with_the_typed_console_error() -> None:
    """A non-TTY caller with an amendable baseline gets the substrate's typed refusal.

    The test process is non-interactive, so the wizard -- which has a CHECKBOX
    selection page to present -- must refuse through the flow substrate's
    unsupported-console error rather than block. Asserted structurally on the
    envelope error code, never on localized prose.
    """
    _create_profile()
    work_unit_id = _create_m130_work_unit()
    _import_external_baseline(work_unit_id)

    result = _invoke(["--format", "json", "app", "modelo", "work", "amend-wizard", work_unit_id])

    assert result.exit_code != 0
    assert "Traceback" not in result.output
    error = json.loads(result.output)["error"]
    assert error["code"] == "REFUSED_FLOW_UNSUPPORTED_CONSOLE"


def test_amend_wizard_refuses_without_evidence_baseline() -> None:
    """A local work unit cannot enter the external-filing amendment path.

    The evidence check runs before any flow is constructed, so the refusal is a
    plain instructive parameter error, never the console refusal.
    """
    _create_profile()
    work_unit_id = _create_m130_work_unit()

    result = _invoke(["--format", "json", "app", "modelo", "work", "amend-wizard", work_unit_id])

    assert result.exit_code != 0
    assert "Traceback" not in result.output
