"""Historical one-shot applicability transcriber retained for ``W03.P08.S19``.

``W01.P03.S09`` used this tool to transcribe every then-unowned literal into
``applicability/0001-applicability.toml`` fragments, hydration-check the real
loader result, cut production over to the registry family, and delete those
literals. Production therefore already reads the registry-authored fragments
for every migrated modelo; only the export campaign's still-owned Modelo 303
and 390 literals remain.

Those two modelos stay in :data:`EXCLUDED_MODELOS` until ``W03.P08.S19``
releases their trees. That step reuses this exact transcriber for the final
equivalence proof before it removes the last literal-carrying mechanism. This
module is historical tooling, never a production fallback.

Usage:

    python -m dev.registry.authoring_migrate_applicability_fragments [--apply] [--json OUT.json]

Default is a dry run: prints what would be written, writes nothing. ``--apply``
performs the writes, then re-loads every migrated modelo through the real
loader, hydrates every written fragment, and proves it compares equal to the
literal it replaced.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import tomlkit

from cadrumo.core.directory_scan import DirectoryEntryKind, scan_directory
from cadrumo.core.modelo import Modelo
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.applicability import (
    ModeloApplicabilityRule,
    hydrate_applicability_rule,
    iter_modelo_applicability_rules,
)
from cadrumo.domain.calculations.registry.loader import load_modelo_directory
from cadrumo.domain.calculations.registry.schema import ApplicabilityRuleDefinition

MODELOS_ROOT = bundled_path("registry", "aeat", "modelos")

#: Owned by the export-fragment-generator-authority campaign. ``W03.P08.S19``
#: releases these trees and removes this temporary exclusion before its final run.
EXCLUDED_MODELOS: frozenset[str] = frozenset({"303", "390"})


@dataclass(frozen=True)
class MigrationOutcome:
    """The result of migrating one modelo's applicability rule."""

    modelo: str
    revisions: tuple[str, ...]
    written: bool
    equal_to_literal: bool
    mismatch_detail: str | None = None


def _fragment_table_text(rule: ModeloApplicabilityRule) -> str:
    """Render ``rule`` as an ``ApplicabilityRuleDefinition`` TOML table body.

    Uses ``tomlkit`` for correct string escaping (Spanish reason prose can
    carry accents and, occasionally, quotes) rather than hand-formatting.
    """
    doc = tomlkit.document()
    doc["id"] = f"m{rule.modelo}-seed"
    doc["applicable_entity_types"] = sorted(member.value for member in rule.applicable_entity_types)
    if rule.required_income_categories:
        doc["required_income_categories"] = sorted(member.value for member in rule.required_income_categories)
    if rule.required_estimation_regimes:
        doc["required_estimation_regimes"] = sorted(member.value for member in rule.required_estimation_regimes)
    if rule.applicable_fiscal_residencies:
        doc["applicable_fiscal_residencies"] = sorted(member.value for member in rule.applicable_fiscal_residencies)
    if rule.applicable_iva_regimes:
        doc["applicable_iva_regimes"] = sorted(member.value for member in rule.applicable_iva_regimes)
    if rule.required_payer_fact is not None:
        doc["required_payer_fact"] = rule.required_payer_fact.value
    doc["applicable_reason"] = rule.applicable_reason
    doc["not_applicable_reason"] = rule.not_applicable_reason
    doc["cuota_bearing"] = rule.cuota_bearing
    doc["legal_refs"] = list(rule.legal_refs)
    return tomlkit.dumps(doc).rstrip("\n")


def _revision_dirs(modelo: str) -> tuple[Path, ...]:
    revisions_dir = MODELOS_ROOT / modelo / "revisions"
    if not revisions_dir.is_dir():
        raise AssertionError(f"modelo {modelo!r}: expected directory-mode revisions/ under {revisions_dir}")
    return scan_directory(revisions_dir, select=DirectoryEntryKind.DIRECTORIES)


def _write_fragment(revision_dir: Path, rule: ModeloApplicabilityRule) -> Path:
    """Write ``applicability/0001-applicability.toml`` under ``revision_dir``.

    Refuses to overwrite an existing fragment -- this migrator is one-shot and
    a second run over an already-migrated tree is a no-op error, not a silent
    replace.
    """
    fragment_dir = revision_dir / "applicability"
    fragment_dir.mkdir(exist_ok=True)
    target = fragment_dir / "0001-applicability.toml"
    if target.exists():
        raise AssertionError(f"{target}: already exists; this migrator never overwrites")
    header = f'[[revisions."{revision_dir.name}".applicability]]'
    target.write_text(f"{header}\n{_fragment_table_text(rule)}\n", encoding="utf-8", newline="\n")
    return target


def _prove_hydration_equals_literal(
    modelo: str, revisions: tuple[str, ...], literal: ModeloApplicabilityRule
) -> str | None:
    """Reload ``modelo`` and prove every migrated revision hydrates back to ``literal``.

    Returns ``None`` on success, or a mismatch detail string naming the
    offending revision otherwise.
    """
    definition = load_modelo_directory(MODELOS_ROOT / modelo)
    for revision_id in revisions:
        revision = definition.revisions.get(revision_id)
        if revision is None:
            return f"revision {revision_id!r} missing from reloaded definition"
        if len(revision.applicability) != 1:
            return f"revision {revision_id!r} carries {len(revision.applicability)} applicability rule(s), expected 1"
        fragment: ApplicabilityRuleDefinition = revision.applicability[0]
        hydrated = hydrate_applicability_rule(Modelo(modelo), fragment)
        if hydrated != literal:
            return f"revision {revision_id!r}: hydrated value does not equal the literal it replaced"
    return None


def migrate(*, apply: bool) -> list[MigrationOutcome]:
    """Migrate every eligible modelo's applicability rule; return one outcome per modelo."""
    outcomes: list[MigrationOutcome] = []
    for rule in iter_modelo_applicability_rules():
        modelo = rule.modelo
        if modelo in EXCLUDED_MODELOS:
            continue
        revision_dirs = _revision_dirs(modelo)
        revision_ids = tuple(path.name for path in revision_dirs)
        if not apply:
            outcomes.append(
                MigrationOutcome(modelo=modelo, revisions=revision_ids, written=False, equal_to_literal=False),
            )
            continue
        for revision_dir in revision_dirs:
            _write_fragment(revision_dir, rule)
        mismatch = _prove_hydration_equals_literal(modelo, revision_ids, rule)
        outcomes.append(
            MigrationOutcome(
                modelo=modelo,
                revisions=revision_ids,
                written=True,
                equal_to_literal=mismatch is None,
                mismatch_detail=mismatch,
            ),
        )
    return outcomes


def main() -> int:
    """Run the migrator: dry-run by default, ``--apply`` to write and prove."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write fragments and prove hydration equality (default: dry run, writes nothing)",
    )
    parser.add_argument("--json", type=Path, default=None, help="Write the outcome report as JSON to this path")
    args = parser.parse_args()

    outcomes = migrate(apply=args.apply)

    mode = "APPLY" if args.apply else "DRY RUN"
    print(f"=== applicability fragment migration ({mode}) ===")
    print(f"excluded modelos (owned by another campaign): {sorted(EXCLUDED_MODELOS)}")
    print(f"modelos processed: {len(outcomes)}")
    for outcome in outcomes:
        if not args.apply:
            status = "would-write"
        elif outcome.equal_to_literal:
            status = "OK"
        else:
            status = "MISMATCH"
        print(f"  [{status}] modelo {outcome.modelo}: revisions={list(outcome.revisions)}")
        if outcome.mismatch_detail:
            print(f"      {outcome.mismatch_detail}")

    if args.json:
        args.json.write_text(json.dumps([asdict(o) for o in outcomes], indent=2), encoding="utf-8", newline="\n")
        print(f"Wrote outcome report to {args.json}")

    failed = [o for o in outcomes if args.apply and not o.equal_to_literal]
    if failed:
        print(f"\n{len(failed)} modelo(s) FAILED the hydration-equals-literal proof; see above")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
