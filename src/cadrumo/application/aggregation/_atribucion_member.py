"""Modelo 184 attribution-member source resolver.

See Also:
    :class:`UserProfileRecord`
        Active taxpayer profile the resolver reads attribution-entity socio
        facts from.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ...core import BindingSourceKind
from ...core.hashing import content_hash_hex
from ...domain.calculations.registry import AtributionMemberObservation, resolve_atribucion_binding_row_values
from ...domain.modelos import Modelo184MemberRow
from ...domain.user_profile import ProfileNotFoundError, UserProfileFact, UserProfileRecord
from ..user_profile import UserProfileLifecycleRepository
from ._source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)

_OWNED_SOURCES: tuple[BindingSourceKind, ...] = (BindingSourceKind.ATRIBUCION_MEMBER,)
_SOCIO_FACT_RE = re.compile(r"^attribution_entity_socios\.(?P<index>[0-9]+)\.(?P<field>[a-z][a-z0-9_]*)$")
_REQUIRED_FIELDS = frozenset({"nif", "name", "share_pct", "base_imponible_assigned"})


@dataclass(frozen=True, slots=True)
class _SocioFacts:
    index: int
    values: Mapping[str, object]


class AtribucionMemberSourceResolver:
    """Resolve M184 member rows from the active attribution-entity profile."""

    resolver_id = "atribucion_member_profile"
    owned_sources = _OWNED_SOURCES

    def __init__(self, *, profile_record: UserProfileRecord | None = None) -> None:
        self._profile_record = profile_record

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        if not _revision_uses_atribucion_member(context):
            return CalculationSourceResolution(resolver_id=self.resolver_id, owned_sources=self.owned_sources)

        record = self._profile_record
        if record is None:
            try:
                record = UserProfileLifecycleRepository(bucket_id=context.bucket_id).load(context.bucket_id)
            except ProfileNotFoundError:
                return CalculationSourceResolution(
                    resolver_id=self.resolver_id,
                    owned_sources=self.owned_sources,
                    diagnostics=(
                        _diagnostic("active attribution-entity profile is missing; M184 member rows cannot resolve"),
                    ),
                )

        socio_facts = _attribution_entity_socio_facts(record.facts)
        diagnostics = tuple(_missing_field_diagnostic(socio) for socio in socio_facts if _missing_fields(socio))
        complete = tuple(sorted((socio for socio in socio_facts if not _missing_fields(socio)), key=_socio_sort_key))
        observations = tuple(_observation_from_socio(socio, filing_year=context.filing_year) for socio in complete)
        row_binding_values = resolve_atribucion_binding_row_values(context.revision, observations)
        detail_rows = tuple(_detail_row_from_socio(socio) for socio in complete)
        fingerprint = _profile_record_fingerprint(record) if complete else None
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            row_binding_values=row_binding_values,
            detail_rows=detail_rows,
            diagnostics=diagnostics,
            provenance=tuple(
                CalculationSourceProvenance(
                    source_kind=BindingSourceKind.ATRIBUCION_MEMBER.value,
                    source_ref=f"profile:{context.bucket_id}:attribution_entity_socios:{socio.index}",
                    fingerprint=fingerprint,
                )
                for socio in complete
            ),
        )


def _revision_uses_atribucion_member(context: CalculationSourceContext) -> bool:
    return any(binding.source == BindingSourceKind.ATRIBUCION_MEMBER for binding in context.revision.bindings)


def _attribution_entity_socio_facts(facts: tuple[UserProfileFact, ...]) -> tuple[_SocioFacts, ...]:
    grouped: dict[int, dict[str, object]] = {}
    for fact in facts:
        match = _SOCIO_FACT_RE.match(fact.path)
        if match is None or fact.value is None:
            continue
        index = int(match.group("index"))
        grouped.setdefault(index, {})[match.group("field")] = fact.value
    return tuple(_SocioFacts(index=index, values=grouped[index]) for index in sorted(grouped))


def _missing_fields(socio: _SocioFacts) -> frozenset[str]:
    return frozenset(field for field in _REQUIRED_FIELDS if _blank(socio.values.get(field)))


def _socio_sort_key(socio: _SocioFacts) -> tuple[str, str]:
    return ("ES", str(socio.values.get("nif", "")).strip().upper())


def _blank(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _missing_field_diagnostic(socio: _SocioFacts) -> CalculationSourceDiagnostic:
    missing = ", ".join(sorted(_missing_fields(socio)))
    return _diagnostic(
        f"attribution_entity_socios.{socio.index} is incomplete for M184; missing {missing}. "
        "Declare an explicit assigned base for each socio instead of deriving it from share percentage.",
    )


def _diagnostic(message: str) -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind=BindingSourceKind.ATRIBUCION_MEMBER.value,
        resolver_id=AtribucionMemberSourceResolver.resolver_id,
        message=message,
    )


def _observation_from_socio(socio: _SocioFacts, *, filing_year: int) -> AtributionMemberObservation:
    return AtributionMemberObservation(
        source_id=f"profile:attribution_entity_socios:{socio.index}",
        member_tax_id=str(socio.values["nif"]).strip().upper(),
        member_legal_name=str(socio.values["name"]).strip(),
        transaction_date=date(filing_year, 1, 1),
        share_percentage=_decimal(socio.values["share_pct"]),
        base_imponible_assigned=_decimal(socio.values["base_imponible_assigned"]),
    )


def _detail_row_from_socio(socio: _SocioFacts) -> Modelo184MemberRow:
    return Modelo184MemberRow(
        nif=str(socio.values["nif"]).strip().upper(),
        nombre=str(socio.values["name"]).strip(),
        porcentaje=_decimal(socio.values["share_pct"]),
        importe=_decimal(socio.values["base_imponible_assigned"]),
    )


def _decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return Decimal(value)
    if isinstance(value, str):
        return Decimal(value.strip())
    raise ValueError(f"attribution member numeric profile fact must be Decimal-compatible; got {type(value).__name__}")


def _profile_record_fingerprint(record: UserProfileRecord) -> str:
    return f"sha256:{content_hash_hex(record.model_dump(mode='json'))}"


__all__ = ["AtribucionMemberSourceResolver"]
