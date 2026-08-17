"""Acceptance-wall catalogue: the closed-wall -> regression-test binding table.

Issue ``#406`` names the failure mode: an acceptance-journey scenario ("an
acceptance wall") closes behind a regression test, but nothing structurally
proves that test keeps running -- so the wall can silently reopen (its
guarding test is deleted, renamed, or its module stops being collectible)
with no CI signal.

The investigation (see the ``#406`` verify-and-triage comment trail) found the
mechanism gap is NOT "no regression tests exist" -- ~2500 ``integration``-marked
tests already guard closed acceptance walls end-to-end via the real CLI. The
gap is that ``pyproject.toml`` scopes every plain ``pytest`` invocation
(including the CI "Test (unit)" step, which runs bare
``pytest --junitxml=junit.xml`` and inherits ``addopts -m 'unit'``) to the
``unit`` marker only. Every ``integration``-marked wall test -- which is every
acceptance-journey / persona CLI acceptance suite in this codebase -- never
runs in CI at all, so a real regression in one is invisible until a human
happens to run ``just test-integration`` locally.

This module is the catalogue half of the fix: a small, typed, explicit binding
from a closed acceptance-wall issue to the exact test module + test function
that guards it. :mod:`cadrumo.tests.test_acceptance_wall_catalogue` is the gate
half: it walks this catalogue and proves, by real pytest collection, that
every enrolled wall's guarding test still exists and still collects.

This is a representative subset, not the full closed-wall set (~30+ closed
``acceptance-journey``-labelled issues at time of writing). Follow-up
enrollment passes added closed issues that (a) name a concrete, still-current
observable capability and (b) resolve to a real, collectible,
``integration``-marked guarding test at time of enrollment. Several closed
``acceptance-journey`` issues are deliberately NOT enrolled because they were
closed as duplicate, obsolete, or superseded-by-a-later-architecture (the
pre-registry ``aeat.formulas`` ruleset issues, the pre-restructure top-level
CLI surfaces, the Google Cloud bootstrap issues, and the per-modelo
"calc-verify-roundtrip"/Tier-R/Tier-S PDF-extraction family whose cited tests
either no longer exist or are ``unit``-marked parser-boundary tests that the
gate's ``-m integration`` subprocess mechanism would silently deselect --
enrolling those would require fabricating a test binding or accepting a
tautological "0 tests ran" pass, either of which the gate's subprocess-run
mechanism would then treat as unrelated to a real regression. Enrolling the
remainder is scoped as an ongoing follow-up; the mechanism (this catalogue +
the gate + the CI wiring) is what issue ``#406`` asks for, and it generalises
to any number of future entries with no further catalogue-format change.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from ..core import STRICT_FROZEN_CONFIG


class AcceptanceWallEntry(BaseModel):
    """One closed acceptance-wall -> regression-test binding.

    Attributes:
        issue: The GitHub issue number that closed this wall, or ``None`` when
            the wall was tracked as an internal finding (a persona testimonial
            or CRUD-audit defect) rather than a filed issue. Exactly one of
            ``issue`` / ``internal_reference`` must be set.
        internal_reference: A short internal citation (e.g. a persona name or
            defect label) when no GitHub issue number exists.
        capability: One sentence naming the capability this wall protects.
        test_module: Repository-relative path to the guarding test module,
            POSIX-separated (e.g.
            ``"src/cadrumo/entrypoints/cli/tests/test_ledger_exclude_journey.py"``).
        test_function: The guarding test function name inside ``test_module``.
    """

    model_config = STRICT_FROZEN_CONFIG

    issue: int | None = Field(default=None, ge=1)
    internal_reference: str | None = Field(default=None, min_length=1)
    capability: str = Field(min_length=1)
    test_module: str = Field(min_length=1)
    test_function: str = Field(min_length=1)

    @model_validator(mode="after")
    def _exactly_one_reference(self) -> AcceptanceWallEntry:
        """Refuse an entry with both, or neither, of ``issue`` / ``internal_reference``."""
        has_issue = self.issue is not None
        has_internal = self.internal_reference is not None
        if has_issue == has_internal:
            message = "AcceptanceWallEntry requires exactly one of `issue` or `internal_reference`, got: " + repr(self)
            raise ValueError(message)
        return self

    @property
    def node_id(self) -> str:
        """Return the pytest node id ``test_module::test_function``."""
        return f"{self.test_module}::{self.test_function}"

    @property
    def label(self) -> str:
        """Return a human-readable label for diagnostics: issue or internal ref."""
        if self.issue is not None:
            return f"#{self.issue}"
        return self.internal_reference or "unlabelled"


ACCEPTANCE_WALL_CATALOGUE: tuple[AcceptanceWallEntry, ...] = (
    AcceptanceWallEntry(
        issue=220,
        capability=("A stored draft revision renders the formula and operand values inline when reviewed."),
        test_module="src/cadrumo/entrypoints/cli/tests/test_modelo_revision_trace.py",
        test_function="test_work_revision_renders_inline_formula_trace_for_computed_casilla",
    ),
    AcceptanceWallEntry(
        issue=224,
        capability="A transaction can be marked 'reviewed and intentionally excluded'.",
        test_module="src/cadrumo/entrypoints/cli/tests/test_ledger_exclude_journey.py",
        test_function="test_exclude_returns_quintet_and_marks_row_excluded",
    ),
    AcceptanceWallEntry(
        internal_reference="ledger-restore-journey (CRUD-audit journey e, D2 restore verb)",
        capability=(
            "An operator who stashed half their ledger rows by mistake can restore them without a whole-ledger reset."
        ),
        test_module="src/cadrumo/entrypoints/cli/tests/test_ledger_restore_journey.py",
        test_function="test_bulk_stash_recovery_restores_every_row_without_a_reset",
    ),
    AcceptanceWallEntry(
        internal_reference="ledger-fx-conversion (persona-surfaced HIGH defect)",
        capability="Foreign-currency bank rows import converted to EUR, not silently unconverted.",
        test_module="src/cadrumo/entrypoints/cli/tests/test_ledger_fx_import.py",
        test_function="test_cli_import_converts_foreign_rows_to_eur",
    ),
    AcceptanceWallEntry(
        issue=529,
        capability="--output-language is available on every user-facing verb, not just some of them.",
        test_module="src/cadrumo/entrypoints/cli/tests/test_output_language_parity.py",
        test_function="test_modelo_work_commands_accept_output_language",
    ),
    AcceptanceWallEntry(
        internal_reference="autonoma-persona-1t-2025-close (autonoma quarterly-close testimonial)",
        capability=("A freelance/autónoma filer can import, classify, and close a full quarter end-to-end."),
        test_module="src/cadrumo/entrypoints/cli/tests/test_ledger_persona_autonoma_close.py",
        test_function="test_autonoma_closes_1t_2025_end_to_end",
    ),
    AcceptanceWallEntry(
        issue=223,
        capability=(
            "The operator records WHY when classifying a transaction, via a --reason flag that persists to notes."
        ),
        test_module="src/cadrumo/entrypoints/cli/tests/test_ledger_classify_ux.py",
        test_function="test_classify_reason_persists_to_transaction_notes",
    ),
    AcceptanceWallEntry(
        issue=263,
        capability=(
            "The operator filters their transaction catalogue by an AEAT period token plus year, "
            "not a bespoke calendar grammar."
        ),
        test_module="src/cadrumo/entrypoints/cli/tests/test_ledger_period_grammar.py",
        test_function="test_aeat_token_plus_year_resolves_to_period",
    ),
    AcceptanceWallEntry(
        issue=260,
        capability="One command walks the data-prep workflow and shows which step the operator is on.",
        test_module="src/cadrumo/entrypoints/cli/tests/test_overview_prepare_verb.py",
        test_function="test_prepare_shows_import_step_pending_on_fresh_profile",
    ),
    AcceptanceWallEntry(
        issue=261,
        capability=(
            "The operator asks what data is needed for a given modelo and period and gets a "
            "registry-grounded checklist."
        ),
        test_module="src/cadrumo/entrypoints/cli/tests/test_modelo_requires_data_inventory.py",
        test_function="test_requires_classifies_m130_casillas_against_live_registry_no_active_profile",
    ),
    AcceptanceWallEntry(
        issue=276,
        capability=(
            "The operator backs up their local catalogue to an archive and restores it on a fresh "
            "machine without data loss."
        ),
        test_module="src/cadrumo/entrypoints/cli/tests/test_profile_archive_roundtrip.py",
        test_function="test_archive_export_restore_roundtrip",
    ),
    AcceptanceWallEntry(
        issue=219,
        capability=("A Modelo 130 draft is built through a guided wizard instead of hand-writing casilla-code JSON."),
        test_module="src/cadrumo/entrypoints/cli/tests/test_modelo_work_wizard.py",
        test_function="test_wizard_scripted_path_walks_the_manual_sequence_and_lands_the_m130_draft",
    ),
    AcceptanceWallEntry(
        issue=217,
        capability="Hundreds of transactions bulk-classify from a CSV instead of one-by-one.",
        test_module="src/cadrumo/entrypoints/cli/tests/test_ledger_bulk_classify.py",
        test_function="test_classify_from_csv_applies_all_valid_rows",
    ),
    AcceptanceWallEntry(
        issue=423,
        capability=(
            "A late-night filing completes in one command via aeat quickfile, all the way to an exported fichero."
        ),
        test_module="src/cadrumo/entrypoints/cli/tests/test_app_quickfile.py",
        test_function="test_quickfile_runs_full_chain_to_exported_fichero",
    ),
    AcceptanceWallEntry(
        issue=419,
        capability=(
            "An Autoliquidacion Rectificativa IVA correction on Modelo 303 files through the guided amend wizard."
        ),
        test_module="src/cadrumo/entrypoints/cli/tests/test_modelo_amend_wizard.py",
        test_function="test_amend_wizard_scripted_sequence_files_m303_rectificativa",
    ),
    AcceptanceWallEntry(
        internal_reference="amend-wizard-complementaria (wall #419 capability/test split)",
        capability=(
            "A complementaria correction on an AEAT-attested Modelo 130 filing runs through the guided amend wizard."
        ),
        test_module="src/cadrumo/entrypoints/cli/tests/test_modelo_amend_wizard.py",
        test_function="test_amend_wizard_scripted_sequence_files_m130_complementaria",
    ),
    AcceptanceWallEntry(
        issue=425,
        capability=(
            "Actionable post-filing AEAT events (requerimientos, propuestas, devoluciones) surface "
            "as a single warning notice."
        ),
        test_module="src/cadrumo/entrypoints/cli/tests/test_overview_post_filing_notices.py",
        test_function="test_actionable_events_emit_single_warning_notice",
    ),
    AcceptanceWallEntry(
        issue=259,
        capability=(
            "The operator sets their own home-office/mileage/phone usage ratio once via "
            "`aeat app ledger ratios set`, and it sticks -- never re-entered."
        ),
        test_module="src/cadrumo/entrypoints/cli/tests/test_ratios_verbs.py",
        test_function="test_ratios_set_persists_and_list_reflects",
    ),
    AcceptanceWallEntry(
        issue=271,
        capability=(
            "The operator has the justificante PDF of a filing already made on the AEAT portal and "
            "reconciles a local work unit against it without any AEAT certificate authentication -- "
            "`aeat app modelo reconcile file --file`."
        ),
        test_module="src/cadrumo/entrypoints/cli/tests/test_modelo_reconcile_verb.py",
        test_function="test_reconcile_file_happy_path",
    ),
    AcceptanceWallEntry(
        issue=273,
        capability=(
            "The operator imports a past filing's casilla values from a spreadsheet (CSV/XLSX) with "
            "no AEAT certificate, and those values feed the cross-period `previous_filing` prefill "
            "for a later calculation."
        ),
        test_module="src/cadrumo/entrypoints/cli/tests/test_modelo_local_observation_spreadsheet_cli.py",
        test_function="test_observe_local_from_csv_spreadsheet_persists_non_official_observation",
    ),
    AcceptanceWallEntry(
        issue=253,
        capability=(
            "A spending category is assigned to a transaction at classification time, and the "
            "category persists on the transaction record."
        ),
        test_module="src/cadrumo/entrypoints/cli/tests/test_ledger_validation_paths.py",
        test_function="test_ledger_classify_persists_professional_service_paid_net_of_irpf_withholding",
    ),
    AcceptanceWallEntry(
        issue=218,
        capability=(
            "The operator sees how much is owed for Modelo 130 this quarter: classified ledger "
            "income and expenses aggregate into the registry-computed resultado parcial casilla, "
            "not a hand-maintained spreadsheet."
        ),
        test_module="src/cadrumo/entrypoints/cli/tests/test_modelo_calculation_through_real_cli.py",
        test_function="test_modelo_130_resultado_apartado_i_direct_estimation",
    ),
    AcceptanceWallEntry(
        issue=324,
        capability=(
            "Modelo 200 (Impuesto sobre Sociedades) micro-empresa cuota integra computes correctly "
            "against the AEAT Manual Practico rate, not just a formula that happens to run."
        ),
        test_module="src/cadrumo/entrypoints/cli/tests/test_modelo_calculation_through_real_cli.py",
        test_function="test_modelo_200_micro_empresa_pyme_cuota_2024",
    ),
    AcceptanceWallEntry(
        issue=325,
        capability=(
            "Modelo 202 pago fraccionado (Art. 40.2 LIS lane) computes the 18% cuota against the "
            "prior period's base correctly for a taxpayer below the INCN threshold."
        ),
        test_module="src/cadrumo/entrypoints/cli/tests/test_modelo_calculation_through_real_cli.py",
        test_function="test_modelo_202_art_40_2_cuota_incn_below_threshold",
    ),
    AcceptanceWallEntry(
        issue=257,
        capability=(
            "The usage ratio (home-office/mileage/phone split) actually feeds the deductible-expense "
            "calculation, not just a stored preference: classified ledger expenses aggregate into the "
            "registry-computed M100 casilla at the ratio-adjusted amount."
        ),
        test_module="src/cadrumo/entrypoints/cli/tests/test_modelo_source_mesh_calculate.py",
        test_function="test_work_calculate_modelo_100_routes_autonoma_auto_ledger_expenses",
    ),
    AcceptanceWallEntry(
        issue=326,
        capability=(
            "The operator has their Modelo 303 declaración PDF and reconciles a work unit against it "
            "via `aeat app modelo reconcile file --kind declaration`: the tool re-derives every "
            "printed casilla against the computed revision and reports a real casilla-level "
            "divergence, not a header-only compare."
        ),
        test_module="src/cadrumo/entrypoints/cli/tests/test_modelo_reconcile_verb.py",
        test_function="test_reconcile_file_kind_declaration_catches_casilla_divergence",
    ),
    AcceptanceWallEntry(
        issue=321,
        capability=(
            "The operator has their Modelo 130 declaración PDF and reconciles a work unit against it "
            "via `aeat app modelo reconcile file --kind declaration`: a computed casilla that "
            "disagrees with the filed declaración is caught as a real divergence, not a silent "
            "identity match."
        ),
        test_module="src/cadrumo/entrypoints/cli/tests/test_modelo_reconcile_verb.py",
        test_function="test_reconcile_file_kind_declaration_m130_catches_casilla_divergence",
    ),
    AcceptanceWallEntry(
        issue=318,
        capability=(
            "The operator has their Modelo 111 declaración PDF and reconciles a work unit against it "
            "via `aeat app modelo reconcile file --kind declaration`, even though the fixture's own "
            "header lacks a detectable ejercicio stamp -- the work unit's own known context lets the "
            "parse succeed, and a computed casilla that disagrees with the filed declaración is "
            "still caught as a real divergence."
        ),
        test_module="src/cadrumo/entrypoints/cli/tests/test_modelo_reconcile_verb.py",
        test_function="test_reconcile_file_kind_declaration_m111_catches_casilla_divergence",
    ),
    AcceptanceWallEntry(
        issue=327,
        capability=(
            "The operator has their Modelo 390 (IVA resumen anual) declaración PDF and reconciles a "
            "work unit against it via `aeat app modelo reconcile file --kind declaration`: a computed "
            "IVA anual casilla that disagrees with the filed declaración is caught as a real "
            "divergence."
        ),
        test_module="src/cadrumo/entrypoints/cli/tests/test_modelo_reconcile_verb.py",
        test_function="test_reconcile_file_kind_declaration_m390_catches_casilla_divergence",
    ),
    AcceptanceWallEntry(
        issue=328,
        capability=(
            "The operator has their Modelo 190 (resumen anual de retenciones) declaración PDF and "
            "reconciles a work unit against it via `aeat app modelo reconcile file --kind "
            "declaration`: a computed retenciones-total casilla that disagrees with the filed "
            "declaración is caught as a real divergence, the Tier-S summary return "
            "calc-verify-roundtrip claim."
        ),
        test_module="src/cadrumo/entrypoints/cli/tests/test_modelo_reconcile_verb.py",
        test_function="test_reconcile_file_kind_declaration_m190_catches_casilla_divergence",
    ),
)
"""The enrolled representative subset of closed acceptance walls.

Append new entries here as later work enrolls the remaining closed
``acceptance-journey`` issues; :mod:`cadrumo.tests.test_acceptance_wall_catalogue`
re-derives its assertions from this tuple, so no gate code changes are needed
to enroll more walls.
"""


__all__ = ["ACCEPTANCE_WALL_CATALOGUE", "AcceptanceWallEntry"]
