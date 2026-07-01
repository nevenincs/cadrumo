"""Verification-power gate: every externally-oracle-grounded casilla is enrolled.

Enrollment (every computed casilla named in a `verification_expectation`) is a
ceiling; verification POWER is the count of casillas whose engine value is
reconciled against an AEAT-authoritative expected value. Today the only
per-casilla external oracle is the Renta WEB Open open-simulator replay corpus
(`corpus/parity_replays/renta_web_open/`), whose `expected_by_casilla_id`
carries AEAT-computed figures.

This gate protects that hard-won grounding: every casilla with an external
oracle expected value MUST be (1) a computed casilla and (2) enrolled in a
verification contract for its modelo revision, so the oracle value is actually
consumed by the verify gate rather than stranded. It also emits the honest
external-grounding fraction as a visible signal (the verification-power baseline
recorded in the `verification-power` research). Uses the non-validating loader so
it survives concurrent peer registry churn per
`registry-revision-content-inline-or-fragmented` and
`full-tree-gate-must-distinguish-owner`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .....core.resources import bundled_path
from .._loader import load_registry_tree

pytestmark = [pytest.mark.integration, pytest.mark.hex_domain]


def _as_list(value: object) -> list:
    return list(value.values()) if isinstance(value, dict) else list(value)


def _renta_web_open_grounded_casilla_ids_by_year() -> dict[str, set[str]]:
    """Map each replay's filing year to its externally-grounded casilla ids.

    Casilla ids renumber across filing years, so a 2025-captured oracle figure is
    only a valid grounding claim against the 2025 revision. The replay filename
    encodes the year (``modelo-100-<year>-<scenario>.json``).
    """
    replay_dir = Path(bundled_path("corpus", "parity_replays", "renta_web_open"))
    by_year: dict[str, set[str]] = {}
    for payload_path in sorted(replay_dir.glob("modelo-100-*.json")):
        parts = payload_path.stem.split("-")
        year = parts[2] if len(parts) > 2 and parts[2].isdigit() else None
        if year is None:
            continue
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        by_year.setdefault(year, set()).update(payload.get("expected_by_casilla_id", {}))
    return by_year


def _m100_revisions() -> list:
    modelos, _catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    for modelo in modelos:
        if modelo.id == "100":
            return _as_list(modelo.revisions)
    return []


def test_every_externally_grounded_casilla_is_computed_and_enrolled() -> None:
    grounded_by_year = _renta_web_open_grounded_casilla_ids_by_year()
    assert grounded_by_year, "no Renta WEB Open external oracle casilla ids are bundled"

    revisions_by_id = {revision.id: revision for revision in _m100_revisions()}
    problems: list[str] = []
    checked_years = 0
    for year, grounded in sorted(grounded_by_year.items()):
        # M100 revisions are keyed by filing-year id; a replay grounds exactly its
        # own year's revision (casilla ids are not comparable across years).
        revision = revisions_by_id.get(year)
        if revision is None:
            continue
        casillas = _as_list(revision.casillas)
        computed = {c.id for c in casillas if getattr(c, "input_kind", None) == "computed"}
        enrolled: set[str] = set()
        for expectation in _as_list(revision.verification_expectations):
            enrolled |= set(expectation.computed_casilla_ids)
            enrolled |= set(getattr(expectation, "reconcile_when_present_casilla_ids", ()))
        checked_years += 1
        for casilla_id in sorted(grounded):
            if casilla_id not in computed:
                problems.append(f"100 {year}: oracle-grounded casilla {casilla_id} is not input_kind=computed")
            elif casilla_id not in enrolled:
                problems.append(
                    f"100 {year}: oracle-grounded casilla {casilla_id} is not enrolled in a verification contract",
                )

    assert checked_years, "no M100 revision matched a Renta WEB Open replay filing year"
    assert not problems, "external oracle grounding is stranded (not enrolled/computed):\n" + "\n".join(problems)


def test_every_declared_externally_grounded_casilla_has_oracle_evidence() -> None:
    """Symmetric honesty gate: a registry grounding claim must be backed by evidence.

    R1 lets a revision DECLARE `externally_grounded_casilla_ids` on its verification
    expectations. This gate is the other direction of
    `test_every_externally_grounded_casilla_is_computed_and_enrolled`: every casilla
    the registry declares externally grounded MUST actually appear in a bundled
    Renta WEB Open replay's `expected_by_casilla_id` for that revision's filing
    year. It fails loudly if a grounding tier is asserted with no independent AEAT
    oracle behind it - the guard against a fabricated grounding claim
    (`aeat-safety-legal-gates`, `no-tautological-calculation-tests`).
    """
    grounded_by_year = _renta_web_open_grounded_casilla_ids_by_year()
    problems: list[str] = []
    checked = 0
    for revision in _m100_revisions():
        declared: set[str] = set()
        for expectation in _as_list(revision.verification_expectations):
            declared |= set(getattr(expectation, "externally_grounded_casilla_ids", ()))
        if not declared:
            continue
        evidence = grounded_by_year.get(revision.id, set())
        for casilla_id in sorted(declared):
            checked += 1
            if casilla_id not in evidence:
                problems.append(
                    f"100 {revision.id}: casilla {casilla_id} is declared externally_grounded "
                    "but no bundled Renta WEB Open replay for that year carries it in expected_by_casilla_id",
                )
    assert checked, "no revision declared externally_grounded_casilla_ids to cross-check"
    assert not problems, "declared external grounding lacks oracle evidence:\n" + "\n".join(problems)
