"""A semantically-named casilla feeds an official byte while its numbered siblings starve.

The sibling gate ``test_rate_specific_box_pins_its_rate`` joins casillas to the
design on ``casilla.number``, and records in its own docstring that the Modelo
390 recargo casillas which demonstrably merge rates "carry no number at all, so
this module cannot see them" -- its blind spot and the defect's cause being the
same fact.

This module closes that blind spot from the other side, without needing a box
number and without needing the design at all.

THE SHAPE, and why it is self-evidencing. Within ONE revision:

  * a casilla whose ``number`` is NOT an official box number OWNS an export
    field -- it writes real bytes of a filed artefact; and
  * a casilla whose ``number`` IS an official box number, under the same concept
    namespace, is bound (it computes a value) but carries EMPTY ``export_refs``
    -- it reaches no byte at all.

That pairing is a mis-declaration in structural form: the per-box slot the
design asks for exists and is starved, while a differently-keyed casilla is fed
in its place. Modelo 390 writes one merged recargo sum into a slot the design
labels ``Tipo 1,4%``, and the six correctly rate-split casillas that should have
filled the rungs compute and go nowhere.

WHY NOT MATCH ON THE EXPORT OFFSET INSTEAD. That would name the box directly and
be stronger. It is unavailable: one byte offset carries four different boxes
across Modelo 390's span, so offset-to-box is undefined until that revision is
partitioned. The join has to avoid offsets entirely, which is why this module
pairs on the concept namespace the registry already declares.

NAMESPACE DEPTH IS NOT TASTE. The stem must have at least three segments. At
depth two ``iva.anual`` spans an entire modelo, so every starved box would pair
with every fed casilla and the result is a cross-product rather than evidence of
substitution. Three segments is the shallowest depth at which the two casillas
are making a claim about the same quantity.

WHAT THIS DOES NOT CHECK, so its silence is not read as coverage. A casilla with
no box number that feeds a byte with NO starved numbered sibling is invisible
here -- and that is correct, because Modelos 145, 180, 232 and 349 address
detail-record fields semantically by design and have no official box numbers to
carry. Measured: 126 casillas tree-wide feed a byte under a non-numeric number,
and only the entries pinned below sit beside a starved numbered sibling. The
rest are legitimately named, not defects.
"""

from __future__ import annotations

import re
from typing import Final

import pytest

from .....core.resources._boundary import bundled_path
from ..authority import ValidatedRegistryAuthority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: An official AEAT box number: digits, optionally with a variant letter.
_BOX_NUMBER = re.compile(r"^\d+[A-Za-z]?$")

#: Shallowest namespace at which two casillas describe the same quantity.
_MIN_STEM_SEGMENTS: Final = 3

#: Pairings that exist today, each against the row that owns the fix.
#:
#: This is NOT a suppression. Every entry is a live mis-declaration on a filed
#: artefact; they are pinned so that a pairing appearing on a DIFFERENT modelo
#: cannot hide inside a known-bad population, and so that fixing one forces a
#: visible edit here rather than passing silently.
#:
#: The revision-span split (temporal, not this defect) replaced the single
#: ``2010-y-siguientes`` revision with four exact-year revisions (2022, 2023,
#: 2024, 2025). Verified rather than assumed: this module's own detector, run
#: against each of the four, reports all five pairings under EVERY new revision
#: id -- the split changed nothing about export-field ownership, so the entries
#: below are the same five defects MOVED to four ids each, not five defects
#: resolved. Do not delete an entry on the strength of a temporal split alone;
#: confirm the detector against the new revision first, the way this list was.
_KNOWN_PAIRINGS: Final[frozenset[tuple[str, str, str]]] = frozenset(
    {
        # row #137 -- merged tier sums occupy [36]/[600]/[602]; six rate-split
        # rungs compute and reach no byte.
        ("390", "2022", "iva.anual.repercutido.recargo.general"),
        ("390", "2022", "iva.anual.repercutido.recargo.reducido"),
        ("390", "2022", "iva.anual.repercutido.recargo.super-reducido"),
        ("390", "2023", "iva.anual.repercutido.recargo.general"),
        ("390", "2023", "iva.anual.repercutido.recargo.reducido"),
        ("390", "2023", "iva.anual.repercutido.recargo.super-reducido"),
        ("390", "2024", "iva.anual.repercutido.recargo.general"),
        ("390", "2024", "iva.anual.repercutido.recargo.reducido"),
        ("390", "2024", "iva.anual.repercutido.recargo.super-reducido"),
        ("390", "2025", "iva.anual.repercutido.recargo.general"),
        ("390", "2025", "iva.anual.repercutido.recargo.reducido"),
        ("390", "2025", "iva.anual.repercutido.recargo.super-reducido"),
        # row #135 / #134 -- the soportado split beside a starved [48] -- is
        # REMOVED because its fix landed, and the removal was confirmed to be a
        # fix rather than a blinded detector, which is the failure this pin's own
        # message warns about. Casilla 48
        # (`iva.anual.soportado.interiores.base`) keeps its binding AND now
        # carries an export ref in all four revisions, so it is fed rather than
        # unbound; the two aliases still own their export fields, so the detector
        # can still see the shape it looks for. Only the starvation ended.
    },
)


def _authority() -> ValidatedRegistryAuthority:
    return ValidatedRegistryAuthority.load(bundled_path("registry", "aeat"), source_root=bundled_path())


def _is_box_number(number: str | None) -> bool:
    return bool(_BOX_NUMBER.match((number or "").strip()))


def _casillas_owning_an_export_field(revision) -> set[str]:
    owned: set[str] = set()
    for layout in getattr(revision, "export_layouts", ()) or ():
        for record in getattr(layout, "records", ()) or ():
            for field in getattr(record, "fields", ()) or ():
                casilla_id = getattr(field, "casilla_id", None)
                if casilla_id:
                    owned.add(str(casilla_id))
    return owned


def _pairings() -> dict[tuple[str, str, str], tuple[str, ...]]:
    """Fed non-numeric casilla -> the numbered siblings starving beside it."""
    found: dict[tuple[str, str, str], tuple[str, ...]] = {}
    for modelo in _authority().modelos:
        for revision_id, revision in modelo.revisions.items():
            owned = _casillas_owning_an_export_field(revision)
            fed = [c for c in revision.casillas if str(c.id) in owned and not _is_box_number(c.number)]
            if not fed:
                continue
            starved = [
                c for c in revision.casillas if _is_box_number(c.number) and c.binding and not (c.export_refs or ())
            ]
            if not starved:
                continue

            for casilla in fed:
                segments = str(casilla.id).split(".")[:-1]
                if len(segments) < _MIN_STEM_SEGMENTS:
                    continue
                stem = ".".join(segments)
                siblings = tuple(sorted(str(c.number).strip() for c in starved if str(c.id).startswith(f"{stem}.")))
                if siblings:
                    found[(modelo.id, revision_id, str(casilla.id))] = siblings
    return found


def test_the_detector_still_resolves_export_ownership() -> None:
    """Anti-vacuity, and the failure this module is most likely to suffer.

    Every check here is a difference against ``_pairings()``. If export-field
    ownership stopped resolving -- a renamed attribute, a layout shape change --
    the result empties and both checks below pass while detecting nothing. An
    empty result is a broken detector, not a clean tree, until the last known
    pairing is genuinely resolved.
    """
    assert _pairings(), (
        "no fed-alias/starved-box pairing resolved at all. If the Modelo 390 split really has "
        "landed and fixed every entry, delete this module together with the last _KNOWN_PAIRINGS "
        "entry; until then an empty result means export-field ownership stopped resolving"
    )


def test_no_unknown_modelo_has_developed_the_shape() -> None:
    """A NEW occurrence must not hide inside a known-bad population.

    The pinned entries are all one modelo and one revision. A pairing appearing
    anywhere else is a fresh mis-declaration on a filed artefact, and without
    this check it would be indistinguishable from the five already tolerated.
    """
    pairings = _pairings()
    unexpected = sorted(key for key in pairings if key not in _KNOWN_PAIRINGS)

    assert not unexpected, (
        "these casillas feed an official export field under a non-numeric number while a numbered "
        "sibling in the same namespace computes and reaches no byte -- the numbered box the design "
        "asks for is starved while an alias is filed in its place:\n  "
        + "\n  ".join(f"modelo {m} {r}: {c!r} starves {pairings[(m, r, c)]}" for m, r, c in unexpected)
    )


def test_a_resolved_pairing_is_removed_from_the_pin() -> None:
    """Fixing one entry must force a visible edit here.

    Without this, a fix leaves a stale pin that quietly widens the tolerated set
    for whatever lands next. The failure message names what still reports, so
    the editor can confirm a fix removed exactly its own entry rather than
    silencing the detector.
    """
    pairings = _pairings()
    stale = sorted(key for key in _KNOWN_PAIRINGS if key not in pairings)

    assert not stale, (
        f"these pairings no longer resolve, so their fix has landed: {stale}. Remove them from "
        f"_KNOWN_PAIRINGS. Still reporting: {sorted(pairings)} -- confirm that list is the one you "
        "expected, because a change that emptied MORE than its own entry blinded the detector "
        "rather than fixing a mis-declaration"
    )
