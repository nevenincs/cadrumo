"""The DANA 2024 relief authority refuses four specific ways of being wrong.

The measure this guards is RDL 7/2024 art. 11.2: a 25 per cent reduction of the
2024 annual IVA regimen simplificado cuota devengada por operaciones
corrientes, for taxpayers operating in the municipalities of the RDL 6/2024
anexo. Four things can go wrong with grounding it, and each is a refusal here
rather than a review convention:

**Timeless geography.** The anexo is expressly amendable by Acuerdo de Consejo
de Ministros (RDL 6/2024 art. 1.4), so a municipal list with no "as of when" is
a snapshot wearing the clothes of law. The catalogue may only answer "which
municipalities" by citing consolidated bytes carrying a consolidation date.

**Inferred applicability.** "When does the reduction apply" is answered by the
final provision governing entry into force, never by reading a date off the
article that sets the percentage. The catalogue must carry that provision, its
corpus text must actually state the entry-into-force rule, and the reduction's
own ``effective_from`` must equal what that rule yields rather than a date an
author found plausible.

**Missing correction provenance.** RDL 6/2024 was corrected by BOE-A-2024-24097
five pages into its own article 1, apartado 4. A grounding that cites the
corrected text without the correction behind it cannot show which redaction it
means.

**Invented identifiers.** Every BOE identifier, permalink and pinned digest must
resolve against an artefact actually in the tree, and that artefact must itself
declare the identifier claimed for it.

Every assertion below runs against the real registry loader, the real legal
verifier and the real bundled corpus bytes. Nothing is stubbed, and no test
pins a count: a growing anexo or an added citation must not force an edit here.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from cadrumo.core import normalise_corpus_text, resolve_anchored_extracted_unit
from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.resources import bundled_path
from cadrumo.domain.calculations.registry.schema import (
    LegalReference,
    SourceReference,
)
from cadrumo.domain.calculations.registry.legal import (
    legal_reference_quotes_corpus,
    verify_legal_catalogue_grounding,
)
from cadrumo.tests.registry_tree import bundled_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: The one geography authority. RDL 7/2024 art. 11.2 cites it instead of
#: enumerating municipalities, so this entry is where "where" is answered.
GEOGRAPHY_REF = "real-decreto-ley-6-2024:anexo"

#: The article establishing the anexo's mutability, and carrying the
#: consolidation note that names the correction.
SCOPE_REF = "real-decreto-ley-6-2024:art-1"

#: The apartado that fixes the 25 per cent and scopes it to the annual cuota.
REDUCTION_REF = "real-decreto-ley-7-2024:art-11.2"

#: The provision that says from when the reduction's norm is in force.
ENTRY_INTO_FORCE_REF = "real-decreto-ley-7-2024:df-14"

#: The corrección de errores, bundled as its own as-published artefact.
CORRECTION_REF = "correccion-errores-rdl-6-2024"

#: The numeric parameter the measure compiles down to.
REDUCTION_PARAMETER = "rdl-7-2024-art-11-2:iva-simplificado-reduccion-cuota-devengada-2024"

#: Distinct anexo municipality names inside one authored registry value that
#: make it an enumeration rather than a word collision. See
#: :func:`test_no_registry_value_enumerates_the_anexo_instead_of_citing_it` for
#: the measurement behind the boundary.
_ENUMERATION_THRESHOLD = 3

#: The anexo must parse to substantially its published length or the scan is
#: measuring nothing. The published list carries 78 entries; the floor sits
#: below that so a lawful amendment does not force an edit here.
_ANEXO_ANTI_VACUITY_FLOOR = 50

#: ``required_text`` is the sanctioned place to quote anexo lines, so it is cut
#: out before scanning. Non-greedy to the first closing bracket: these arrays
#: hold only quoted phrases, never nested brackets.
_REQUIRED_TEXT_ARRAY = re.compile(r"required_text\s*=\s*\[.*?\]", re.DOTALL)

#: One authored TOML string value, basic or multi-line, with escapes honoured.
_TOML_STRING = re.compile(r'"""(?:.|\n)*?"""|"(?:[^"\\]|\\.)*"')

DANA_LEGAL_REFS = (
    GEOGRAPHY_REF,
    SCOPE_REF,
    REDUCTION_REF,
    ENTRY_INTO_FORCE_REF,
    CORRECTION_REF,
)

DANA_SOURCE_REFS = (
    "boe-rdl-6-2024-dana-authority",
    "boe-rdl-7-2024-dana-authority",
    "boe-correccion-errores-rdl-6-2024",
)

#: The literal BOE identifier grammar. An identifier that does not match this
#: was invented rather than read off a BOE document.
BOE_DOCUMENT_ID = re.compile(r"^BOE-[A-Z]-\d{4}-\d+$")

BOE_HOST = "www.boe.es"

#: The rule the final provision states, in the norm's own words. Asserted
#: against the corpus so the derived date below is read from the law rather
#: than encoded here as an author's belief about it.
ENTRY_INTO_FORCE_RULE = "entrará en vigor el día siguiente al de su publicación"

#: The clause that makes the anexo mutable, and therefore makes an undated
#: municipal list unsound.
MUTABILITY_CLAUSE = (
    "El anexo que acompaña a este real decreto-ley podrá ser modificado mediante Acuerdo de Consejo de Ministros"
)


@dataclass(frozen=True)
class DanaAuthority:
    """The DANA slice of the committed registry catalogues."""

    legal: dict[str, LegalReference]
    sources: dict[str, SourceReference]
    parameter_legal_refs: tuple[str, ...]
    source_root: Path


def dana_authority() -> DanaAuthority:
    """Load the DANA entries from the committed registry tree.

    The one seam in this module. Every test reads its subject through here, so
    a proof that a refusal really bites can substitute a mutated authority
    without any test needing an injection parameter of its own.

    Returns:
        The DANA legal entries, source entries, the reduction parameter's
        declared legal refs, and the corpus root they resolve against.

    Raises:
        AssertionError: If any expected DANA entry is absent from the tree.
    """
    _, catalogues = bundled_registry_tree()
    missing_legal = [ref for ref in DANA_LEGAL_REFS if ref not in catalogues.legal]
    missing_sources = [ref for ref in DANA_SOURCE_REFS if ref not in catalogues.sources]
    assert not missing_legal, f"DANA legal entries absent from the registry: {missing_legal!r}"
    assert not missing_sources, f"DANA source entries absent from the registry: {missing_sources!r}"
    assert REDUCTION_PARAMETER in catalogues.parameters, (
        f"the 25 per cent reduction parameter {REDUCTION_PARAMETER!r} is absent from the registry"
    )
    return DanaAuthority(
        legal={ref: catalogues.legal[ref] for ref in DANA_LEGAL_REFS},
        sources={ref: catalogues.sources[ref] for ref in DANA_SOURCE_REFS},
        parameter_legal_refs=tuple(catalogues.parameters[REDUCTION_PARAMETER].legal_refs),
        source_root=bundled_path(),
    )


def _source_pinning(authority: DanaAuthority, reference: LegalReference) -> SourceReference:
    """Return the DANA source whose bundled artefact backs ``reference``.

    Args:
        authority: The loaded DANA slice.
        reference: The legal entry whose corpus artefact is wanted.

    Returns:
        The single source pinning that artefact's bytes.

    Raises:
        AssertionError: If no source, or more than one, pins it.
    """
    corpus_path = reference.corpus_ref.partition("#")[0]
    pinning = [source for source in authority.sources.values() if source.corpus_path == corpus_path]
    assert len(pinning) == 1, (
        f"legal entry {reference.id!r} cites {corpus_path!r}, which {len(pinning)} DANA sources pin; "
        "exactly one source must pin the bytes behind a citation"
    )
    return pinning[0]


def test_the_dana_catalogue_verifies_against_the_bundled_corpus() -> None:
    """Every DANA citation's required text is really in the artefact it cites.

    Grounding is the subject here, so the audit that excludes review eligibility
    is the right one: whether an operator has countersigned these references is
    a separate question, answered where a filing snapshot selects its legal
    slice, and an unfinished countersignature must not mask a corpus defect.
    """
    authority = dana_authority()

    verify_legal_catalogue_grounding(authority.legal, source_root=authority.source_root)


def test_a_municipal_geography_without_a_consolidation_date_is_refused() -> None:
    """The anexo may only be cited as bytes carrying an "as of when"."""
    authority = dana_authority()
    geography = authority.legal[GEOGRAPHY_REF]
    scope = authority.legal[SCOPE_REF]

    assert geography.consolidated_as_of is not None, (
        f"{GEOGRAPHY_REF} declares no consolidated_as_of, so it asserts a municipal list with no date; "
        "the anexo is amendable by Acuerdo de Consejo de Ministros, so an undated list is a snapshot "
        "presented as law"
    )
    assert geography.consolidated_as_of >= geography.effective_from, (
        f"{GEOGRAPHY_REF} claims to be consolidated at {geography.consolidated_as_of}, before the "
        f"anexo took effect on {geography.effective_from}"
    )
    assert legal_reference_quotes_corpus(scope, MUTABILITY_CLAUSE, source_root=authority.source_root), (
        f"{SCOPE_REF} no longer quotes the clause making the anexo amendable, so nothing in the corpus "
        "establishes why the geography must be dated"
    )

    pinning = _source_pinning(authority, geography)
    assert pinning.applies_from is not None, (
        f"source {pinning.id!r} pins the anexo bytes with no applies_from, so the geography it backs "
        "has no start of validity"
    )
    assert pinning.applies_from <= geography.effective_from, (
        f"source {pinning.id!r} claims validity only from {pinning.applies_from}, after the anexo took "
        f"effect on {geography.effective_from}"
    )


def test_the_reduction_reads_its_applicability_off_the_final_provision() -> None:
    """When the reduction applies comes from the entry-into-force provision."""
    authority = dana_authority()
    reduction = authority.legal[REDUCTION_REF]
    entry_into_force = authority.legal[ENTRY_INTO_FORCE_REF]

    assert legal_reference_quotes_corpus(
        entry_into_force,
        ENTRY_INTO_FORCE_RULE,
        source_root=authority.source_root,
    ), (
        f"{ENTRY_INTO_FORCE_REF} does not quote the entry-into-force rule, so the reduction's start "
        "date rests on an author's reading rather than on the provision"
    )
    assert entry_into_force.published_at is not None, (
        f"{ENTRY_INTO_FORCE_REF} declares no published_at, so the rule it quotes -- in force the day "
        "after publication -- cannot be evaluated"
    )

    derived = entry_into_force.published_at + timedelta(days=1)
    assert entry_into_force.effective_from == derived, (
        f"{ENTRY_INTO_FORCE_REF} was published {entry_into_force.published_at} and states it takes "
        f"effect the following day, which is {derived}, but declares {entry_into_force.effective_from}"
    )
    assert reduction.effective_from == entry_into_force.effective_from, (
        f"{REDUCTION_REF} claims to apply from {reduction.effective_from} while the final provision "
        f"governing its norm puts it in force on {entry_into_force.effective_from}; the reduction's "
        "applicability must be the provision's, not an independent judgement"
    )
    assert entry_into_force.document_id == reduction.document_id, (
        f"{ENTRY_INTO_FORCE_REF} governs {entry_into_force.document_id!r}, not the reduction's own "
        f"{reduction.document_id!r}, so it cannot establish when the reduction applies"
    )


def test_the_correction_provenance_is_bundled_and_cited_by_the_text_it_corrects() -> None:
    """BOE-A-2024-24097 ships as bytes and the corrected article names it."""
    authority = dana_authority()
    correction = authority.legal[CORRECTION_REF]
    scope = authority.legal[SCOPE_REF]

    pinning = _source_pinning(authority, correction)
    artefact = authority.source_root / pinning.corpus_path
    assert artefact.is_file(), (
        f"correction provenance source {pinning.id!r} cites missing bytes {pinning.corpus_path!r}"
    )

    payload = artefact.read_bytes()
    assert hashlib.sha256(payload).hexdigest() == pinning.sha256, (
        f"correction artefact {pinning.corpus_path!r} does not hash to the digest {pinning.id!r} pins"
    )
    assert len(payload) == pinning.bytes, (
        f"correction artefact {pinning.corpus_path!r} is {len(payload)} bytes, not the {pinning.bytes} "
        f"{pinning.id!r} pins"
    )

    assert legal_reference_quotes_corpus(
        scope,
        f"Ref. {correction.document_id}",
        source_root=authority.source_root,
    ), (
        f"the corrected article {SCOPE_REF} does not carry a consolidation note naming "
        f"{correction.document_id}, so nothing ties the text being cited to the correction that "
        "produced it"
    )
    assert legal_reference_quotes_corpus(
        correction,
        scope.document_id,
        source_root=authority.source_root,
    ), (
        f"{CORRECTION_REF} does not name {scope.document_id} in its own text, so it cannot be shown to "
        "correct the norm it is filed against"
    )


def test_every_dana_identifier_resolves_to_a_bundled_official_boe_artefact() -> None:
    """No BOE identifier, permalink or pinned digest may be invented."""
    authority = dana_authority()
    failures: list[str] = []

    for ref, reference in authority.legal.items():
        if not BOE_DOCUMENT_ID.match(reference.document_id):
            failures.append(f"{ref}: document_id {reference.document_id!r} is not a BOE identifier")
            continue
        permalink = urlsplit(reference.permalink)
        if permalink.scheme != "https" or permalink.hostname != BOE_HOST:
            failures.append(f"{ref}: permalink {reference.permalink!r} does not resolve against {BOE_HOST}")
        if reference.document_id not in reference.permalink:
            failures.append(f"{ref}: permalink {reference.permalink!r} does not name {reference.document_id}")
        artefact = authority.source_root / reference.corpus_ref.partition("#")[0]
        if not artefact.is_file():
            failures.append(f"{ref}: cites missing corpus artefact {reference.corpus_ref!r}")
            continue
        if reference.document_id not in artefact.read_text(encoding="utf-8", errors="replace"):
            failures.append(
                f"{ref}: bundled artefact {artefact.name} never declares {reference.document_id}, so the "
                "identifier was asserted rather than read off the document"
            )

    for ref, source in authority.sources.items():
        artefact = authority.source_root / source.corpus_path
        if not artefact.is_file():
            failures.append(f"{ref}: pins missing artefact {source.corpus_path!r}")
            continue
        payload = artefact.read_bytes()
        if hashlib.sha256(payload).hexdigest() != source.sha256:
            failures.append(f"{ref}: pinned sha256 does not match {source.corpus_path!r} on disk")
        if len(payload) != source.bytes:
            failures.append(f"{ref}: pinned byte count {source.bytes} does not match {len(payload)} on disk")
        url = urlsplit(source.source_url)
        if url.scheme != "https" or url.hostname != BOE_HOST:
            failures.append(f"{ref}: source_url {source.source_url!r} does not resolve against {BOE_HOST}")
        found = BOE_DOCUMENT_ID.match(url.query.removeprefix("id="))
        if found is None:
            failures.append(f"{ref}: source_url {source.source_url!r} carries no BOE identifier")

    assert not failures, "DANA authority cites artefacts that do not resolve:\n" + "\n".join(failures)


def test_the_reduction_parameter_cites_the_three_authorities_the_measure_needs() -> None:
    """The percentage, the entry into force and the geography are all cited."""
    authority = dana_authority()
    declared = set(authority.parameter_legal_refs)
    required = {REDUCTION_REF, ENTRY_INTO_FORCE_REF, GEOGRAPHY_REF}

    assert required <= declared, (
        f"the reduction parameter cites {sorted(declared)!r} and so omits {sorted(required - declared)!r}; "
        "the measure needs the apartado that fixes the rate, the provision that says from when, and the "
        "anexo that says where"
    )
    unresolved = sorted(ref for ref in declared if ref not in authority.legal)
    assert not unresolved, f"the reduction parameter cites legal refs outside the DANA authority: {unresolved!r}"


def test_the_geography_is_cited_rather_than_transcribed() -> None:
    """The reduction points at the anexo instead of listing municipalities."""
    authority = dana_authority()
    reduction = authority.legal[REDUCTION_REF]
    geography = authority.legal[GEOGRAPHY_REF]

    assert legal_reference_quotes_corpus(
        reduction,
        "los términos municipales citados en el anexo del Real Decreto-ley 6/2024",
        source_root=authority.source_root,
    ), (
        f"{REDUCTION_REF} no longer defers to the RDL 6/2024 anexo for its scope, so the geography it "
        "applies to would have to come from somewhere this catalogue does not control"
    )
    assert geography.consolidated_as_of is not None, (
        f"{GEOGRAPHY_REF} answers 'which municipalities' without an as-of date, so the deferral above "
        "buys nothing: the reduction would point at an undated list the Consejo de Ministros may since "
        "have amended"
    )


@pytest.mark.parametrize("ref", DANA_LEGAL_REFS)
def test_every_dana_citation_is_backed_by_exactly_one_pinned_source(ref: str) -> None:
    """A citation's bytes are pinned once, and that pin names the same document.

    The exactly-one half is asserted by :func:`_source_pinning`. What remains
    here is the half a same-artefact pin can still get wrong: the pin's own
    provenance URL must name the BOE document the citation claims. A pin whose
    URL was copied from a neighbouring entry keeps pointing at the right file
    on disk while recording where the WRONG bytes came from, and every
    sha-and-artefact check in this module passes over it.

    Deliberately not asserted: ``source.review_status``. It is typed
    ``Literal["reviewed"]``, so no other value is representable and the
    comparison could not fail. ``_legal.verify_legal_reference`` had the same
    dead branch removed for the same reason; re-adding it here as a test would
    reintroduce it one layer up.
    """
    authority = dana_authority()
    reference = authority.legal[ref]

    source = _source_pinning(authority, reference)

    assert reference.document_id in source.source_url, (
        f"{ref} claims document {reference.document_id!r} but the source pinning its bytes was fetched "
        f"from {source.source_url!r}, which names a different document; the pin records the provenance "
        "of the wrong bytes"
    )


def _anexo_municipalities(authority: DanaAuthority) -> tuple[str, ...]:
    """Return the anexo's municipality names, read from the bundled corpus.

    Derived from the cited corpus unit rather than transcribed here, because a
    list hardcoded into the test that refuses transcription would be the very
    thing it refuses. The anexo renders as alternating number and name lines,
    each name terminated by a full stop.
    """
    reference = authority.legal[GEOGRAPHY_REF]
    path, _, anchor = reference.corpus_ref.partition("#")
    text = resolve_anchored_extracted_unit(
        authority.source_root / (path + ".extracted.json"),
        anchor=anchor,
        include_title=True,
    )
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return tuple(
        lines[index + 1].rstrip(".")
        for index, line in enumerate(lines[:-1])
        if line.isdigit() and lines[index + 1].endswith(".")
    )


def test_no_registry_value_enumerates_the_anexo_instead_of_citing_it() -> None:
    """The registry may cite the anexo; it may never reproduce the list.

    The refusal this whole authority exists for, asserted where it can actually
    be broken: across the WHOLE registry authoring tree, not just the DANA
    slice, because a transcription would most plausibly appear in a modelo
    construct or a parameter note rather than beside the citation it replaces.

    ``required_text`` is excluded by construction. Quoting anexo lines there is
    the sanctioned mechanism -- those phrases are the anchor that pins WHICH
    redaction of the list is meant, and the geography entry depends on them.

    Detection is on list SHAPE, not on name membership, and that is forced by
    the data: three of the 78 names ("Real", "Silla", "Mira") are ordinary
    Spanish words, so a membership scan flags most of the tree. Measured over
    the current tree at FILE granularity -- deliberately the more permissive
    measurement, since a file's name set contains every one of its values' --
    17,033 of 17,151 registry files name no municipality, 117 name exactly
    one, and a single file names two. Nothing reaches three. Three distinct
    names inside ONE authored value is therefore not a word collision; it is
    the beginning of a list. The boundary describes the shape of an
    enumeration rather than counting current sites, so adding entries or prose
    cannot walk the tree into it.

    The file-level pass is a pure speed prefilter and cannot hide an offender:
    a value's names are a subset of its file's, so a file under the threshold
    has no value over it.
    """
    authority = dana_authority()
    municipalities = _anexo_municipalities(authority)

    assert len(municipalities) >= _ANEXO_ANTI_VACUITY_FLOOR, (
        f"only {len(municipalities)} municipalities parsed out of the anexo; the probe is not reaching "
        "the list, so every assertion below would hold vacuously"
    )
    named_anywhere = re.compile(
        r"\b(?:" + "|".join(re.escape(normalise_corpus_text(name)) for name in municipalities) + r")\b",
    )

    offenders: list[str] = []
    for toml_path in scan_directory(bundled_path("registry", "aeat"), pattern="*.toml", recursive=True):
        body = _REQUIRED_TEXT_ARRAY.sub(" ", toml_path.read_text(encoding="utf-8"))
        if len(set(named_anywhere.findall(normalise_corpus_text(body)))) < _ENUMERATION_THRESHOLD:
            continue
        for value in _TOML_STRING.finditer(body):
            named = set(named_anywhere.findall(normalise_corpus_text(value.group(0))))
            if len(named) >= _ENUMERATION_THRESHOLD:
                offenders.append(f"{toml_path.name}: names {sorted(named)[:6]}")

    assert not offenders, (
        "registry values enumerate anexo municipalities instead of citing the anexo; the list is "
        "amendable by Acuerdo de Consejo de Ministros, so a copy in the registry is a snapshot that "
        "silently stops matching the law:\n" + "\n".join(offenders[:10])
    )
