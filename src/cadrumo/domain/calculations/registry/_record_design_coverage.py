"""Off-load-path record-design coverage and calculation-closure derivations.

:func:`calculation_closure_casilla_ids` and
:func:`calculation_closure_legal_refs` derive bounded closure projections from
a :class:`ModeloRevision`; :class:`DisenoCoverageReport` remains the advisory
full-Diseño inventory.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ....core import CasillaId
from ._bindings import binding_source_casilla_ids, binding_source_modelo
from ._casilla_membership import casillas_by_id
from ._errors import RegistryValidationError
from ._ids import LegalRefId, RevisionId
from ._record_design_schema import RecordDesignSheet
from ._runtime_graph import expression_casilla_refs
from ._schema import CasillaDefinition, DataBindingDefinition, ModeloRevision


def _extract_record_design(path: Path) -> tuple[RecordDesignSheet, ...]:
    """Return the sheets a design source yielded, ACCEPTING an incomplete read.

    This coverage derivation tolerates a partial extraction today, and that
    tolerance is written here rather than left implicit. It is not obviously
    right: a design whose record body was skipped produces a coverage report
    that understates the modelo, and nothing downstream can tell. It is
    preserved because tightening it to
    :meth:`~._record_design_schema.RecordDesignExtraction.require_complete`
    changes what the registry can load -- Modelo 232's ``TABLAS`` lookup tab is
    skipped legitimately and would begin refusing the whole modelo -- and that
    is a capability decision with its own blast radius, not a side effect of
    making partiality visible.

    Returns:
        The parsed sheets, complete or not.
    """
    from ._record_design import extract_record_design

    return extract_record_design(path).accept_partial()


# ---------------------------------------------------------------------------
# Calculation-completeness manifest derivation and Diseño extraction
# (off-load-path)
# ---------------------------------------------------------------------------
#
# The derivations below run off the snapshot-build hot path; they are
# called only by manifest-authoring scripts, the off-load-path coverage
# report, and the drift re-verification test.
#
# - ``calculation_closure_casilla_ids`` enumerates a revision's calculation
#   closure as canonical ``casilla.id`` values only. Reference tokens that do
#   not name a declared casilla id remain unresolved and fail the manifest
#   derivation instead of being reinterpreted as display metadata.
#
# - ``calculation_closure_record_design_metadata`` projects that canonical
#   closure through each closure casilla's own registry ``(segmento, number)``
#   metadata. This metadata is reviewed against Diseño where needed, while
#   the manifest row also carries the canonical ``casilla.id`` that consumers
#   resolve.
#
# - ``derive_calculation_completeness_casillas`` derives the
#   *calculation-completeness manifest* casilla set from that closure:
#   the modelo's calculation surface keyed on canonical ``casilla.id`` and
#   carrying the registry metadata each closure casilla declares. For a multi-segment modelo it optionally
#   verifies the derived record segments against the AEAT Diseño de
#   Registros. This is the set the load-blocking completeness gate
#   enforces.
#
# - ``derive_diseno_coverage_casillas`` extracts the *full* Diseño
#   casilla set — every five-digit casilla tag AEAT embeds in a field
#   description, accounting-statement data-entry fields included. It
#   parses the multi-megabyte Diseño corpus and is the input to the
#   off-load-path advisory coverage report that inventories form-level
#   data coverage; it is NOT a load-blocking gate.

_CASILLA_TAG_RE = re.compile(r"\[(\d{1,5})\]")
"""Matches the bracketed casilla tag AEAT embeds in Diseño field text.

The official AEAT Diseño de Registros workbooks annotate every casilla
field with its casilla number in square brackets within the field
description, validation or content text (e.g. ``Liquidación III - ... -
Base imponible [00552]``). This regex extracts those tags so a derivation
can enumerate the ``(segmento, number)`` casilla set.

**The tag width is NOT five digits across AEAT.** It was written as
``\\d{5}``, which is the Impuesto sobre Sociedades convention that Modelo
200 and Modelo 220 use. Every other modelo family brackets its box number
at its natural width -- Modelo 303 writes ``[01]`` and ``[150]``, Modelo
390 ``[01]``, Modelo 036 two and three digits. A fixed five-digit pattern
therefore matched nothing on them, and because a matchless sweep yields an
empty Diseño set rather than an error, the coverage report said
``0 casillas, 0 gap`` for 36 of the 38 revisions that bundle an official
record design. Reading as fully covered is the worst available failure for
an instrument whose whole job is to find what the registry has not
authored.

Widening it takes the population that extracts anything from 2 revisions
to 24. The remaining 14 annotate their casillas outside bracketed field
text entirely and are inventoried, not silently zeroed, by
:func:`build_diseno_coverage_report`.

Bounded at five digits rather than open-ended: an unbounded ``\\d+`` would
admit amounts, NIF fragments and position offsets that appear bracketed in
the same columns.
"""


@dataclass(frozen=True, slots=True)
class DerivedDisenoCasilla:
    """One casilla derived from a registry closure or AEAT Diseño workbook.

    ``segmento`` carries the AEAT record-segment code (the workbook sheet
    name) for multi-segment modelos and is ``None`` for single-segment
    modelos. ``number`` is the registry/display metadata under review.
    ``casilla_id`` is present only when the row came from a registry
    calculation closure; full-Diseño coverage rows may have no registry
    casilla yet and therefore leave it unset.
    """

    segmento: str | None
    number: str
    casilla_id: CasillaId | None = None


def _binding_is_cross_modelo(binding: DataBindingDefinition, modelo_id: str) -> bool:
    """Return whether a binding names a foreign source modelo.

    A binding is *cross-modelo* when its typed selector helper reports a
    ``source_modelo`` that is not the modelo whose closure is being derived.
    A binding with no source modelo, or one set to ``modelo_id``, is a
    *within-modelo* binding: its ``source_casilla_ids`` / ``source_casilla_id``
    name casillas on the modelo being derived, and those casillas belong in
    the modelo's own calculation closure.
    """
    source_modelo = binding_source_modelo(binding)
    if source_modelo is None:
        return False
    return source_modelo != modelo_id


def _visit_formula_closure_tokens(
    revision: ModeloRevision,
    visit_token: Callable[[CasillaId], None],
) -> None:
    for formula in revision.formulas:
        visit_token(formula.target_casilla_id)
        for ref in expression_casilla_refs(formula.expression):
            visit_token(ref)


def _visit_expectation_closure_tokens(
    revision: ModeloRevision,
    visit_token: Callable[[CasillaId], None],
) -> None:
    for expectation in revision.verification_expectations:
        for ref in expectation.computed_casilla_ids:
            visit_token(ref)
        for ref in expectation.reconciliation_total_casilla_ids.values():
            visit_token(ref)


def _visit_binding_closure_tokens(
    revision: ModeloRevision,
    modelo_id: str,
    visit_token: Callable[[CasillaId], None],
) -> None:
    for binding in revision.bindings:
        if _binding_is_cross_modelo(binding, modelo_id):
            continue
        for token in binding_source_casilla_ids(binding):
            visit_token(token)


def _visit_relation_closure_tokens(
    revision: ModeloRevision,
    modelo_id: str,
    visit_token: Callable[[CasillaId], None],
) -> None:
    for relation in revision.relations:
        if relation.source_modelo == modelo_id:
            visit_token(relation.source_casilla_id)


def _walk_calculation_closure(
    revision: ModeloRevision,
    modelo_id: str,
    *,
    visit_token: Callable[[CasillaId], None],
    visit_endpoint: Callable[[CasillaDefinition], None],
) -> None:
    """Walk the within-modelo calculation closure, dispatching each member.

    Shared by :func:`calculation_closure_casilla_ids` and
    :func:`calculation_closure_record_design_metadata`; ``visit_endpoint`` receives every
    formula/binding endpoint casilla and ``visit_token`` every referenced
    casilla token (formula targets, transitive expression refs,
    verification-expectation operands, and within-modelo binding/relation
    selectors).
    """
    for casilla in revision.casillas:
        if casilla.formula is not None or casilla.binding is not None:
            visit_endpoint(casilla)
    _visit_formula_closure_tokens(revision, visit_token)
    _visit_expectation_closure_tokens(revision, visit_token)
    _visit_binding_closure_tokens(revision, modelo_id, visit_token)
    _visit_relation_closure_tokens(revision, modelo_id, visit_token)


def calculation_closure_casilla_ids(revision: ModeloRevision, modelo_id: str) -> frozenset[CasillaId]:
    """Return canonical casilla ids in a revision's calculation closure.

    The *calculation closure* is the set of casillas the cross-connecting
    calculation engine traverses **within this modelo revision**:

    - every ``formula.target_casilla_id`` casilla;
    - every casilla referenced inside any ``formula.expression``, walked
      transitively via the runtime-graph ``expression_casilla_refs``
      walker;
    - every casilla that declares a ``formula`` (a computed endpoint) or
      a ``binding`` (a bound endpoint) — the engine-visible casillas;
    - every verification-expectation operand casilla
      (``computed_casilla_ids`` and the ``reconciliation_total_casilla_ids`` targets);
    - every *within-modelo* binding ``source_casilla_ids`` / ``source_casilla_id``
      selector casilla, and every *within-modelo*
      ``RelationDefinition.source_casilla_id``.

    A binding ``source_casilla_ids`` / ``source_casilla_id`` selector — and a
    ``RelationDefinition.source_casilla_id`` — is excluded from this closure
    **only when it is genuinely cross-modelo**: when the selector
    explicitly names a ``source_modelo`` that differs from ``modelo_id``.
    A cross-modelo selector's ``source_casilla_ids`` / ``source_casilla_id``
    name casillas on that *foreign* modelo, not on the modelo whose
    closure is being derived; the cross-modelo edge enters the current
    modelo through the *bound* casilla — the current-modelo casilla that
    declares the binding (or, for a relation, ``relation.target_binding``)
    — which is already counted above as a binding endpoint. Folding a
    foreign-modelo casilla id into this closure would make the
    completeness gate demand it from the wrong modelo's registry.

    A selector that omits ``source_modelo`` or sets it equal to
    ``modelo_id`` is a *within-modelo* selector: a ``previous_filing``
    self-binding or a ``previous_period`` self-relation names a casilla
    on the modelo being derived, so that casilla is a genuine closure
    member and is kept.

    References are not normalised through record-design metadata. A formula,
    binding, relation, or verification token must already be the canonical
    ``casilla.id`` for this revision. A reference token that matches no
    declared casilla id is kept verbatim so the manifest derivation and
    registry validation fail loudly on the unresolved canonical reference.

    Args:
        revision: The :class:`ModeloRevision` whose formula and binding graph
            is walked to derive the closure.
        modelo_id: The AEAT modelo identifier used to exclude cross-modelo
            selector casillas from the closure.
    """
    closure: set[CasillaId] = set()
    _walk_calculation_closure(
        revision,
        modelo_id,
        visit_token=closure.add,
        visit_endpoint=lambda casilla: closure.add(casilla.id),
    )
    return frozenset(closure)


def calculation_closure_record_design_metadata(
    revision: ModeloRevision,
    modelo_id: str,
) -> frozenset[tuple[str | None, str]]:
    """Return the ``(segmento, number)`` metadata in a revision's calculation closure.

    Metadata projection of :func:`calculation_closure_casilla_ids`. The
    canonical closure never resolves through ``casilla.number``; this function
    resolves each canonical id token to the declared casilla it names and keeps
    that casilla's ``(segmento, number)`` record-design metadata.

    Args:
        revision: The :class:`ModeloRevision` whose calculation closure to derive.
        modelo_id: Modelo identifier used to scope cross-modelo selectors;
            selectors whose ``source_modelo`` differs from ``modelo_id`` are
            excluded from the closure.

    The closure spans the same surface (formula targets, transitive
    formula-expression refs, formula/binding endpoint casillas,
    verification-expectation operands, and within-modelo binding /
    relation source casillas; only genuinely cross-modelo selectors —
    those whose ``source_modelo`` differs from ``modelo_id`` — are
    excluded, see :func:`calculation_closure_casilla_ids`). A reference token
    is resolved against the casilla ``id`` index only:

    - a token that matches a casilla ``id`` resolves to that exact
      casilla's metadata — this is how a multi-segment modelo's formulas,
      which reference casillas by the segment-carrying composite ``id``
      (e.g. ``DP200014:00562``), pin the closure to the correct record
      segment;
    - a token that resolves to no declared casilla is kept as a bare
      ``(None, token)`` metadata placeholder so a calculation that names a
      casilla the registry never declared still surfaces in the closure.

    The calculation-completeness manifest is keyed on canonical
    ``casilla.id`` and carries this metadata only for review and Diseño
    drift checks.
    """
    by_id = casillas_by_id(revision)
    metadata: set[tuple[str | None, str]] = set()

    def _resolve(token: CasillaId) -> None:
        casilla = by_id.get(token)
        if casilla is not None:
            metadata.add((casilla.segmento, casilla.number))
            return
        metadata.add((None, token))

    _walk_calculation_closure(
        revision,
        modelo_id,
        visit_token=_resolve,
        visit_endpoint=lambda casilla: metadata.add((casilla.segmento, casilla.number)),
    )
    return frozenset(metadata)


def calculation_closure_legal_refs(revision: ModeloRevision, modelo_id: str) -> frozenset[LegalRefId]:
    """Return legal references carried by a revision's calculation closure.

    Legal-ref projection of :func:`calculation_closure_casilla_ids`. The
    completeness manifest is the reviewed ledger for the calculation closure,
    so its own ``legal_refs`` must equal the refs carried by the closure
    casillas plus their endpoint formula/binding definitions and verification
    expectations.

    Unresolved closure tokens are skipped here because
    :func:`derive_calculation_completeness_casillas` and the manifest drift
    gate already surface missing required casillas explicitly.

    Args:
        revision: The :class:`ModeloRevision` whose calculation closure legal
            references are projected.
        modelo_id: Modelo identifier used to scope cross-modelo selectors.
    """
    declared_by_id = casillas_by_id(revision)
    formulas_by_id = {formula.id: formula for formula in revision.formulas}
    bindings_by_id = {binding.id: binding for binding in revision.bindings}
    legal_refs: set[LegalRefId] = set()

    for casilla_id in calculation_closure_casilla_ids(revision, modelo_id):
        casilla = declared_by_id.get(casilla_id)
        if casilla is None:
            continue
        legal_refs.update(casilla.legal_refs)
        if casilla.formula is not None:
            legal_refs.update(formulas_by_id[casilla.formula].legal_refs)
        if casilla.binding is not None:
            legal_refs.update(bindings_by_id[casilla.binding].legal_refs)
        for binding_id in casilla.alternate_bindings:
            legal_refs.update(bindings_by_id[binding_id].legal_refs)
    for expectation in revision.verification_expectations:
        legal_refs.update(expectation.legal_refs)
    return frozenset(legal_refs)


def derive_calculation_completeness_casillas(
    revision: ModeloRevision,
    modelo_id: str,
    *,
    multi_segment: bool,
    diseno_path: Path | None = None,
) -> tuple[DerivedDisenoCasilla, ...]:
    r"""Return the calculation-completeness manifest casilla set for a revision.

    Derives the modelo's *calculation closure*
    (:func:`calculation_closure_casilla_ids`) and carries each closure casilla's
    own registry ``(segmento, number)`` metadata. The closure
    bounds the manifest to exactly the casillas the cross-connecting
    calculation engine traverses; the registry's canonical ``casilla.id`` —
    not a five-digit AEAT Diseño tag — names each manifest entry.

    This derivation is *vocabulary-agnostic*. Only Modelo 200's registry
    casilla ``number``\\ s are genuine five-digit AEAT Diseño tags; the
    other calculation-bearing modelos identify casillas by semantic slug
    (``iva.cuota-devengada-total``) or short ordinal (``01``-``19``). The
    manifest is therefore derived from the modelo's calculation surface
    keyed on canonical ``casilla.id`` and carrying the registry metadata
    each closure casilla declares, so it can be authored for any
    calculation-bearing modelo regardless of its casilla vocabulary.

    App-internal casillas are excluded from the manifest for every modelo.
    They may participate in the calculation closure so formulas and
    verification predicates can consume them, but they do not identify an
    official filing slot and therefore cannot contribute to the manifest
    denominator.

    For a ``multi_segment`` modelo the result is *segment-aware*. A
    multi-segment modelo reuses the same casilla number across distinct
    record segments and its formulas reference casillas by the
    segment-carrying composite ``id``, so the metadata-preserving closure
    (:func:`calculation_closure_record_design_metadata`) already pins each closure
    casilla to the exact record segment the calculation surface uses.
    When ``diseno_path`` is supplied each segment-scoped metadata pair is
    additionally **verified against the AEAT Diseño de Registros**: the
    Diseño remains authoritative on which record segment carries a
    number, and a pinned ``(segmento, number)`` absent from the Diseño is
    a derivation error.

    For a single-segment modelo ``segmento`` is left unset and the
    closure casilla's registry ``number`` alone carries the reviewed metadata; no Diseño
    is required because a single-segment modelo's metadata is unambiguous
    without one.

    A closure reference that resolves to no declared casilla is omitted
    from the derived set — the calculation-completeness gate then fires
    on the missing required casilla when it compares the manifest to the
    declared casillas, which is the gate fulfilling its mission. The
    drift / coverage tests surface such gaps explicitly.

    This is an off-load-path tool. When ``diseno_path`` is supplied it
    parses the multi-megabyte Diseño corpus and must never run on the
    snapshot-build path.

    Args:
        revision: The :class:`ModeloRevision` whose calculation closure to derive into a manifest.
        modelo_id: Modelo identifier; cross-modelo selectors whose
            ``source_modelo`` differs from ``modelo_id`` are excluded from
            the closure.
        multi_segment: When True, the manifest is segment-aware and a casilla
            number repeated across distinct segments produces distinct manifest
            rows; when False, segment metadata is dropped from the manifest key.
        diseno_path: Optional path to an AEAT Diseño workbook used to
            cross-check that every derived manifest casilla also appears on
            the published record design.

    Returns:
        Tuple of :class:`DerivedDisenoCasilla` representing the calculation-completeness manifest.
    """
    declared_by_id = casillas_by_id(revision)

    diseno_pairs: frozenset[tuple[str, str]] | None = None
    if diseno_path is not None:
        diseno_pairs = frozenset(
            (sheet.name, number)
            for sheet in _extract_record_design(diseno_path)
            for number in _sheet_record_numbers(sheet)
        )

    ordered: list[DerivedDisenoCasilla] = []
    for casilla_id in sorted(calculation_closure_casilla_ids(revision, modelo_id)):
        casilla = declared_by_id.get(casilla_id)
        if casilla is None:
            raise RegistryValidationError(
                f"calculation-completeness derivation: closure reference {casilla_id!r} "
                "is not a declared canonical casilla.id",
            )
        segmento = casilla.segmento
        number = casilla.number
        if casilla.internal_only:
            # App-internal computed casilla intentionally absent from the
            # AEAT-published structure (e.g. a regulatory ceiling materialised
            # so verification predicates can bound an operator-elective
            # amount). The schema validator guarantees it carries no
            # export_refs and is formula-derived; it is not an AEAT box, so it
            # never appears in the completeness manifest, regardless of whether
            # the modelo is single- or multi-segment.
            continue
        if not multi_segment:
            ordered.append(DerivedDisenoCasilla(segmento=None, number=number, casilla_id=casilla.id))
            continue
        # An EMPTY pair set is no evidence, not evidence of absence. The pairs are
        # built from the bracketed casilla tags a design prints, and a PDF design
        # may print none at all: modelo 184's yields zero tags across all three of
        # its sheets, so every declared casilla would refuse here for a reason the
        # design never stated. Refusing from an empty set asserts absence out of
        # ignorance, which is the same shape as a gate whose matcher cannot see
        # the construct it governs. `None` already means "no design supplied";
        # empty now joins it as "design supplied, said nothing on this axis".
        #
        # This does not soften the check where it has teeth: a design that prints
        # tags for any sheet yields a non-empty set, and a casilla declared under
        # a segment that set does not carry still refuses.
        # A segmento NAMES a design sheet, and designs differ in whether the name
        # carries a trailing description. Modelo 200's segmentos are exact sheet
        # names ("DP200012"); modelo 714's are the sheet's leading code, where the
        # design writes "714-10 Patrimonio". Both identify one sheet, so the match
        # admits an exact name or that name followed by a space. It stays a
        # prefix-to-WORD-boundary comparison rather than a bare startswith, so
        # "714-1" cannot claim "714-10 Patrimonio".
        matched = any(
            number == pair_number and (segmento == sheet_name or sheet_name.startswith(f"{segmento} "))
            for sheet_name, pair_number in diseno_pairs
        )
        if diseno_pairs and segmento is not None and not matched:
            raise RegistryValidationError(
                f"calculation-completeness derivation: casilla {number!r} is "
                f"declared under segmento {segmento!r} but the AEAT Diseño de "
                "Registros does not carry it under that segment",
            )
        ordered.append(DerivedDisenoCasilla(segmento=segmento, number=number, casilla_id=casilla.id))
    return tuple(ordered)


def derive_diseno_coverage_casillas(
    path: Path,
    *,
    multi_segment: bool,
) -> tuple[DerivedDisenoCasilla, ...]:
    """Return :class:`DerivedDisenoCasilla` items for the full casilla set declared by a Diseño.

    Runs read-only record-design extraction against the official AEAT
    Diseño de Registros source at ``path`` and collects *every*
    five-digit casilla tag embedded in the field descriptions, including
    the accounting-statement data-entry fields that feed no calculation.

    This is the input to the off-load-path advisory coverage report that
    inventories form-level data coverage. It is intentionally NOT a
    load-blocking gate: a modelo whose registry is not yet exhaustively
    backfilled against the full Diseño is reported as having a coverage
    gap, not failed at load. The load-blocking gate is keyed on the
    bounded calculation closure
    (:func:`derive_calculation_completeness_casillas`) instead.

    For a ``multi_segment`` modelo (e.g. Modelo 200, which reuses the
    same casilla number across distinct record segments) every casilla
    carries the workbook sheet name as its ``segmento``, so the same
    number under two segments yields two distinct metadata pairs. For a
    single-segment modelo ``segmento`` is left unset and the bare number
    alone identifies the casilla; a number that recurs across sheets of a
    single-segment Diseño collapses to one metadata pair, matching the
    bare-number registry behaviour.

    This is an off-load-path tool: it parses the multi-megabyte Diseño
    corpus and must never run on the snapshot-build path.
    """
    return _derive_diseno_coverage_casillas_from_sheets(
        _extract_record_design(path),
        multi_segment=multi_segment,
    )


def _derive_diseno_coverage_casillas_from_sheets(
    sheets: tuple[RecordDesignSheet, ...],
    *,
    multi_segment: bool,
) -> tuple[DerivedDisenoCasilla, ...]:
    """Derive the casilla set from ALREADY-EXTRACTED sheets.

    Split out so a caller that needs both the casillas and facts about the
    extraction itself parses the multi-megabyte source once instead of twice.
    """
    if multi_segment:
        seen: set[tuple[str | None, str]] = set()
        ordered: list[DerivedDisenoCasilla] = []
        for sheet in sheets:
            for number in _sheet_record_numbers(sheet):
                metadata_pair = (sheet.name, number)
                if metadata_pair in seen:
                    continue
                seen.add(metadata_pair)
                ordered.append(DerivedDisenoCasilla(segmento=sheet.name, number=number))
        return tuple(ordered)
    seen_numbers: set[str] = set()
    bare: list[DerivedDisenoCasilla] = []
    for sheet in sheets:
        for number in _sheet_record_numbers(sheet):
            if number in seen_numbers:
                continue
            seen_numbers.add(number)
            bare.append(DerivedDisenoCasilla(segmento=None, number=number))
    return tuple(bare)


@dataclass(frozen=True)
class DisenoCoverageReport:
    """An off-load-path advisory inventory of one revision's Diseño coverage.

    Compares a modelo revision's declared casillas against the *full*
    AEAT Diseño de Registros casilla set — every five-digit casilla tag
    AEAT embeds in the form's field descriptions, accounting-statement
    data-entry fields included.

    This report is **advisory**: it is produced off the snapshot-build
    load path and never reds a load. A modelo whose registry is not yet
    exhaustively backfilled against the full Diseño is reported here as
    having a coverage gap, surfaced as information for follow-up
    authoring. The load-blocking gate is the bounded
    calculation-completeness gate, not this full-Diseño inventory — that
    Calculation-completeness is enforced at load; full-Diseño coverage is
    inventoried off-load-path as an advisory follow-up surface.

    Fields:

    - ``modelo_id`` / ``revision_id`` identify the revision inventoried.
    - ``diseno_casillas`` is the full ``(segmento, number)`` set the
      Diseño declares.
    - ``covered_casillas`` is the subset the registry also declares —
      the Diseño casillas the registry has backfilled.
    - ``coverage_gap_casillas`` is the subset the Diseño declares that
      the registry does not — the advisory follow-up inventory.

    ``extraction_found_no_casillas`` separates the two states that
    otherwise present identically. A revision whose registry covers the
    whole form reports an empty gap; so does a revision whose Diseño could
    not be read at all, because an unread source yields an empty set and
    every count derived from it is zero. Only the first is good news, and
    for 36 of 38 revisions it was the second one being reported. Consult
    this flag before treating an empty gap as coverage.
    """

    modelo_id: str
    revision_id: RevisionId
    diseno_casillas: tuple[DerivedDisenoCasilla, ...]
    covered_casillas: tuple[DerivedDisenoCasilla, ...]
    coverage_gap_casillas: tuple[DerivedDisenoCasilla, ...]
    extracted_fields: int = 0
    described_fields: int = 0

    @property
    def descriptions_unavailable(self) -> bool:
        """Whether the source yielded fields but no readable field descriptions.

        Casilla tags are recognised only inside field DESCRIPTIONS, so a
        design parsed from chart geometry alone -- every field carrying the
        visual-chart type code and a placeholder in place of prose -- can
        never yield a casilla however many boxes the form prints. Its empty
        set is an artefact of what could be read, not a statement about the
        form.

        :attr:`extraction_found_no_casillas` tells a reader to "distinguish
        the two by whether the source yielded fields at all", and until this
        field existed the report carried no count with which to do it. Modelo
        038 is the worked case: 58 fields extracted, 58 of them
        description-less, zero casillas -- indistinguishable in the old
        report from modelo 185, whose 35 fields carry 8283 characters of real
        description and genuinely number nothing.
        """
        return self.extracted_fields > 0 and self.described_fields == 0

    @property
    def extraction_found_no_casillas(self) -> bool:
        """Whether the Diseño source yielded no casillas at all.

        ``True`` means this report carries no information about coverage:
        the source was parsed but no casilla tag was recognised in it, so
        the registry was compared against nothing. Either way the counts
        below are not evidence of coverage.

        It does NOT mean extraction failed. **Correcting an earlier claim
        made here:** this docstring asserted that an official AEAT record
        design always declares casillas, so an empty set had to be an
        extraction limitation. That is false. The 16 revisions in this
        state are informative declarations -- 111, 115, 180, 184, 190,
        193, 232, 347, 349, 360, 369 and 720 -- whose Diseño describes
        positional records with NAMED fields (``TIPO DE REGISTRO``,
        ``NIF DEL DECLARANTE``) and no numbered boxes at all. Measured:
        zero bracketed numbers across all 16, at any digit width. For
        them an empty casilla set is the correct answer, not a failure,
        and casilla-number coverage is simply not the applicable measure
        -- field coverage against the record layout would be.

        So read this flag as "casilla coverage does not apply or could
        not be computed", and distinguish the two by whether the source
        yielded fields at all. Do not read it as a defect to be fixed by
        widening extraction.
        """
        return not self.diseno_casillas

    @property
    def diseno_casilla_count(self) -> int:
        """Total ``(segmento, number)`` casillas the Diseño declares."""
        return len(self.diseno_casillas)

    @property
    def covered_count(self) -> int:
        """Diseño casillas the registry also declares."""
        return len(self.covered_casillas)

    @property
    def coverage_gap_count(self) -> int:
        """Diseño casillas the registry does not yet declare."""
        return len(self.coverage_gap_casillas)


def build_diseno_coverage_report(
    path: Path,
    modelo_id: str,
    revision: ModeloRevision,
    *,
    multi_segment: bool,
) -> DisenoCoverageReport:
    """Return the off-load-path full-Diseño coverage advisory report for a revision.

    Extracts the full AEAT Diseño de Registros casilla set
    (:func:`derive_diseno_coverage_casillas`) and compares it against the
    revision's declared casillas, keyed on the ``(segmento, number)``
    metadata. The result is a :class:`DisenoCoverageReport` that
    inventories how much of the form's data surface the registry covers
    and which Diseño casillas remain to be authored.

    This is an **advisory** inventory, never a load gate. It is produced
    off the snapshot-build path — it parses the multi-megabyte Diseño
    corpus — and must never run on the load path. A coverage gap reported
    here does not fail any modelo: the load-blocking enforcement is the
    bounded calculation-completeness gate; calculation-completeness is
    enforced at load while full-Diseño coverage is inventoried
    off-load-path.

    The registry side keys on ``form_number`` where a casilla declares
    one, falling back to ``number``. Both fields carry a box number, and
    which one holds it is not uniform: a casilla whose ``id`` is a domain
    name rather than a box number tends to repeat that id in ``number``
    and record the official box in ``form_number``. Modelo 303's
    ``iva.resultado-regimen-general`` is the worked example -- it IS box
    46, exports to box 46, and was reported as an unauthored Diseño
    casilla purely because the comparison read ``number`` and found the id
    there.

    This rescues only the casillas that record their box number somewhere.
    A casilla whose ``number`` repeats its id and which declares no
    ``form_number`` records the official box number nowhere, so nothing
    can match it to the form; those remain in the coverage gap, which is
    the honest report of their state.

    For a ``multi_segment`` modelo the comparison is segment-aware: a
    Diseño casilla under segment ``S`` is "covered" only when the
    registry declares a casilla with the same ``(S, number)`` metadata. For
    a single-segment modelo ``segmento`` is unset on both sides and the
    bare number alone identifies the casilla.

    Args:
        path: Path to the official AEAT Diseño de Registros source file.
        modelo_id: The AEAT modelo identifier for the coverage report.
        revision: The :class:`ModeloRevision` whose declared casillas are
            compared against the extracted Diseño casilla set.
        multi_segment: Whether the modelo uses segment-qualified casilla ids.
    """
    sheets = _extract_record_design(path)
    diseno = _derive_diseno_coverage_casillas_from_sheets(sheets, multi_segment=multi_segment)
    declared_metadata = {(casilla.segmento, casilla.form_number or casilla.number) for casilla in revision.casillas}
    covered: list[DerivedDisenoCasilla] = []
    gap: list[DerivedDisenoCasilla] = []
    for casilla in diseno:
        if (casilla.segmento, casilla.number) in declared_metadata:
            covered.append(casilla)
        else:
            gap.append(casilla)
    # Counted from the same source the casillas were derived from, so an empty
    # casilla set can be read as "nothing to scan" or "scanned, none present".
    # The geometry-only marker is read from the extractor that stamps it, never
    # copied: a second literal would silently stop matching if the extractor
    # changed it, and `descriptions_unavailable` would quietly go false for every
    # design instead of failing.
    from ._record_design import _VISUAL_CHART_TYPE_CODE

    extracted_fields = sum(len(sheet.fields) for sheet in sheets)
    described_fields = sum(
        1
        for sheet in sheets
        for design_field in sheet.fields
        if design_field.type_code != _VISUAL_CHART_TYPE_CODE
    )
    return DisenoCoverageReport(
        modelo_id=modelo_id,
        revision_id=revision.id,
        diseno_casillas=diseno,
        covered_casillas=tuple(covered),
        coverage_gap_casillas=tuple(gap),
        extracted_fields=extracted_fields,
        described_fields=described_fields,
    )


def _sheet_record_numbers(sheet: RecordDesignSheet) -> tuple[str, ...]:
    """Return the official record-design numeric tags declared in one sheet, in field order."""
    numbers: list[str] = []
    seen: set[str] = set()
    for design_field in sheet.fields:
        for text in (design_field.description, design_field.validation, design_field.content):
            if not text:
                continue
            for match in _CASILLA_TAG_RE.finditer(text):
                number = match.group(1)
                if number in seen:
                    continue
                seen.add(number)
                numbers.append(number)
    return tuple(numbers)


__all__ = [
    "DerivedDisenoCasilla",
    "DisenoCoverageReport",
    "build_diseno_coverage_report",
    "calculation_closure_casilla_ids",
    "calculation_closure_legal_refs",
    "calculation_closure_record_design_metadata",
    "derive_calculation_completeness_casillas",
    "derive_diseno_coverage_casillas",
]
