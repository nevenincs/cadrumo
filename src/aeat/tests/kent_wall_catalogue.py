"""Kent-wall catalogue: the closed-wall -> regression-test binding table.

Issue ``#406`` names the failure mode: a Kent-journey acceptance scenario ("a
Kent wall") closes behind a regression test, but nothing structurally proves
that test keeps running -- so the wall can silently reopen (its guarding test
is deleted, renamed, or its module stops being collectible) with no CI signal.

The investigation (see the ``#406`` verify-and-triage comment trail) found the
mechanism gap is NOT "no regression tests exist" -- ~2500 ``integration``-marked
tests already guard closed Kent walls end-to-end via the real CLI. The gap is
that ``pyproject.toml`` scopes every plain ``pytest`` invocation (including the
CI "Test (unit)" step, which runs bare ``pytest --junitxml=junit.xml`` and
inherits ``addopts -m 'unit'``) to the ``unit`` marker only. Every
``integration``-marked wall test -- which is every Kent-journey / persona CLI
acceptance suite in this codebase -- never runs in CI at all, so a real
regression in one is invisible until a human happens to run
``just test-integration`` locally.

This module is the catalogue half of the fix: a small, typed, explicit binding
from a closed Kent-wall issue to the exact test module + test function that
guards it. :mod:`aeat.tests.test_kent_wall_catalogue` is the gate half: it
walks this catalogue and proves, by real pytest collection, that every
enrolled wall's guarding test still exists and still collects.

This is a representative subset, not the full closed-wall set (~30+ closed
``kent-journey``-labelled issues at time of writing). A follow-up enrollment
pass added the batch of closed issues that (a) name a concrete, still-current
Kent-observable capability and (b) resolve to a real, collectible,
``integration``-marked guarding test at time of enrollment. Several closed
``kent-journey`` issues are deliberately NOT enrolled because they were closed
as duplicate, obsolete, or superseded-by-a-later-architecture (the pre-registry
``aeat.formulas`` ruleset issues, the pre-restructure top-level CLI surfaces,
and the Google Cloud bootstrap issues), and therefore name no guarding test that
still exists; enrolling those would require fabricating a test binding, which
the gate's subprocess-run mechanism would then fail on for reasons unrelated to
a real regression. Enrolling the remainder is scoped as an ongoing follow-up;
the mechanism (this catalogue + the gate + the CI wiring) is what issue
``#406`` asks for, and it generalises to any number of future entries with no
further catalogue-format change.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from ..core import STRICT_FROZEN_CONFIG


class KentWallEntry(BaseModel):
    """One closed Kent-wall -> regression-test binding.

    Attributes:
        issue: The GitHub issue number that closed this wall, or ``None`` when
            the wall was tracked as an internal finding (a persona testimonial
            or CRUD-audit defect) rather than a filed issue. Exactly one of
            ``issue`` / ``internal_reference`` must be set.
        internal_reference: A short internal citation (e.g. a persona name or
            defect label) when no GitHub issue number exists.
        kent_perspective: One sentence, Kent's perspective, naming the
            capability this wall protects.
        test_module: Repository-relative path to the guarding test module,
            POSIX-separated (e.g.
            ``"src/aeat/entrypoints/cli/tests/test_ledger_exclude_journey.py"``).
        test_function: The guarding test function name inside ``test_module``.
    """

    model_config = STRICT_FROZEN_CONFIG

    issue: int | None = Field(default=None, ge=1)
    internal_reference: str | None = Field(default=None, min_length=1)
    kent_perspective: str = Field(min_length=1)
    test_module: str = Field(min_length=1)
    test_function: str = Field(min_length=1)

    @model_validator(mode="after")
    def _exactly_one_reference(self) -> KentWallEntry:
        """Refuse an entry with both, or neither, of ``issue`` / ``internal_reference``."""
        has_issue = self.issue is not None
        has_internal = self.internal_reference is not None
        if has_issue == has_internal:
            message = "KentWallEntry requires exactly one of `issue` or `internal_reference`, got: " + repr(self)
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


KENT_WALL_CATALOGUE: tuple[KentWallEntry, ...] = (
    KentWallEntry(
        issue=220,
        kent_perspective=("Kent sees the formula and operand values inline when he reviews a stored draft revision."),
        test_module="src/aeat/entrypoints/cli/tests/test_modelo_revision_trace.py",
        test_function="test_work_revision_renders_inline_formula_trace_for_computed_casilla",
    ),
    KentWallEntry(
        issue=224,
        kent_perspective="Kent can mark a transaction 'reviewed and intentionally excluded'.",
        test_module="src/aeat/entrypoints/cli/tests/test_ledger_exclude_journey.py",
        test_function="test_exclude_returns_quintet_and_marks_row_excluded",
    ),
    KentWallEntry(
        internal_reference="ledger-restore-journey (CRUD-audit journey e, D2 restore verb)",
        kent_perspective=(
            "Kent who stashed half his ledger rows by mistake can restore them without a whole-ledger reset."
        ),
        test_module="src/aeat/entrypoints/cli/tests/test_ledger_restore_journey.py",
        test_function="test_bulk_stash_recovery_restores_every_row_without_a_reset",
    ),
    KentWallEntry(
        internal_reference="ledger-fx-conversion (persona-surfaced HIGH defect)",
        kent_perspective="Kent's foreign-currency bank rows import converted to EUR, not silently unconverted.",
        test_module="src/aeat/entrypoints/cli/tests/test_ledger_fx_import.py",
        test_function="test_cli_import_converts_foreign_rows_to_eur",
    ),
    KentWallEntry(
        issue=529,
        kent_perspective="Kent can request --output-language on every user-facing verb, not just some of them.",
        test_module="src/aeat/entrypoints/cli/tests/test_output_language_parity.py",
        test_function="test_modelo_work_commands_accept_output_language",
    ),
    KentWallEntry(
        internal_reference="marta-persona-1t-2025-close (autonoma quarterly-close testimonial)",
        kent_perspective=(
            "Kent (as Marta, a freelance consultant) can import, classify, and close a full quarter end-to-end."
        ),
        test_module="src/aeat/entrypoints/cli/tests/test_ledger_persona_autonoma_close.py",
        test_function="test_marta_closes_1t_2025_end_to_end",
    ),
    KentWallEntry(
        issue=223,
        kent_perspective=(
            "Kent records WHY when he classifies a transaction, via a --reason flag that persists to notes."
        ),
        test_module="src/aeat/entrypoints/cli/tests/test_ledger_classify_ux.py",
        test_function="test_classify_reason_persists_to_transaction_notes",
    ),
    KentWallEntry(
        issue=263,
        kent_perspective=(
            "Kent filters his transaction catalogue by an AEAT period token plus year, not a bespoke calendar grammar."
        ),
        test_module="src/aeat/entrypoints/cli/tests/test_ledger_period_grammar.py",
        test_function="test_aeat_token_plus_year_resolves_to_period",
    ),
    KentWallEntry(
        issue=260,
        kent_perspective="Kent runs one command to walk the data-prep workflow and sees which step he is on.",
        test_module="src/aeat/entrypoints/cli/tests/test_overview_prepare_verb.py",
        test_function="test_prepare_shows_import_step_pending_on_fresh_profile",
    ),
    KentWallEntry(
        issue=261,
        kent_perspective=(
            "Kent asks what data he needs for a given modelo and period and gets a registry-grounded checklist."
        ),
        test_module="src/aeat/entrypoints/cli/tests/test_modelo_requires_data_inventory.py",
        test_function="test_requires_classifies_m130_casillas_against_live_registry_no_active_profile",
    ),
    KentWallEntry(
        issue=276,
        kent_perspective=(
            "Kent backs up his local catalogue to an archive and restores it on a fresh machine without data loss."
        ),
        test_module="src/aeat/entrypoints/cli/tests/test_profile_archive_roundtrip.py",
        test_function="test_archive_export_import_recovery_wrap_roundtrip",
    ),
    KentWallEntry(
        issue=219,
        kent_perspective=(
            "Kent builds a Modelo 130 draft through a guided wizard instead of hand-writing casilla-code JSON."
        ),
        test_module="src/aeat/entrypoints/cli/tests/test_modelo_work_wizard.py",
        test_function="test_wizard_drives_m130_draft_through_full_prompt_sequence",
    ),
    KentWallEntry(
        issue=217,
        kent_perspective="Kent bulk-classifies hundreds of transactions from a CSV instead of one-by-one.",
        test_module="src/aeat/entrypoints/cli/tests/test_ledger_bulk_classify.py",
        test_function="test_classify_from_csv_applies_all_valid_rows",
    ),
    KentWallEntry(
        issue=423,
        kent_perspective=(
            "Kent at 11pm on deadline night files in one command via aeat quickfile, all the way to an exported "
            "fichero."
        ),
        test_module="src/aeat/entrypoints/cli/tests/test_app_quickfile.py",
        test_function="test_quickfile_runs_full_chain_to_exported_fichero",
    ),
    KentWallEntry(
        issue=419,
        kent_perspective=(
            "Kent files an Autoliquidacion Rectificativa IVA correction on Modelo 303 through the guided amend wizard."
        ),
        test_module="src/aeat/entrypoints/cli/tests/test_modelo_amend_wizard.py",
        test_function="test_amend_wizard_drives_full_prompt_sequence_and_files_correction",
    ),
    KentWallEntry(
        issue=425,
        kent_perspective=(
            "Kent sees actionable post-filing AEAT events (requerimientos, propuestas, devoluciones) "
            "surfaced as a single warning notice."
        ),
        test_module="src/aeat/entrypoints/cli/tests/test_overview_post_filing_notices.py",
        test_function="test_actionable_events_emit_single_warning_notice",
    ),
    KentWallEntry(
        issue=259,
        kent_perspective=(
            "Kent sets his own home-office/mileage/phone usage ratio once via "
            "`aeat app ledger ratios set`, and it sticks -- he never re-enters it."
        ),
        test_module="src/aeat/entrypoints/cli/tests/test_ratios_verbs.py",
        test_function="test_ratios_set_persists_and_list_reflects",
    ),
)
"""The enrolled representative subset of closed Kent walls.

Append new entries here as later work enrolls the remaining closed
``kent-journey`` issues; :mod:`aeat.tests.test_kent_wall_catalogue` re-derives
its assertions from this tuple, so no gate code changes are needed to enroll
more walls.
"""


__all__ = ["KENT_WALL_CATALOGUE", "KentWallEntry"]
