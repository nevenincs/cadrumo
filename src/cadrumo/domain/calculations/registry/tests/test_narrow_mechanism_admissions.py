"""Every admission into a widened registry mechanism must still earn its place.

Three deliberately narrow mechanisms were widened under one accepted decision:
a record-design correction kind for a mis-declared filler start, a binding
source kind carrying a diseño-declared constant, and an auxiliary-header
contract that stopped asserting the filing cadence of whichever modelo carries
it. Each widening is bounded by what somebody wrote down, which is the whole
reason a declaration was chosen over a looser matcher -- but a declaration
mechanism decays in two directions and needs holding from both.

**Empty is not clean.** If a declared set silently becomes empty -- the sidecar
renamed, the loader stopped resolving, the source kind dropped from the
registry -- every consumer that filters on it keeps passing while filtering
nothing. That is the failure the provenance-only design exclusion already
guards, and it reads as rigour right up until someone checks.

**A satisfied admission is debt.** An entry whose subject no longer needs it is
a spare slot: it widens the mechanism for a case that no longer exists and
nobody notices, because deletion is the only signal and nothing asks for it.

The third mechanism has no declared set at all -- unpinning the cadence slot
widened a predicate rather than opening a registry -- so it is held by the
opposite assertion: the slot must still REFUSE what it always refused. A
widening that stopped refusing anything would be a hole, and a hole in a header
contract is how an unrelated sheet gets read as an envelope.

See Also:
    :class:`RegistrySnapshot`
        The compiled authority these admissions are measured against.
"""

from __future__ import annotations

import json

import pytest

from .....core.aggregation import BindingSourceKind
from .....core.directory_scan import DirectoryEntryKind, scan_directory
from .....core.external_constants import UTF_8_ENCODING
from .....core.resources.bundled_data import bundled_path
from ..authority import bundled_authority
from ..binding_selector_utils import selector_as_dict
from ..record_design import extract_record_design
from ..record_design_schema import (
    _AUXILIARY_ENVELOPE_HEADER_PERIOD_RE,
    _auxiliary_header_constant,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DESIGN_ROOT_PARTS = ("corpus", "aeat_official", "disenos_registro")
_CORRECTION_SUFFIX = ".record-design-correction.json"


def _range_start_sidecars() -> tuple[tuple[str, dict[str, object]], ...]:
    """Return every declared range-start correction, with its design filename."""
    root = bundled_path(*_DESIGN_ROOT_PARTS)
    declared: list[tuple[str, dict[str, object]]] = []
    for path in scan_directory(root, recursive=True, select=DirectoryEntryKind.FILES):
        if not path.name.endswith(_CORRECTION_SUFFIX):
            continue
        payload = json.loads(path.read_text(encoding=UTF_8_ENCODING))
        design_name = path.name.removesuffix(_CORRECTION_SUFFIX)
        for entry in payload.get("corrections", ()):
            if entry.get("kind") == "range_start":
                declared.append((design_name, entry))
    return tuple(declared)


def _design_constant_bindings() -> tuple[tuple[str, str, str], ...]:
    """Return ``(modelo, revision, binding_id)`` for every design-constant binding."""
    declared: list[tuple[str, str, str]] = []
    for modelo in bundled_authority().modelos:
        for revision_id, revision in modelo.revisions.items():
            for binding in revision.bindings:
                if binding.source is BindingSourceKind.DESIGN_CONSTANT:
                    declared.append((str(modelo.id), str(revision_id), str(binding.id)))
    return tuple(declared)


def test_the_range_start_admission_is_not_an_empty_filter() -> None:
    """A correction kind nothing declares would widen the schema for nobody."""
    declared = _range_start_sidecars()

    assert declared, (
        "no range-start correction is declared anywhere in the corpus. Either the sidecar was "
        "renamed or removed, or the loader stopped resolving it -- and in both cases the kind "
        "sits in the discriminated union widening it for a case that no longer exists"
    )


def test_every_range_start_admission_still_describes_a_real_hole() -> None:
    """Delete a correction whose design no longer needs it, never leave it standing.

    Re-reads the design WITH the correction applied and asserts it reports the
    correction as applied. A declaration the extractor silently ignores -- a
    renamed sheet, a start no row begins at any more after a parser improvement
    -- would otherwise sit in the corpus reading as a fix while fixing nothing.
    """
    root = bundled_path(*_DESIGN_ROOT_PARTS)
    unapplied: list[str] = []
    for design_name, entry in _range_start_sidecars():
        matches = [
            path
            for path in scan_directory(root, recursive=True, select=DirectoryEntryKind.FILES)
            if path.name == design_name
        ]
        assert matches, f"range-start correction names a design not in the corpus: {design_name!r}"
        applied = {
            (correction.sheet, correction.declared_start)
            for correction in extract_record_design(matches[0]).corrections
            if correction.kind == "range_start"
        }
        if (entry["sheet"], entry["declared_start"]) not in applied:
            unapplied.append(f"{design_name} {entry['sheet']!r} start {entry['declared_start']}")

    assert not unapplied, (
        "range-start correction(s) are declared but not applied by the extractor, so they widen "
        "the schema while fixing nothing. Delete the entry if the design no longer needs it:\n  "
        + "\n  ".join(unapplied)
    )


def test_the_design_constant_admission_is_not_an_empty_filter() -> None:
    """A source kind no binding declares is an orphan the taxonomy gate also refuses.

    Asserted here as well because the two gates fail for different reasons and a
    reader of THIS module should not have to know the other exists: there, an
    orphan is a taxonomy defect; here, it means the constant channel the
    coverage checker reads is empty and its join contribution is silently nil.
    """
    declared = _design_constant_bindings()

    assert declared, (
        "no binding declares BindingSourceKind.DESIGN_CONSTANT. The coverage checker reads that "
        "channel when identifying a record, so an empty set makes `_design_constant_values` a "
        "map that never contributes -- passing, and contributing nothing"
    )


def test_every_design_constant_carries_a_value_that_fills_its_run() -> None:
    """The admission's own promise, asserted against the compiled registry.

    The selector validates this at registry build, so this is a second reading
    of the same property against the COMPILED authority rather than the authored
    TOML -- the build could stop running the validator and nothing else would
    say so. A constant that does not fill its run is a mis-read diseño, and
    padding one silently is how it reaches the wire.
    """
    offenders: list[str] = []
    for modelo_id, revision_id, binding_id in _design_constant_bindings():
        for modelo in bundled_authority().modelos:
            if str(modelo.id) != modelo_id:
                continue
            revision = modelo.revisions[revision_id]
            binding = next(item for item in revision.bindings if str(item.id) == binding_id)
            selector = selector_as_dict(binding)
            value = selector.get("value")
            length = selector.get("length")
            if not isinstance(value, str) or value == "" or len(value) != length:
                offenders.append(f"{binding_id}: value={value!r} declared length={length!r}")

    assert not offenders, (
        "design-constant binding(s) carry a value that does not fill the declared run:\n  " + "\n  ".join(offenders)
    )


@pytest.mark.parametrize(
    "rejected",
    ["BLANCOS", '"<T"', '"<AUX>"', '"</AUX>"', "Nota 2", "", "0A"],
    ids=["blancos", "opening-tag", "aux-open", "aux-close", "footnote", "empty", "unquoted"],
)
def test_the_unpinned_period_slot_still_refuses_what_it_always_refused(rejected: str) -> None:
    """Unpinning the cadence must widen the contract, never open a hole.

    The period slot stopped requiring the annual literal so a quarterly or
    monthly modelo could carry the same header -- which is what admitted Modelo
    131's page zero. What it must NOT have become is a slot that accepts
    anything: a header contract that stops refusing is how an unrelated sheet
    gets classified as an envelope, and the coverage answer for an envelope is
    computed from the envelope contract rather than from any record.

    The rejected set is deliberately drawn from values that appear in OTHER
    slots of this very header -- the tag constants, a footnote marker, the
    reserved-run filler -- because those are what a mis-aligned read would
    actually put here.
    """
    assert not _AUXILIARY_ENVELOPE_HEADER_PERIOD_RE.fullmatch(_auxiliary_header_constant(rejected) or ""), (
        f"the period slot now accepts {rejected!r}, which is not a period declaration. The cadence "
        "unpin was meant to widen the contract from one literal to the period vocabulary, not to "
        "stop discriminating"
    )


@pytest.mark.parametrize(
    "accepted",
    ['"0A"', '"1T"', '"01"', '"01"..."12"', '"01"..."12" o "1T"…"4T"'],
    ids=["annual", "quarter", "month", "month-range", "month-and-quarter-ranges"],
)
def test_the_unpinned_period_slot_accepts_every_cadence_the_corpus_declares(accepted: str) -> None:
    """Anti-vacuity: a slot that refused everything would satisfy the test above.

    Each value is one AEAT actually prints -- Modelo 390's annual literal and
    Modelo 303's own combined month-and-quarter range, whose two separators are
    three literal dots and U+2026 in the same string.
    """
    assert _AUXILIARY_ENVELOPE_HEADER_PERIOD_RE.fullmatch(_auxiliary_header_constant(accepted) or ""), (
        f"the period slot refuses {accepted!r}, which AEAT declares in a bundled design"
    )
