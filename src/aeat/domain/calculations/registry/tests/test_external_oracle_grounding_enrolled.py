"""Verification-power gate: every externally-oracle-grounded casilla is enrolled.

Enrollment (every computed casilla named in a `verification_expectation`) is a
ceiling; verification POWER is the count of casillas whose engine value is
reconciled against an AEAT-authoritative expected value. Two independent
per-casilla external oracle KINDS are bundled today:

* the Renta WEB Open open-simulator replay corpus
  (`corpus/parity_replays/renta_web_open/`), whose `expected_by_casilla_id`
  carries AEAT-computed figures captured from the live simulator; and
* the AEAT Manual practico worked-example oracle corpus
  (`corpus/manual_oracles/`), whose `expected_by_casilla_id` carries figures
  quoted verbatim from a bundled AEAT manual's own caso practico table (see
  `fixture-provenance-declared-in-sidecar` for the sibling PDF-fixture
  provenance discipline this mirrors).

This gate protects that hard-won grounding: every casilla with an external
oracle expected value (from EITHER corpus) MUST be (1) a computed casilla and
(2) enrolled in a verification contract for its modelo revision, so the oracle
value is actually consumed by the verify gate rather than stranded. It also
emits the honest external-grounding fraction as a visible signal (the
verification-power baseline recorded in the `verification-power` research).
Uses the non-validating loader so it survives concurrent peer registry churn
per `registry-revision-content-inline-or-fragmented` and
`full-tree-gate-must-distinguish-owner`.

Modelo-agnostic: every bundled oracle payload names its own modelo and filing
year (`modelo-<id>-<year>-<scenario>.json`, cross-checked against the
payload's own `modelo`/`filing_year` fields), and this gate resolves the
applicable revision for every modelo the bundled oracles cover — not just
M100 — via each revision's own `period_selector` (`years`, or
`year_from`/`year_to`). A revision keyed directly by its year string (the
M100 per-filing-year convention) resolves by direct id match first; a
revision that spans a range of filing years (the M303-style
`<start-year>-y-siguientes` convention) resolves via the period selector.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from .....core.resources import bundled_path
from .._loader import load_registry_tree

pytestmark = [pytest.mark.integration, pytest.mark.hex_domain]


def _as_list(value: object) -> list[Any]:
    return list(value.values()) if isinstance(value, dict) else list(value)


def _casilla_ids_by_modelo_year_from_dir(directory: Path) -> dict[tuple[str, int], set[str]]:
    """Map each ``modelo-<id>-<year>-<scenario>.json`` payload's (modelo, filing
    year) to its ``expected_by_casilla_id`` keys.

    Casilla ids renumber across filing years and are scoped per modelo, so a
    captured oracle figure is only a valid grounding claim against its own
    modelo's revision covering that year. The payload filename encodes both
    the modelo id and the year (``modelo-<id>-<year>-<scenario>.json``) for
    both bundled oracle corpora this gate reads; the payload's own ``modelo``
    and ``filing_year`` fields are authoritative when present and are
    cross-checked against the filename-derived values so a misnamed file
    cannot silently misattribute its evidence.
    """
    by_modelo_year: dict[tuple[str, int], set[str]] = {}
    for payload_path in sorted(directory.glob("modelo-*.json")):
        parts = payload_path.stem.split("-")
        if len(parts) < 3 or parts[0] != "modelo" or not parts[1] or not parts[2].isdigit():
            continue
        filename_modelo_id = parts[1]
        filename_year = int(parts[2])
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        declared_modelo_id = str(payload.get("modelo", filename_modelo_id)).strip() or filename_modelo_id
        declared_year_value = payload.get("filing_year", filename_year)
        declared_year = int(declared_year_value) if declared_year_value is not None else filename_year
        assert declared_modelo_id == filename_modelo_id, (
            f"{payload_path.name}: payload modelo {declared_modelo_id!r} does not match filename modelo "
            f"{filename_modelo_id!r}"
        )
        assert declared_year == filename_year, (
            f"{payload_path.name}: payload filing_year {declared_year!r} does not match filename year {filename_year!r}"
        )
        by_modelo_year.setdefault((declared_modelo_id, declared_year), set()).update(
            payload.get("expected_by_casilla_id", {}),
        )
    return by_modelo_year


def _renta_web_open_grounded_casilla_ids_by_modelo_year() -> dict[tuple[str, int], set[str]]:
    """Map each Renta WEB Open replay's (modelo, filing year) to its externally-grounded
    casilla ids.
    """
    replay_dir = Path(bundled_path("corpus", "parity_replays", "renta_web_open"))
    return _casilla_ids_by_modelo_year_from_dir(replay_dir)


def _manual_oracle_grounded_casilla_ids_by_modelo_year() -> dict[tuple[str, int], set[str]]:
    """Map each bundled AEAT-manual worked-example oracle's (modelo, filing year) to
    its externally-grounded casilla ids.
    """
    manual_oracle_dir = Path(bundled_path("corpus", "manual_oracles"))
    return _casilla_ids_by_modelo_year_from_dir(manual_oracle_dir)


def _external_oracle_grounded_casilla_ids_by_modelo_year() -> dict[tuple[str, int], set[str]]:
    """Union both bundled per-casilla external-oracle corpora by (modelo, filing year).

    The evidence set backing a registry ``externally_grounded_casilla_ids``
    declaration is the UNION of every bundled oracle kind, not just the Renta
    WEB Open replay corpus - a manual worked-example figure is an equally real,
    independent AEAT authority.
    """
    by_modelo_year: dict[tuple[str, int], set[str]] = {}
    for source in (
        _renta_web_open_grounded_casilla_ids_by_modelo_year(),
        _manual_oracle_grounded_casilla_ids_by_modelo_year(),
    ):
        for key, casilla_ids in source.items():
            by_modelo_year.setdefault(key, set()).update(casilla_ids)
    return by_modelo_year


def _all_modelo_revisions() -> dict[str, list[Any]]:
    """Every modelo's revisions, keyed by modelo id, from the non-validating loader."""
    modelos, _catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    return {modelo.id: _as_list(modelo.revisions) for modelo in modelos}


def _revision_covers_year(revision: Any, year: int) -> bool:
    """Whether ``revision``'s own ``period_selector`` covers ``year``.

    Handles both selector shapes: a discrete ``years`` set (the M100
    per-filing-year revision convention) and a ``year_from``/``year_to`` span
    (the M303-style ``<start-year>-y-siguientes`` convention, open-ended when
    ``year_to`` is ``None``).
    """
    selector = getattr(revision, "period_selector", None)
    if selector is None:
        return False
    years = getattr(selector, "years", ())
    if years:
        return year in years
    year_from = getattr(selector, "year_from", None)
    if year_from is None or year < year_from:
        return False
    year_to = getattr(selector, "year_to", None)
    return year_to is None or year <= year_to


def _select_revision_for_year(revisions: list[Any], year: int) -> Any | None:
    """Resolve the single revision applicable to ``year`` among ``revisions``.

    Tries a direct revision-id match first (the M100 convention, where the
    revision id IS the filing-year string), then falls back to the declared
    ``period_selector`` coverage (the M303-style convention). Returns ``None``
    when no revision matches, or when more than one revision ambiguously
    claims the year (a registry authoring defect out of this gate's scope to
    adjudicate; it simply cannot attribute the oracle evidence).
    """
    year_str = str(year)
    by_id = {revision.id: revision for revision in revisions}
    if year_str in by_id:
        return by_id[year_str]
    matches = [revision for revision in revisions if _revision_covers_year(revision, year)]
    if len(matches) == 1:
        return matches[0]
    return None


def _grounded_evidence_for_revision(
    *,
    modelo_id: str,
    revision: Any,
    revisions: list[Any],
    grounded_by_modelo_year: dict[tuple[str, int], set[str]],
) -> set[str]:
    """Union the oracle evidence of every bundled (modelo, year) key that resolves to ``revision``."""
    evidence: set[str] = set()
    for (candidate_modelo_id, year), casilla_ids in grounded_by_modelo_year.items():
        if candidate_modelo_id != modelo_id:
            continue
        if _select_revision_for_year(revisions, year) is revision:
            evidence |= casilla_ids
    return evidence


def test_every_externally_grounded_casilla_is_computed_and_enrolled() -> None:
    grounded_by_modelo_year = _external_oracle_grounded_casilla_ids_by_modelo_year()
    assert grounded_by_modelo_year, "no external oracle casilla ids are bundled (replay or manual worked example)"

    revisions_by_modelo = _all_modelo_revisions()
    problems: list[str] = []
    checked = 0
    for (modelo_id, year), grounded in sorted(grounded_by_modelo_year.items()):
        revisions = revisions_by_modelo.get(modelo_id, [])
        revision = _select_revision_for_year(revisions, year)
        if revision is None:
            continue
        casillas = _as_list(revision.casillas)
        computed = {c.id for c in casillas if getattr(c, "input_kind", None) == "computed"}
        enrolled: set[str] = set()
        for expectation in _as_list(revision.verification_expectations):
            enrolled |= set(expectation.computed_casilla_ids)
            enrolled |= set(getattr(expectation, "reconcile_when_present_casilla_ids", ()))
        checked += 1
        for casilla_id in sorted(grounded):
            if casilla_id not in computed:
                problems.append(
                    f"{modelo_id} {year} ({revision.id}): oracle-grounded casilla {casilla_id} "
                    "is not input_kind=computed",
                )
            elif casilla_id not in enrolled:
                problems.append(
                    f"{modelo_id} {year} ({revision.id}): oracle-grounded casilla {casilla_id} "
                    "is not enrolled in a verification contract",
                )

    assert checked, "no bundled oracle (modelo, filing year) matched a registry revision"
    assert not problems, "external oracle grounding is stranded (not enrolled/computed):\n" + "\n".join(problems)


def test_every_declared_externally_grounded_casilla_has_oracle_evidence() -> None:
    """Symmetric honesty gate: a registry grounding claim must be backed by evidence.

    R1 lets a revision DECLARE `externally_grounded_casilla_ids` on its verification
    expectations. This gate is the other direction of
    `test_every_externally_grounded_casilla_is_computed_and_enrolled`: every casilla
    the registry declares externally grounded MUST actually appear in a bundled
    oracle's `expected_by_casilla_id` for that revision's applicable filing year(s) -
    either a Renta WEB Open replay or a bundled AEAT-manual worked-example oracle. It
    fails loudly if a grounding tier is asserted with no independent AEAT oracle
    behind it - the guard against a fabricated grounding claim
    (`aeat-safety-legal-gates`, `no-tautological-calculation-tests`). Runs across
    every modelo in the registry tree, not just M100.
    """
    grounded_by_modelo_year = _external_oracle_grounded_casilla_ids_by_modelo_year()
    revisions_by_modelo = _all_modelo_revisions()
    problems: list[str] = []
    checked = 0
    for modelo_id, revisions in sorted(revisions_by_modelo.items()):
        for revision in revisions:
            declared: set[str] = set()
            for expectation in _as_list(revision.verification_expectations):
                declared |= set(getattr(expectation, "externally_grounded_casilla_ids", ()))
            if not declared:
                continue
            evidence = _grounded_evidence_for_revision(
                modelo_id=modelo_id,
                revision=revision,
                revisions=revisions,
                grounded_by_modelo_year=grounded_by_modelo_year,
            )
            for casilla_id in sorted(declared):
                checked += 1
                if casilla_id not in evidence:
                    problems.append(
                        f"{modelo_id} {revision.id}: casilla {casilla_id} is declared externally_grounded "
                        "but no bundled external oracle (replay or manual worked example) for an applicable "
                        "filing year carries it in expected_by_casilla_id",
                    )
    assert checked, "no revision declared externally_grounded_casilla_ids to cross-check"
    assert not problems, "declared external grounding lacks oracle evidence:\n" + "\n".join(problems)
