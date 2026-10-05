"""Strict pydantic records for the authenticated AEAT sede surface.

Every record represents a read-only AEAT filing, document, or
notification observation. The schema is intentionally narrow so
malformed or unsupported AEAT response shapes fail during parsing.

Every boundary-crossing record carries ``mode: Literal["read"]``. That
field is a DOCUMENTATION AND TEST marker, not a runtime guard: nothing
in production reads it, so it constrains a record's declared shape and
nothing else. It was previously described here as "part of the
structural write-guard", which credited it with protection it does not
provide.

The package does not mutate AEAT state, but that is a property the
guards below MAINTAIN rather than one the type system makes impossible.
Stating it as a structural incapability is what this note exists to
stop, because a reader asking whether this boundary can write is asking
the right question and deserves the real answer:

* A forbidden-verb scan over the package's own source text
  (``_no_write_surface_fixture.txt``, enforced by
  ``tests/test_no_write_surface.py``) rejects mutation verbs in a call
  position — ``submit``, ``presentar``, ``firmar``, ``pagar`` and the
  rest. It deliberately ALLOWS the browser-interaction verbs
  (``click``, ``fill``, ``press``, ``check``, ``select_option``),
  because reads here are driven by opening selectors and submitting
  consulta forms.
* ``_assert_read_http`` refuses any non-GET method on a
  FIRST-PARTY HTTP call. A form POST issued by the browser after a
  ``click`` never reaches it, so it does not bound browser-driven
  navigation.
* A landing refusal rejects a page AEAT dispatched to that the
  surface does not declare as one of its read pages. This is the only
  wall that sees where a browser-driven navigation actually ENDED, and
  it is the one the others' blind spots leave to it. Every module that
  drives an AEAT control now carries one, each with its own allow-list
  because the surfaces genuinely differ -- the Renta WEB Open simulator
  is served from ``index.zul``, which the censal reader's marker list
  forbids outright, so one shared list cannot serve every surface. The
  shared runtime rule is ``_adapter_utils.assert_read_landing``.

The residual this note previously named -- a ``page.click`` on a filing
control in a module with no landing refusal, passing the verb scan
(``click`` is allowed), ``_assert_read_http`` (never consulted for a
browser POST) and this ``mode`` marker (never read) -- is now a
mechanism rather than a matter of review: adding such a click to an
unenrolled module fails the enrollment gate.

What remains true, and is stated so nobody mistakes the above for more
than it is: the enrollment gate is a SOURCE scan, so it establishes that
a landing rule is called from a navigation path, never that the rule's
allow-list is correct for the surface. That second question is answered
per module by that module's own proof, and only against the AEAT
behaviour observed so far.

Public surface: :class:`FiledDeclaracionArtefact`,
:class:`ObservedCasillaValue`, :class:`FiledDeclaracionObservation`,
:class:`FiledDeclarationAvailability`,
:class:`FiledDeclarationAvailabilityReport`.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, Field, NonNegativeInt, field_validator, model_validator

from .....core.casilla_id import CasillaId
from .....core.casilla_value_kind import CasillaValueKind
from .....core.decimal.coercion import coerce_decimal_strict
from .....core.errors.hierarchy import pydantic_validation_boundary
from .....core.filed_history_discovery_signal import FiledHistoryDiscoverySignal
from .....core.filing_year import FILING_YEAR_MAX, FILING_YEAR_MIN, FilingYear
from .....core.identity.aeat_expediente import AeatExpedienteId
from .....core.identity.digest import ContentDigest
from .....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core.observed_header_fact import ObservedHeaderFact
from .....core.period import Period
from .....core.time.utc import UtcInstant
from .....core.unit_proportion import UnitFraction
from .....domain.calculations.registry.schema_references import RegistrySnapshotRef
from .errors import SedeValidationError


class FiledDeclaracionArtefact(BaseModel):
    """One immutable artefact captured from AEAT's filed-declaration surface.

    The artefact is evidence of what AEAT served during a read-only
    session. It is not calculation authority; legal/formula authority
    remains in BOE, AEAT instructions, manuals, and registry definitions.
    """

    model_config = _STRICT_FROZEN

    kind: Literal["register_row", "submitted_file", "declaration_pdf", "justificante_pdf"]
    source_url: AnyHttpUrl
    content_type: str = Field(min_length=1, max_length=255)
    byte_count: NonNegativeInt
    sha256: ContentDigest
    captured_at: datetime
    storage_ref: str | None = Field(default=None, min_length=1, max_length=4096)
    mode: Literal["read"] = "read"


class ObservedCasillaValue(BaseModel):
    """One casilla value observed from an AEAT filed-data artefact.

    ``value`` keeps the artefact's own token as text; ``value_kind`` carries the
    parser's decision about how that text is meant to be read. Read a number
    through :meth:`decimal_value` rather than converting ``value`` directly --
    the conversion succeeds on text that merely looks numeric.
    """

    model_config = _STRICT_FROZEN

    casilla_id: CasillaId
    value: str = Field(min_length=1, max_length=4096)
    value_kind: CasillaValueKind
    source_artefact_kind: Literal[
        "submitted_file",
        "declaration_pdf",
        "justificante_pdf",
        "derived_registry_formula",
        "derived_carry_policy",
    ]
    source_locator: str = Field(min_length=1, max_length=512)
    confidence: UnitFraction
    mode: Literal["read"] = "read"

    def decimal_value(self) -> Decimal:
        """Return the observed amount, refusing any casilla that is not numeric.

        The kind check comes BEFORE the conversion, and that order is the whole
        point. :func:`~core.decimal.coercion.coerce_decimal_strict` is the canonical strict
        coercion and this method delegates to it rather than adding a third
        implementation, but it is strict about parse FAILURE and knows nothing
        about the declaration -- ``coerce_decimal_strict("15")`` returns
        ``Decimal("15")`` and is right to, because nothing in that token says it
        is an epígrafe IAE. Only the kind can say so. Converting first and asking
        questions afterwards is how a free-text Modelo 100 casilla enrols as an
        amount.

        No gate is watching this call site. The string-to-Decimal enrollment gate
        governs ``entrypoints/`` and ``application/`` only, so this adapter is
        outside its scope; and its matcher resolves no attribute types, so it
        would not see an attribute read even in scope. The accessor test is the
        enforcement -- keep it.

        Raises:
            SedeValidationError: When the casilla is not
                :attr:`~core.casilla_value_kind.CasillaValueKind.NUMERIC`.
            decimal.InvalidOperation: When a numeric casilla carries an
                unparseable token.
        """
        if self.value_kind is not CasillaValueKind.NUMERIC:
            raise SedeValidationError(
                f"casilla {self.casilla_id!r} is {self.value_kind.value}, not numeric; "
                "its value is not an amount and must not be read as one",
            )
        return coerce_decimal_strict(self.value)


class ObservedCasillaSkip(BaseModel):
    """One casilla the Decimal-only registry channel cannot carry.

    Enumerated by
    :func:`~adapters.outbound.aeat.sede.declarations_observations.non_numeric_observed_casillas` so a
    caller can refuse, log, or surface a diagnostic, rather than being folded
    into the enrolment result. The check is caller-opt-in: a caller with no
    operator surface to report on has nothing to do with these rows.

    There is deliberately NO value field, and adding one later would be a
    regression rather than an enrichment. The casillas that land here are the
    non-numeric ones, which on Modelo 100 include a referencia catastral
    (``0066``) and the taxpayer's street address (``0069``); these rows are
    built to be rendered to an operator, so carrying the value would put
    personal data on that surface. The casilla id and its registry label say
    which field was skipped without disclosing what it holds.
    """

    model_config = _STRICT_FROZEN

    casilla_id: CasillaId
    label: str = Field(min_length=1, max_length=512)
    value_kind: CasillaValueKind
    reason: Literal["not_numeric", "unreadable_numeric_token"]


class IvaCompensationWalletRow(BaseModel):
    """One AEAT wallet row for IVA compensation generated in a source period.

    The row represents external AEAT state, not a filed-declaration casilla. It
    maps one line of AEAT's "Cartera de cuotas de IVA a compensar" detail table:
    the period that generated the credit plus its still-available balance
    (the "Cuota Disponible" column), carried in ``pending_amount``.

    AEAT's read-only cartera consultation surface exposes only the available
    balance per generation period; it does not break out the original generated
    amount or the cumulative applied amount. ``generated_amount`` and
    ``applied_amount`` are therefore optional and stay ``None`` for this surface,
    reserved for a richer AEAT view that itemises the movement columns.
    """

    model_config = _STRICT_FROZEN

    generation_year: FilingYear
    generation_period: Period
    generated_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    applied_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    pending_amount: Decimal = Field(ge=Decimal("0"))
    raw_label: str | None = Field(default=None, min_length=1, max_length=256)
    mode: Literal["read"] = "read"


class IvaCompensationWalletObservation(BaseModel):
    """Read-only observation of AEAT's IVA compensation wallet.

    Produced by the authenticated Sede wallet reader. Calculation code
    must not consume this record directly; it is raw evidence consumed
    by the reconciliation layer, which emits the effective binding
    decision for Modelo 303 casilla `110`.
    """

    model_config = _STRICT_FROZEN

    taxpayer_nif: str = Field(min_length=1, max_length=32)
    authenticated_identity: str = Field(min_length=1, max_length=32)
    target_modelo: Literal["303"] = "303"
    target_year: FilingYear
    target_period: Period
    rows: tuple[IvaCompensationWalletRow, ...] = ()
    total_pending: Decimal = Field(ge=Decimal("0"))
    source_url: AnyHttpUrl
    captured_at: datetime
    raw_sha256: ContentDigest | None = None
    mode: Literal["read"] = "read"


class FiledDeclarationAvailability(BaseModel):
    """The ejercicios the declaraciones register OFFERS for one modelo.

    Read from the register form's own combobox option lists, so this record
    states what AEAT's UI put in front of the session — nothing more. Whether
    those lists are scoped to the authenticated NIF or are a static universal
    catalogue the form renders for every taxpayer is UNCONFIRMED; a reader must
    not upgrade ``ejercicios`` into "the years this taxpayer filed", and an
    ejercicio ABSENT from the tuple is not evidence that nothing was filed for
    it. Provenance is pinned on the enclosing
    :class:`FiledDeclarationAvailabilityReport`.

    Attributes:
        modelo: Modelo code as carried by the combobox option, e.g. ``"303"``.
            Parsed off the leading ``"<modelo> -"`` segment of the option text.
        ejercicios: Every ejercicio the register offered for ``modelo``,
            newest-first so a caller walking the tuple reaches recent filings
            before historical ones.
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=8)
    ejercicios: tuple[int, ...] = ()
    mode: Literal["read"] = "read"

    @field_validator("ejercicios")
    @classmethod
    @pydantic_validation_boundary
    def _ejercicios_in_range(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        """Reject an ejercicio outside the range every other record in this module accepts."""
        for ejercicio in value:
            if not FILING_YEAR_MIN <= ejercicio <= FILING_YEAR_MAX:
                error = SedeValidationError(
                    f"ejercicio outside the supported range [{FILING_YEAR_MIN}, {FILING_YEAR_MAX}]: {ejercicio!r}"
                )
                raise ValueError(str(error)) from error
        return value


class FiledDeclarationAvailabilityReport(BaseModel):
    """What the declaraciones register offered across every modelo it listed.

    The report is tagged
    :attr:`~core.filed_history_discovery_signal.FiledHistoryDiscoverySignal.AEAT_REGISTER_OPTIONS` and the tag
    is a pinned :class:`~typing.Literal`, not a caller-supplied field, so this
    record can never be passed off as the taxpayer-specific
    :attr:`~core.filed_history_discovery_signal.FiledHistoryDiscoverySignal.PROFILE_APPLICABILITY` signal. It
    is read-only evidence of an offered option set and persists nothing.

    Attributes:
        items: One :class:`FiledDeclarationAvailability` per modelo option the
            register listed, in the order the combobox rendered them.
        discovered_at: When the option sets were read.
        signal: Pinned provenance. Always
            :attr:`~core.filed_history_discovery_signal.FiledHistoryDiscoverySignal.AEAT_REGISTER_OPTIONS`.
    """

    model_config = _STRICT_FROZEN

    items: tuple[FiledDeclarationAvailability, ...] = ()
    discovered_at: UtcInstant
    signal: Literal[FiledHistoryDiscoverySignal.AEAT_REGISTER_OPTIONS] = (
        FiledHistoryDiscoverySignal.AEAT_REGISTER_OPTIONS
    )
    mode: Literal["read"] = "read"

    @property
    def offered_pairs(self) -> tuple[tuple[str, int], ...]:
        """Return every offered ``(modelo, ejercicio)`` pair, in report order."""
        return tuple((item.modelo, ejercicio) for item in self.items for ejercicio in item.ejercicios)


class FiledDeclaracionObservation(BaseModel):
    """Normalized read-only observation of one filed AEAT declaration.

    A complete observation starts from the register row and may include
    submitted machine-readable data, declaration PDFs, and justificante
    PDFs. Parsed casillas are observations only; downstream calculation
    logic must validate them through registry extraction profiles.

    ``headers`` carries the diseño header facts AEAT states in the submitted
    fichero -- the tipo de declaración, the sin-actividad and REDEME markers --
    as typed :class:`~core.observed_header_fact.ObservedHeaderFact` rows rather than in the flat
    ``metadata`` map. A header is not a casilla, so it does not belong in
    ``casillas``; and it is not free-form provenance text, so a flat map loses
    the record-design position that makes it auditable. ``metadata`` remains the
    home for register-row provenance that genuinely is untyped text.
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=8)
    ejercicio: FilingYear
    period: Period
    expediente_id: AeatExpedienteId
    status: str = Field(min_length=1, max_length=32)
    presented_at: datetime
    authenticated_identity: str = Field(min_length=1, max_length=32)
    artefacts: tuple[FiledDeclaracionArtefact, ...] = Field(min_length=1)
    casillas: tuple[ObservedCasillaValue, ...] = ()
    headers: tuple[ObservedHeaderFact, ...] = ()
    metadata: dict[str, str] = Field(default_factory=dict)
    extraction_coverage: dict[str, float] = Field(default_factory=dict)
    registry_snapshot_ref: RegistrySnapshotRef
    mode: Literal["read"] = "read"

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _registry_coordinate_matches_observation(self) -> FiledDeclaracionObservation:
        ref = self.registry_snapshot_ref
        if ref.modelo != self.modelo or ref.modelo_year != self.ejercicio or ref.period != self.period.registry_token:
            raise ValueError("filed declaration registry_snapshot_ref must match modelo, ejercicio, and period")
        return self


__all__ = [
    "FiledDeclaracionArtefact",
    "FiledDeclaracionObservation",
    "FiledDeclarationAvailability",
    "FiledDeclarationAvailabilityReport",
    "IvaCompensationWalletObservation",
    "IvaCompensationWalletRow",
    "ObservedCasillaValue",
]
