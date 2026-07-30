"""Pre-write structural-parity gate for the fichero-BOE export.

A ``.boe`` file is accepted by AEAT on its bytes, and a SHA-256 digest proves
only that the bytes on disk are the bytes that were written -- never that they
carry what the modelo requires. A draft that silently lost a computed casilla
still serialises to a well-formed, correctly-digested file whose slots are
blank: a *structurally-thin* filing. This module holds the assertions that run
between rendering and :meth:`pathlib.Path.write_bytes`, so such a file is
refused before it can exist rather than discovered by AEAT.

Three dimensions are asserted, each a hard enumerated
:class:`~domain.filing.FilingExportError` naming exactly what drifted:

* **Casilla presence** -- every casilla that is a calculation RESULT (declares a
  formula) or is schema-required, that the completeness manifest lists AND the
  official record files a slot for at this filing's disposition, carries a real
  value on disk (:func:`assert_export_mirrors_manifest`).
* **Record/section order** -- the records reaching disk, emitted in their
  declared ``order``, follow the registry export-layout declaration order, with
  no two rendered records sharing an ``order``
  (:func:`_assert_record_order_fidelity`).
* **Casilla numbering/segmento** -- every representable manifest casilla carries
  the ``(number, segmento)`` the registry ``CasillaDefinition`` declares
  (:func:`_assert_casilla_metadata_fidelity`).

Disposition is the axis running through all three
---------------------------------------------------

None of the three is a property of the layout alone: each is scoped to what
*this* filing's disposition actually files. The refund (DID) page is the worked
case -- it belongs to the layout but reaches disk only on a refund disposition,
so a casilla it carries is required on a refund filing and out of scope on a
non-refund one. :func:`_did_page_suppressed` is therefore the shared predicate
behind representability and record order alike, and lives here with the
disposition-scoped concern rather than beside the renderer that also consults
it.

Set derivation and the gate are one concern
--------------------------------------------

:func:`boe_representable_casilla_ids`, :func:`rendered_casilla_ids`, and
:func:`required_applicable_casilla_ids` are the gate's own set algebra, and are
public because the parity regressions and the export-completeness gate pin them
directly. They are exported here so a change to the required-set semantics
propagates from one derivation authority to every production consumer, rather
than being mirrored into a second copy that can drift out of agreement with the
gate it is supposed to describe.

See Also:
    :mod:`application.filing._export`
        Renders the layout and calls :func:`assert_export_mirrors_manifest`
        before writing the bytes.
"""

from __future__ import annotations

from ...core import ExportLayoutFormat, ResultDisposition, result_disposition_is_refund
from ...domain.calculations.registry import (
    CalculationCompletenessManifest,
    CasillaFieldKind,
    CasillaId,
    ExportLayoutDefinition,
    ExportRecordDefinition,
    xml_dictionary_entries,
)
from ...domain.filing import CasillaCollection, FilingExportError, ModeloDraft
from .runtime import CasillaRecordMetadata, RegistrySchemaAccessor

#: ``record_type`` of the cuenta-devolución (DID) page in the DR303 export
#: layout. The DID page carries the refund-account block (IBAN / SWIFT-BIC /
#: bank block) AEAT pays into and is emitted ONLY for a refund disposition — a
#: non-refund filing has no refund account to declare, so emitting the page
#: would write an empty 823-byte record the Diseño intends only for a refund.
_DID_PAGE_RECORD_TYPE = "page_did"


def _did_page_suppressed(record: ExportRecordDefinition, *, headers: dict[str, str]) -> bool:
    """Return whether a DID (cuenta-devolución) page record must be suppressed.

    The DID page is emitted only when the determined disposition (carried on the
    ``declaration_type`` header) is a refund (``D`` / ``V`` / ``X``). A
    non-refund filing suppresses the page rather than emitting an empty refund
    block. Non-DID records are never suppressed by this guard.

    This is the single disposition predicate shared by the renderer (which skips
    the record) and this module's parity assertions (which must not require a
    casilla the disposition never files), so the two cannot disagree about what
    reaches disk.
    """
    if record.record_type != _DID_PAGE_RECORD_TYPE:
        return False
    declaration_type = headers.get("declaration_type", "")
    try:
        disposition = ResultDisposition(declaration_type)
    except ValueError:
        return True
    return not result_disposition_is_refund(disposition)


def boe_representable_casilla_ids(
    layout: ExportLayoutDefinition,
    *,
    headers: dict[str, str],
    schema_provider: RegistrySchemaAccessor,
) -> frozenset[CasillaId]:
    """Return the casillas the ``.boe`` layout files a slot for, for this disposition.

    A casilla is *representable* when the official record design carries a field
    for it that this draft's disposition does not suppress. ``xml_dictionary``
    layouts derive their casillas from the dictionary entries; ``fixed_width``
    layouts from every ``CASILLA`` field plus the binding-row casilla mappings
    (``row_field_casilla_ids``), across records not suppressed for the disposition
    (e.g. the DID refund page on a non-refund filing).

    The completeness gate intersects the calculation-completeness manifest with
    this set: a manifest casilla absent here is a calculation-closure casilla the
    official filed record does not carry, so it is out of scope for the ``.boe``
    parity gate rather than a drift.
    """
    if layout.format is ExportLayoutFormat.XML_DICTIONARY:
        entries = xml_dictionary_entries(
            layout,
            source_root=schema_provider.source_root,
            sources=schema_provider.sources,
        )
        return frozenset(entry.casilla_id for entry in entries if entry.casilla_id is not None)
    normalized_headers = {key.lower(): value for key, value in headers.items()}
    representable: set[CasillaId] = set()
    for record in layout.records:
        if _did_page_suppressed(record, headers=normalized_headers):
            continue
        for field in record.fields:
            if field.kind == CasillaFieldKind.CASILLA and field.casilla_id is not None:
                representable.add(field.casilla_id)
        representable.update(record.row_field_casilla_ids.values())
    return frozenset(representable)


def rendered_casilla_ids(
    layout: ExportLayoutDefinition,
    *,
    draft: ModeloDraft,
    headers: dict[str, str],
    schema_provider: RegistrySchemaAccessor,
) -> frozenset[CasillaId]:
    """Return the representable casillas whose value actually reaches disk.

    A representable casilla reaches disk only when the :class:`ModeloDraft`
    carries a value for it; a representable casilla absent from
    ``draft.values`` renders as a blank fixed-width slot (or an omitted xml
    element), which is the structurally-thin file the completeness gate
    exists to refuse. This is the rendered set the gate compares against the
    manifest-required-and-representable set.
    """
    # build_draft emits a ModeloValue for every declared casilla, using
    # value=None (kind=EMPTY) as the "nothing here" marker, so casilla-id
    # membership in draft.values is NOT value presence: an EMPTY casilla would
    # render as a blank slot. Filter to real values (value is None iff EMPTY).
    valued_casillas = {value.casilla_id for value in draft.values if value.value is not None}
    return frozenset(
        boe_representable_casilla_ids(layout, headers=headers, schema_provider=schema_provider) & valued_casillas
    )


def required_applicable_casilla_ids(
    manifest: CalculationCompletenessManifest,
    *,
    collection: CasillaCollection,
    representable: frozenset[CasillaId],
) -> frozenset[CasillaId]:
    """Return the casillas that must carry a value in a complete fichero-BOE export.

    A casilla is *required-applicable* when it declares a formula (a calculation
    RESULT) or is schema-required, AND the official export record files a slot for
    it at this filing's disposition (``representable``).  Optional operator-input
    casillas — retenciones, prior payments, deductions the taxpayer may
    legitimately not have — declare neither a formula nor a ``required`` flag, so
    they are excluded: a blank slot for them is a valid zero, not a
    structurally-thin file.

    This is the single derivation authority behind the completeness gate
    (:func:`assert_export_mirrors_manifest`), so a change to the required-set
    semantics propagates to every production consumer in one place.

    The regression tests deliberately do NOT consume this function as their
    expectation: they pin it against an independent partition read straight off the
    :class:`CasillaCollection`. A test whose expected set comes from the subject
    itself can only detect that the subject was called, never that its semantics
    changed -- and a relaxation here silently drops a casilla out of the pre-write
    gate, letting a structurally-thin fichero-BOE ship behind a valid SHA-256
    digest. Do not "de-duplicate" the tests onto this function.

    Args:
        manifest: Revision's
            :class:`~domain.calculations.registry.CalculationCompletenessManifest`.
        collection: :class:`~domain.filing.CasillaCollection` for the modelo,
            supplying ``formula`` and ``required`` for each declared casilla.
        representable: Casilla IDs the official export record files a slot for
            at this filing's disposition; see :func:`boe_representable_casilla_ids`.

    Returns:
        Frozen set of casilla IDs that must carry a real value before the
        fichero-BOE bytes are written.

    See Also:
        :func:`boe_representable_casilla_ids`
            Derives the ``representable`` argument from the export layout and headers.
        :func:`assert_export_mirrors_manifest`
            Gate that enforces this required set before writing bytes.
    """
    return (
        frozenset(
            casilla.casilla_id
            for casilla in manifest.casillas
            if (schema := collection.get(casilla.casilla_id)) is not None
            and (schema.formula is not None or schema.required)
        )
        & representable
    )


def assert_export_mirrors_manifest(
    layout: ExportLayoutDefinition,
    *,
    draft: ModeloDraft,
    headers: dict[str, str],
    schema_provider: RegistrySchemaAccessor,
    manifest: CalculationCompletenessManifest,
    casilla_metadata: tuple[CasillaRecordMetadata, ...],
) -> None:
    """Panic if the ``.boe`` would not mirror the manifest-required structure.

    The completeness gate: every casilla that is a calculation RESULT (declares a
    formula) or is schema-required, and that the calculation-completeness manifest
    lists AND the official record files (``representable`` for this
    :class:`ModeloDraft`'s disposition), MUST carry a value on disk. Such a casilla
    rendered blank means the calculation did not populate it -- a structurally-thin
    file behind a valid SHA-256 digest, which this gate refuses with a hard
    :class:`FilingExportError` naming every missing casilla with its official record
    number and segmento, so the panic is loud and explicit.

    Optional operator-input casillas -- retenciones, prior payments, deductions the
    taxpayer may legitimately not have -- are NOT required to carry a value: a blank
    slot for them is a valid zero, not a thin file (grounded in the AEAT casilla
    semantics; e.g. Modelo 131 casillas 02/08/09/12/14 are optional inputs), so they
    are excluded from the required set. A manifest casilla absent from the
    representable set is a calculation-closure casilla the official record does not
    file and is likewise out of scope. Callers pass ``manifest`` only when the
    revision declares one; a revision without a manifest is handled by the
    coverage-advisory path, not here.

    The gate applies only to the fixed-width fichero-BOE. In that format every
    field occupies its byte slot always, so an omitted required casilla renders a
    blank slot behind a valid digest -- the structurally-thin file. An
    ``xml_dictionary`` export instead omits an absent casilla as an absent
    optional element, which is legitimate (a filer declares only the casillas its
    situation requires), so completeness is not asserted for that transport.

    Beyond casilla presence, the gate asserts two further structural-fidelity
    dimensions before any bytes are written, so the ``.boe`` mirrors the official
    modelo-revision structure and not merely its casilla set:

    - Record/section order: the records that reach disk, emitted in their declared
      ``order``, must follow the registry export-layout declaration order, and no
      two rendered records may share an ``order``
      (:func:`_assert_record_order_fidelity`).
    - Casilla numbering/segmento: every manifest casilla the official record files
      a slot for must carry the same ``(number, segmento)`` the registry
      ``CasillaDefinition`` declares -- re-grounded against the projected
      :class:`~application.filing.runtime.CasillaRecordMetadata`, not the
      manifest's own copy (:func:`_assert_casilla_metadata_fidelity`).

    Each dimension is a hard, enumerated :class:`FilingExportError`; a structural
    divergence is a failure, never a warning.
    """
    if layout.format is not ExportLayoutFormat.FIXED_WIDTH:
        return
    _assert_record_order_fidelity(modelo=draft.modelo, layout=layout, headers=headers)
    representable = boe_representable_casilla_ids(layout, headers=headers, schema_provider=schema_provider)
    _assert_casilla_metadata_fidelity(
        modelo=draft.modelo,
        manifest=manifest,
        representable=representable,
        casilla_metadata=casilla_metadata,
    )
    rendered = rendered_casilla_ids(layout, draft=draft, headers=headers, schema_provider=schema_provider)
    # Require a value on disk only for calculation RESULTS (casillas declaring a
    # formula) and schema-required casillas. Optional operator inputs -- retenciones,
    # prior payments, deductions the taxpayer may legitimately not have -- render a
    # blank slot that is a valid zero, not a thin file, so they are excluded from the
    # required set (grounded in the AEAT casilla semantics, e.g. Modelo 131 casillas
    # 02/08/09/12/14).
    collection = schema_provider.get_collection(draft.modelo)
    required_applicable = required_applicable_casilla_ids(
        manifest,
        collection=collection,
        representable=representable,
    )
    missing = sorted(required_applicable - rendered)
    if not missing:
        return
    metadata = {casilla.casilla_id: (casilla.number, casilla.segmento) for casilla in manifest.casillas}
    rendered_missing = "; ".join(_format_missing_casilla(casilla_id, metadata[casilla_id]) for casilla_id in missing)
    raise FilingExportError(
        f"fichero-BOE export for modelo {draft.modelo!r} would omit {len(missing)} required "
        f"casilla(s) the official record files, rendering them as blank slots (structurally-thin "
        f"filing): {rendered_missing}. Every required casilla must be declared in the draft before export.",
    )


def _segmento_phrase(segmento: str | None) -> str:
    """Render a segmento clause for a fidelity-drift enumeration, blank when unset."""
    return "" if segmento is None else f" within segmento {segmento!r}"


def _assert_record_order_fidelity(
    *,
    modelo: str,
    layout: ExportLayoutDefinition,
    headers: dict[str, str],
) -> None:
    """Panic if the rendered record order drifts from the registry declaration order.

    A fixed-width ``.boe`` emits its records sorted by each record's ``order``
    field; the AEAT *Diseño de registros* fixes that page/segment sequence and the
    registry export layout declares the records in that official order
    (``layout.records``). This assertion re-grounds the emitted record sequence
    against that declaration: the records that reach disk (excluding
    disposition-suppressed records such as the DID refund page) must, when emitted
    in ``order``, appear in the same sequence the registry declares, and no two
    rendered records may share an ``order`` (an ambiguous emit sequence). A
    permuted or ambiguous record order is a hard, enumerated
    :class:`FilingExportError` -- the ``.boe`` record/section sequence must mirror
    the official modelo-revision structure.
    """
    normalized_headers = {key.lower(): value for key, value in headers.items()}
    declared = tuple(
        record for record in layout.records if not _did_page_suppressed(record, headers=normalized_headers)
    )
    orders = [record.order for record in declared]
    duplicate_orders = sorted({order for order in orders if orders.count(order) > 1})
    if duplicate_orders:
        rendered = ", ".join(str(order) for order in duplicate_orders)
        raise FilingExportError(
            f"fichero-BOE export for modelo {modelo!r} declares export records that share an emit "
            f"order ({rendered}), so the rendered record sequence is ambiguous "
            f"(structural-fidelity drift). Each rendered record must declare a distinct order so the "
            f"exported record sequence mirrors the official modelo-revision structure.",
        )
    emitted = tuple(sorted(declared, key=lambda record: record.order))
    if [record.id for record in emitted] != [record.id for record in declared]:
        drifts = "; ".join(
            f"position {index}: registry declares record {declared[index].id!r} "
            f"but the .boe would emit {emitted[index].id!r}"
            for index in range(len(declared))
            if declared[index].id != emitted[index].id
        )
        raise FilingExportError(
            f"fichero-BOE export for modelo {modelo!r} would emit its records out of the "
            f"registry-declared record order (structural-fidelity drift): {drifts}. The rendered "
            f"record sequence must follow the official modelo-revision structure.",
        )


def _assert_casilla_metadata_fidelity(
    *,
    modelo: str,
    manifest: CalculationCompletenessManifest,
    representable: frozenset[CasillaId],
    casilla_metadata: tuple[CasillaRecordMetadata, ...],
) -> None:
    """Panic if a representable manifest casilla's number/segmento drifts from the registry.

    The completeness manifest carries its own copy of each casilla's official
    ``(number, segmento)`` -- the metadata this parity gate reports and keys on.
    This assertion re-grounds that copy against the authoritative
    :class:`~application.filing.runtime.CasillaRecordMetadata` projected from
    the registry ``CasillaDefinition`` (the same authority the calculation engine
    consumes), for every manifest casilla the official record files a slot for
    (``representable``). A divergent ``number`` or ``segmento`` -- or a manifest
    casilla the registry no longer declares -- is a hard, enumerated
    :class:`FilingExportError` with the expected registry value versus the value the
    ``.boe`` would file, so the exported casilla numbering and segmento cannot drift
    from the official modelo-revision structure behind a valid digest.
    """
    registry_by_id = {meta.casilla_id: meta for meta in casilla_metadata}
    drifts: list[str] = []
    for manifest_casilla in manifest.casillas:
        casilla_id = manifest_casilla.casilla_id
        if casilla_id not in representable:
            continue
        registry_meta = registry_by_id.get(casilla_id)
        if registry_meta is None:
            drifts.append(
                f"{casilla_id} (manifest declares number {manifest_casilla.number!r}"
                f"{_segmento_phrase(manifest_casilla.segmento)} but the registry does not declare this casilla)",
            )
            continue
        if (manifest_casilla.number, manifest_casilla.segmento) != (registry_meta.number, registry_meta.segmento):
            drifts.append(
                f"{casilla_id} (registry declares number {registry_meta.number!r}"
                f"{_segmento_phrase(registry_meta.segmento)} but the .boe would file it as number "
                f"{manifest_casilla.number!r}{_segmento_phrase(manifest_casilla.segmento)})",
            )
    if not drifts:
        return
    raise FilingExportError(
        f"fichero-BOE export for modelo {modelo!r} would render {len(drifts)} casilla(s) whose "
        f"number/segmento drifts from the registry-declared record-design metadata "
        f"(structural-fidelity drift): {'; '.join(drifts)}. The exported casilla numbering and "
        f"segmento must mirror the official modelo-revision structure.",
    )


def _format_missing_casilla(casilla_id: CasillaId, metadata: tuple[str, str | None]) -> str:
    number, segmento = metadata
    if segmento is not None:
        return f"{casilla_id} (segmento {segmento}, casilla {number})"
    return f"{casilla_id} (casilla {number})"


__all__ = [
    "assert_export_mirrors_manifest",
    "boe_representable_casilla_ids",
    "rendered_casilla_ids",
    "required_applicable_casilla_ids",
]
