"""Registry-declared clave scope of perceptor-record casillas.

An informative withholding summary files one record per perceptor and clave,
and its record design reserves many positions for particular claves only
("Solo para percepciones correspondientes a las claves ..."). A casilla outside
a record's scope is left blank or zero-filled for that record, so it is not a
required input there. The scope is registry data, authored per design edition
in a governed mapping fact, never a list in code.

A scope token is ``CLAVE`` (every subclave) or ``CLAVE.SUBCLAVE``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Final

from ...core.casilla_id import CasillaId, validated_casilla_id
from ...core.time.clock import today_madrid
from ..calculations.registry.errors import RegistryValidationError
from ..calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ..calculations.registry.governed_fact_scope import GovernedFactSource, governed_facts_in_scope
from ..calculations.registry.ids import BindingId
from ..calculations.registry.schema_base import DateAxis
from ..calculations.registry.validate_cross_domain_snapshot import register_cross_domain_snapshot_check
from ..calculations.registry.withholding_bindings import resolve_retencion_clave

PERCEPTOR_CLAVE_SCOPE_FACT_ID: Final = "m190-perceptor-casilla-clave-scope"
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
    effective_date: date,
    authority: GovernedFactSource | None = None,
) -> PerceptorClaveScope:
    """Resolve the clave scope declared for the filing period of ``effective_date``."""
    selected_authority = authority or governed_facts_in_scope()
    if selected_authority is None:
        raise RegistryValidationError("perceptor clave scope requires an explicit authority operation or scope")
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
) -> list[str]:
    """Assert the declared scope names real casillas and claves where it applies.

    A revision that declares no per-record clave binding carries no perceptor
    records to scope, so the check has no claim over it.
    """
    del renta_first_slice_binding_targets
    scope = resolve_perceptor_clave_scope(effective_date=today_madrid())
    if modelo_id != scope.modelo_id or scope.row_clave_binding not in revision_binding_ids:
        return []
    failures = perceptor_clave_scope_failures(scope, casilla_ids=casilla_ids)
    if scope.row_subclave_binding not in revision_binding_ids:
        failures.append(f"perceptor clave scope names absent subclave binding {scope.row_subclave_binding!r}")
    return failures


register_cross_domain_snapshot_check(check_perceptor_clave_scope)


__all__ = [
    "PERCEPTOR_CLAVE_SCOPE_FACT_ID",
    "ClaveScopeToken",
    "PerceptorClaveScope",
    "check_perceptor_clave_scope",
    "perceptor_clave_scope_failures",
    "resolve_perceptor_clave_scope",
]
