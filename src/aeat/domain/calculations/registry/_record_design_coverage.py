"""Off-load-path record-design coverage and calculation-closure derivations."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

from ._errors import RegistryValidationError
from ._record_design_schema import RecordDesignSheet
from ._runtime_graph import expression_casilla_refs
from ._schema import CasillaDefinition, DataBindingDefinition, ModeloRevision


def _extract_record_design(path: Path) -> tuple[RecordDesignSheet, ...]:
    from ._record_design import extract_record_design

    return extract_record_design(path)


# ---------------------------------------------------------------------------
# Calculation-completeness manifest derivation and Diseño extraction
# (off-load-path)
# ---------------------------------------------------------------------------
#
# The derivations below run off the snapshot-build hot path; they are
# called only by manifest-authoring scripts, the off-load-path coverage
# report, and the drift re-verification test.
#
# - ``calculation_closure_identities`` enumerates a revision's
#   calculation closure keyed on each closure casilla's own registry
#   ``(segmento, number)`` identity. It is vocabulary-agnostic: it works
#   for Modelo 200's five-digit AEAT Diseño tags and equally for the
#   semantic-slug and short-ordinal casilla numbers the other
#   calculation-bearing modelos use.
#
# - ``derive_calculation_completeness_casillas`` derives the
#   *calculation-completeness manifest* casilla set from that closure:
#   the modelo's calculation surface keyed on the registry identity each
#   closure casilla declares. For a multi-segment modelo it optionally
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

_CASILLA_TAG_RE = re.compile(r"\[(\d{5})\]")
"""Matches the five-digit casilla tag AEAT embeds in Diseño field text.

The official AEAT Diseño de Registros workbooks annotate every casilla
field with its five-digit casilla number in square brackets within the
field description (e.g. ``Liquidación III - ... - Base imponible
[00552]``). This regex extracts those tags so a derivation can enumerate
the ``(segmento, number)`` casilla set.
"""


@dataclass(frozen=True)
class DerivedDisenoCasilla:
    """One ``(segmento, number)`` casilla derived from an AEAT Diseño workbook.

    ``segmento`` carries the AEAT record-segment code (the workbook sheet
    name) for multi-segment modelos and is ``None`` for single-segment
    modelos. ``number`` is the bare five-digit AEAT casilla number.
    """

    segmento: str | None
    number: str


def _selector_is_cross_modelo(selector: Mapping[str, object], modelo_id: str) -> bool:
    """Return whether a binding / relation selector names a foreign modelo.

    A binding ``selector`` (or a relation's ``source_modelo``) is
    *cross-modelo* when it explicitly names a ``source_modelo`` that is
    not the modelo whose closure is being derived. A selector that omits
    ``source_modelo``, or sets it equal to ``modelo_id``, is a
    *within-modelo* selector: its ``source_casillas`` / ``source_output``
    name casillas on the modelo being derived (a ``previous_filing``
    self-binding or a ``previous_period`` self-relation), and those
    casillas belong in the modelo's own calculation closure.
    """
    source_modelo = selector.get("source_modelo")
    if source_modelo is None:
        return False
    return str(source_modelo) != modelo_id


def _binding_selector_tokens(binding: DataBindingDefinition) -> Iterator[str]:
    source_casillas = binding.selector.get("source_casillas")
    if isinstance(source_casillas, tuple):
        for token in source_casillas:
            if isinstance(token, str):
                yield token
    source_output = binding.selector.get("source_output")
    if isinstance(source_output, str):
        yield source_output


def _walk_calculation_closure(
    revision: ModeloRevision,
    modelo_id: str,
    *,
    visit_token: Callable[[str], None],
    visit_endpoint: Callable[[CasillaDefinition], None],
) -> None:
    """Walk the within-modelo calculation closure, dispatching each member.

    Shared by :func:`calculation_closure_numbers` and
    :func:`calculation_closure_identities`; ``visit_endpoint`` receives every
    formula/binding endpoint casilla and ``visit_token`` every referenced
    casilla token (formula targets, transitive expression refs,
    verification-expectation operands, and within-modelo binding/relation
    selectors).
    """
    for casilla in revision.casillas:
        if casilla.formula is not None or casilla.binding is not None:
            visit_endpoint(casilla)
    for formula in revision.formulas:
        visit_token(formula.target)
        for ref in expression_casilla_refs(formula.expression):
            visit_token(ref)
    for expectation in revision.verification_expectations:
        for ref in expectation.computed_casillas:
            visit_token(ref)
        for ref in expectation.reconciliation_totals.values():
            visit_token(ref)
    for binding in revision.bindings:
        if _selector_is_cross_modelo(binding.selector, modelo_id):
            continue
        for token in _binding_selector_tokens(binding):
            visit_token(token)
    for relation in revision.relations:
        if relation.source_modelo == modelo_id:
            visit_token(relation.source_output)


def calculation_closure_numbers(revision: ModeloRevision, modelo_id: str) -> frozenset[str]:
    """Return the bare casilla numbers in a revision's calculation closure.

    The *calculation closure* is the set of casillas the cross-connecting
    calculation engine traverses **within this modelo revision**:

    - every ``formula.target`` casilla;
    - every casilla referenced inside any ``formula.expression``, walked
      transitively via the runtime-graph ``expression_casilla_refs``
      walker;
    - every casilla that declares a ``formula`` (a computed endpoint) or
      a ``binding`` (a bound endpoint) — the engine-visible casillas;
    - every verification-expectation operand casilla
      (``computed_casillas`` and the ``reconciliation_totals`` targets);
    - every *within-modelo* binding ``source_casillas`` / ``source_output``
      selector casilla, and every *within-modelo*
      ``RelationDefinition.source_output``.

    A binding ``source_casillas`` / ``source_output`` selector — and a
    ``RelationDefinition.source_output`` — is excluded from this closure
    **only when it is genuinely cross-modelo**: when the selector
    explicitly names a ``source_modelo`` that differs from ``modelo_id``.
    A cross-modelo selector's ``source_casillas`` / ``source_output``
    name casillas on that *foreign* modelo, not on the modelo whose
    closure is being derived; the cross-modelo edge enters the current
    modelo through the *bound* casilla — the current-modelo casilla that
    declares the binding (or, for a relation, ``relation.target_binding``)
    — which is already counted above as a binding endpoint. Folding a
    foreign-modelo casilla number into this closure would make the
    completeness gate demand it from the wrong modelo's registry.

    A selector that omits ``source_modelo`` or sets it equal to
    ``modelo_id`` is a *within-modelo* selector: a ``previous_filing``
    self-binding or a ``previous_period`` self-relation names a casilla
    on the modelo being derived, so that casilla is a genuine closure
    member and is kept.

    References are reduced to bare casilla numbers: a reference token may
    be either a casilla ``id`` or a bare ``number``, and a declared
    casilla's ``id`` is mapped back to its ``number`` so the closure is
    expressed in the AEAT bare-number vocabulary the Diseño uses. A
    reference token that matches no declared casilla is kept verbatim so
    a calculation that names a casilla the registry never declared — the
    Modelo 200 defect class — still surfaces in the closure.

    Args:
        revision: The :class:`ModeloRevision` whose formula and binding graph
            is walked to derive the closure.
        modelo_id: The AEAT modelo identifier used to exclude cross-modelo
            selector casillas from the closure.
    """
    id_to_number = {casilla.id: casilla.number for casilla in revision.casillas}
    closure: set[str] = set()
    _walk_calculation_closure(
        revision,
        modelo_id,
        visit_token=lambda token: closure.add(id_to_number.get(token, token)),
        visit_endpoint=lambda casilla: closure.add(casilla.number),
    )
    return frozenset(closure)


def calculation_closure_identities(revision: ModeloRevision, modelo_id: str) -> frozenset[tuple[str | None, str]]:
    """Return the ``(segmento, number)`` identities in a revision's calculation closure.

    Identity-preserving counterpart of :func:`calculation_closure_numbers`.
    Where the bare-number closure reduces every reference to its casilla
    ``number`` — which discards the record segment a multi-segment modelo
    needs — this function resolves each reference token to the *declared
    casilla* it names and keeps that casilla's full
    ``(segmento, number)`` identity.

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
    excluded, see :func:`calculation_closure_numbers`). A reference token
    is resolved against both the casilla ``id`` index and the casilla
    ``number`` index:

    - a token that matches a casilla ``id`` resolves to that exact
      casilla's identity — this is how a multi-segment modelo's formulas,
      which reference casillas by the segment-carrying composite ``id``
      (e.g. ``DP200014:00562``), pin the closure to the correct record
      segment;
    - a token that matches a casilla ``number`` resolves to every
      casilla declared under that number (one for a single-segment
      modelo; possibly several for a multi-segment modelo that reuses the
      number across segments);
    - a token that resolves to no declared casilla is kept as a bare
      ``(None, token)`` identity so a calculation that names a casilla
      the registry never declared still surfaces in the closure.

    This is the identity vocabulary the calculation-completeness manifest
    is keyed on, and it is vocabulary-agnostic: it works for the
    five-digit AEAT Diseño tags of Modelo 200 and equally for the
    semantic-slug and short-ordinal casilla numbers the other
    calculation-bearing modelos use.
    """
    by_id = {casilla.id: casilla for casilla in revision.casillas}
    by_number: dict[str, list[CasillaDefinition]] = {}
    for casilla in revision.casillas:
        by_number.setdefault(casilla.number, []).append(casilla)

    identities: set[tuple[str | None, str]] = set()

    def _resolve(token: str) -> None:
        casilla = by_id.get(token)
        if casilla is not None:
            identities.add((casilla.segmento, casilla.number))
            return
        declared = by_number.get(token)
        if declared:
            for occurrence in declared:
                identities.add((occurrence.segmento, occurrence.number))
            return
        identities.add((None, token))

    _walk_calculation_closure(
        revision,
        modelo_id,
        visit_token=_resolve,
        visit_endpoint=lambda casilla: identities.add((casilla.segmento, casilla.number)),
    )
    return frozenset(identities)


def derive_calculation_completeness_casillas(
    revision: ModeloRevision,
    modelo_id: str,
    *,
    multi_segment: bool,
    diseno_path: Path | None = None,
) -> tuple[DerivedDisenoCasilla, ...]:
    r"""Return the calculation-completeness manifest casilla set for a revision.

    Derives the modelo's *calculation closure*
    (:func:`calculation_closure_numbers`) and keys each closure casilla
    on its **own registry ``(segmento, number)`` identity**. The closure
    bounds the manifest to exactly the casillas the cross-connecting
    calculation engine traverses; the registry's own declared identity —
    not a five-digit AEAT Diseño tag — names each casilla.

    This derivation is *vocabulary-agnostic*. Only Modelo 200's registry
    casilla ``number``\\ s are genuine five-digit AEAT Diseño tags; the
    other calculation-bearing modelos identify casillas by semantic slug
    (``iva.cuota-devengada-total``) or short ordinal (``01``-``19``). The
    manifest is therefore derived from the modelo's calculation surface
    keyed on the registry identity each closure casilla declares, so a
    manifest can be authored for any calculation-bearing modelo
    regardless of its casilla vocabulary.

    For a ``multi_segment`` modelo the result is *segment-aware*. A
    multi-segment modelo reuses the same casilla number across distinct
    record segments and its formulas reference casillas by the
    segment-carrying composite ``id``, so the identity-preserving closure
    (:func:`calculation_closure_identities`) already pins each closure
    casilla to the exact record segment the calculation surface uses.
    When ``diseno_path`` is supplied each segment-scoped identity is
    additionally **verified against the AEAT Diseño de Registros**: the
    Diseño remains authoritative on which record segment carries a
    number, and a pinned ``(segmento, number)`` absent from the Diseño is
    a derivation error.

    For a single-segment modelo ``segmento`` is left unset and the
    closure casilla's registry ``number`` alone identifies it; no Diseño
    is required because a single-segment modelo's identity is unambiguous
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
    declared_identities = {(casilla.segmento, casilla.number) for casilla in revision.casillas}
    internal_only_identities = frozenset(
        (casilla.segmento, casilla.number) for casilla in revision.casillas if casilla.internal_only
    )

    diseno_pairs: frozenset[tuple[str, str]] | None = None
    if diseno_path is not None:
        diseno_pairs = frozenset(
            (sheet.name, number)
            for sheet in _extract_record_design(diseno_path)
            for number in _sheet_casilla_numbers(sheet)
        )

    ordered: list[DerivedDisenoCasilla] = []
    for segmento, number in sorted(
        calculation_closure_identities(revision, modelo_id),
        key=lambda item: (item[0] or "", item[1]),
    ):
        if (segmento, number) not in declared_identities:
            # The closure references a casilla the registry never
            # declares at this identity. It is omitted here; the
            # completeness gate fires on the omission instead.
            continue
        if not multi_segment:
            if (segmento, number) in internal_only_identities:
                # App-internal computed casilla intentionally absent from the
                # AEAT-published structure (e.g. a regulatory ceiling materialised
                # so verification predicates can bound an operator-elective
                # amount). The schema validator guarantees it carries no
                # export_refs and is formula-derived; it is not an AEAT box, so it
                # never appears in the completeness manifest.
                continue
            ordered.append(DerivedDisenoCasilla(segmento=None, number=number))
            continue
        if (segmento, number) in internal_only_identities:
            # App-internal computed casilla intentionally absent from the
            # AEAT-published Diseño de Registros (e.g. a regulatory
            # ceiling materialised so verification predicates can bound
            # an operator-elective amount). The schema validator
            # guarantees such a casilla carries no export_refs and is
            # formula-derived; the Diseño-presence check is skipped while
            # the segment-carrying identity is preserved for downstream
            # manifest consumers.
            ordered.append(DerivedDisenoCasilla(segmento=segmento, number=number))
            continue
        if diseno_pairs is not None and segmento is not None and (segmento, number) not in diseno_pairs:
            raise RegistryValidationError(
                f"calculation-completeness derivation: casilla {number!r} is "
                f"declared under segmento {segmento!r} but the AEAT Diseño de "
                "Registros does not carry it under that segment",
            )
        ordered.append(DerivedDisenoCasilla(segmento=segmento, number=number))
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
    number under two segments yields two distinct identity pairs. For a
    single-segment modelo ``segmento`` is left unset and the bare number
    alone identifies the casilla; a number that recurs across sheets of a
    single-segment Diseño collapses to one identity, matching the
    bare-number registry behaviour.

    This is an off-load-path tool: it parses the multi-megabyte Diseño
    corpus and must never run on the snapshot-build path.
    """
    sheets = _extract_record_design(path)
    if multi_segment:
        seen: set[tuple[str | None, str]] = set()
        ordered: list[DerivedDisenoCasilla] = []
        for sheet in sheets:
            for number in _sheet_casilla_numbers(sheet):
                identity = (sheet.name, number)
                if identity in seen:
                    continue
                seen.add(identity)
                ordered.append(DerivedDisenoCasilla(segmento=sheet.name, number=number))
        return tuple(ordered)
    seen_numbers: set[str] = set()
    bare: list[DerivedDisenoCasilla] = []
    for sheet in sheets:
        for number in _sheet_casilla_numbers(sheet):
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
    """

    modelo_id: str
    revision_id: str
    diseno_casillas: tuple[DerivedDisenoCasilla, ...]
    covered_casillas: tuple[DerivedDisenoCasilla, ...]
    coverage_gap_casillas: tuple[DerivedDisenoCasilla, ...]

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
    identity. The result is a :class:`DisenoCoverageReport` that
    inventories how much of the form's data surface the registry covers
    and which Diseño casillas remain to be authored.

    This is an **advisory** inventory, never a load gate. It is produced
    off the snapshot-build path — it parses the multi-megabyte Diseño
    corpus — and must never run on the load path. A coverage gap reported
    here does not fail any modelo: the load-blocking enforcement is the
    bounded calculation-completeness gate; calculation-completeness is
    enforced at load while full-Diseño coverage is inventoried
    off-load-path.

    For a ``multi_segment`` modelo the comparison is segment-aware: a
    Diseño casilla under segment ``S`` is "covered" only when the
    registry declares a casilla at the same ``(S, number)`` identity. For
    a single-segment modelo ``segmento`` is unset on both sides and the
    bare number alone identifies the casilla.

    Args:
        path: Path to the official AEAT Diseño de Registros source file.
        modelo_id: The AEAT modelo identifier for the coverage report.
        revision: The :class:`ModeloRevision` whose declared casillas are
            compared against the extracted Diseño casilla set.
        multi_segment: Whether the modelo uses segment-qualified casilla ids.
    """
    diseno = derive_diseno_coverage_casillas(path, multi_segment=multi_segment)
    declared_identities = {(casilla.segmento, casilla.number) for casilla in revision.casillas}
    covered: list[DerivedDisenoCasilla] = []
    gap: list[DerivedDisenoCasilla] = []
    for casilla in diseno:
        if (casilla.segmento, casilla.number) in declared_identities:
            covered.append(casilla)
        else:
            gap.append(casilla)
    return DisenoCoverageReport(
        modelo_id=modelo_id,
        revision_id=revision.id,
        diseno_casillas=diseno,
        covered_casillas=tuple(covered),
        coverage_gap_casillas=tuple(gap),
    )


def _sheet_casilla_numbers(sheet: RecordDesignSheet) -> tuple[str, ...]:
    """Return the casilla tags declared in one record-design sheet, in field order."""
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
    "calculation_closure_identities",
    "calculation_closure_numbers",
    "derive_calculation_completeness_casillas",
    "derive_diseno_coverage_casillas",
]
