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
*this* filing's disposition actually files. The bank-account (DID) page is the
worked case -- it belongs to the layout but reaches disk only where the fichero
must carry an account, so a casilla it carries is required on such a filing and
out of scope otherwise. :func:`_did_page_suppressed` is therefore the shared
predicate behind representability and record order alike, and lives here with the
disposition-scoped concern rather than beside the renderer that also consults it.

"Must carry an account" is NOT "is a refund", and this prose said it was until a
domiciliación filing was measured going out with no account for AEAT to debit.
The three refund codes need the page because AEAT pays into the account; ``U``
needs it because AEAT charges the account. The Diseño settles it by labelling
position 23 ``Domiciliación/Devolución - IBAN`` -- one field for both directions
-- while every other field on the page is prefixed ``Devolución -``.

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

from collections.abc import Mapping, Sequence
from decimal import Decimal

from ...core import (
    ExportLayoutFormat,
    FilingProducerKey,
    PriorDomiciliationElection,
    ResultDisposition,
    result_disposition_requires_bank_account,
)
from ...core.modelo import Modelo
from ...core.casilla_id import CasillaId, validated_casilla_id
from ...domain.calculations.registry.export import fixed_width_record_casilla_ids
from ...domain.calculations.registry.export_parse import xml_dictionary_entries
from ...domain.calculations.registry.rate_box_partition import (
    RateBoxPartition,
    rate_box_coverage_shortfalls,
)
from ...domain.calculations.registry.schema_exports import ExportLayoutDefinition, ExportRecordDefinition
from ...domain.calculations.registry.schema_surfaces import CalculationCompletenessManifest
from ...domain.filing.protocols import CasillaCollection
from ...domain.filing.schema import ModeloDraft
from .errors import ModeloApplicationError as FilingExportError
from .runtime import CasillaRecordMetadata, RegistrySchemaAccessor

#: ``record_type`` of the bank-account (DID) page in the DR303 export layout.
#: The page is emitted for any disposition whose fichero must carry an account,
#: which is NOT the same as "a refund". Its IBAN field is the one dual-purpose
#: field on the page -- the Diseño names it ``Domiciliación/Devolución - IBAN``
#: -- while the SWIFT-BIC, bank name, address, city, country and marca SEPA
#: fields are each prefixed ``Devolución -`` and apply to a refund only. So a
#: domiciliación filing needs this page for its IBAN alone, and suppressing it
#: there filed a direct-debit election with no account for AEAT to charge.
_DID_PAGE_RECORD_TYPE = "page_did"
_M303_CASILLA_111: CasillaId = validated_casilla_id("111", surface="M303 Nota 3 DID predicate")
_M303_RECTIFICATIVA_HEADER = FilingProducerKey.AMENDMENT_IS_RECTIFICATIVA


def _m303_nota_three_requires_bank_account(
    *,
    draft: ModeloDraft,
    headers: Mapping[FilingProducerKey, object],
    prior_domiciliation_election: PriorDomiciliationElection,
) -> bool:
    """Return whether M303 Nota 3 independently requires the DID page.

    Casilla 111 is semantically present when it has a value, including zero;
    truthiness would incorrectly collapse a stated zero into an absent field.
    The typed cancellation election alone disables this Nota-3 requirement.
    """
    return (
        draft.modelo == Modelo.M303
        and headers.get(_M303_RECTIFICATIVA_HEADER) is True
        and prior_domiciliation_election is PriorDomiciliationElection.KEEP
        and any(value.casilla_id == _M303_CASILLA_111 and value.value is not None for value in draft.values)
    )


def _did_page_required(
    *,
    draft: ModeloDraft,
    headers: Mapping[FilingProducerKey, object],
    prior_domiciliation_election: PriorDomiciliationElection,
) -> bool:
    """Return whether this filing must include the DID bank-account page."""
    declaration_type = headers.get(FilingProducerKey.FILING_RESULT_DISPOSITION, "")
    try:
        disposition = ResultDisposition(declaration_type)
    except ValueError:
        disposition_requires_bank_account = False
    else:
        disposition_requires_bank_account = result_disposition_requires_bank_account(disposition)
    return disposition_requires_bank_account or _m303_nota_three_requires_bank_account(
        draft=draft,
        headers=headers,
        prior_domiciliation_election=prior_domiciliation_election,
    )


def _did_page_suppressed(
    record: ExportRecordDefinition,
    *,
    draft: ModeloDraft,
    headers: Mapping[FilingProducerKey, object],
    prior_domiciliation_election: PriorDomiciliationElection,
) -> bool:
    """Return whether a DID (bank-account) page record must be suppressed.

    The sole DID predicate is ``disposition_requires_bank_account OR Nota 3``.
    Nota 3 means an M303 rectificativa with casilla 111 semantically present and
    a ``KEEP`` prior-domiciliation election. It is independent of the current
    disposition, while a selected ``CANCEL_OR_MODIFY`` disables only that added
    path, never a DID page required by the current disposition.

    This function is shared by the renderer and parity derivations so they
    cannot disagree about which official record reaches disk.
    """
    if record.record_type != _DID_PAGE_RECORD_TYPE:
        return False
    return not _did_page_required(
        draft=draft,
        headers=headers,
        prior_domiciliation_election=prior_domiciliation_election,
    )


def boe_representable_casilla_ids(
    layout: ExportLayoutDefinition,
    *,
    draft: ModeloDraft,
    headers: Mapping[FilingProducerKey, object],
    prior_domiciliation_election: PriorDomiciliationElection,
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

    That out-of-scope verdict is no longer taken on trust. The fixed-width branch
    delegates to
    :func:`~domain.calculations.registry.fixed_width_record_casilla_ids`, the same
    derivation the registry-build export-exemption gate runs over EVERY declared
    record; that gate refuses at build any manifest casilla this set would exempt
    from a demand unless the casilla declares WHY it files no slot. Absence here
    therefore carries a reviewed reason behind it rather than being
    indistinguishable from a forgotten annotation.
    """
    if layout.format is ExportLayoutFormat.XML_DICTIONARY:
        entries = xml_dictionary_entries(
            layout,
            source_root=schema_provider.source_root,
            sources=schema_provider.sources,
        )
        return frozenset(entry.casilla_id for entry in entries if entry.casilla_id is not None)
    return fixed_width_record_casilla_ids(
        tuple(
            record
            for record in layout.records
            if not _did_page_suppressed(
                record,
                draft=draft,
                headers=headers,
                prior_domiciliation_election=prior_domiciliation_election,
            )
        ),
    )


def rendered_casilla_ids(
    layout: ExportLayoutDefinition,
    *,
    draft: ModeloDraft,
    headers: Mapping[FilingProducerKey, object],
    prior_domiciliation_election: PriorDomiciliationElection,
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
        boe_representable_casilla_ids(
            layout,
            draft=draft,
            headers=headers,
            prior_domiciliation_election=prior_domiciliation_election,
            schema_provider=schema_provider,
        )
        & valued_casillas
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
    headers: Mapping[FilingProducerKey, object],
    prior_domiciliation_election: PriorDomiciliationElection,
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
    _assert_record_order_fidelity(
        modelo=draft.modelo,
        layout=layout,
        draft=draft,
        headers=headers,
        prior_domiciliation_election=prior_domiciliation_election,
    )
    representable = boe_representable_casilla_ids(
        layout,
        draft=draft,
        headers=headers,
        prior_domiciliation_election=prior_domiciliation_election,
        schema_provider=schema_provider,
    )
    _assert_casilla_metadata_fidelity(
        modelo=draft.modelo,
        manifest=manifest,
        representable=representable,
        casilla_metadata=casilla_metadata,
    )
    rendered = rendered_casilla_ids(
        layout,
        draft=draft,
        headers=headers,
        prior_domiciliation_election=prior_domiciliation_election,
        schema_provider=schema_provider,
    )
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
    raise FilingExportError(
        translated_message="application.filing.export_parity.errors.required_casillas_omitted",
        context={
            "modelo": draft.modelo,
            "missing_count": len(missing),
            "missing_casillas": tuple(
                {
                    "casilla_id": casilla_id,
                    "number": metadata[casilla_id][0],
                    "segmento": metadata[casilla_id][1],
                }
                for casilla_id in missing
            ),
        },
    )


def assert_rate_boxes_account_for_total(
    partitions: Sequence[RateBoxPartition],
    *,
    draft: ModeloDraft,
) -> None:
    """Panic if the draft's rate boxes account for less than their declared total.

    A rate-specific official box asserts a rate, so a ledger row recording a
    cuota without recording the rate charged reaches the rate-blind total layer
    and no box. The return keeps the money and the breakdown keeps its integrity;
    what it loses is the property that the parts sum to the whole, and AEAT
    reconciles those boxes against that total.

    The refusal sits at the write door for the same reason the completeness gate
    does: the application never files, so the artefact leaves here for a human to
    submit with nothing behind it. A blank computed slot and a breakdown that
    does not reach its own total are the same class of defect -- a return whose
    structure contradicts what the calculation determined -- and both cost the
    taxpayer a correction they cannot make, where the refusal costs them a ledger
    repair they can.

    Unlike the completeness gate this applies to every transport. That gate is
    fixed-width-only because its subject is a blank BYTE SLOT, which the xml
    transport does not write; this one's subject is an arithmetic relation
    between values, which is equally false in either encoding. A box the xml
    transport legitimately omits reads as zero here, which is what it declares.

    The condition is never the operator's first notice of it: the calculate path
    raises the same shortfall as a non-blocking advisory, computed by the same
    :func:`~domain.calculations.registry.rate_box_coverage_shortfalls` over the
    same partitions.

    Args:
        partitions: The revision's derived rate-box partitions, from
            :attr:`~application.filing.runtime.RegistryModeloSubview.rate_box_partitions`.
            Empty for every revision declaring no rate-specific binding, which
            makes this a no-op there.
        draft: The :class:`ModeloDraft` about to be written.

    Raises:
        FilingExportError: A partition's boxes account for less than its total,
            naming each shortfall with its tier, its total casilla and its boxes.
    """
    if not partitions:
        return
    values = {value.casilla_id: value.value for value in draft.values if value.value is not None}
    numeric = {casilla_id: value for casilla_id, value in values.items() if isinstance(value, Decimal)}
    shortfalls = rate_box_coverage_shortfalls(partitions, numeric)
    if not shortfalls:
        return
    raise FilingExportError(
        translated_message="application.filing.export_parity.errors.rate_boxes_understate_total",
        context={
            "modelo": draft.modelo,
            "shortfall_count": len(shortfalls),
            "shortfalls": tuple(
                {
                    "total_casilla_id": shortfall.partition.total_casilla_id,
                    "rate_kinds": tuple(shortfall.partition.rate_kinds),
                    "fact": shortfall.partition.fact,
                    "declared_total": str(shortfall.total),
                    "box_casilla_ids": tuple(shortfall.partition.box_casilla_ids),
                    "boxes_total": str(shortfall.boxes_total),
                    "unaccounted": str(shortfall.shortfall),
                }
                for shortfall in shortfalls
            ),
        },
    )


def _assert_record_order_fidelity(
    *,
    modelo: str,
    layout: ExportLayoutDefinition,
    draft: ModeloDraft,
    headers: Mapping[FilingProducerKey, object],
    prior_domiciliation_election: PriorDomiciliationElection,
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
    declared = tuple(
        record
        for record in layout.records
        if not _did_page_suppressed(
            record,
            draft=draft,
            headers=headers,
            prior_domiciliation_election=prior_domiciliation_election,
        )
    )
    orders = [record.order for record in declared]
    duplicate_orders = sorted({order for order in orders if orders.count(order) > 1})
    if duplicate_orders:
        raise FilingExportError(
            translated_message="application.filing.export_parity.errors.record_emit_order_duplicated",
            context={
                "modelo": modelo,
                "duplicate_order_count": len(duplicate_orders),
                "duplicate_orders": tuple(duplicate_orders),
            },
        )
    emitted = tuple(sorted(declared, key=lambda record: record.order))
    if [record.id for record in emitted] != [record.id for record in declared]:
        order_drifts = tuple(
            {
                "position": index,
                "registry_record_id": declared[index].id,
                "emitted_record_id": emitted[index].id,
            }
            for index in range(len(declared))
            if declared[index].id != emitted[index].id
        )
        raise FilingExportError(
            translated_message="application.filing.export_parity.errors.record_emit_order_drift",
            context={
                "modelo": modelo,
                "drift_count": len(order_drifts),
                "order_drifts": order_drifts,
            },
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
    drifts: list[dict[str, object]] = []
    for manifest_casilla in manifest.casillas:
        casilla_id = manifest_casilla.casilla_id
        if casilla_id not in representable:
            continue
        registry_meta = registry_by_id.get(casilla_id)
        if registry_meta is None:
            drifts.append(
                {
                    "casilla_id": casilla_id,
                    "registry_declares_casilla": False,
                    "manifest_number": manifest_casilla.number,
                    "manifest_segmento": manifest_casilla.segmento,
                },
            )
            continue
        if (manifest_casilla.number, manifest_casilla.segmento) != (registry_meta.number, registry_meta.segmento):
            drifts.append(
                {
                    "casilla_id": casilla_id,
                    "registry_declares_casilla": True,
                    "registry_number": registry_meta.number,
                    "registry_segmento": registry_meta.segmento,
                    "manifest_number": manifest_casilla.number,
                    "manifest_segmento": manifest_casilla.segmento,
                },
            )
    if not drifts:
        return
    raise FilingExportError(
        translated_message="application.filing.export_parity.errors.casilla_metadata_drift",
        context={
            "modelo": modelo,
            "drift_count": len(drifts),
            "casilla_drifts": tuple(drifts),
        },
    )


did_page_required = _did_page_required
did_page_suppressed = _did_page_suppressed


def assert_xml_declaration_aux_declared(layout: ExportLayoutDefinition) -> None:
    """Panic if an ``xml_dictionary`` export cannot write its mandatory ``Aux``.

    Every AEAT Modelo 100 XSD opens ``Declaracion`` with ``Aux``, ``minOccurs=1``,
    whose ``Idioma`` and ``VERSION`` children are each ``minOccurs=1`` too. No
    bundled dictionary declares a single ``Aux`` row in any revision, so the
    dictionary-driven writer cannot reach the block and the values are declared on
    the layout instead. When one is undeclared the block cannot be written at all:
    a partial ``Aux`` is invalid, and omitting it makes the document fail at its
    very first element.

    The refusal exists because the alternative is worse than an error. AEAT types
    ``VERSION`` as ``tipo_String4L`` — four characters, permissive pattern, no
    enumeration — so an invented token would VALIDATE, the document would start
    passing every check made of it, and the gap would stop being reported while an
    unverified value rode to the tax authority. Refusing keeps the gap visible; the
    export resumes the moment the layout declares a real value, with no code change.

    This runs at the write door rather than inside the renderer because the property
    it defends is that no unfileable artefact reaches the operator, and because an
    operator who receives a file believes they hold a filing artefact.

    Args:
        layout: The export layout about to be written.

    Raises:
        FilingExportError: The layout is ``xml_dictionary`` and cannot supply the
            mandatory block, naming the undeclared field.
    """
    if layout.format is not ExportLayoutFormat.XML_DICTIONARY:
        return
    undeclared = [
        name
        for name, value in (("aux_idioma", layout.aux_idioma), ("aux_version", layout.aux_version))
        if value is None
    ]
    if not undeclared:
        return
    raise FilingExportError(
        translated_message="application.filing.export_parity.errors.aux_block_undeclared",
        context={
            "layout_id": layout.id,
            "layout_format": layout.format.value,
            "undeclared_count": len(undeclared),
            "undeclared_fields": tuple(undeclared),
        },
    )


__all__ = [
    "assert_export_mirrors_manifest",
    "assert_rate_boxes_account_for_total",
    "assert_xml_declaration_aux_declared",
    "boe_representable_casilla_ids",
    "did_page_required",
    "did_page_suppressed",
    "rendered_casilla_ids",
    "required_applicable_casilla_ids",
]
