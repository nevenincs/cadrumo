"""The standing worklist of modelos this application cannot yet file.

THIS TEST IS EXPECTED TO FAIL, AND MUST NOT BE MADE TO PASS BY NARROWING IT.

A permanently-failing test is normally forbidden by this project's quality rules.
This one is sanctioned by explicit operator directive, and it exists because the
previous arrangement was worse: every modelo that could not emit a filing artifact
carried a decision record declaring its layout withdrawn, each individually
grounded and defensible, and nothing ever summed them. The tree stayed green while
the application quietly could not file IVA, sociedades or retenciones. Converting
"we cannot file this" into a declared, gate-satisfying state is precisely what let
that go unnoticed for the whole of the project's history.

So the absence is now loud instead of ratified. The failure message below is the
capability worklist: every modelo and revision that cannot produce a filing
artifact, sorted and counted. It goes green when, and only when, every revision in
the registry can emit -- at which point the list is empty and this test passes on
its own, with no edit.

Forbidden, without exception:

* Do not skip, xfail, or mark this test.
* Do not narrow it to a subset of modelos, add an allowlist, or excuse
  "informative" modelos.
* Do not hardcode the expected list. It is derived from the registry on every run,
  so a modelo that gains a layout leaves the list automatically and one that loses
  a layout rejoins it. A hardcoded tally would rot into a stale claim, which is the
  same failure mode in a new costume.

An authorable row leaves this test only after its layout and filing authority
are actually built. A terminal row remains visible until its own stated
reconsideration condition changes; it is not erased by a synthetic layout.

BUILDING THE LAYOUT IS NECESSARY BUT NOT SUFFICIENT, and the reason is not visible in
the failure message. Every revision currently on this list is ``authority_grade =
"applicability"`` -- measured across the whole list, with no exception. An applicability
revision exists to answer whether a taxpayer has an obligation for a period, not how to
file it, and several say so in their own reviewer notes: modelo 390's 2021 revision
records "filing layout authority is not claimed". Authoring a fixed-width layout onto
such a revision without also promoting its grade would make a filing claim that the
revision's own recorded review disclaims, which is the ratified-absence failure this
module exists to prevent, arriving from the opposite direction.

So clearing a row takes two things: the layout, AND a grounded decision that this
application may claim filing authority for that revision's years. The second is an
authority judgement about what the product asserts it can file, not a mechanical edit,
and it is the reason a row can be technically authorable -- design bundled, casillas
declared, extraction self-consistent -- and still not be cleared by an agent working
alone. Nothing here licenses lowering the bar: a row stays on this list until both are
done.

See Also:
    :func:`cadrumo.domain.calculations.registry.bundled_authority`
        Loads the registry this worklist is derived from.
    :class:`cadrumo.domain.calculations.registry.ModeloRevision`
        The revision whose ``export_layouts`` decide filing capability.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Literal

import pytest

from .....core.modelo import Modelo
from .....core.resources import bundled_path
from .....tests.registry_tree import bundled_registry_tree
from ..export import derive_export_layouts_from_bindings
from ..schema import ModeloDefinition, ModeloRevision
from ..schema_references import SourceReference
from .test_cited_design_field_bounds_are_self_consistent import (
    _KNOWN_SELF_CONTRADICTING_DESIGN,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


#: Designs that number the record's LINE BREAK as a field inside the declared length.
#:
#: This pipeline models a terminator on the TRANSPORT -- an export layout declares
#: ``line_ending`` and the renderer appends it. Modelo 840 instead lists "Salto de
#: linea. Constante CRLF." at positions 1131-1132 of a record whose declared total is
#: 1132, so the break sits inside the extent the design states.
#:
#: Both models cannot hold at once, and every available entry kind writes the wrong
#: bytes. A ``literal`` entry is validated by extracting the constant from the design's
#: own text, which yields the four-character NAME "CRLF" against a two-byte field. A
#: ``filler`` entry renders two spaces where the terminator belongs. Omitting the row is
#: refused, because a semantic map must form a complete bijection with parser output.
#: Excluding it in the reader was tried and measured: it drops the record below its
#: declared total and every sheet then reports a contiguity hole.
#:
#: So this waits only on the missing generic semantic-map bridge: it must retain the
#: official terminal-row anchor while delegating the one emitted CRLF to the existing
#: record ``line_ending`` transport authority.  The canonical renderer already emits
#: that transport terminator; a second table or Modelo-840-specific writer would
#: redeclare it.  Recorded here rather than worked around, because each workaround
#: corrupts the last two bytes of every record in the file.
_TERMINATOR_IS_A_NUMBERED_FIELD = "aeat-dr-840"


type _OwnerRoute = Literal[
    "registry-temporal-coverage",
    "source-casilla-integration",
    "aeat-export-fragment-generator-authority",
]


_TEMPORAL_OWNER: _OwnerRoute = "registry-temporal-coverage"
_SOURCE_CASILLA_OWNER: _OwnerRoute = "source-casilla-integration"
_EXPORT_OWNER: _OwnerRoute = "aeat-export-fragment-generator-authority"
_EXISTING_OWNER_DOMAINS = frozenset({_TEMPORAL_OWNER, _SOURCE_CASILLA_OWNER, _EXPORT_OWNER})

_M038_OWNERS = (
    _TEMPORAL_OWNER,
    _EXPORT_OWNER,
)
_M182_OWNERS = (
    _TEMPORAL_OWNER,
    _SOURCE_CASILLA_OWNER,
    _EXPORT_OWNER,
)
_M185_OWNERS = (_EXPORT_OWNER,)
_M187_OWNERS = (
    _TEMPORAL_OWNER,
    _SOURCE_CASILLA_OWNER,
    _EXPORT_OWNER,
)
_M188_OWNERS = (
    _TEMPORAL_OWNER,
    _SOURCE_CASILLA_OWNER,
    _EXPORT_OWNER,
)
_M194_OWNERS = (
    _TEMPORAL_OWNER,
    _SOURCE_CASILLA_OWNER,
    _EXPORT_OWNER,
)
_M220_2024_OWNERS = (
    _SOURCE_CASILLA_OWNER,
    _EXPORT_OWNER,
)
_M220_2025_OWNERS = (
    _TEMPORAL_OWNER,
    *_M220_2024_OWNERS,
)
_M390_OWNERS = (
    _SOURCE_CASILLA_OWNER,
    _EXPORT_OWNER,
)
_M721_OWNERS = (
    _TEMPORAL_OWNER,
    _SOURCE_CASILLA_OWNER,
    _EXPORT_OWNER,
)
_M763_OWNERS = (
    _TEMPORAL_OWNER,
    _SOURCE_CASILLA_OWNER,
    _EXPORT_OWNER,
)
_M840_OWNERS = (
    _SOURCE_CASILLA_OWNER,
    _EXPORT_OWNER,
)


@dataclass(frozen=True)
class _FilingCapabilityBlocker:
    """One non-emitting revision's current, evidence-bounded disposition.

    This is deliberately the canonical worklist's local report shape, rather
    than a second registry declaration. Registry validation decides whether a
    revision can emit; the worklist makes that absence visible and reports the
    already-adjudicated route that could change it. A terminal refusal is not a
    permanent exclusion: it has no authorable task *under today's authority*,
    and becomes an owner-routed gap when the stated reconsideration condition
    obtains.
    """

    disposition: Literal["terminal_no_authority", "terminal_product_scope", "authorable_gap"]
    finding: str
    reconsideration: str
    owners: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.disposition in {"terminal_no_authority", "terminal_product_scope"} and self.owners:
            raise ValueError("a terminal filing refusal must not claim an authorable owner")
        if self.disposition == "authorable_gap" and not self.owners:
            raise ValueError("an authorable filing gap must name at least one existing-plan owner")
        if self.disposition == "authorable_gap" and not set(self.owners) <= _EXISTING_OWNER_DOMAINS:
            raise ValueError("an authorable filing gap must name only an existing-plan owner domain")

    def report(self) -> str:
        if self.disposition == "terminal_no_authority":
            return (
                f"TERMINAL NO-AUTHORITY: {self.finding}. No export layout is authorable now; "
                f"reconsider only if {self.reconsideration}"
            )
        if self.disposition == "terminal_product_scope":
            return (
                f"TERMINAL PRODUCT-SCOPE: {self.finding}. No M036 filing artifact is authorable now; "
                f"reconsider only if {self.reconsideration}"
            )
        return (
            f"AUTHORABLE GAP ({'; '.join(self.owners)}): {self.finding}. "
            f"Reconsider/clear only after {self.reconsideration}"
        )


def _authorable(
    finding: str,
    *,
    owners: tuple[_OwnerRoute, ...],
    reconsideration: str,
) -> _FilingCapabilityBlocker:
    """Return the one owner-routed report shape for an actionable filing gap."""
    return _FilingCapabilityBlocker(
        disposition="authorable_gap",
        finding=finding,
        owners=owners,
        reconsideration=reconsideration,
    )


def _terminal_product_scope(
    modelo: ModeloDefinition,
    revision: ModeloRevision,
) -> _FilingCapabilityBlocker | None:
    """Return the accepted M036 product-scope refusal for its exact revision.

    This is separate from :func:`_terminal_no_authority`: AEAT publishes an
    exact M036 machine-readable design, but the current product does not
    prepare a censo filing artifact. The classification is intentionally exact
    to the one reviewed revision, rather than an inference from censo taxonomy,
    applicability grade, or a missing producer namespace. Those facts cannot
    silently expand the terminal boundary to another modelo or revision.
    """
    if getattr(modelo, "id", None) != Modelo.M036 or getattr(revision, "id", None) != "2025-02-03-y-siguientes":
        return None
    return _FilingCapabilityBlocker(
        disposition="terminal_product_scope",
        finding=(
            "the shipped product supports censo applicability and records a human-filed declaration, "
            "but does not prepare a Modelo 036 filing artifact"
        ),
        reconsideration=(
            "a new accepted ADR expands M036 artifact scope and the existing source, grade, semantic-map, "
            "render-profile, generated-tree, and emitted-byte prerequisites are independently satisfied"
        ),
    )


def _terminal_no_authority(
    modelo: ModeloDefinition,
    revision: ModeloRevision,
    sources: Mapping[str, SourceReference],
) -> _FilingCapabilityBlocker | None:
    """Return Modelo 136's current evidence-bounded terminal refusal, if still true.

    This is intentionally a *named adjudication*, not an inference that every
    modelo without a fixed-width record design lacks an authorable path. Modelo
    721 is the counterexample only at the architectural-shape level: a future
    source-backed SOAP/XML contract can be an authorable extension of its
    existing authority despite not being a positional record design. The
    official Modelo 136 catalogue/procedure
    review is narrower: its current layout authority is a visual ``manual_pdf``
    and it has no registered ``record_design``, ``xsd`` or ``dictionary``
    source. Treating a visual form as any of those contracts would fabricate a
    wire representation.

    The source-kind condition makes this disposition self-invalidating. If the
    catalogue gains a machine-readable Modelo 136 contract, this helper returns
    ``None`` and the normal owner-routed classifier below takes over; the
    dedicated regression then forces a fresh adjudication before anyone can
    silently retain the terminal label.
    """
    if getattr(modelo, "id", None) != Modelo.M136 or getattr(revision, "id", None) != "2026":
        return None

    source_refs = set(getattr(revision, "source_refs", ()))
    resolved: list[SourceReference] = []
    for ref in source_refs:
        source = sources.get(ref)
        if source is not None:
            resolved.append(source)
    kinds = {source.kind for source in resolved}
    if "manual_pdf" not in kinds or _modelo_136_has_machine_contract(revision, sources):
        return None

    return _FilingCapabilityBlocker(
        disposition="terminal_no_authority",
        finding=(
            "the reviewed AEAT form route has a visual approved form but no current machine-readable "
            "Modelo 136 filing contract"
        ),
        reconsideration=(
            "AEAT publishes a hash-pinned, revision-scoped machine-readable contract and "
            "the export plan receives an accepted, exact predecessor route for the semantic map, render profile, "
            "generated tree, and emitted-byte proof"
        ),
    )


def _modelo_136_has_machine_contract(
    revision: ModeloRevision,
    sources: Mapping[str, SourceReference],
) -> bool:
    """Return whether this Modelo 136 revision itself cites machine authority.

    The scope is the revision's source references, never every source attached to
    the modelo. A future source registered only for another exercise cannot
    silently change the 2026 worklist row. Conversely, when a machine-readable
    contract is cited by this revision, the terminal refusal must retire even
    while the remaining owner-routed implementation work is still open.
    """
    machine_kinds = {"record_design", "xsd", "dictionary"}
    return any(
        getattr(source, "kind", None) in machine_kinds
        for ref in getattr(revision, "source_refs", ())
        if (source := sources.get(ref)) is not None
    )


def _revisions_that_cannot_emit() -> tuple[tuple[str, str, _FilingCapabilityBlocker], ...]:
    """Return every ``(modelo, revision)`` that can produce no filing artifact.

    Capability is read exactly as the filing boundary reads it: layouts are derived
    from bindings first, so a revision declaring none inline but deriving one counts
    as capable and never appears here. That keeps this worklist and the refusal in
    :mod:`.._snapshot` from ever disagreeing about who is on the list.

    The tree is read through the compiler rather than the validated authority on
    purpose. A worklist that can only be produced when the registry is healthy is
    useless precisely when it is needed: any unrelated validation failure anywhere
    in the tree would replace this enumeration with someone else's error, and the
    list of modelos that cannot file would silently stop being reported.
    """
    modelos, catalogues = bundled_registry_tree()
    return tuple(
        sorted(
            (str(modelo.id), str(revision.id), _blocker(modelo, revision, catalogues.sources))
            for modelo in modelos
            for revision in modelo.revisions.values()
            if not derive_export_layouts_from_bindings(revision)
        ),
    )


def _bundled_designs(modelo_id: str) -> tuple[str, ...]:
    """Return the record-design files the corpus holds for one modelo."""
    directory = bundled_path("corpus", "aeat_official", "disenos_registro", f"modelo_{modelo_id}", "files")
    if not directory.is_dir():
        return ()
    return tuple(sorted(path.name for path in directory.iterdir() if path.suffix.lower() in {".pdf", ".xls", ".xlsx"}))


def _blocker(
    modelo: ModeloDefinition,
    revision: ModeloRevision,
    sources: Mapping[str, SourceReference],
) -> _FilingCapabilityBlocker:
    """Return what this revision actually needs before a layout can be authored.

    Derived on every run, never listed. The bare worklist said only "no export
    layout" for every line, which reads as one backlog of one kind of work. It
    is three. A revision whose modelo has no bundled design normally needs the
    source/casilla and export owners to acquire the authority and establish the
    payload. A revision whose designs are bundled but unregistered needs the era
    each governs grounded first, and that is not mechanical: a design may state
    no orden, no BOE reference and no ejercicio anywhere in its text, leaving
    only AEAT's update date, which has twice had to be rejected as a governed
    period. A revision whose modelo HAS registered designs but
    cites none of them is waiting on the design for its own window, which is
    modelo 185's 2003-2025 case: the one bundled design governs 2026 onward and
    correctly grounds its sibling revision instead. A revision already citing a
    registered design is authorable now.

    Two reviewed terminal refusals are classified before generic diagnosis. Modelo
    136 is ``terminal_no_authority`` because its current official surface lacks a
    machine-readable contract. Modelo 036 is ``terminal_product_scope`` because
    the current product records human-filed censo events rather than preparing
    their artifact, even though an exact machine-readable design exists. Neither
    label is inferred from grade, taxonomy, or missing producers; each is exact
    to its reviewed revision so no other row inherits it accidentally.

    Sequencing the remaining work needs that distinction, and deriving it costs
    one directory listing per line.

    What this does NOT establish is that the cited design can be READ reliably.
    Modelo 038 cites a design whose declared era covers every claimed ejercicio
    -- so it reads AUTHORABLE here -- while that design's extraction places
    fields across each other's bytes, which
    ``test_cited_design_field_bounds_are_self_consistent`` already names and
    refuses to let a layout cite. Authoring from it produced records that tiled
    1..250 with no HOLES, because partial overlap leaves none, and the offsets
    were still untrustworthy.

    That check is deliberately not repeated here in general: it must extract
    every cited design, which would turn a listing into minutes of parsing --
    modelo 220's design alone carries 137 sheets and 16,079 fields. The verdict
    says "AUTHORABLE on era" rather than "AUTHORABLE" so the remaining
    precondition is named where it will be read.

    The ONE design the corpus already knows to be self-contradicting is named
    outright, by importing the sibling gate's own anchor rather than copying the
    string. Modelo 038's bundled artefact is a form DIAGRAM -- a byte ruler and
    free-floating labels, with no ordinal/offset/length rows anywhere -- so its
    coordinates are inferred and overlap. Reading AUTHORABLE for it invited an
    authoring attempt that had to be withdrawn; the anchor moves or retires
    through the sibling gate, which fails loudly if the corpus changes.
    """
    modelo_id = str(modelo.id)
    product_scope = _terminal_product_scope(modelo, revision)
    if product_scope is not None:
        return product_scope
    terminal = _terminal_no_authority(modelo, revision, sources)
    if terminal is not None:
        return terminal
    if modelo.id == Modelo.M136 and _modelo_136_has_machine_contract(revision, sources):
        return _authorable(
            "a machine-readable Modelo 136 contract is cited, but its semantic map and emitted-byte proof are absent",
            # No current predecessor route may be claimed for a machine contract
            # that does not yet exist.  The classifier must be re-adjudicated
            # when the authority condition changes instead of borrowing a
            # completed enrollment label.
            owners=(_EXPORT_OWNER,),
            reconsideration=(
                "an accepted export-plan route lands the reviewed map, render profile, generated tree, and "
                "emitted-byte proof"
            ),
        )
    designs = _bundled_designs(modelo_id)
    registered = tuple(
        ref
        for ref, source in sources.items()
        if getattr(source, "kind", None) == "record_design"
        and source.corpus_path
        and f"modelo_{modelo_id}/" in str(source.corpus_path).replace("\\", "/")
    )
    cited = tuple(
        str(ref)
        for ref in (revision.source_refs or ())
        if (source := sources.get(str(ref))) is not None and getattr(source, "kind", None) == "record_design"
    )
    if not designs:
        if modelo.id == Modelo.M721:
            return _authorable(
                "no positional record design is bundled; finite BOE form-spec packages do not establish the missing pair-complete 2023/2024 AEAT structured-message contract",
                owners=_M721_OWNERS,
                reconsideration=(
                    "the three accepted predecessor routes acquire pair-complete versioned AEAT SOAP/XML contract eras, source-derived value lifecycles, and the "
                    "canonical locally-proven serializer"
                ),
            )
        return _authorable(
            "no record design is bundled for this modelo",
            owners=(_TEMPORAL_OWNER, _SOURCE_CASILLA_OWNER, _EXPORT_OWNER),
            reconsideration=(
                "the exact official technical authority is acquired with a bounded era, its complete value "
                "surface has canonical owners, and the export owner proves the authorized payload"
            ),
        )
    if not registered:
        return _authorable(
            f"{len(designs)} design(s) are bundled but none is registered; the era each governs is not grounded",
            owners=(_TEMPORAL_OWNER,),
            reconsideration="the temporal owner registers the official source with exact applicability before it becomes a source_ref",
        )
    if not cited:
        if modelo.id == Modelo.M185:
            return _authorable(
                (
                    "the registered 2026 record design is outside this historical revision; the 2003-2025 Annex-I "
                    "authority has not yet been acquired and registered"
                ),
                owners=_M185_OWNERS,
                reconsideration=(
                    "the exact export predecessor acquires the historic Annex-I source, registers its bounded scope, "
                    "then maps only its 120-position record types"
                ),
            )
        return _authorable(
            f"{len(registered)} record design(s) are registered for this modelo, but none is cited by this revision",
            owners=(_TEMPORAL_OWNER,),
            reconsideration="the temporal owner proves and cites the design governing this revision's exact window",
        )

    if _KNOWN_SELF_CONTRADICTING_DESIGN in cited:
        return _authorable(
            (
                f"cites {_KNOWN_SELF_CONTRADICTING_DESIGN}, whose extraction places fields across bytes; "
                "the bundled artefact is a form diagram rather than a trustworthy field table"
            ),
            owners=_M038_OWNERS,
            reconsideration=(
                "the accepted temporal and export predecessors acquire exact authority and a trustworthy layout before "
                "mapping bytes"
            ),
        )

    if _TERMINATOR_IS_A_NUMBERED_FIELD in cited:
        return _authorable(
            (
                f"{_TERMINATOR_IS_A_NUMBERED_FIELD} numbers the line break inside the record extent, while "
                "the current renderer puts it on the transport; no current entry kind renders that field"
            ),
            owners=_M840_OWNERS,
            reconsideration=(
                "the accepted source and export predecessors model the generic terminator bridge, value lifecycle, and "
                "emitted bytes"
            ),
        )

    uncovered = _uncovered_claimed_years(revision, cited, sources)
    if uncovered:
        span = f"{uncovered[0]}-{uncovered[-1]}" if len(uncovered) > 1 else str(uncovered[0])
        return _authorable(
            (
                f"cites {cited[0]}, but ejercicio(s) {span} ({len(uncovered)} year(s)) fall outside every "
                "cited design era"
            ),
            owners=_uncovered_design_owners(modelo),
            reconsideration=(
                "the accepted temporal, source, and export predecessors resolve the exact window and map only "
                "evidenced values and offsets"
            ),
        )
    short = _casilla_surface_shortfall(modelo, revision)
    if short is not None:
        return short
    missing_producers = _producer_vocabulary_gap(modelo)
    if missing_producers is not None:
        return missing_producers
    return _authorable(
        (
            f"cites {cited[0]} and declares {len(revision.casillas or ())} casilla(s); it needs its semantic "
            "map and authorized export form after the design extraction is checked for partial overlap"
        ),
        owners=(_EXPORT_OWNER,),
        reconsideration="the export owner lands and reviews the semantic map, render profile, generated tree, and emitted-byte proof",
    )


def _producer_vocabulary_gap(modelo: ModeloDefinition) -> _FilingCapabilityBlocker | None:
    """Return why this modelo cannot be exported YET, when nothing can supply its values.

    A record design says WHERE each value sits. It does not say where the value comes
    FROM. Most fields on a declaration are not casillas at all -- an address, a
    municipio, an activity code, a representative -- and the semantic map addresses
    those with ``kind = "header"`` plus a ``producer_key`` naming one member of the
    closed :class:`FilingProducerKey` vocabulary. A key that names nothing the
    application produces is a design-only shell, so the vocabulary has to exist before
    the map can.

    Measured across the tree: every modelo that ships a generated export tree owns a
    producer namespace -- 135 keys for modelo 200, 112 for 296, 102 for 210, 70 for
    360 -- and every modelo still on this worklist owns none. Modelo 840 is the worked
    example: its design carries 381 fields of which 130 are casillas and 177 are
    untagged data (Delegación, Municipio, Elementos Tributarios del grupo o epígrafe),
    and the vocabulary contains no IAE identity at all. Authoring its map would mean
    inventing 177 keys with no producer behind them.

    THE NAMESPACE TEST CAN ONLY UNDER-FLAG. Modelo 210's keys are namespaced ``irnr``
    rather than ``m210``, so a modelo whose keys sit under a domain alias reads as
    empty here. That direction is safe: such a modelo already ships its export and is
    therefore not on this list. A modelo genuinely lacking a vocabulary cannot be
    hidden by the alias, because it has no keys under any name.
    """
    from .....core import FilingProducerKey

    prefix = f"m{modelo.id}."
    if any(member.value.startswith(prefix) for member in FilingProducerKey):
        return None
    owners = _M220_2024_OWNERS if modelo.id == Modelo.M220 else (_SOURCE_CASILLA_OWNER, _EXPORT_OWNER)
    return _authorable(
        (
            f"no FilingProducerKey is namespaced {prefix!r}, so non-casilla design fields have no canonical "
            "identity or application producer"
        ),
        owners=owners,
        reconsideration=(
            "the accepted source/casilla predecessor supplies provenance-carrying producers before the export "
            "predecessor maps them"
        ),
    )


def _casilla_surface_shortfall(
    modelo: ModeloDefinition,
    revision: ModeloRevision,
) -> _FilingCapabilityBlocker | None:
    """Return why this revision cannot be exported YET, when its casilla surface is short.

    An era match says the cited design governs the years claimed. It says nothing about
    whether the revision declares the boxes that design carries, and the two were being
    conflated: modelo 390's 2021 revision declares TEN casillas while every filing-grade
    sibling of the same modelo declares 325 or more, so a layout authored from it would
    emit a return missing almost every box AEAT expects -- structurally thin, correctly
    sized, and valid to every digest.

    The yardstick is the modelo's OWN filing-grade revisions rather than a threshold: a
    ratio would be a constant to argue about, while a revision declaring strictly fewer
    casillas than every sibling that already files is short by the modelo's own standard.
    Where a modelo has no filing-grade sibling there is nothing to compare against and
    this returns ``None`` -- the era verdict stands on its own.
    """
    declared = len(revision.casillas or ())
    peers = [
        len(sibling.casillas or ())
        for sibling in (modelo.revisions or {}).values()
        if sibling is not revision
        and str(getattr(sibling, "authority_grade", "") or "").lower() == "filing"
        and (sibling.casillas or ())
    ]
    if not peers or declared >= min(peers):
        return None
    owners = _M390_OWNERS if modelo.id == Modelo.M390 else (_SOURCE_CASILLA_OWNER, _EXPORT_OWNER)
    return _authorable(
        (
            f"declares {declared} casilla(s) while every filing-grade sibling declares at least {min(peers)}; "
            "the cited era matches but the current surface cannot represent the declaration"
        ),
        owners=owners,
        reconsideration=(
            "the accepted source/casilla predecessor completes the grounded surface before the export predecessor "
            "maps it"
        ),
    )


#: Open-ended designs are treated as covering to this horizon, matching
#: :mod:`test_layout_design_applies_to_claimed_years`, which asks the same
#: question about revisions that already declare a layout.
_OPEN_ENDED_HORIZON = 2026


def _uncovered_design_owners(modelo: ModeloDefinition) -> tuple[_OwnerRoute, ...]:
    """Return the accepted route bundle for a live design-era shortfall.

    The condition is derived from the loaded revision and source catalogue.
    These route bundles only point to the predecessor rows that the three plans
    already accepted for each distinct evidence gap; they do not create a
    parallel temporal, source, or export authority.
    """
    if modelo.id == Modelo.M182:
        return _M182_OWNERS
    if modelo.id == Modelo.M187:
        return _M187_OWNERS
    if modelo.id == Modelo.M188:
        return _M188_OWNERS
    if modelo.id == Modelo.M194:
        return _M194_OWNERS
    if modelo.id == Modelo.M220:
        return _M220_2025_OWNERS
    if modelo.id == Modelo.M763:
        return _M763_OWNERS
    # A new live shortfall must stay visibly unrouted until its own predecessor
    # row is accepted; it may not inherit one of the reviewed Modelo routes.
    return (_TEMPORAL_OWNER, _EXPORT_OWNER)


def _uncovered_claimed_years(
    revision: ModeloRevision,
    cited: tuple[str, ...],
    sources: Mapping[str, SourceReference],
) -> list[int]:
    """Return the ejercicios this revision claims that no cited design covers.

    The distinction this draws is the one that cost three modelos. A revision
    can cite a registered record design and still be unauthorable, because
    citing a design is not the same as that design covering the years the
    revision claims. Modelos 187, 188 and 194 each cite a design beginning in
    2022, 2023 or 2024 while claiming ejercicios from 2019: authoring a layout
    from those designs satisfied THIS gate and immediately put the same
    revisions on `test_layout_design_applies_to_claimed_years`, having replaced
    a refusal with an emitted record at unevidenced offsets.

    Their own review stamps had already recorded it -- "0 comparable bundled
    design year(s) inside this revision's claimed span" -- so the information
    was in the tree before the mistake and this classifier simply did not ask.
    """
    selector = revision.period_selector
    if selector.years:
        claimed = sorted(selector.years)
    elif selector.year_from is None:
        return []
    else:
        upper = selector.year_to if selector.year_to is not None else _OPEN_ENDED_HORIZON
        claimed = list(range(selector.year_from, upper + 1))

    windows: list[tuple[int | None, int | None]] = []
    for ref in cited:
        source = sources.get(ref)
        start = getattr(source, "applies_from", None)
        end = getattr(source, "applies_to", None)
        windows.append(
            (start.year if isinstance(start, date) else None, end.year if isinstance(end, date) else None),
        )
    return [
        year
        for year in claimed
        if not any((start is None or year >= start) and (end is None or year <= end) for start, end in windows)
    ]


def test_every_registry_revision_can_produce_a_filing_artifact() -> None:
    """Fail with the list of revisions that cannot emit, until that list is empty."""
    unable = _revisions_that_cannot_emit()

    assert not unable, (
        f"{len(unable)} registry revision(s) across "
        f"{len({modelo for modelo, _revision, _blocker in unable})} modelo(s) declare no export layout, so this "
        "application cannot file them. This is the capability worklist, not a defect to suppress: an AUTHORABLE "
        "GAP names its existing-plan owners, while each distinct TERMINAL refusal names the exact authority or "
        "product-scope condition that must change before an export task exists.\n"
        + "\n".join(
            f"  modelo {modelo} revision {revision}: no export layout -- {blocker.report()}"
            for modelo, revision, blocker in unable
        )
    )


def test_loaded_worklist_keeps_terminal_and_generic_owner_dispositions_distinct() -> None:
    """Terminal refusals have no owner; authorable gaps retain real owner domains."""
    unable = _revisions_that_cannot_emit()
    allowed_owners = {_TEMPORAL_OWNER, _SOURCE_CASILLA_OWNER, _EXPORT_OWNER}

    for modelo, revision, blocker in unable:
        if blocker.disposition in {"terminal_no_authority", "terminal_product_scope"}:
            assert blocker.owners == ()
            continue
        assert len(blocker.owners) == len(set(blocker.owners)), (
            f"{modelo}/{revision} repeats a generic ownership domain"
        )
        assert set(blocker.owners) <= allowed_owners

    by_revision = {(modelo, revision): blocker for modelo, revision, blocker in unable}
    modelo_185 = by_revision[(Modelo.M185.value, "2003-2025")]
    assert modelo_185.owners == _M185_OWNERS
    assert "Annex-I authority" in modelo_185.finding


def test_worklist_keeps_distinct_terminal_refusals_separate_from_owner_routed_gaps() -> None:
    """M136 authority and M036 product scope cannot become layout backlogs.

    The test reads the same compiler-loaded corpus as the expected-failing worklist.
    It is a regression over the report's *classification*, not a second list of
    missing layouts: new non-emitting rows remain visible without editing this
    test, and every authorable row must carry at least one canonical owner.
    """
    unable = _revisions_that_cannot_emit()
    by_revision = {(modelo, revision): blocker for modelo, revision, blocker in unable}

    modelo_136 = by_revision[(Modelo.M136.value, "2026")]
    assert modelo_136.disposition == "terminal_no_authority"
    assert modelo_136.owners == ()
    assert "No export layout is authorable now" in modelo_136.report()

    modelo_036 = by_revision[(Modelo.M036.value, "2025-02-03-y-siguientes")]
    assert modelo_036.disposition == "terminal_product_scope"
    assert modelo_036.owners == ()
    assert "TERMINAL PRODUCT-SCOPE" in modelo_036.report()
    assert "No M036 filing artifact is authorable now" in modelo_036.report()

    authorable = [blocker for blocker in by_revision.values() if blocker.disposition == "authorable_gap"]
    assert authorable, "the worklist no longer contains an owner-routed authorable gap to prove"
    assert all(blocker.owners for blocker in authorable)
    assert all("AUTHORABLE GAP" in blocker.report() for blocker in authorable)


def test_modelo_136_terminal_refusal_becomes_owner_routed_when_machine_authority_arrives() -> None:
    """MUTATION: a machine-readable M136 source invalidates the terminal label.

    A copied real source is changed from ``manual_pdf`` to ``xsd`` only at the
    classifier boundary. The expected transition proves that the terminal
    disposition is tied to the authority condition, rather than to the modelo
    identifier or a permanent hand-maintained exclusion.
    """
    modelos, catalogues = bundled_registry_tree()
    modelo = next(item for item in modelos if item.id == Modelo.M136)
    revision = modelo.revisions["2026"]
    source_id = "boe-modelo-136-current-form"
    upgraded = dict(catalogues.sources)
    upgraded[source_id] = upgraded[source_id].model_copy(update={"kind": "xsd"})

    assert _terminal_no_authority(modelo, revision, catalogues.sources) is not None
    assert _terminal_no_authority(modelo, revision, upgraded) is None
    blocker = _blocker(modelo, revision, upgraded)
    assert blocker.disposition == "authorable_gap"
    assert blocker.owners == (_EXPORT_OWNER,)


def test_modelo_036_product_scope_terminal_is_exact_to_the_reviewed_revision() -> None:
    """MUTATION: an adjacent identity cannot inherit M036's product boundary."""
    modelos, _catalogues = bundled_registry_tree()
    modelo_036 = next(item for item in modelos if item.id == Modelo.M036)
    reviewed_revision = modelo_036.revisions["2025-02-03-y-siguientes"]
    modelo_038 = next(item for item in modelos if item.id == Modelo.M038)
    other_revision = next(iter(modelo_038.revisions.values()))

    terminal = _terminal_product_scope(modelo_036, reviewed_revision)
    assert terminal is not None
    assert terminal.disposition == "terminal_product_scope"
    assert terminal.owners == ()

    wrong_revision = reviewed_revision.model_copy(update={"id": "2025-02-04-y-siguientes"})
    assert _terminal_product_scope(modelo_036, wrong_revision) is None
    assert _terminal_product_scope(modelo_038, other_revision) is None


def test_authorable_gap_rejects_an_unowned_domain() -> None:
    """MUTATION: a fourth, undeclared owner domain cannot enter the worklist."""
    with pytest.raises(ValueError, match="only an existing-plan owner domain"):
        _FilingCapabilityBlocker(
            disposition="authorable_gap",
            finding="mutation-only finding",
            reconsideration="mutation-only condition",
            owners=("unowned-owner-domain",),
        )
