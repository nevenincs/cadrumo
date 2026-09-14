"""Cross-cutting Convenio doble imposición (CDI) treaty-override authority.

A development compiler reads the registry authoring surface into the immutable
artifact. This runtime module retains only the resulting treaty authority types
that any IRNR rate formula consumes through the
:class:`~domain.calculations.registry.RegistrySnapshot` — so a second consumer
(M216 retenciones a no residentes) reads treaty data without reaching across a
modelo boundary.

Each override row carries a typed :class:`~core.ConvenioOverrideKind` so the
"más favorable" / limitation-of-benefits decision is computed rather than
coincidental: ``flat`` replaces the domestic rate, ``ceiling`` applies
``min(domestic, treaty)``, ``allocation_domestic_tariff`` delegates the amount to
the domestic tariff, and ``exempt`` drives the source-state rate to zero.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated, cast

from pydantic import Field, field_validator, model_validator

from ....core.decimal.constants import ONE, ZERO
from ....core.frozen_mapping import FROZEN_MAPPING
from ....core.irnr import ConvenioOverrideKind, TipoRentaIrnr
from .errors import RegistryValidationError
from .ids import LegalRefId
from .schema_base import DateAxis, RegistryModel

if TYPE_CHECKING:
    from .authority import PinnedAuthorityOperation, ValidatedRegistryAuthority
    from .facts.resolution import ResolvedOverrideFact
    from .governed_fact_scope import GovernedFactSource


def _validated_override_rate(
    kind: ConvenioOverrideKind,
    value: object,
    *,
    tipo_renta: TipoRentaIrnr,
) -> Decimal | None:
    """Validate and normalize one registry-owned convenio rate projection."""
    if kind.value in {"flat", "ceiling"}:
        if value is None:
            raise RegistryValidationError(
                f"convenio override kind {kind.value!r} requires a rate for tipo_renta {tipo_renta.value!r}",
            )
        if not isinstance(value, (str, Decimal)):
            raise RegistryValidationError(
                f"convenio override rate must be a parseable Decimal; got {value!r}",
            )
        try:
            parsed = Decimal(value)
        except (ArithmeticError, ValueError) as exc:
            raise RegistryValidationError(
                f"convenio override rate must be a parseable Decimal; got {value!r}",
            ) from exc
        if not parsed.is_finite() or parsed < ZERO or parsed > ONE:
            raise RegistryValidationError(
                f"convenio override rate must be within [0, 1]; got {value!r}",
            )
        return parsed
    if kind.value not in {"allocation_domestic_tariff", "exempt"}:
        raise RegistryValidationError(f"unsupported convenio override kind {kind.value!r}")
    if value is not None:
        raise RegistryValidationError(
            f"convenio override kind {kind.value!r} must not declare a rate "
            f"(the amount is delegated to the domestic tariff or driven to zero)",
        )
    return None


class ConvenioOverrideRow(RegistryModel):
    """One per-income-type treaty override keyed by :class:`~core.TipoRentaIrnr`.

    The typed :class:`~core.ConvenioOverrideKind` decides how the row acts on
    the domestic IRNR rate. ``flat`` and ``ceiling`` rows MUST declare a ``rate``
    in ``[0, 1]``; ``allocation_domestic_tariff`` and ``exempt`` rows MUST NOT (the
    amount is delegated to the domestic tariff or driven to zero). The
    ``legal_ref_anchor`` MUST be one of the row's ``legal_refs`` and resolve to a
    treaty article in the shared ``legal/`` catalogue.
    """

    tipo_renta: TipoRentaIrnr
    kind: ConvenioOverrideKind
    rate: str | None = Field(default=None, max_length=32)
    legal_ref_anchor: LegalRefId
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    notes: str | None = Field(default=None, max_length=512)
    valid_from: date
    valid_to: date | None = None

    @field_validator("tipo_renta", mode="before")
    @classmethod
    def _coerce_tipo_renta(cls, value: object) -> object:
        """Hydrate the TOML token into the opaque tipo-renta wire type."""
        if isinstance(value, str) and not isinstance(value, TipoRentaIrnr):
            return TipoRentaIrnr._from_registry(value)
        return value

    @field_validator("kind", mode="before")
    @classmethod
    def _coerce_kind(cls, value: object) -> object:
        """Hydrate the TOML ``kind`` string into an opaque registry token."""
        if isinstance(value, str) and not isinstance(value, ConvenioOverrideKind):
            return ConvenioOverrideKind._from_registry(value)
        return value

    @model_validator(mode="after")
    def _validate_override_row(self) -> ConvenioOverrideRow:
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValueError("convenio override valid_to must be on or after valid_from")
        try:
            _validated_override_rate(self.kind, self.rate, tipo_renta=self.tipo_renta)
        except RegistryValidationError as exc:
            # Pydantic validators must expose malformed authored rows as a
            # ValidationError.  The pure rate resolver deliberately retains
            # RegistryValidationError for runtime callers.
            raise ValueError(str(exc)) from exc
        if self.legal_ref_anchor not in self.legal_refs:
            raise ValueError("convenio override legal_ref_anchor must be included in legal_refs")
        return self

    @property
    def rate_decimal(self) -> Decimal | None:
        """The parsed ``rate`` for a rate-bearing kind, else ``None``."""
        return _validated_override_rate(self.kind, self.rate, tipo_renta=self.tipo_renta)


class ConvenioTreaty(RegistryModel):
    """One bilateral double-taxation treaty and its per-income-type overrides.

    Projected from the canonical ``irnr.convenio.override`` governed fact and
    keyed by the counterpart ``country_code`` (ISO 3166-1 alpha-2). The optional
    permanent-establishment / employment-income surfaces are deliberately not
    modelled yet; the schema leaves room for them without foreclosing.
    """

    country_code: str = Field(min_length=2, max_length=2, pattern=r"^[A-Z]{2}$")
    document_id: str = Field(min_length=1, max_length=64)
    overrides: tuple[ConvenioOverrideRow, ...] = Field(min_length=1)
    notes: str | None = Field(default=None, max_length=512)

    @model_validator(mode="after")
    def _validate_treaty(self) -> ConvenioTreaty:
        seen: set[tuple[TipoRentaIrnr, date]] = set()
        for row in self.overrides:
            key = (row.tipo_renta, row.valid_from)
            if key in seen:
                raise ValueError(
                    f"convenio treaty {self.country_code!r} declares a duplicate override for "
                    f"tipo_renta {row.tipo_renta.value!r} from {row.valid_from.isoformat()}",
                )
            seen.add(key)
        return self


class ConvenioOverride(RegistryModel):
    """The resolved treaty override returned by :meth:`ConvenioAuthority.resolve`.

    A flat projection of the matched :class:`ConvenioOverrideRow` bound to its
    treaty's ``country_code`` and ``document_id`` — the shape the IRNR rate op and
    the modelo verification sweep branch on. ``rate`` is populated only for
    the rate-bearing kinds (``flat`` / ``ceiling``).
    """

    country_code: str
    document_id: str
    tipo_renta: TipoRentaIrnr
    kind: ConvenioOverrideKind
    rate: Decimal | None
    legal_refs: tuple[LegalRefId, ...]


class ConvenioAuthority(RegistryModel):
    """The compiled cross-cutting treaty authority projected onto every snapshot.

    Owns the ``{country_code: ConvenioTreaty}`` map and the single
    :meth:`resolve` lookup any IRNR rate formula consumes. Projected onto the
    :class:`~domain.calculations.registry.RegistrySnapshot` the same way the
    shared ``legal/`` catalogue is, so the treaty override is one branch of the
    single tipo-de-gravamen resolution path, never a parallel rate mechanism.
    """

    treaties: Annotated[Mapping[str, ConvenioTreaty], FROZEN_MAPPING] = Field(
        default_factory=dict, validate_default=True
    )

    @classmethod
    def empty(cls) -> ConvenioAuthority:
        """Return a :class:`ConvenioAuthority` with no treaties (the no-override default)."""
        return cls(treaties={})

    def resolve(self, country_code: str, tipo_renta: TipoRentaIrnr, year: int) -> ConvenioOverride | None:
        """Return the :class:`ConvenioOverride` for ``(country_code, tipo_renta, year)``, or ``None``.

        ``None`` means no treaty row applies — the caller keeps the domestic
        baseline (no country declared) or raises the missing-row BLOCKING
        sentinel (a treaty country was declared but carries no row for the
        filed income type), never a silent blank.
        """
        treaty = self.treaties.get(country_code.upper())
        if treaty is None:
            return None
        for row in treaty.overrides:
            if (
                row.tipo_renta == tipo_renta
                and row.valid_from.year <= year
                and (row.valid_to is None or row.valid_to.year >= year)
            ):
                return ConvenioOverride(
                    country_code=treaty.country_code,
                    document_id=treaty.document_id,
                    tipo_renta=row.tipo_renta,
                    kind=row.kind,
                    rate=row.rate_decimal,
                    legal_refs=row.legal_refs,
                )
        return None

    def all_legal_refs(self) -> frozenset[LegalRefId]:
        """Every ``legal_ref`` cited by any override row across every treaty."""
        return frozenset(ref for treaty in self.treaties.values() for row in treaty.overrides for ref in row.legal_refs)


CONVENIO_OVERRIDE_FACT_ID = "irnr.convenio.override"


@dataclass(frozen=True, slots=True)
class ResolvedConvenioOverride:
    """One provider-selected treaty override with legal provenance."""

    kind: ConvenioOverrideKind
    rate: Decimal | None
    country_code: str
    document_id: str
    fact: ResolvedOverrideFact

    @property
    def is_exempt(self) -> bool:
        """Whether the selected registry row drives the source rate to zero."""
        return self.kind.value == "exempt"

    @property
    def has_flat_rate(self) -> bool:
        """Whether the selected registry row replaces the domestic rate."""
        return self.kind.value == "flat"

    @property
    def has_ceiling_rate(self) -> bool:
        """Whether the selected registry row caps the domestic rate."""
        return self.kind.value == "ceiling"

    @property
    def delegates_to_domestic_tariff(self) -> bool:
        """Whether the selected registry row delegates to the domestic tariff."""
        return self.kind.value == "allocation_domestic_tariff"


def resolve_convenio_override(
    *,
    country_code: str,
    tipo_renta: TipoRentaIrnr,
    devengo_date: date,
    authority: GovernedFactSource | None = None,
    operation: PinnedAuthorityOperation | None = None,
) -> ResolvedConvenioOverride | None:
    """Resolve and validate the exact dated treaty fact, or return no row.

    Registry corruption, an ambiguous selection, unsupported payloads, and
    missing legal provenance remain registry refusals.  Only the absence of a
    matching dated selector is represented by ``None``.
    """
    from .facts.resolution import OverrideFactQuery, ResolvedOverrideFact
    from .facts.schema import FactSelector

    if not isinstance(tipo_renta, TipoRentaIrnr):
        raise RegistryValidationError("convenio override requires a TipoRentaIrnr value")
    from .irnr_tipo_renta import require_tipo_renta_irnr

    if operation is None and authority is not None and hasattr(authority, "pin"):
        operation = cast("PinnedAuthorityOperation", authority)
        authority = None
    if authority is not None and operation is not None:
        raise TypeError("convenio resolution accepts either authority or operation, not both")
    selected = operation or authority
    if selected is None:
        from .governed_fact_scope import governed_facts_in_scope

        selected = governed_facts_in_scope()
        if selected is None:
            raise RegistryValidationError("convenio resolution requires an explicit operation or scoped fact source")
        authority = selected
    tipo_renta = require_tipo_renta_irnr(tipo_renta, effective_date=devengo_date, authority=selected)
    normalized_country = country_code.upper()
    selectors = (
        FactSelector(name="country_code", value=normalized_country),
        FactSelector(name="tipo_renta", value=tipo_renta.value),
    )
    selector_identity = frozenset((selector.name, type(selector.value), selector.value) for selector in selectors)
    query = OverrideFactQuery(
        fact_id=CONVENIO_OVERRIDE_FACT_ID,
        date_axis=DateAxis.DEVENGO_DATE,
        effective_date=devengo_date,
        selectors=selectors,
    )
    if operation is None and authority is not None and not hasattr(authority, "catalogues"):
        try:
            resolved = selected.resolve_governed_fact(query)
        except RegistryValidationError as exc:
            if "no variant" in str(exc).lower() or "not registered" in str(exc).lower():
                return None
            raise
        fact = None
    else:
        if operation is None:
            validated = cast("ValidatedRegistryAuthority", selected)
            fact = validated.catalogues.facts.facts.get(CONVENIO_OVERRIDE_FACT_ID)
        else:
            fact = operation.governed_fact(CONVENIO_OVERRIDE_FACT_ID)
        if fact is None:
            raise RegistryValidationError(f"governed fact {CONVENIO_OVERRIDE_FACT_ID!r} is not registered")
        if not any(
            variant.date_axis is DateAxis.DEVENGO_DATE
            and variant.valid_from is not None
            and variant.valid_from <= devengo_date
            and (variant.valid_to is None or devengo_date <= variant.valid_to)
            and frozenset((selector.name, type(selector.value), selector.value) for selector in variant.selectors)
            == selector_identity
            for variant in fact.variants
        ):
            return None
        resolved = selected.resolve_governed_fact(query)
    if not isinstance(resolved, ResolvedOverrideFact):
        raise RegistryValidationError(f"convenio override resolved non-override fact {resolved.fact_id!r}")
    raw_kind = resolved.payload.override_code
    declared_override_codes = (
        frozenset(
            code
            for variant in fact.variants
            if isinstance(code := getattr(variant.payload, "override_code", None), str)
        )
        if fact is not None
        else frozenset({raw_kind})
    )
    if raw_kind not in declared_override_codes:
        raise RegistryValidationError(
            f"convenio override fact {resolved.fact_id!r} has undeclared kind {raw_kind!r}",
        )
    try:
        kind = ConvenioOverrideKind._from_registry(raw_kind)
    except (TypeError, ValueError) as exc:
        raise RegistryValidationError(
            f"convenio override fact {resolved.fact_id!r} has invalid kind {raw_kind!r}",
        ) from exc
    rate = _validated_override_rate(kind, resolved.payload.value, tipo_renta=tipo_renta)
    if not resolved.legal_refs:
        raise RegistryValidationError(f"convenio override fact {resolved.fact_id!r} lacks legal provenance")
    try:
        if operation is None:
            validated = cast("ValidatedRegistryAuthority", selected)
            document_id = validated.catalogues.legal[resolved.legal_refs[0]].document_id
        else:
            document_id = operation.legal_reference(str(resolved.legal_refs[0])).document_id
    except KeyError as exc:
        raise RegistryValidationError(
            f"convenio override fact {resolved.fact_id!r} names unknown legal reference {resolved.legal_refs[0]!r}",
        ) from exc
    return ResolvedConvenioOverride(
        kind=kind,
        rate=rate,
        country_code=normalized_country,
        document_id=document_id,
        fact=resolved,
    )
