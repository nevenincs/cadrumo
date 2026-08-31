"""Canonical application-layer source resolution contracts.

The source mesh is the calculation-facing envelope for values derived from
bucket-local ledgers, invoices, prior filings, profile facts, borrador data,
relation prefill, and other registry-declared sources. A
:class:`CalculationSourceContext` binds the active bucket, modelo,
:class:`Period`, and selected :class:`ModeloRevision`; each
:class:`ModeloSourceResolver` claims one or more :class:`BindingSourceKind`
members and returns a :class:`CalculationSourceResolution`.

``CalculationSourceResolution`` is the single resolved-source carrier consumed
by modelo calculation. It carries decimal, enum, date, row-indexed binding,
relation, bound-casilla, detail-row, transaction-id, diagnostic, and provenance
channels. Exclusive merges use :func:`merge_source_resolutions`; precedence overlays use
:func:`merge_source_resolutions_by_precedence`; and
:func:`collect_unhandled_source_diagnostics` is the no-silent-blank safety net
for declared binding sources without an enrolled resolver.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, ClassVar, Final, Literal, NamedTuple, Protocol, Self, runtime_checkable

from pydantic import BaseModel, Field, TypeAdapter, field_serializer, field_validator, model_validator

from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...core.casilla_id import CasillaId
from ...core.decimal._coerce import coerce_decimal
from ...core.errors.hierarchy import CoreValidationError
from ...core.filing_year import FilingYear
from ...core.identity import BucketId, SnapshotId, WorkUnitId
from ...core.irnr import M210GrossIncomeSourceMode
from ...core.logging import get_logger
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.period import Period
from ...core.prose_elision import ElidedProse
from ...core.type_adapters import OBJECT_TUPLE_ADAPTER, STR_KEYED_MAPPING_ADAPTER
from ...domain.calculations._row_casilla import DirectRowMaterializationProvenance, RowCasillaKey
from ...domain.calculations._row_source_identity import RowBindingKey, RowSourceIdentity
from ...domain.calculations.registry.ids import (
    BindingId,
    LegalRefId,
    ModeloId,
    RelationId,
    SourceRefId,
)
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.modelos.calculation_revision import M303RegimenSimplificadoAnnualSummaryHandoff
from ...domain.modelos.row_models import ModeloDetailRow
from .errors import AggregationValidationError, t

RowBindingValue = str | Decimal | int | bool

_ROW_BINDING_VALUES = TypeAdapter(dict[RowBindingKey, RowBindingValue])


_ROW_SOURCE_IDENTITIES = TypeAdapter(dict[RowBindingKey, RowSourceIdentity])

_ROW_CASILLA_VALUES = TypeAdapter(dict[RowCasillaKey, Decimal])

_ROW_CASILLA_PROVENANCE = TypeAdapter(dict[RowCasillaKey, DirectRowMaterializationProvenance])


def _empty_row_binding_values() -> dict[RowBindingKey, RowBindingValue]:
    return {}


def _empty_row_source_identities() -> dict[RowBindingKey, RowSourceIdentity]:
    return {}


def _empty_row_casilla_values() -> dict[RowCasillaKey, Decimal]:
    return {}


def _empty_row_casilla_provenance() -> dict[RowCasillaKey, DirectRowMaterializationProvenance]:
    return {}


class SourceMeshError(CoreValidationError):
    """Raised when a ``CalculationSourceMesh`` field validator rejects an invariant.

    Replaces bare :exc:`ValueError` at the ``owned_sources`` uniqueness / blank
    guards and the ``source_transaction_ids`` uniqueness / blank guards so
    callers receive a typed, registry-bound, localized error.  Inherits from
    :class:`~core.errors.CoreValidationError` (which inherits from
    :exc:`ValueError`) so pydantic field validators surface it through
    ``ValidationError`` without special handling.
    """

    def __init__(self, message_key: str) -> None:
        super().__init__(message_key, translated_message=message_key)


_log = get_logger(__name__)

CalculationSourceDiagnosticReason = Literal[
    "duplicate_binding_owner",
    "duplicate_bound_casilla_owner",
    "duplicate_relation_owner",
    "source_issue",
    "unresolved_binding",
    "storage_degraded",
    "source_domain_not_ready",
    "unhandled_binding_source",
    "unresolved_derived_binding",
    "unrouted_observation",
    # An independent QUANTITY consumed rows carry that no binding drawing that
    # quantity reaches -- the retención suffered on the renta side, a base
    # imponible or recargo on the IVA side. Distinct from "unrouted_observation"
    # on the axis that matters to a reader: there, no binding consumes the row
    # and every screen agrees it is unrouted; here the row IS consumed, so the
    # row-keyed screens are silent by construction and their silence must not
    # read as confirmation. Collapsing THOSE two would leave an operator unable
    # to tell "this row reaches nothing" from "this row reaches a casilla but
    # its withholding does not".
    #
    # Deliberately ONE member across every ledger family. Which family raised it
    # is already on the diagnostic as source_kind (and binding_source derived
    # from it), so a per-family member would carry nothing a consumer cannot
    # already read while growing this Literal once per family -- the opposite
    # gradient to the one the shared screen exists to produce. The consequence
    # differs by family (a vanishing retención credit is a settlement error, a
    # missing base imponible is a completeness error) and that belongs in the
    # message, not in a routing key nothing routes on.
    "unrouted_declarable_quantity",
    # A fourth axis beside the one above, and OBSERVATION-INDEPENDENT unlike
    # it: "unrouted_declarable_quantity" needs a real row whose fact is
    # uncovered by a binding that DOES exist; this fires when no binding on
    # the revision could EVER draw a present category's base, for any row of
    # that category, before this taxpayer's own row is even considered. True
    # or false from the registry alone. Advisory rather than blocking -- the
    # affected categories are typically cuota-less by law, so no tax is lost,
    # only the base itself has nowhere on this revision to land.
    "structurally_unroutable_base_category",
    # A row a binding DOES consume, but without the invoice substrate the
    # binding's fact assumes: its contribution rests on bank cash (or is
    # absent). Distinct from "unrouted_observation", which is a row no binding
    # consumes at all.
    "ungrounded_income_substrate",
    # A row whose LINKED sales invoice could not be trusted, so it declares
    # bank cash instead of the invoice base. Distinct from
    # "ungrounded_income_substrate", where no invoice was linked at all: here
    # the operator did the linking and the link itself is what needs repair.
    "unusable_sales_invoice_evidence",
    # An invoice folded into this period whose LIVA art. 75 devengo date was
    # not recorded, so its issue date stood in for it. The figures are the best
    # available, not a legal determination: an operation performed near a
    # quarter boundary and invoiced in the next one is declared in the wrong
    # period by exactly this substitution.
    "devengo_date_proxy_attribution",
    "oss_no_live_source",
    "missing_transaction_evidence",
    "administrador_retencion_rate_mismatch",
    # An ISSUED-side retención the ledger INFERRED from a cash shortfall whose
    # figure is no statutory rate product. The shortfall may be a bank fee, a
    # discount, or a disputed line rather than tax withheld, in which case the
    # credit is an over-claim. Screened on the rate rather than on the inference
    # marker so the correct domestic-B2B majority stays silent.
    "inferred_retencion_rate_unmatched",
    # The weaker sibling: the inferred figure DOES equal a statutory sectoral
    # rate, but 1 % and 2 % are small enough that a bank fee or discount reaches
    # them by accident. Kept a separate reason rather than a reworded message so
    # an automated operator routes on the field; the two carry different
    # epistemic weight and must not be collapsed.
    "inferred_retencion_sectoral_rate_unconfirmed",
    # A Modelo 349 clave the resolver INFERRED from the invoice's IVA category
    # because the record stated no operation type. Correct for an ordinary LIVA
    # art. 25 exempt supply, but a supply following an exempt importation (art.
    # 27.12) reports under clave "M" or "H", and the invoice carries no fact
    # separating the two. Raised only when the bucket also holds an importation,
    # so it cannot fire on a taxpayer for whom "E" is the only available clave.
    "m349_clave_inferred_from_category",
    # An invoice denominated in a foreign currency with no resolved euro rate,
    # withheld from an informativa because its euro value is unknown. Excluding
    # the AMOUNT is correct -- declaring the foreign face value as euro would
    # misstate it. What this reason exists for is the OPERATION: it is real and
    # declarable, only its euro figure is missing, so an informativa that simply
    # omits it leaves the operator filing an incomplete return. Kept distinct
    # from `unrouted_observation` because the remedy is different: that one
    # needs a binding, this one needs a conversion rate on the record.
    "unconverted_foreign_currency",
    # A Modelo 347 filer carries a declaring role (art. 31's claves C/D/E
    # population) whose clave depends on a transaction-level fact this
    # invoice leaves UNDECLARED (tri-state ``None``, not ``False``): whether
    # an acquisition is al margen de la actividad empresarial (clave D), or
    # whether a payment is a subvención/auxilio/ayuda (clave E). Neither a
    # silent ``False`` (under-declares the population the role exists to
    # cover) nor a silent ``True`` (over-declares) is acceptable, so an
    # undeclared fact surfaces here instead of picking a side.
    "unclassified_declarant_role_fact",
    # An invoice whose declared IVA treatment and whose counterparty contradict
    # each other: an intra-community supply to a third country, or an export to
    # a member state. Routing on the category alone would declare volume the
    # taxpayer never supplied that way, so the line is withheld -- and this
    # reason exists so the withholding is reported rather than silent. The
    # bank-transaction path returns a typed gate issue for the same shape; the
    # invoice projector returns observations, so it reports through here.
    "invoice_category_counterparty_mismatch",
    # A received reverse charge whose line carries no rated slot. The recipient
    # owes the self-assessed cuota (LIVA art. 84.Uno.2), the supplier charges
    # nothing, and the record states no rate to apply -- so the figure cannot be
    # derived without asserting which rate the supply bore. Refusing to invent it
    # is correct; refusing silently would file a quietly short return, which is
    # what this reason prevents.
    "invoice_reverse_charge_cuota_not_derivable",
    # The recorded recargo departs from the rate art. 161 publishes for that
    # slot. A cross-check beside the declared figure, never a replacement of it.
    "invoice_recargo_departs_from_published_rate",
    "official_box_unpopulated",
    "prior_payment_not_deducted",
    "prior_payment_minoracion_not_captured",
    "settlement_not_computed",
    "prorrata_especial_obligatoria",
    "prorrata_especial_check_unavailable",
    "dt12_regime_window_closed",
    "dt12_regime_window_unverified",
    "dt12_parcial_rescate_guidance",
    # A rate-keyed official box layer that accounts for LESS than the rate-blind
    # total it breaks down. Not an unrouted quantity: the money IS routed, into
    # the total, and the return declares it in full. What is missing is a rate
    # for it, so no box may claim one -- which makes this the one advisory whose
    # remedy is a ledger edit rather than a registry or resolver gap, and the one
    # the export gate later refuses on.
    "rate_boxes_underaccount_total",
    # A casilla whose aggregation resolved to ZERO over a NON-EMPTY income set,
    # because every contributing row was excluded by an activity narrowing the
    # operator has no channel to satisfy. The exclusion itself is correct and is
    # NOT what this reports -- admitting an undeclared row would route a
    # non-agrarian filer's income into an agrarian box, the over-declaration
    # error. What it reports is that the box is empty for a reason invisible from
    # the box: income exists in the period and no activity is declared for it.
    # Deliberately makes no claim ABOUT the income's activity, because nothing in
    # the ledger establishes one -- that absence is the finding.
    "aggregation_activity_undeclared",
    # An operator-supplied casilla value that REPLACED a value the resolvers
    # computed for the same casilla, where the two differ. Not an error: the
    # operator wins by design, because the facts behind a regularizacion may
    # live outside the ledger. What it discloses is that a derived figure was
    # discarded, which nothing else on this path says out loud. Distinct from
    # every unrouted reason: nothing here is missing from the return, one of two
    # available figures was chosen over the other.
    "operator_override_diverges_from_computed",
]


def _binding_source_for_token(value: object) -> BindingSourceKind | None:
    if isinstance(value, BindingSourceKind):
        return value
    if not isinstance(value, str):
        return None
    token = value.strip()
    if not token:
        return None
    try:
        return BindingSourceKind(token)
    except ValueError:
        return None


def _infer_binding_source(payload: object) -> object:
    """Hydrate ``binding_source`` when the free ``source_kind`` token is canonical."""
    if not isinstance(payload, Mapping):
        return payload
    data = STR_KEYED_MAPPING_ADAPTER.validate_python(payload)
    source = _binding_source_for_token(data.get("source_kind"))
    source_kind = data.get("source_kind")
    if isinstance(source_kind, BindingSourceKind):
        data["source_kind"] = source_kind.value

    explicit = data.get("binding_source")
    if explicit is None:
        if source is not None:
            data["binding_source"] = source
        return data

    explicit_source = _binding_source_for_token(explicit)
    if explicit_source is not None:
        data["binding_source"] = explicit_source
    if source is not None and explicit_source is not None and source is not explicit_source:
        raise SourceMeshError("aggregation.source_mesh.errors.binding_source_mismatch")
    return data


# Source kinds that are explicitly deferred — known to the closed taxonomy, but
# no mesh resolver is built yet. A deferred kind must produce a standing
# advisory on source_diagnostics rather than a silent blank: the boundary gate
# (in _calculation_actions) accepts it without flagging it as an unknown-novel
# source, and the safety net (``collect_unhandled_source_diagnostics``) emits the
# advisory. A deferred kind is never on the ``manual_sources`` allowlist, which
# would suppress that advisory.
#
# The detail-row producers need a row taxonomy, an evidence shape, and a
# detail-record fold before a resolver can exist. Inventory is absent here
# because its repository resolver is enrolled by the canonical calculation
# route; runtime repository construction remains a separate composition step.
DEFERRED_SOURCE_KINDS: frozenset[BindingSourceKind] = frozenset(
    {
        BindingSourceKind.RELATED_PARTY_OPERATION,
        BindingSourceKind.REFUND_OPERATION,
        BindingSourceKind.DONATIVO_DONOR,
        BindingSourceKind.GASTO193_CONTRIBUTOR,
        BindingSourceKind.WITHHOLDING296,
    },
)

# Source kinds reserved-undeclared: a member that exists in the closed taxonomy
# but carries no registry binding and no resolver yet (counterpart / invoice-shaped
# headroom). They are neither enrolled nor deferred-with-advisory; the disposition
# registry records them RESERVED so the parity gate accounts for every member.
RESERVED_SOURCE_KINDS: frozenset[BindingSourceKind] = frozenset(
    {
        BindingSourceKind.PURCHASE_INVOICE_EVIDENCE,
        BindingSourceKind.LEDGER_TRANSACTION,
    },
)


class CallerOverrideDisposition(StrEnum):
    """Whether the calculate path permits a caller override of a source's value.

    The override disposition axis of the caller-override precedence ladder.

    Members:
        LOCK: Deterministic bucket-owned resolvers (ledger aggregations,
            invoice families, inventory projection, and other complete source
            authorities). A caller override is REJECTED so the persisted
            revision faithfully reflects the sources it aggregates.
        CARRY: Carry-style sources (previous_filing, relation_prefill, the
            IVA-compensation annual partition, and prorrata regularizacion).
            A caller override of an
            automatically-carried prior value is legitimate and must reach the
            engine, so these are EXCLUDED from the post-merge caller-override
            guard.
    """

    LOCK = "lock"
    CARRY = "carry"


class CallerOverridePrecedenceTier(NamedTuple):
    """One ordered tier of the calculate-path caller-override precedence ladder.

    Carries the tier name, the source kinds it owns, and the override disposition
    the guard applies to them. The ordered ladder is the single declaration the
    caller-override guard sets are derived from — :data:`CALLER_OVERRIDE_PRECEDENCE_LADDER`
    replaces the hand-listed lock / carry frozensets, and a conformance test binds
    the policy's derived sets to it so the two cannot silently diverge.
    """

    name: str
    source_kinds: frozenset[BindingSourceKind]
    disposition: CallerOverrideDisposition


#: The calculate-path caller-override precedence ladder as ordered tier data,
#: lowest-precedence tier first. The
#: guard's lock and carry source sets are the unions of the LOCK- and
#: CARRY-disposition tiers (see :func:`precedence_ladder_sources`). This encodes
#: the override DISPOSITION axis only; the merge OVERLAY order (profile < mesh
#: backend < borrador < caller, later tier wins) is enforced separately by
#: :func:`merge_source_resolutions`.
CALLER_OVERRIDE_PRECEDENCE_LADDER: tuple[CallerOverridePrecedenceTier, ...] = (
    CallerOverridePrecedenceTier(
        name="deterministic_lock",
        source_kinds=frozenset(
            {
                BindingSourceKind.LEDGER_IVA_AGGREGATION,
                BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION,
                BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,
                BindingSourceKind.LEDGER_RENTA_GASTOS_PAGO_FRACCIONADO_AGGREGATION,
                BindingSourceKind.LEDGER_IMPATRIADO_INCOME_AGGREGATION,
                BindingSourceKind.LEDGER_IRNR_INCOME_AGGREGATION,
                BindingSourceKind.LEDGER_OSS_AGGREGATION,
                BindingSourceKind.COLLECTIBLE_INVOICE,
                BindingSourceKind.PAYABLE_INVOICE,
                BindingSourceKind.M347_THIRD_PARTY_OPERATION,
                BindingSourceKind.M303_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY,
                BindingSourceKind.INVENTORY,
            },
        ),
        disposition=CallerOverrideDisposition.LOCK,
    ),
    CallerOverridePrecedenceTier(
        name="carry_forward",
        source_kinds=frozenset(
            {
                BindingSourceKind.PREVIOUS_FILING,
                BindingSourceKind.RELATION_PREFILL,
                BindingSourceKind.IVA_COMPENSATION_ANNUAL_PARTITION,
                BindingSourceKind.PRORRATA_REGULARIZACION,
            },
        ),
        disposition=CallerOverrideDisposition.CARRY,
    ),
)


def precedence_ladder_sources(disposition: CallerOverrideDisposition) -> frozenset[BindingSourceKind]:
    """Union of the source kinds carried by every ladder tier of ``disposition``.

    The single derivation the caller-override policy sets read, so a source kind's
    lock-vs-carry disposition is declared once in
    :data:`CALLER_OVERRIDE_PRECEDENCE_LADDER` rather than hand-listed per set.

    Returns:
        The :class:`BindingSourceKind` members carried by every ladder tier
        whose disposition matches *disposition*.
    """
    return frozenset(
        kind
        for tier in CALLER_OVERRIDE_PRECEDENCE_LADDER
        if tier.disposition is disposition
        for kind in tier.source_kinds
    )


class BindingSourceDisposition(StrEnum):
    """Where a binding source kind resolves on the live calculate mesh.

    The single closed answer to "where does source X resolve" for every
    :class:`~core.BindingSourceKind` member, replacing the four scattered
    enrollment structures (the ``merge_source_resolutions`` resolver tuple, the
    pre-mesh-handled set, ``DEFERRED_SOURCE_KINDS``, and the per-modelo service
    provider enum).
    """

    ENROLLED = "enrolled"  # routed by an active resolver / pre-mesh tier on the live calculate path
    DEFERRED = "deferred"  # known but no resolver yet; emits a standing advisory, never a silent blank
    RESERVED = "reserved"  # in the taxonomy but no binding and no resolver yet (counterpart/invoice headroom)


class CompositeSourceResolverId(StrEnum):
    """Closed identities owned only by source-resolution composition."""

    EXCLUSIVE_MESH = "source_mesh"
    PRECEDENCE_MESH = "source_mesh_precedence"


def build_binding_source_dispositions(
    enrolled_sources: frozenset[BindingSourceKind],
) -> Mapping[BindingSourceKind, BindingSourceDisposition]:
    """Classify every :class:`BindingSourceKind` member by its live mesh :class:`BindingSourceDisposition`.

    ``enrolled_sources`` is the LIVE enrolled set read at execution time -- the
    union of every active resolver's ``owned_sources`` plus the pre-mesh tiers and
    ``manual_input`` -- so no disposition is hard-coded; a newly-enrolled source
    (e.g. withholding, or profile / borrador now folded into the mesh) is reflected
    automatically. ``DEFERRED_SOURCE_KINDS`` and ``RESERVED_SOURCE_KINDS`` supply the
    other two states. Raises if a member is in two states at once, or in none
    (an unaccounted source kind -- the "neither set contains the other" defect).
    """
    dispositions: dict[BindingSourceKind, BindingSourceDisposition] = {}
    for member in BindingSourceKind:
        states = (
            (member in enrolled_sources, BindingSourceDisposition.ENROLLED),
            (member in DEFERRED_SOURCE_KINDS, BindingSourceDisposition.DEFERRED),
            (member in RESERVED_SOURCE_KINDS, BindingSourceDisposition.RESERVED),
        )
        matched = [disposition for present, disposition in states if present]
        if len(matched) != 1:
            raise AggregationValidationError(
                t("aggregation.source_mesh.errors.ambiguous_source_disposition"),
                context={
                    "source_kind": member.value,
                    "matched_dispositions": [disposition.value for disposition in matched],
                },
            )
        dispositions[member] = matched[0]
    return MappingProxyType(dispositions)


class CalculationSourceContext(BaseModel):
    """Context supplied to a calculation source resolver.

    The ``period`` field is the typed :class:`~core.Period` value
    carrying both the filing year and the bare registry period code.  Consumers
    that need the raw token for a downstream ``str``-typed API should use
    ``context.period.registry_token``; those that need only the year can use
    ``context.period.filing_year`` (which mirrors ``context.filing_year``).
    """

    model_config = _STRICT_FROZEN

    bucket_id: BucketId
    # Normal calculate routes carry the exact selected work unit.  Legacy
    # resolver-unit tests may intentionally construct a context without one;
    # a resolver that requires target calculation identity must refuse that
    # incomplete context rather than select by coordinate alone.
    work_unit_id: WorkUnitId | None = None
    modelo: str = Field(min_length=1, max_length=16)
    filing_year: FilingYear
    period: Period
    revision: ModeloRevision
    m210_official_tipo_renta_code: str | None = Field(default=None, min_length=2, max_length=2)
    m210_gross_income_source_mode: M210GrossIncomeSourceMode | None = None
    calculated_at: datetime | None = None


#: Cap on a diagnostic's operator-facing message.
DIAGNOSTIC_MESSAGE_MAX_LENGTH: Final[int] = 512

#: The message annotation: elides rather than refusing.
#:
#: These are NON-BLOCKING advisories, and refusing one turns it into a blocking
#: failure -- the model raises, ``calculate`` exits with a raw validation error,
#: and the filing stops at exactly the moment the advisory had something to say.
#: That is strictly worse than the advisory being shortened, so the cap is
#: enforced by cutting rather than by raising. See
#: :func:`~core.prose_elision.ElidedProse` for why the cap is a property of the
#: type rather than of each call site.
_DiagnosticMessage = Annotated[str, ElidedProse(DIAGNOSTIC_MESSAGE_MAX_LENGTH)]

#: Cap on a diagnostic's operator-facing remedy.
#:
#: Bounded like every other string on this model, but bounded to REFUSE where
#: ``message`` is bounded to elide, and the asymmetry is deliberate. A message
#: interpolates the taxpayer's own data, so its length is a property of the
#: household and a filer with many descendants must never be the one whose
#: advisory turns into a blocking error. A remedy is fixed prose naming a
#: command: its length is a property of what the author typed, so an overrun is
#: an authoring mistake that should surface loudly at authoring time rather than
#: be silently cut in front of an operator. Any remedy that ever does
#: interpolate taxpayer data must move to an eliding bound instead.
DIAGNOSTIC_REMEDY_MAX_LENGTH: Final[int] = 512


class CalculationSourceDiagnostic(BaseModel):
    """Diagnostic emitted while resolving source-backed calculation values."""

    model_config = _STRICT_FROZEN

    reason: CalculationSourceDiagnosticReason
    source_kind: str = Field(min_length=1, max_length=64)
    binding_source: BindingSourceKind | None = None
    """Canonical binding source when ``source_kind`` names one; ``None`` for advisory categories."""
    message: _DiagnosticMessage
    remedy: str | None = Field(default=None, min_length=1, max_length=DIAGNOSTIC_REMEDY_MAX_LENGTH)
    """What the operator should DO about it, carried apart from what happened.

    Separated because the two are read at different moments and bounded against
    different pressures. ``message`` states the problem and is the part whose
    length scales with taxpayer data -- a household's worth of interpolated
    descendant paths lands there -- while the remedy is fixed prose naming a
    command. Fusing them made the fixed half compete for room against the
    variable half, so the filers with the most at stake were the ones whose
    remedy got cut.

    Projected as the advisory's operator remedy at the CLI boundary. ``None``
    where the advisory discloses a state with no action attached to it."""
    resolver_id: str | None = Field(default=None, min_length=1, max_length=128)
    source_ref: str | None = Field(default=None, min_length=1, max_length=256)
    binding_id: BindingId | None = None
    relation_id: RelationId | None = None
    relation_ids: tuple[RelationId, ...] = ()
    """Every relation this ONE diagnostic speaks for, when it groups several.

    A diagnostic naming a missing source filing is about the FILING, not
    about any one relation reading it — Modelo 190's ten annual-summary
    relations sourcing the same absent Modelo 111 return are ten symptoms of
    one cause, and reporting them as ten separate advisories trains an
    operator to stop reading the channel. :attr:`relation_id` stays populated
    with the lowest sorted member for a caller that only ever consulted the
    singular field before this one existed; this field is the FULL
    machine-readable set the grouped advisory actually covers. Empty for a
    diagnostic that was never about more than one relation to begin with —
    absence means "nothing to add beyond `relation_id`", not "unknown".
    """
    casilla_id: CasillaId | None = None
    legal_refs: tuple[LegalRefId, ...] = ()
    """Registry legal references grounding the subject this advisory speaks about.

    Empty on an advisory whose subject is a mechanism rather than a regulated
    value -- a degraded store, a duplicate owner -- and populated by READING the
    grounding off the registry definitions the advisory already resolved, never
    by restating an article in this layer. An advisory about a casilla carries
    that casilla's own refs (and its binding's, where a binding is the subject),
    at parity with the provenance channel beside it: an operator asked to act on
    a regulated figure needs the provision that establishes it, and prose in
    ``message`` is not a field a machine consumer can route on.

    This is the CASILLA-DERIVED path: the subject is the casilla's (or its
    binding's) own computation, and the refs are read off a registry object the
    advisory already holds, never minted here. For an advisory whose subject is
    instead a rule the advisory itself is asserting -- an eligibility condition
    governing one of the casilla's INPUTS, which the casilla's own refs do not
    describe -- use :attr:`asserted_legal_refs`, not this field. Reading a
    casilla's whole-article refs onto a claim about one apartado of it produces a
    ref coarser than the claim, which is worse than no ref at all: it looks
    corroborated and is not.
    """
    source_refs: tuple[SourceRefId, ...] = ()
    """Official AEAT source references grounding this advisory's subject.

    The ``source_refs`` half of the pair above, carried for the same reason and
    populated from the same registry definitions. Casilla-derived, at parity
    with :attr:`legal_refs`.
    """
    asserted_legal_refs: tuple[LegalRefId, ...] = ()
    """Legal-catalogue ids the advisory asserts ITSELF, distinct from any casilla.

    The ADVISORY-ASSERTED path, not a replacement for :attr:`legal_refs` and not
    replaced by it -- the two coexist because they answer different questions.
    ``legal_refs`` describes what establishes the casilla the advisory happens
    to be about; this field describes the provision the advisory's own MESSAGE
    is a claim about, which is what a message such as "Art. 61 norma 1 halves
    this" or an eligibility-rule disclosure asserts. That claim is a property of
    the advisory, not of the casilla it addresses, and a casilla's whole-article
    refs are frequently coarser than it.

    Every id here is validated at registry build to resolve to a
    :class:`~domain.calculations.registry.LegalReference` catalogue entry --
    the check a prose-only message could never carry. Declaring an id here is a
    TAX REVIEW against the provision the message states, never a mechanical
    derivation from a casilla or binding already in hand: copying the
    :attr:`legal_refs` construction pattern (reading a casilla's or binding's own
    refs) onto this field reproduces exactly the coarse-ref defect this field
    exists to avoid.
    """
    out_of_window_count: int | None = Field(default=None, ge=1)
    out_of_window_min_filing_date: date | None = None
    out_of_window_max_filing_date: date | None = None

    @model_validator(mode="before")
    @classmethod
    def _set_binding_source(cls, value: object) -> object:
        return _infer_binding_source(value)

    @model_validator(mode="after")
    def _validate_out_of_window_summary(self) -> Self:
        count = self.out_of_window_count
        min_filing_date = self.out_of_window_min_filing_date
        max_filing_date = self.out_of_window_max_filing_date
        if count is None and min_filing_date is None and max_filing_date is None:
            return self
        if count is None or min_filing_date is None or max_filing_date is None:
            raise SourceMeshError("aggregation.source_mesh.errors.out_of_window_summary_incomplete")
        if max_filing_date < min_filing_date:
            raise SourceMeshError("aggregation.source_mesh.errors.out_of_window_summary_date_span_invalid")
        return self


def out_of_window_summary_message(
    *,
    count: int,
    min_filing_date: date,
    max_filing_date: date,
) -> str:
    """Return the standard source-diagnostic message for summarized period exclusions."""
    return (
        f"{count} ledger transaction(s) have filing dates outside the requested period "
        f"({min_filing_date.isoformat()}..{max_filing_date.isoformat()}); "
        "excluded by period before classification"
    )


def out_of_window_summary_source_diagnostic(
    *,
    source_kind: str,
    resolver_id: str,
    count: int,
    min_filing_date: date,
    max_filing_date: date,
) -> CalculationSourceDiagnostic:
    """Build one structured source diagnostic for summarized ``OUTSIDE_PERIOD`` rows."""
    return CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind=source_kind,
        resolver_id=resolver_id,
        message=out_of_window_summary_message(
            count=count,
            min_filing_date=min_filing_date,
            max_filing_date=max_filing_date,
        ),
        out_of_window_count=count,
        out_of_window_min_filing_date=min_filing_date,
        out_of_window_max_filing_date=max_filing_date,
    )


def casilla_registry_legal_refs(revision: ModeloRevision, casilla_id: CasillaId) -> tuple[LegalRefId, ...]:
    """Return one casilla's own legal grounding, plus its binding's, off ``revision``.

    The CASILLA-DERIVED path shared by every advisory whose subject IS the
    named casilla's own computation: :attr:`CalculationSourceDiagnostic.legal_refs`
    is populated by READING this off the registry definitions the caller already
    resolved, never by restating an article in the caller's own layer. Ordered
    union, casilla first: the casilla is the subject an operator reads about, and
    the binding grounds the route the value would have taken.

    Returns an empty tuple when ``casilla_id`` is absent from ``revision`` --
    the caller's subject casilla is not on this filing, which is a statement
    about the registry rather than about the taxpayer, or when the casilla
    carries no grounding of its own.
    """
    casilla = next((candidate for candidate in revision.casillas if candidate.id == casilla_id), None)
    if casilla is None:
        return ()
    binding = next((candidate for candidate in revision.bindings if candidate.id == casilla.binding), None)
    binding_legal = binding.legal_refs if binding is not None else ()
    return tuple(dict.fromkeys((*casilla.legal_refs, *binding_legal)))


class CalculationSourceProvenance(BaseModel):
    """One primary or contributing node in a resolver-owned provenance graph."""

    model_config = _STRICT_FROZEN

    resolver_id: str = Field(min_length=1, max_length=128)
    resolved_binding_source: BindingSourceKind
    contributor_source_kind: str = Field(min_length=1, max_length=64)
    contributor_binding_source: BindingSourceKind | None
    lineage_role: CalculationSourceLineageRole
    source_ref: str = Field(min_length=1, max_length=256)
    parent_source_ref: str | None = Field(min_length=1, max_length=256)
    fingerprint: str | None = Field(default=None, min_length=1, max_length=256)
    relation_id: RelationId | None = None
    source_modelo: ModeloId | None = None
    source_filing_year: FilingYear | None = None
    source_periods: tuple[str, ...] = ()
    source_casilla_ids: tuple[CasillaId, ...] = ()
    legal_refs: tuple[LegalRefId, ...] = ()
    source_refs: tuple[SourceRefId, ...] = ()
    #: The registry's declared dependency treatment for this carry, empty when the
    #: revision declares none. A ``factual_evidence`` carry is a fact to reconcile
    #: against rather than a figure that settles the return, and a consumer must be
    #: able to tell it from a ``direct_annual_settlement`` one. Carried here rather
    #: than gated here: the value is NOT withheld, because a taxpayer is entitled to
    #: a suffered retención and dropping it silently is an over-declaration. Empty
    #: means the revision declared no treatment, which is not the same as any
    #: particular one and must never be read as one.
    dependency_treatment: str = ""

    @model_validator(mode="after")
    def _require_coherent_lineage(self) -> CalculationSourceProvenance:
        try:
            contributor_kind = BindingSourceKind(self.contributor_source_kind)
        except ValueError:
            contributor_kind = None
        if self.contributor_binding_source is None:
            if contributor_kind is not None:
                raise SourceMeshError("aggregation.source_mesh.errors.provenance_binding_source_missing")
        elif contributor_kind is not self.contributor_binding_source:
            raise SourceMeshError("aggregation.source_mesh.errors.provenance_binding_source_mismatch")
        if self.lineage_role is CalculationSourceLineageRole.PRIMARY:
            if self.parent_source_ref is not None:
                raise SourceMeshError("aggregation.source_mesh.errors.provenance_primary_has_parent")
        elif self.parent_source_ref is None:
            raise SourceMeshError("aggregation.source_mesh.errors.provenance_contributor_missing_parent")
        return self

    @model_validator(mode="after")
    def _relation_provenance_is_complete(self) -> CalculationSourceProvenance:
        if self.relation_id is None:
            return self
        if (
            self.source_modelo is None
            or self.source_filing_year is None
            or not self.source_periods
            or not self.source_casilla_ids
            or not self.legal_refs
            or not self.source_refs
        ):
            raise SourceMeshError("aggregation.source_mesh.errors.relation_provenance_incomplete")
        return self


class BorradorSourceProvenance(BaseModel):
    """Typed borrador-snapshot provenance carried on a source resolution.

    The AEAT borrador snapshot is the one source whose downstream consumer
    (``persist_calculation_revision``) needs more than the generic
    :class:`CalculationSourceProvenance` row: it persists the originating
    ``borrador_snapshot_id`` and the sorted ``bindings_sourced_from_borrador``
    trace onto the :class:`CalculationRevision`. Carrying that as ONE typed
    sub-model keeps the generic :class:`CalculationSourceResolution` envelope
    from accreting per-source named fields while preserving the trace as typed
    data the call site reads directly -- never by parsing the
    ``borrador:{id}:binding:{bid}`` provenance ``source_ref`` strings.
    """

    model_config = _STRICT_FROZEN

    snapshot_id: SnapshotId
    bindings_sourced: tuple[BindingId, ...] = Field(default_factory=tuple)


class CalculationSourceResolution(BaseModel):
    """Resolved values and provenance returned by one source resolver."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    resolver_id: str | CompositeSourceResolverId = Field(min_length=1, max_length=128)
    owned_sources: tuple[BindingSourceKind, ...] = Field(default_factory=tuple)
    binding_values: Mapping[BindingId, Decimal] = Field(default_factory=dict)
    enum_binding_values: Mapping[BindingId, str] = Field(default_factory=dict)
    date_binding_values: Mapping[BindingId, date] = Field(default_factory=dict)
    row_binding_values: Mapping[RowBindingKey, RowBindingValue] = Field(default_factory=_empty_row_binding_values)
    row_source_identities: Mapping[RowBindingKey, RowSourceIdentity] = Field(
        default_factory=_empty_row_source_identities,
        exclude=True,
        repr=False,
    )
    row_casilla_values: Mapping[RowCasillaKey, Decimal] = Field(default_factory=_empty_row_casilla_values)
    row_casilla_provenance: Mapping[RowCasillaKey, DirectRowMaterializationProvenance] = Field(
        default_factory=_empty_row_casilla_provenance,
        exclude=True,
        repr=False,
    )
    relation_values: Mapping[RelationId, Decimal] = Field(default_factory=dict)
    unresolved_relation_ids: tuple[RelationId, ...] = Field(default_factory=tuple)
    unresolved_binding_ids: tuple[BindingId, ...] = Field(default_factory=tuple)
    bound_inputs_by_casilla_id: Mapping[CasillaId, Decimal] = Field(default_factory=dict)
    detail_rows: tuple[ModeloDetailRow, ...] = Field(default_factory=tuple)
    source_transaction_ids: Sequence[str] = Field(default_factory=tuple)
    # Typed borrador provenance. Carried only by the borrador resolution
    # (``Modelo100BorradorSourceResolver``); ``merge_source_resolutions``
    # preserves it onto the merged result so the calculate call site reads the
    # snapshot id and sourced-binding set as TYPED data and hands them to
    # ``persist_calculation_revision``. ``None`` for every other resolver.
    borrador_provenance: BorradorSourceProvenance | None = None
    # The persisted cross-model annual-summary input is a single frozen carrier,
    # not a binding channel.  It remains separate so a later persistence layer
    # cannot reconstruct it from scalar values or provenance strings.
    m303_regimen_simplificado_annual_summary_handoff: M303RegimenSimplificadoAnnualSummaryHandoff | None = None
    diagnostics: tuple[CalculationSourceDiagnostic, ...] = Field(default_factory=tuple)
    provenance: tuple[CalculationSourceProvenance, ...] = Field(default_factory=tuple)

    @field_validator("owned_sources", mode="before")
    @classmethod
    def _coerce_owned_sources(cls, value: object) -> object:
        """Hydrate known bare source-token strings to their :class:`BindingSourceKind` member.

        The model carries :data:`~core.STRICT_FROZEN_CONFIG` (``strict=True``),
        which disables string→enum coercion. Resolvers declare their owned source as a
        canonical token and may pass either the member or its bare string value; this
        before-validator maps each KNOWN bare string to its member (the
        ``BindingAggregation._coerce_op`` precedent in :mod:`core.aggregation`) so
        the field stays strictly typed while a known token still validates. A blank
        string raises :class:`SourceMeshError`; any other non-member value is left
        untouched for the strict field to reject with its standard enum error, so a
        genuine typo is still caught — without minting a new diagnostic locale key.
        """
        if not isinstance(value, (tuple, list)):
            return value
        coerced: list[object] = []
        for item in OBJECT_TUPLE_ADAPTER.validate_python(value):
            if isinstance(item, BindingSourceKind):
                coerced.append(item)
                continue
            if isinstance(item, str):
                stripped = item.strip()
                if not stripped:
                    raise SourceMeshError("aggregation.source_mesh.errors.owned_sources_blank")
                try:
                    coerced.append(BindingSourceKind(stripped))
                except ValueError:
                    # Unknown token: leave it for the strict typed field to reject.
                    coerced.append(item)
                continue
            coerced.append(item)
        return tuple(coerced)

    @field_validator("owned_sources")
    @classmethod
    def _owned_sources_are_unique(cls, value: tuple[BindingSourceKind, ...]) -> tuple[BindingSourceKind, ...]:
        # After the before-coercer, every item is a canonical BindingSourceKind member
        # (no blank/whitespace possible). Guard uniqueness and sort by the stable string
        # value so the carrier is deterministic, preserving members (never downgrading
        # them to bare str).
        if len(value) != len(set(value)):
            raise SourceMeshError("aggregation.source_mesh.errors.owned_sources_duplicate")
        return tuple(sorted(value, key=lambda source: source.value))

    @field_validator("binding_values")
    @classmethod
    def _freeze_binding_values(cls, value: Mapping[BindingId, Decimal]) -> Mapping[BindingId, Decimal]:
        return MappingProxyType(dict(sorted(value.items())))

    @field_validator("enum_binding_values")
    @classmethod
    def _freeze_enum_binding_values(cls, value: Mapping[BindingId, str]) -> Mapping[BindingId, str]:
        return MappingProxyType(dict(sorted(value.items())))

    @field_validator("date_binding_values")
    @classmethod
    def _freeze_date_binding_values(cls, value: Mapping[BindingId, date]) -> Mapping[BindingId, date]:
        return MappingProxyType(dict(sorted(value.items())))

    @field_validator("row_binding_values", mode="before")
    @classmethod
    def _coerce_row_binding_values(cls, value: object) -> object:
        if isinstance(value, Mapping):
            return _ROW_BINDING_VALUES.validate_python(value)
        if not isinstance(value, (list, tuple)):
            return value
        items = OBJECT_TUPLE_ADAPTER.validate_python(value)
        normalized: dict[tuple[object, object], object] = {}
        for item in items:
            if not isinstance(item, Mapping):
                return items
            row = STR_KEYED_MAPPING_ADAPTER.validate_python(item)
            row_value = row.get("value")
            if row.get("value_kind") == "decimal":
                row_value = coerce_decimal(row_value)
                if row_value is None:
                    raise SourceMeshError("aggregation.source_mesh.errors.row_binding_value_invalid")
            normalized[(row.get("binding_id"), row.get("row_index"))] = row_value
        return normalized

    @field_validator("row_binding_values")
    @classmethod
    def _freeze_row_binding_values(
        cls,
        value: Mapping[RowBindingKey, RowBindingValue],
    ) -> Mapping[RowBindingKey, RowBindingValue]:
        normalized: dict[RowBindingKey, RowBindingValue] = {}
        for (binding_id, row_index), row_value in value.items():
            if row_index < 1:
                raise SourceMeshError("aggregation.source_mesh.errors.row_binding_index_invalid")
            normalized[(binding_id, row_index)] = row_value
        return MappingProxyType(dict(sorted(normalized.items(), key=lambda item: (item[0][0], item[0][1]))))

    @field_validator("row_source_identities", mode="before")
    @classmethod
    def _coerce_row_source_identities(cls, value: object) -> object:
        if isinstance(value, Mapping):
            return _ROW_SOURCE_IDENTITIES.validate_python(value)
        if not isinstance(value, (list, tuple)):
            return value
        items = OBJECT_TUPLE_ADAPTER.validate_python(value)
        normalized: dict[tuple[object, object], object] = {}
        for item in items:
            if not isinstance(item, Mapping):
                return items
            row = STR_KEYED_MAPPING_ADAPTER.validate_python(item)
            normalized[(row.get("binding_id"), row.get("row_index"))] = {
                "source_kind": row.get("source_kind"),
                "source_row_identity": row.get("source_row_identity"),
                "fingerprint": row.get("fingerprint"),
                "row_set_grouping": row.get("row_set_grouping"),
            }
        return normalized

    @field_validator("row_source_identities")
    @classmethod
    def _freeze_row_source_identities(
        cls,
        value: Mapping[RowBindingKey, RowSourceIdentity],
    ) -> Mapping[RowBindingKey, RowSourceIdentity]:
        normalized: dict[RowBindingKey, RowSourceIdentity] = {}
        for (binding_id, row_index), identity in value.items():
            if row_index < 1:
                raise SourceMeshError("aggregation.source_mesh.errors.row_binding_index_invalid")
            normalized[(binding_id, row_index)] = identity
        return MappingProxyType(dict(sorted(normalized.items(), key=lambda item: (item[0][0], item[0][1]))))

    @field_validator("row_casilla_values", mode="before")
    @classmethod
    def _coerce_row_casilla_values(cls, value: object) -> object:
        if isinstance(value, Mapping):
            return _ROW_CASILLA_VALUES.validate_python(value)
        if not isinstance(value, (list, tuple)):
            return value
        items = OBJECT_TUPLE_ADAPTER.validate_python(value)
        normalized: dict[tuple[object, object], object] = {}
        for item in items:
            if not isinstance(item, Mapping):
                return items
            row = STR_KEYED_MAPPING_ADAPTER.validate_python(item)
            key = (row.get("casilla_id"), row.get("row_index"))
            if key in normalized:
                raise SourceMeshError("aggregation.source_mesh.errors.duplicate_row_casilla_coordinate")
            row_value = coerce_decimal(row.get("value"))
            if row_value is None:
                raise SourceMeshError("aggregation.source_mesh.errors.row_casilla_value_invalid")
            normalized[key] = row_value
        return normalized

    @field_validator("row_casilla_values")
    @classmethod
    def _freeze_row_casilla_values(cls, value: Mapping[RowCasillaKey, Decimal]) -> Mapping[RowCasillaKey, Decimal]:
        normalized: dict[RowCasillaKey, Decimal] = {}
        for (casilla_id, row_index), row_value in value.items():
            if row_index < 1:
                raise SourceMeshError("aggregation.source_mesh.errors.row_casilla_index_invalid")
            normalized[(casilla_id, row_index)] = row_value
        return MappingProxyType(dict(sorted(normalized.items(), key=lambda item: (item[0][0], item[0][1]))))

    @field_validator("row_casilla_provenance", mode="before")
    @classmethod
    def _coerce_row_casilla_provenance(cls, value: object) -> object:
        if isinstance(value, Mapping):
            return _ROW_CASILLA_PROVENANCE.validate_python(value)
        if not isinstance(value, (list, tuple)):
            return value
        items = OBJECT_TUPLE_ADAPTER.validate_python(value)
        normalized: dict[tuple[object, object], object] = {}
        for item in items:
            if not isinstance(item, Mapping):
                return items
            row = STR_KEYED_MAPPING_ADAPTER.validate_python(item)
            key = (row.get("casilla_id"), row.get("row_index"))
            if key in normalized:
                raise SourceMeshError("aggregation.source_mesh.errors.duplicate_row_casilla_coordinate")
            normalized[key] = {
                "source_binding_id": row.get("source_binding_id"),
                "source_row_index": row.get("source_row_index"),
                "source_identity": row.get("source_identity"),
                "materialization_rule_id": row.get("materialization_rule_id"),
                "materialization_rule_version": row.get("materialization_rule_version"),
            }
        return normalized

    @field_validator("row_casilla_provenance")
    @classmethod
    def _freeze_row_casilla_provenance(
        cls,
        value: Mapping[RowCasillaKey, DirectRowMaterializationProvenance],
    ) -> Mapping[RowCasillaKey, DirectRowMaterializationProvenance]:
        normalized: dict[RowCasillaKey, DirectRowMaterializationProvenance] = {}
        for (casilla_id, row_index), provenance in value.items():
            if row_index < 1:
                raise SourceMeshError("aggregation.source_mesh.errors.row_casilla_index_invalid")
            normalized[(casilla_id, row_index)] = provenance
        return MappingProxyType(dict(sorted(normalized.items(), key=lambda item: (item[0][0], item[0][1]))))

    @field_validator("relation_values")
    @classmethod
    def _freeze_relation_values(cls, value: Mapping[RelationId, Decimal]) -> Mapping[RelationId, Decimal]:
        return MappingProxyType(dict(sorted(value.items())))

    @field_validator("unresolved_relation_ids")
    @classmethod
    def _freeze_unresolved_relation_ids(cls, value: tuple[RelationId, ...]) -> tuple[RelationId, ...]:
        normalized = tuple(item.strip() for item in value)
        if any(not item for item in normalized):
            raise SourceMeshError("aggregation.source_mesh.errors.unresolved_relation_ids_blank")
        if len(normalized) != len(set(normalized)):
            raise SourceMeshError("aggregation.source_mesh.errors.unresolved_relation_ids_duplicate")
        return tuple(sorted(normalized))

    @field_validator("unresolved_binding_ids")
    @classmethod
    def _freeze_unresolved_binding_ids(cls, value: tuple[BindingId, ...]) -> tuple[BindingId, ...]:
        normalized = tuple(item.strip() for item in value)
        if any(not item for item in normalized):
            raise SourceMeshError("aggregation.source_mesh.errors.unresolved_binding_ids_blank")
        if len(normalized) != len(set(normalized)):
            raise SourceMeshError("aggregation.source_mesh.errors.unresolved_binding_ids_duplicate")
        return tuple(sorted(normalized))

    @field_validator("bound_inputs_by_casilla_id")
    @classmethod
    def _freeze_bound_inputs_by_casilla_id(cls, value: Mapping[CasillaId, Decimal]) -> Mapping[CasillaId, Decimal]:
        return MappingProxyType(dict(sorted(value.items())))

    @field_validator("source_transaction_ids")
    @classmethod
    def _freeze_source_transaction_ids(cls, value: Sequence[str]) -> tuple[str, ...]:
        normalized = tuple(item.strip() for item in value)
        if any(not item for item in normalized):
            raise SourceMeshError("aggregation.source_mesh.errors.source_transaction_ids_blank")
        if len(normalized) != len(set(normalized)):
            raise SourceMeshError("aggregation.source_mesh.errors.source_transaction_ids_duplicate")
        return tuple(sorted(normalized))

    @model_validator(mode="after")
    def _row_source_identities_have_row_values(self) -> CalculationSourceResolution:
        """Refuse orphan identities while row producers migrate independently.

        Existing row producers remain outside this new identity-bearing contract
        until their own source-specific migration is adjudicated. Every identity
        coordinate must already carry a row value; source-specific cohort gates
        own any stronger completeness requirement.
        """
        if not set(self.row_source_identities).issubset(self.row_binding_values):
            raise SourceMeshError("aggregation.source_mesh.errors.row_source_identity_coordinate_mismatch")
        return self

    @model_validator(mode="after")
    def _row_casillas_are_an_exact_direct_materialization(self) -> CalculationSourceResolution:
        if set(self.row_casilla_values) != set(self.row_casilla_provenance):
            raise SourceMeshError("aggregation.source_mesh.errors.row_casilla_provenance_coordinate_mismatch")
        for (casilla_id, casilla_row_index), provenance in self.row_casilla_provenance.items():
            source_key = (provenance.source_binding_id, provenance.source_row_index)
            source_value = self.row_binding_values.get(source_key)
            source_identity = self.row_source_identities.get(source_key)
            if source_value is None or source_identity is None:
                raise SourceMeshError("aggregation.source_mesh.errors.row_casilla_source_coordinate_missing")
            if casilla_row_index != provenance.source_row_index:
                raise SourceMeshError("aggregation.source_mesh.errors.row_casilla_row_index_mismatch")
            if (
                not isinstance(source_value, Decimal)
                or self.row_casilla_values[(casilla_id, casilla_row_index)] != source_value
            ):
                raise SourceMeshError("aggregation.source_mesh.errors.row_casilla_source_value_mismatch")
            if provenance.source_identity != source_identity:
                raise SourceMeshError("aggregation.source_mesh.errors.row_casilla_source_identity_mismatch")
        return self

    @model_validator(mode="after")
    def _provenance_names_its_producing_resolver(self) -> CalculationSourceResolution:
        primary_refs = tuple(
            row.source_ref for row in self.provenance if row.lineage_role is CalculationSourceLineageRole.PRIMARY
        )
        if len(primary_refs) != len(set(primary_refs)):
            raise SourceMeshError("aggregation.source_mesh.errors.provenance_primary_ref_ambiguous")
        primary_ref_set = frozenset(primary_refs)
        if any(
            row.parent_source_ref not in primary_ref_set
            for row in self.provenance
            if row.lineage_role is CalculationSourceLineageRole.CONTRIBUTOR
        ):
            raise SourceMeshError("aggregation.source_mesh.errors.provenance_contributor_parent_missing")
        if isinstance(self.resolver_id, CompositeSourceResolverId):
            return self
        if self.resolver_id in set(CompositeSourceResolverId):
            raise SourceMeshError("aggregation.source_mesh.errors.reserved_composite_resolver_id")
        mismatched = tuple(row.resolver_id for row in self.provenance if row.resolver_id != self.resolver_id)
        if mismatched:
            raise SourceMeshError("aggregation.source_mesh.errors.provenance_resolver_mismatch")
        return self

    @field_serializer("binding_values")
    def _serialize_binding_values(self, value: Mapping[BindingId, Decimal]) -> dict[BindingId, Decimal]:
        return dict(value)

    @field_serializer("enum_binding_values")
    def _serialize_enum_binding_values(self, value: Mapping[BindingId, str]) -> dict[BindingId, str]:
        return dict(value)

    @field_serializer("date_binding_values")
    def _serialize_date_binding_values(self, value: Mapping[BindingId, date]) -> dict[BindingId, date]:
        return dict(value)

    @field_serializer("row_binding_values")
    def _serialize_row_binding_values(
        self,
        value: Mapping[RowBindingKey, RowBindingValue],
    ) -> tuple[dict[str, object], ...]:
        return tuple(
            {
                "binding_id": binding_id,
                "row_index": row_index,
                "value": row_value,
                "value_kind": "decimal" if isinstance(row_value, Decimal) else "text",
            }
            for (binding_id, row_index), row_value in value.items()
        )

    @field_serializer("row_casilla_values")
    def _serialize_row_casilla_values(
        self,
        value: Mapping[RowCasillaKey, Decimal],
    ) -> tuple[dict[str, object], ...]:
        return tuple(
            {"casilla_id": casilla_id, "row_index": row_index, "value": row_value}
            for (casilla_id, row_index), row_value in value.items()
        )

    @field_serializer("relation_values")
    def _serialize_relation_values(self, value: Mapping[RelationId, Decimal]) -> dict[RelationId, Decimal]:
        return dict(value)

    @field_serializer("unresolved_relation_ids")
    def _serialize_unresolved_relation_ids(self, value: tuple[RelationId, ...]) -> tuple[RelationId, ...]:
        return tuple(value)

    @field_serializer("unresolved_binding_ids")
    def _serialize_unresolved_binding_ids(self, value: tuple[BindingId, ...]) -> tuple[BindingId, ...]:
        return tuple(value)

    @field_serializer("bound_inputs_by_casilla_id")
    def _serialize_bound_inputs_by_casilla_id(self, value: Mapping[CasillaId, Decimal]) -> dict[CasillaId, Decimal]:
        return dict(value)

    @field_serializer("source_transaction_ids")
    def _serialize_source_transaction_ids(self, value: Sequence[str]) -> tuple[str, ...]:
        return tuple(value)


@runtime_checkable
class ModeloSourceResolver(Protocol):
    """Application port implemented by one calculation source adapter."""

    resolver_id: ClassVar[str] = ""
    """Stable class-level resolver identifier for registration and provenance."""

    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = ()
    """Class-level registry source ownership used by registration and instances."""

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        """Resolve source-backed calculation values for ``context``.

        Returns a :class:`CalculationSourceResolution` carrying resolved
        binding values, provenance, and any source diagnostics.
        """
        ...


__all__ = [
    "CALLER_OVERRIDE_PRECEDENCE_LADDER",
    "DEFERRED_SOURCE_KINDS",
    "RESERVED_SOURCE_KINDS",
    "BindingSourceDisposition",
    "BorradorSourceProvenance",
    "CalculationSourceContext",
    "CalculationSourceDiagnostic",
    "CalculationSourceDiagnosticReason",
    "CalculationSourceProvenance",
    "CalculationSourceResolution",
    "CallerOverrideDisposition",
    "CallerOverridePrecedenceTier",
    "ModeloSourceResolver",
    "RowBindingKey",
    "RowBindingValue",
    "RowSourceIdentity",
    "build_binding_source_dispositions",
    "out_of_window_summary_message",
    "out_of_window_summary_source_diagnostic",
    "precedence_ladder_sources",
]
