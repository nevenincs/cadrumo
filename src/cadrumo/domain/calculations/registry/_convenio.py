"""Cross-cutting Convenio doble imposición (CDI) treaty-override authority.

A dedicated registry authoring surface — ``registry/aeat/treaties/`` — sibling to
the cross-cutting ``legal/`` tree. One TOML file per bilateral double-taxation
treaty declares the counterpart country, the treaty BOE ``document_id``, and a
list of per-income-type override rows keyed by :class:`~core.TipoRentaIrnr`.
The loader compiles the tree into a :class:`ConvenioAuthority` projection that any
IRNR rate formula consumes through the
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
from datetime import date
from decimal import Decimal
from pathlib import Path

from pydantic import Field, field_validator, model_validator

from ....core import ConvenioOverrideKind, TipoRentaIrnr, freeze_toml, read_toml, scan_directory
from .errors import RegistryLoadError, RegistryValidationError
from ._ids import LegalRefId
from ._loader_cache import toml_file_fingerprint
from ._schema_base import RegistryModel

_ZERO = Decimal("0")
_ONE = Decimal("1")


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
        """Hydrate the TOML ``tipo_renta`` string into its :class:`~core.TipoRentaIrnr` member."""
        if isinstance(value, str) and not isinstance(value, TipoRentaIrnr):
            return TipoRentaIrnr(value)
        return value

    @field_validator("kind", mode="before")
    @classmethod
    def _coerce_kind(cls, value: object) -> object:
        """Hydrate the TOML ``kind`` string into its :class:`~core.ConvenioOverrideKind` member."""
        if isinstance(value, str) and not isinstance(value, ConvenioOverrideKind):
            return ConvenioOverrideKind(value)
        return value

    @model_validator(mode="after")
    def _validate_override_row(self) -> ConvenioOverrideRow:
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise RegistryValidationError("convenio override valid_to must be on or after valid_from")
        if self.kind.carries_rate:
            if self.rate is None:
                raise RegistryValidationError(
                    f"convenio override kind {self.kind.value!r} requires a rate for "
                    f"tipo_renta {self.tipo_renta.value!r}",
                )
            try:
                parsed = Decimal(self.rate)
            except (ArithmeticError, ValueError) as exc:
                raise RegistryValidationError(
                    f"convenio override rate must be a parseable Decimal; got {self.rate!r}",
                ) from exc
            if parsed < _ZERO or parsed > _ONE:
                raise RegistryValidationError(
                    f"convenio override rate must be within [0, 1]; got {self.rate!r}",
                )
        elif self.rate is not None:
            raise RegistryValidationError(
                f"convenio override kind {self.kind.value!r} must not declare a rate "
                f"(the amount is delegated to the domestic tariff or driven to zero)",
            )
        if self.legal_ref_anchor not in self.legal_refs:
            raise RegistryValidationError("convenio override legal_ref_anchor must be included in legal_refs")
        return self

    @property
    def rate_decimal(self) -> Decimal | None:
        """The parsed ``rate`` for a rate-bearing kind, else ``None``."""
        return Decimal(self.rate) if self.rate is not None else None


class ConvenioTreaty(RegistryModel):
    """One bilateral double-taxation treaty and its per-income-type overrides.

    Authored one file per treaty under ``registry/aeat/treaties/`` and keyed by
    the counterpart ``country_code`` (ISO 3166-1 alpha-2). The optional
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
                raise RegistryValidationError(
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

    treaties: Mapping[str, ConvenioTreaty] = Field(default_factory=dict)

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


def load_convenio_authority(treaties_dir: Path) -> ConvenioAuthority:
    """Compile the ``treaties/`` TOML tree into a :class:`ConvenioAuthority`.

    Reads one ``[treaty]`` table per file, rejecting a duplicate counterpart
    country declared across two files. An absent tree yields an empty authority.

    Returns:
        The compiled :class:`ConvenioAuthority`.
    """
    resolved = treaties_dir.resolve()
    if not resolved.is_dir():
        return ConvenioAuthority.empty()
    treaties: dict[str, ConvenioTreaty] = {}
    for path in scan_directory(resolved, pattern="*.toml"):
        raw = freeze_toml(read_toml(path, error_factory=RegistryLoadError))
        table = raw.get("treaty")
        if not isinstance(table, Mapping):
            raise RegistryLoadError(f"{path}: treaty file must declare a [treaty] table")
        try:
            treaty = ConvenioTreaty.model_validate(table)
        except RegistryValidationError as exc:
            raise RegistryLoadError(f"{path}: invalid treaty: {exc}") from exc
        if treaty.country_code in treaties:
            raise RegistryLoadError(
                f"{path}: treaty country {treaty.country_code!r} already declared in another treaties/*.toml file",
            )
        treaties[treaty.country_code] = treaty
    return ConvenioAuthority(treaties=treaties)


def collect_convenio_fingerprints(root: Path) -> tuple[tuple[str, int, int, str], ...]:
    """Return ``(path, size, mtime_ns, content_digest)`` fingerprints for every ``treaties/*.toml``.

    Folded into the authority-level cache key so a treaty content edit (which
    does not bump the parent directory mtime the registry-tree walk observes)
    invalidates the compiled authority, per ``aeat-registry-authority-flow``.
    Shares the loader's per-file fingerprint so a mutable-tree treaty rewrite
    that collides on ``(size, mtime_ns)`` still re-keys via the content digest.
    """
    treaties_dir = root.resolve() / "treaties"
    return tuple(toml_file_fingerprint(path.resolve()) for path in scan_directory(treaties_dir, pattern="*.toml"))


def validate_convenio_legal_refs(
    authority: ConvenioAuthority,
    legal_ref_ids: frozenset[str],
) -> None:
    """Raise when a treaty override cites a ``legal_ref`` absent from the catalogue.

    The grounding gate: every treaty rate MUST cite a treaty article defined in
    the shared ``legal/`` catalogue (which itself resolves to bundled BOE corpus
    text). An override pointing at an undefined ref is a build-time failure.
    """
    missing: list[str] = []
    for country_code, treaty in sorted(authority.treaties.items()):
        for row in treaty.overrides:
            for ref in row.legal_refs:
                if ref not in legal_ref_ids:
                    missing.append(f"treaty {country_code} tipo_renta {row.tipo_renta.value}: legal_ref {ref!r}")
    if missing:
        raise RegistryValidationError(
            "convenio treaty legal_refs missing from the legal catalogue:\n"
            + "\n".join(f" - {entry}" for entry in missing),
        )
