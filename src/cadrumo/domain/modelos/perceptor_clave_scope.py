"""Registry-declared clave scope of perceptor-record casillas.

An informative withholding summary files one record per perceptor and clave,
and its record design reserves many positions for particular claves only
("Solo para percepciones correspondientes a las claves ..."). A casilla outside
a record's scope is left blank or zero-filled for that record, so it is not a
required input there. The scope is registry data, authored per design edition
in a governed mapping fact, never a list in code.

A scope token is ``CLAVE`` (every subclave) or ``CLAVE.SUBCLAVE``.

The scope is evaluated against a :class:`ModeloRevision`, whose export layouts
name each record's row-field casillas and whose bindings fill them.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Final

from ...core.casilla_id import CasillaId, validated_casilla_id
from ...core.modelo import Modelo
from ...core.period import Period, StandardPeriodCode
from ..calculations.registry.errors import GovernedFactNotApplicableError, RegistryValidationError
from ..calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ..calculations.registry.governed_fact_scope import GovernedFactSource, governed_facts_in_scope
from ..calculations.registry.ids import BindingId
from ..calculations.registry.schema import ModeloRevision
from ..calculations.registry.schema_base import DateAxis
from ..calculations.registry.validate_cross_domain_snapshot import register_cross_domain_snapshot_check
from ..calculations.registry.withholding_bindings import resolve_retencion_clave

PERCEPTOR_CLAVE_SCOPE_FACT_ID: Final = "m190-perceptor-casilla-clave-scope"
#: The modelo whose perceptor records the scope fact governs. The snapshot check
#: tests it before resolving the fact, because a year the fact has no edition
#: for is a finding only for this modelo.
PERCEPTOR_CLAVE_SCOPE_MODELO: Final = Modelo("190")
_CASILLA_KEY_PREFIX: Final = "casilla:"
_RESERVED_KEYS: Final = frozenset({"modelo", "row_clave_binding", "row_subclave_binding"})


@dataclass(frozen=True, slots=True)
class ClaveScopeToken:
    """One clave, optionally narrowed to a single subclave."""

    clave: str
    subclave: str | None

    @classmethod
    def parse(cls, raw: str) -> ClaveScopeToken:
        """Parse ``CLAVE`` or ``CLAVE.SUBCLAVE``; refuse any other shape."""
        clave, separator, subclave = raw.strip().partition(".")
        if not clave or (separator and not (len(subclave) == 2 and subclave.isdigit())):
            raise RegistryValidationError(f"perceptor clave scope token {raw!r} is not CLAVE or CLAVE.NN")
        return cls(clave=clave, subclave=subclave if separator else None)

    def admits(self, clave: str, subclave: str | None) -> bool:
        """Whether a record with ``clave``/``subclave`` falls inside this token."""
        return clave == self.clave and (self.subclave is None or self.subclave == subclave)


@dataclass(frozen=True, slots=True)
class PerceptorClaveScope:
    """The selected edition's clave scope for one modelo's perceptor casillas."""

    modelo_id: str
    row_clave_binding: BindingId
    row_subclave_binding: BindingId
    casillas: Mapping[CasillaId, tuple[ClaveScopeToken, ...]]
    effective_date: date

    def is_scoped(self, casilla_id: CasillaId) -> bool:
        """Whether the registry declares a clave scope for ``casilla_id``."""
        return casilla_id in self.casillas

    def admits(self, casilla_id: CasillaId, clave: str, subclave: str | None) -> bool:
        """Whether a record with ``clave``/``subclave`` carries ``casilla_id``.

        An unscoped casilla applies to every record.
        """
        tokens = self.casillas.get(casilla_id)
        return tokens is None or any(token.admits(clave, subclave) for token in tokens)


def resolve_perceptor_clave_scope(
    *,
    period: Period,
    authority: GovernedFactSource | None = None,
) -> PerceptorClaveScope:
    """Resolve the clave scope declared for the filing ``period``.

    The editions are windows on the filing-period axis with no period
    selector, so the coordinate is the period's own end date and the governed
    fact resolver picks the edition, including any temporal projection.
    """
    selected_authority = authority or governed_facts_in_scope()
    if selected_authority is None:
        raise RegistryValidationError("perceptor clave scope requires an explicit authority operation or scope")
    effective_date = period.end_date
    resolved = selected_authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id=PERCEPTOR_CLAVE_SCOPE_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError("perceptor clave scope must resolve as a mapping fact")
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError("perceptor clave scope entries must be string-to-string")
        if entry.key in entries:
            raise RegistryValidationError(f"duplicate perceptor clave scope key {entry.key!r}")
        entries[entry.key] = entry.value.strip()

    def required(key: str) -> str:
        value = entries.get(key)
        if not value:
            raise RegistryValidationError(f"perceptor clave scope is missing {key!r}")
        return value

    casillas: dict[CasillaId, tuple[ClaveScopeToken, ...]] = {}
    for key, value in entries.items():
        if key in _RESERVED_KEYS:
            continue
        if not key.startswith(_CASILLA_KEY_PREFIX):
            raise RegistryValidationError(f"perceptor clave scope key {key!r} is not a casilla declaration")
        casilla_id = validated_casilla_id(key.removeprefix(_CASILLA_KEY_PREFIX), surface="perceptor clave scope")
        tokens = tuple(ClaveScopeToken.parse(token) for token in value.split(",") if token.strip())
        if not tokens or len(tokens) != len(set(tokens)):
            raise RegistryValidationError(f"perceptor clave scope for {casilla_id!r} has no unique tokens")
        casillas[casilla_id] = tokens
    if not casillas:
        raise RegistryValidationError("perceptor clave scope declares no casilla")
    return PerceptorClaveScope(
        modelo_id=required("modelo"),
        row_clave_binding=required("row_clave_binding"),
        row_subclave_binding=required("row_subclave_binding"),
        casillas=MappingProxyType(casillas),
        effective_date=effective_date,
    )


def row_field_value_bindings(revision: ModeloRevision) -> dict[CasillaId, BindingId]:
    """Map each row-template casilla to the row-set binding that fills it.

    The export record names the casilla of each row field, and the row-set
    binding names the row field it supplies for that record.

    Args:
        revision: The :class:`ModeloRevision` whose export layouts and bindings
            are joined on the record and row field they share.
    """
    casilla_by_record_field: dict[tuple[str, str], CasillaId] = {}
    for layout in revision.export_layouts:
        for record in layout.records:
            if record.binding_record is None:
                continue
            for row_field, casilla_id in record.row_field_casilla_ids.items():
                casilla_by_record_field[(str(record.binding_record), str(row_field))] = casilla_id
    bindings: dict[CasillaId, BindingId] = {}
    for binding in revision.bindings:
        record = getattr(binding.provider, "record", None)
        row_field = getattr(binding.provider, "row_field", None)
        if record is None or row_field is None:
            continue
        casilla_id = casilla_by_record_field.get((str(record), str(row_field)))
        if casilla_id is not None:
            bindings[casilla_id] = binding.id
    return bindings


def rows_missing_scoped_casilla(
    scope: PerceptorClaveScope,
    *,
    casilla_id: CasillaId,
    value_binding: BindingId,
    row_binding_values: Mapping[BindingId, Mapping[str, str]],
) -> tuple[str, ...]:
    """Return the rows inside ``casilla_id``'s clave scope that carry no value for it.

    A row is identified by its row-set index. A row whose clave the scope
    excludes owes the casilla nothing; every other row must carry a value,
    zero included.
    """
    claves = row_binding_values.get(scope.row_clave_binding, dict[str, str]())
    subclaves = row_binding_values.get(scope.row_subclave_binding, dict[str, str]())
    values = row_binding_values.get(value_binding, dict[str, str]())
    return tuple(
        row
        for row, clave in claves.items()
        if scope.admits(casilla_id, clave.strip(), (subclaves.get(row) or "").strip() or None)
        and not (values.get(row) or "").strip()
    )


def perceptor_clave_scope_failures(
    scope: PerceptorClaveScope,
    *,
    casilla_ids: frozenset[CasillaId],
    authority: GovernedFactSource | None = None,
) -> list[str]:
    """Return every scope declaration the given revision surface cannot honour."""
    failures = [
        f"perceptor clave scope names casilla {casilla_id!r}, which the revision does not declare"
        for casilla_id in sorted(scope.casillas)
        if casilla_id not in casilla_ids
    ]
    claves = {token.clave for tokens in scope.casillas.values() for token in tokens}
    for clave in sorted(claves):
        try:
            resolve_retencion_clave(clave, scope.effective_date, modelo=scope.modelo_id, authority=authority)
        except RegistryValidationError as error:
            failures.append(f"perceptor clave scope clave {clave!r} is not in the registry vocabulary: {error}")
    return failures


def check_perceptor_clave_scope(
    modelo_id: str,
    casilla_ids: frozenset[CasillaId],
    renta_first_slice_binding_targets: frozenset[CasillaId],  # shared Protocol shape, unused here
    revision_binding_ids: frozenset[BindingId] = frozenset(),
    *,
    filing_year: int,
) -> list[str]:
    """Assert the declared scope names real casillas and claves where it applies.

    The scope is the edition governing ``filing_year``, the validated
    snapshot's own year, so each revision is held to its own record design.
    A revision that declares no per-record clave binding carries no perceptor
    records to scope, so the check has no claim over it; one that declares no
    binding at all cannot carry that binding under any edition's name. A
    revision that declares bindings in a year no edition governs is refused:
    whether it carries perceptor records is exactly what the missing edition
    would have to say.
    """
    del renta_first_slice_binding_targets
    if modelo_id != PERCEPTOR_CLAVE_SCOPE_MODELO or not revision_binding_ids:
        return []
    try:
        # Modelo 190 is an annual summary, so its filing coordinate is the year's 0A period.
        scope = resolve_perceptor_clave_scope(
            period=Period.from_year_and_code(filing_year, StandardPeriodCode.ANNUAL.value)
        )
    except GovernedFactNotApplicableError as error:
        return [
            f"no perceptor clave scope edition governs filing year {filing_year}, "
            f"but the revision declares bindings: {error}"
        ]
    if scope.modelo_id != modelo_id:
        return [
            f"perceptor clave scope for filing year {filing_year} names modelo {scope.modelo_id!r}, not {modelo_id!r}"
        ]
    if scope.row_clave_binding not in revision_binding_ids:
        return []
    failures = perceptor_clave_scope_failures(scope, casilla_ids=casilla_ids)
    if scope.row_subclave_binding not in revision_binding_ids:
        failures.append(f"perceptor clave scope names absent subclave binding {scope.row_subclave_binding!r}")
    return failures


register_cross_domain_snapshot_check(check_perceptor_clave_scope)


__all__ = [
    "PERCEPTOR_CLAVE_SCOPE_FACT_ID",
    "PERCEPTOR_CLAVE_SCOPE_MODELO",
    "ClaveScopeToken",
    "PerceptorClaveScope",
    "check_perceptor_clave_scope",
    "perceptor_clave_scope_failures",
    "resolve_perceptor_clave_scope",
    "row_field_value_bindings",
    "rows_missing_scoped_casilla",
]
