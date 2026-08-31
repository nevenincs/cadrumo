"""Continuity grounding is a one-way ratchet: the ungrounded backlog only shrinks.

``_validate_cross_revision.py`` scopes strict continuity to *declared* surfaces:
a casilla id repeated across non-overlapping revisions hard-fails on drift only
once someone has stamped it with a ``continuidad_id``. That is deliberate — the
validator refuses to infer continuity from a repeated numeric id, because AEAT
renumbers casillas between filing years and id ``1911`` is a ganancia box in one
revision and a deducción-maternidad box in another. The cost of that correctness
is that an *unstamped* repeated id is invisible to the strict validator: it
carries no continuity claim, so there is nothing to hard-fail against, and the
corpus can silently accrete un-reviewed repeated ids forever.

That validator's own top comment names the missing half — unannotated
repeated-id drift stays advisory "until a separate corpus-wide completeness gate
proves every repeated id has been reviewed". This is that gate. It does not
adjudicate identity (that is the grounding work itself, against official AEAT
and BOE sources); it counts what is left to adjudicate and refuses to let the
number grow unremarked.

Two invariants, with deliberately different strengths:

* **Ungrounded groups ratchet down.** Per modelo, the number of casilla ids
  appearing in two or more revisions where at least one occurrence carries no
  ``continuidad_id``. This is a backlog, not a defect: 2,170 of them ship today
  and grounding them is ongoing work. The committed baseline below must equal
  the observed count exactly, so a grounding commit carries the delta in its
  diff and the ratchet can never rot into a vacuous ``<= 999999``.

* **Partial stamping is zero, always.** A chain where some occurrences carry a
  ``continuidad_id`` and others do not is never a legitimate resting state — it
  asserts a continuity claim for part of a chain and stays silent for the rest,
  which is precisely the shape the strict validator cannot see past. It is a
  defect count, so it is pinned at zero and has no baseline to raise.

An *increase* in the ungrounded count is legitimate in exactly one case: a new
revision of an existing modelo landed and brought repeated ids with it. That is
not a regression, but it is also not silent — the baseline edit is how the
corpus records that the new revision's repeated ids are un-reviewed. The failure
message spells out both readings and prints the replacement baseline literal.

The scan walks the fragment tree directly rather than the compiled registry: it
is the same corpus the loader compiles, both counts were confirmed identical at
introduction (2,170 ungrounded / 0 partial across 73 modelos), and the file walk
keeps the gate independent of loader health so a registry that fails to compile
still cannot smuggle in ungrounded chains.
"""

from __future__ import annotations

import tomllib
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import pytest

from .....core.directory_scan import scan_directory
from .....core.resources._boundary import bundled_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")

# The corpus this gate protects is large; a walk that suddenly finds far fewer
# fragments means the gate is looking at the wrong tree, not that the backlog
# was cleared. Floors are deliberately far below the real counts (12,663
# fragments in 90 revision directories at introduction) so ordinary growth or
# pruning never trips them. The exact-equality baseline below is the second,
# sharper guard: a counter that silently stopped seeing casillas reports zero
# for every modelo and fails nine baselines at once.
_MIN_FRAGMENTS = 5_000
_MIN_DIRECTORIES = 40

# Ungrounded multi-revision casilla-id groups per modelo, measured 2026-08-05
# against the committed corpus (2,170 total, after the 178-chain grounding
# batch). Modelos absent from this mapping carry zero. Lower an entry in the
# same commit that grounds the chains; the gate prints the replacement literal.
#: Raised 2026-08-21 for newly AUTHORED casillas, not for lost stamps -- the
#: ratchet's two readings were distinguished before it moved. Modelos 490,
#: 322, 714 and 190 carry ZERO continuidad_id stamps of any kind, so none
#: could have been lost there; and across the whole modelos tree the set of
#: continuidad_id lines is IDENTICAL to its state forty commits back (1,283
#: distinct lines, none gone), so no chain anywhere dropped its stamp. The
#: +1,066 is newly authored export-schema and casilla content arriving
#: un-reviewed, which is the arm the gate's own message calls legitimate.
_UNGROUNDED_BASELINE: dict[str, int] = {
    # `d2809391b7` split Modelo 038 at the grounded June 2024 boundary. The
    # two repeated groups belong to that newly authored split and remain
    # unreviewed; no source has yet adjudicated their continuity identities.
    "038": 2,
    "100": 1518,
    "123": 8,
    "131": 10,
    "151": 5,
    "180": 7,
    # Split at ejercicio 2025 (Orden HAC/1430/2025): the later half repeats the
    # earlier half's casilla ids, un-reviewed.
    "184": 86,
    "185": 2,
    "190": 70,
    "193": 52,
    # `8824172d83` split Modelo 194 into the published 2019, 2023, and 2024
    # revisions. These five repeated groups are the split's unreviewed backlog,
    # not a missing stamp on a previously grounded chain.
    "194": 5,
    "202": 13,
    # Split at devengos from 2026 (AEAT record design "a partir del
    # 01-01-2026"): the later half repeats the earlier half's casilla ids,
    # un-reviewed. The split was a RECORD-LENGTH change -- Pagina 01 goes
    # from 2700 declared positions to 4000 -- so no casilla moved and no
    # sibling revision carries a continuidad_id to copy. Stamping would mean
    # inventing a chain identity no source establishes.
    "210": 34,
    "220": 2,
    "232": 46,
    "303": 6,
    "322": 220,
    # Split at ejercicio 2025 (Orden HAC/1431/2025), same shape as modelo 184.
    "347": 39,
    "353": 12,
    "369": 2,
    "390": 5,
    "490": 477,
    "604": 42,
    "714": 111,
    # `0598215cab` split Modelo 721 into 2023 and 2024 revisions, and
    # `5ccbc15a69` split Modelo 763 into its six published revisions. Their
    # repeated groups are explicitly recorded as unreviewed backlog until
    # official evidence adjudicates continuity; no continuidad_id is inferred.
    "721": 7,
    "763": 2,
}


@dataclass(frozen=True)
class _Census:
    """What one walk of the casilla fragment tree found."""

    ungrounded: dict[str, int]
    partial: dict[str, tuple[str, ...]]
    multi_revision: dict[str, int]
    fragments: int
    directories: int


def _stamping(root: Path) -> tuple[dict[str, dict[str, dict[str, bool]]], int, int]:
    """Map modelo -> casilla id -> revision id -> "every occurrence is stamped"."""
    stamping: dict[str, dict[str, dict[str, bool]]] = defaultdict(lambda: defaultdict(dict))
    fragments = 0
    directories = 0
    for directory in sorted((root / "modelos").glob("*/revisions/*/casillas")):
        if not directory.is_dir():
            continue
        directories += 1
        modelo_id = directory.parents[2].name
        for path in scan_directory(directory, pattern="*.toml", recursive=True):
            fragments += 1
            document = tomllib.loads(path.read_text(encoding="utf-8"))
            revisions = document.get("revisions")
            if not isinstance(revisions, dict):
                continue
            for revision_id, body in revisions.items():
                if not isinstance(body, dict):
                    continue
                entries = body.get("casillas")
                if not isinstance(entries, list):
                    continue
                for entry in entries:
                    if not isinstance(entry, dict) or entry.get("id") is None:
                        continue
                    casilla_id = str(entry["id"])
                    stamped = entry.get("continuidad_id") is not None
                    by_revision = stamping[modelo_id][casilla_id]
                    # A revision fragmented across several files is one
                    # occurrence set: unstamped anywhere means unstamped.
                    by_revision[revision_id] = stamped and by_revision.get(revision_id, True)
    return stamping, fragments, directories


def _census(root: Path) -> _Census:
    stamping, fragments, directories = _stamping(root)
    ungrounded: dict[str, int] = {}
    partial: dict[str, tuple[str, ...]] = {}
    multi_revision: dict[str, int] = {}
    for modelo_id, by_casilla in stamping.items():
        ungrounded_ids: list[str] = []
        partial_ids: list[str] = []
        repeated = 0
        for casilla_id, by_revision in by_casilla.items():
            if len(by_revision) < 2:
                continue
            repeated += 1
            states = set(by_revision.values())
            if False not in states:
                continue
            ungrounded_ids.append(casilla_id)
            if True in states:
                partial_ids.append(casilla_id)
        if repeated:
            multi_revision[modelo_id] = repeated
        if ungrounded_ids:
            ungrounded[modelo_id] = len(ungrounded_ids)
        if partial_ids:
            partial[modelo_id] = tuple(sorted(partial_ids))
    return _Census(
        ungrounded=ungrounded,
        partial=partial,
        multi_revision=multi_revision,
        fragments=fragments,
        directories=directories,
    )


def _scan_is_representative(census: _Census) -> bool:
    return census.fragments >= _MIN_FRAGMENTS and census.directories >= _MIN_DIRECTORIES


def _baseline_literal(ungrounded: dict[str, int]) -> str:
    body = "\n".join(f'    "{modelo_id}": {count},' for modelo_id, count in sorted(ungrounded.items()))
    return "_UNGROUNDED_BASELINE: dict[str, int] = {\n" + body + "\n}"


def _ratchet_violations(census: _Census) -> list[str]:
    violations: list[str] = []
    for modelo_id in sorted(set(_UNGROUNDED_BASELINE) | set(census.ungrounded)):
        observed = census.ungrounded.get(modelo_id, 0)
        baseline = _UNGROUNDED_BASELINE.get(modelo_id, 0)
        if observed == baseline:
            continue
        if observed > baseline:
            violations.append(
                f"modelo {modelo_id}: {observed} ungrounded groups, baseline {baseline} (+{observed - baseline}). "
                f"Either a chain lost its continuidad_id stamp (a regression — restore the stamp), "
                f"or a NEW revision of modelo {modelo_id} landed carrying repeated casilla ids "
                f"(legitimate — those ids are un-reviewed, so raise the baseline)"
            )
            continue
        violations.append(
            f"modelo {modelo_id}: {observed} ungrounded groups, baseline {baseline} ({observed - baseline}). "
            f"Grounding progress is not recorded — lower the baseline to {observed} in this commit "
            f"so the ratchet keeps its teeth"
        )
    return violations


def test_ungrounded_continuity_backlog_matches_its_committed_baseline() -> None:
    census = _census(_REGISTRY_ROOT)

    assert _scan_is_representative(census), (
        f"gate scanned only {census.fragments} fragments in {census.directories} revision directories; "
        f"the walk no longer covers the corpus, so a green result would be vacuous"
    )

    violations = _ratchet_violations(census)
    assert not violations, (
        f"{len(violations)} modelo(s) diverge from the committed continuity baseline "
        f"({sum(census.ungrounded.values())} ungrounded groups observed, "
        f"{sum(_UNGROUNDED_BASELINE.values())} recorded):\n"
        + "\n".join(f" - {violation}" for violation in violations)
        + "\n\nReplacement baseline for this corpus:\n"
        + _baseline_literal(census.ungrounded)
    )


def test_no_continuity_chain_is_partially_stamped() -> None:
    """Half-stamped chains are a defect, never a backlog: pinned at zero."""
    census = _census(_REGISTRY_ROOT)

    assert _scan_is_representative(census), (
        f"gate scanned only {census.fragments} fragments in {census.directories} revision directories; "
        f"the walk no longer covers the corpus, so a green result would be vacuous"
    )

    partial = [
        f"modelo {modelo_id} casilla {casilla_id!r}"
        for modelo_id, casilla_ids in sorted(census.partial.items())
        for casilla_id in casilla_ids
    ]
    assert not partial, (
        f"{len(partial)} casilla chain(s) are stamped with a continuidad_id in some revisions and "
        f"unstamped in others. A partial stamp claims continuity for part of a chain and stays "
        f"silent for the rest, so the strict validator checks only the stamped half. Stamp every "
        f"occurrence of the chain, or remove the stamp and leave the whole chain in the backlog:\n"
        + "\n".join(f" - {item}" for item in partial[:20])
    )


def _write_casilla_fragment(
    root: Path,
    modelo_id: str,
    revision_id: str,
    name: str,
    casillas: dict[str, str | None],
) -> None:
    directory = root / "modelos" / modelo_id / "revisions" / revision_id / "casillas"
    directory.mkdir(parents=True, exist_ok=True)
    blocks: list[str] = []
    for casilla_id, continuidad_id in casillas.items():
        block = f'[[revisions."{revision_id}".casillas]]\nid = "{casilla_id}"'
        if continuidad_id is not None:
            block += f'\ncontinuidad_id = "{continuidad_id}"'
        blocks.append(block)
    (directory / name).write_text("\n\n".join(blocks) + "\n", encoding="utf-8")


def _repeated_chain(root: Path, *, left: str | None, right: str | None) -> None:
    _write_casilla_fragment(root, "999", "2024", "0001-c0700.toml", {"0700": left})
    _write_casilla_fragment(root, "999", "2025", "0001-c0700.toml", {"0700": right})


def test_counter_sees_a_chain_move_from_ungrounded_to_grounded(tmp_path: Path) -> None:
    """Positive control: a gate whose counter has never moved cannot be trusted."""
    _repeated_chain(tmp_path, left=None, right=None)
    assert _census(tmp_path).ungrounded == {"999": 1}

    _repeated_chain(tmp_path, left="iva.base.general", right="iva.base.general")
    census = _census(tmp_path)
    assert census.ungrounded == {}
    assert census.multi_revision == {"999": 1}, "the chain must stay visible as a repeated id, just grounded"


def test_counter_sees_a_half_stamped_chain(tmp_path: Path) -> None:
    _repeated_chain(tmp_path, left="iva.base.general", right=None)
    census = _census(tmp_path)

    assert census.partial == {"999": ("0700",)}
    assert census.ungrounded == {"999": 1}, "a half-stamped chain is also still ungrounded"


def test_an_id_confined_to_one_revision_is_not_a_chain(tmp_path: Path) -> None:
    """AEAT renumbers between filing years; a single-revision id makes no continuity claim."""
    _write_casilla_fragment(tmp_path, "999", "2024", "0001-c0700.toml", {"0700": None})
    _write_casilla_fragment(tmp_path, "999", "2025", "0001-c0800.toml", {"0800": None})
    census = _census(tmp_path)

    assert census.multi_revision == {}
    assert census.ungrounded == {}


def test_a_revision_fragmented_across_files_is_one_occurrence_set(tmp_path: Path) -> None:
    """Stamped in one fragment and unstamped in another is unstamped for that revision."""
    _write_casilla_fragment(tmp_path, "999", "2024", "0001-c0700.toml", {"0700": "iva.base.general"})
    _write_casilla_fragment(tmp_path, "999", "2024", "0002-c0700.toml", {"0700": None})
    _write_casilla_fragment(tmp_path, "999", "2025", "0001-c0700.toml", {"0700": "iva.base.general"})
    census = _census(tmp_path)

    assert census.ungrounded == {"999": 1}
    assert census.partial == {"999": ("0700",)}


def test_modelos_are_counted_independently(tmp_path: Path) -> None:
    """A repeated id is a chain within one modelo; the same number in two modelos is not."""
    _write_casilla_fragment(tmp_path, "998", "2024", "0001-c0700.toml", {"0700": None})
    _write_casilla_fragment(tmp_path, "997", "2025", "0001-c0700.toml", {"0700": None})
    assert _census(tmp_path).ungrounded == {}

    _write_casilla_fragment(tmp_path, "998", "2025", "0001-c0700.toml", {"0700": None})
    assert _census(tmp_path).ungrounded == {"998": 1}


def test_ratchet_reports_both_directions_and_a_replacement_literal() -> None:
    """The failure message must distinguish a regression from unrecorded progress."""
    # Derived from the baseline, never re-typed as a literal: this test asserts
    # the SHAPE of the message, so pinning a copy of the M100 figure would make
    # every legitimate grounding commit edit the same number in four places.
    baseline = _UNGROUNDED_BASELINE["100"]
    regressed = _Census(
        ungrounded={"100": baseline + 1, "303": 4},
        partial={},
        multi_revision={},
        fragments=_MIN_FRAGMENTS,
        directories=_MIN_DIRECTORIES,
    )
    (message,) = [v for v in _ratchet_violations(regressed) if v.startswith("modelo 100")]
    assert "(+1)" in message
    assert "lost its continuidad_id stamp" in message
    assert "NEW revision" in message

    progressed = _Census(
        ungrounded={"100": baseline - 103, "303": 4},
        partial={},
        multi_revision={},
        fragments=_MIN_FRAGMENTS,
        directories=_MIN_DIRECTORIES,
    )
    (message,) = [v for v in _ratchet_violations(progressed) if v.startswith("modelo 100")]
    assert "(-103)" in message
    assert f"lower the baseline to {baseline - 103}" in message

    unchanged = _Census(
        ungrounded=dict(_UNGROUNDED_BASELINE),
        partial={},
        multi_revision={},
        fragments=_MIN_FRAGMENTS,
        directories=_MIN_DIRECTORIES,
    )
    assert _ratchet_violations(unchanged) == []

    assert f'"100": {baseline + 1},' in _baseline_literal(regressed.ungrounded)


def test_a_modelo_absent_from_the_baseline_may_not_carry_a_backlog() -> None:
    """A brand-new modelo cannot arrive with un-reviewed chains and stay silent."""
    newcomer = _Census(
        ungrounded={**_UNGROUNDED_BASELINE, "600": 7},
        partial={},
        multi_revision={},
        fragments=_MIN_FRAGMENTS,
        directories=_MIN_DIRECTORIES,
    )

    (message,) = [v for v in _ratchet_violations(newcomer) if v.startswith("modelo 600")]
    assert "7 ungrounded groups, baseline 0 (+7)" in message


def test_scan_scope_floor_refuses_a_walk_that_missed_the_corpus(tmp_path: Path) -> None:
    """The floor is what stops an empty or mis-rooted walk from reporting a clean corpus."""
    _repeated_chain(tmp_path, left=None, right=None)

    assert not _scan_is_representative(_census(tmp_path))
    assert _scan_is_representative(_census(_REGISTRY_ROOT))
