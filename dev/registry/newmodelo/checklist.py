"""The 12-item contributor checklist for taking a scaffolded modelo revision calc-grade.

Scaffolding an empty directory tree (:mod:`dev.registry.newmodelo.manager`) only
creates the skeleton a new modelo revision needs; it does not — and cannot —
author the regulated content itself. This module is the single source of the
checklist a contributor works through after scaffolding, so the same 12 items
render identically from ``python -m dev.registry.newmodelo checklist`` and from
the summary the ``scaffold`` command prints after writing the tree.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["CHECKLIST", "ChecklistItem"]


@dataclass(frozen=True, slots=True)
class ChecklistItem:
    """One contributor checklist entry.

    Attributes:
        title: Short imperative summary of the required action.
        detail: The concrete registry fragment(s) and grounding this item
            covers, and why it is required before the revision is calc-grade.
    """

    title: str
    detail: str


CHECKLIST: tuple[ChecklistItem, ...] = (
    ChecklistItem(
        title="Declare the modelo manifest",
        detail=(
            "manifest.toml: [modelo] id, tax_domain, cadence, jurisdiction, legal_refs, "
            "source_refs. legal_refs must resolve against the legal catalogue "
            "(aeat-registry-authority-flow) and source_refs against the source catalogue. "
            "The title and official name are localizable values, not schema fields: author "
            "them in the shared locale catalogues with 'python -m dev.locales set', "
            "against the derived keys the scaffolded manifest names in its header comment."
        ),
    ),
    ChecklistItem(
        title="Ground the revision window and applicability",
        detail=(
            "revisions/<revision-id>/revision.toml: valid_from/valid_to, period_selector, "
            "legal_refs, source_refs, and the mandatory orden_aplicabilidad citing the "
            "Orden(es) ministeriales that approve or amend this revision's form."
        ),
    ),
    ChecklistItem(
        title="Author every casilla with legal grounding",
        detail=(
            "revisions/<revision-id>/casillas/*.toml: one CasillaDefinition per box, each "
            "carrying legal_refs to the specific binding provision that establishes it "
            "(aeat-calculation-grounding), not just the framework article, and "
            "source_refs to the AEAT Diseño / procedure that defines its number/segment."
        ),
    ),
    ChecklistItem(
        title="Author formulas for every computed casilla",
        detail=(
            "revisions/<revision-id>/formulas/*.toml: a FormulaDefinition per derived "
            "casilla; the formula and every casilla it references must resolve inside the "
            "revision's calculation closure (no orphan formula targets)."
        ),
    ),
    ChecklistItem(
        title="Author bindings for every data-sourced casilla",
        detail=(
            "revisions/<revision-id>/bindings/*.toml: a DataBindingDefinition per casilla "
            "fed from the ledger, profile, counterpart, or another modelo. Use the single "
            "canonical BindingSourceKind taxonomy (aeat-registry-bindings) and "
            "enroll a new source resolver in the live calculate mesh "
            "(aeat-calculation-aggregation) rather than leaving it dormant."
        ),
    ),
    ChecklistItem(
        title="Close the calculation-completeness manifest",
        detail=(
            "revisions/<revision-id>/completeness_manifest/*.toml: enumerate the "
            "revision's full calculation closure (every formula target, formula-expression "
            "reference, binding/relation endpoint, verification-expectation operand) keyed "
            "by canonical casilla_id plus reviewed segment/number metadata "
            "(modelo-export-mirrors-official-structure)."
        ),
    ),
    ChecklistItem(
        title="Author verification expectations and predicates",
        detail=(
            "revisions/<revision-id>/verification_expectations/*.toml: declare "
            "computed / reconcile-when-present casillas and any BLOCKING_RULE or ADVISORY "
            "verification_predicates (no-silent-under-declaration); ground every predicate "
            "against a bundled AEAT-authoritative oracle before marking it "
            "externally_grounded (no-silent-under-declaration)."
        ),
    ),
    ChecklistItem(
        title="Register the export layout(s)",
        detail=(
            "revisions/<revision-id>/export_layouts/*.toml: the fixed-width fichero-BOE "
            "and/or xml_dictionary layout(s) that mirror the official AEAT structure "
            "(modelo-export-mirrors-official-structure); every required, representable "
            "casilla must be exportable, not silently blank."
        ),
    ),
    ChecklistItem(
        title="Register an extraction profile (if the modelo has a PDF/justificante source)",
        detail=(
            "revisions/<revision-id>/extraction_profiles/*.toml: the field-extraction "
            "profile used to parse a filed PDF/justificante back into casilla values, when "
            "the modelo supports local-filed reconciliation."
        ),
    ),
    ChecklistItem(
        title="Author shared locale keys",
        detail=(
            "src/cadrumo/locales/{es,en,ca,hu}.yml: derived casilla labels and "
            "help text via `python -m dev.locales scaffold/set` "
            "(aeat-locales-cli) — never create revision-local locale files or "
            "hand-edit catalogue YAML. Spanish in es.yml is the official Casilla source; "
            "non-Spanish values derive from that source through the shared key resolver."
        ),
    ),
    ChecklistItem(
        title="Enroll the modelo id in the core Modelo enum",
        detail=(
            "src/cadrumo/core/modelo.py: add the new modelo's Modelo.M<code> member so "
            "production code references it through the enum, never a bare string literal "
            "(aeat-registry-authority-flow); the registry-parity gate binds enum "
            "members to registry_modelo_codes()."
        ),
    ),
    ChecklistItem(
        title="Write real-behavior tests and regenerate generated docs",
        detail=(
            "Add roundtrip/structural tests under the owning domain tests/ folder "
            "(aeat-architecture-boundaries, aeat-quality-gates); "
            "regenerate docs/api stubs (`python -m dev.docs.apidocs scaffold`) and modelo "
            "coverage docs if the new modelo introduces new public symbols."
        ),
    ),
)


def render_checklist() -> str:
    """Render the 12-item checklist as a numbered, human-readable report."""
    lines: list[str] = [f"Contributor checklist for a new modelo revision ({len(CHECKLIST)} items):"]
    for index, item in enumerate(CHECKLIST, start=1):
        lines.append(f"  {index:>2}. {item.title}")
        lines.append(f"      {item.detail}")
    return "\n".join(lines)
