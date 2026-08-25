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
from decimal import Decimal, InvalidOperation
from typing import ClassVar

from ...core import BindingSourceKind, CalculationSourceLineageRole
from ...core.hashing import content_hash_hex
from ...core.identity import tax_id_identity_token
from ...core.resources import resources
from ...domain.calculations.registry import AtributionMemberObservation, resolve_atribucion_binding_row_values
from ...domain.modelos import Modelo184MemberRow
from ...domain.user_profile import (
    ProfileNotFoundError,
    UserProfileFact,
    UserProfileRecord,
    numeric_value_refusal,
)
from ..user_profile.profile_record_repository import ProfileRecordRepository
from ._source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)

_OWNED_SOURCES: tuple[BindingSourceKind, ...] = (BindingSourceKind.ATRIBUCION_MEMBER,)
_SOCIO_FACT_RE = re.compile(r"^attribution_entity_socios\.(?P<index>[0-9]+)\.(?P<field>[a-z][a-z0-9_]*)$")
_REQUIRED_FIELDS = frozenset({"nif", "name", "share_pct", "base_imponible_assigned"})
_SOCIOS_SECTION_KEY = "attribution_entity_socios"


@dataclass(frozen=True, slots=True)
class _SocioFacts:
    index: int
    values: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class _AtribucionSocioProjection:
    complete: tuple[_SocioFacts, ...]
    diagnostics: tuple[CalculationSourceDiagnostic, ...]


class AtribucionMemberSourceResolver:
    """Resolve M184 member rows from the active attribution-entity profile."""

    resolver_id: ClassVar[str] = "atribucion_member_profile"
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = _OWNED_SOURCES

    def __init__(self, *, profile_record: UserProfileRecord | None = None) -> None:
        self._profile_record = profile_record

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        if not _revision_uses_atribucion_member(context):
            return CalculationSourceResolution(resolver_id=self.resolver_id, owned_sources=self.owned_sources)

        record = self._profile_record
        if record is None:
            try:
                record = ProfileRecordRepository.for_current_session(context.bucket_id).load(context.bucket_id)
            except ProfileNotFoundError:
                return CalculationSourceResolution(
                    resolver_id=self.resolver_id,
                    owned_sources=self.owned_sources,
                    diagnostics=(
                        _diagnostic("active attribution-entity profile is missing; M184 member rows cannot resolve"),
                    ),
                )

        projection = _project_attribution_socio_facts(_attribution_entity_socio_facts(record.facts))
        observations = tuple(
            _observation_from_socio(socio, filing_year=context.filing_year) for socio in projection.complete
        )
        row_binding_values = resolve_atribucion_binding_row_values(context.revision, observations)
        detail_rows = tuple(_detail_row_from_socio(socio) for socio in projection.complete)
        fingerprint = _profile_record_fingerprint(record) if projection.complete else None
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            row_binding_values=row_binding_values,
            detail_rows=detail_rows,
            diagnostics=projection.diagnostics,
            provenance=tuple(
                CalculationSourceProvenance(
                    resolver_id=self.resolver_id,
                    resolved_binding_source=BindingSourceKind.ATRIBUCION_MEMBER,
                    contributor_source_kind=BindingSourceKind.ATRIBUCION_MEMBER.value,
                    contributor_binding_source=BindingSourceKind.ATRIBUCION_MEMBER,
                    lineage_role=CalculationSourceLineageRole.PRIMARY,
                    source_ref=f"profile:{context.bucket_id}:attribution_entity_socios:{socio.index}",
                    parent_source_ref=None,
                    fingerprint=fingerprint,
                )
                for socio in projection.complete
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


def _project_attribution_socio_facts(socio_facts: tuple[_SocioFacts, ...]) -> _AtribucionSocioProjection:
    # A row that is PRESENT but carries a value its declaration refuses is
    # not usable, and used to be treated as though it were: an out-of-range
    # share percentage reached the attribution calculation unchallenged, and
    # a malformed one crashed inside it. Both now stop here, as a visible
    # diagnostic naming the row -- never a silent number and never a
    # domain-less traceback.
    invalid = {socio.index: _invalid_value_refusals(socio) for socio in socio_facts}
    diagnostics = (
        *(_missing_field_diagnostic(socio) for socio in socio_facts if _missing_fields(socio)),
        *(_invalid_value_diagnostic(socio, invalid[socio.index]) for socio in socio_facts if invalid[socio.index]),
    )
    complete = tuple(
        sorted(
            (socio for socio in socio_facts if not _missing_fields(socio) and not invalid[socio.index]),
            key=_socio_sort_key,
        ),
    )
    return _AtribucionSocioProjection(complete=complete, diagnostics=diagnostics)


def _missing_fields(socio: _SocioFacts) -> frozenset[str]:
    return frozenset(field for field in _REQUIRED_FIELDS if _blank(socio.values.get(field)))


def _socio_sort_key(socio: _SocioFacts) -> tuple[str, str]:
    return ("ES", tax_id_identity_token(str(socio.values.get("nif", ""))))


def _blank(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _invalid_value_refusals(socio: _SocioFacts) -> tuple[str, ...]:
    """Report why any of this row's values fail their own declaration.

    Asks the schema's own
    :func:`~cadrumo.domain.user_profile.numeric_value_refusal` rather than
    re-deciding what a legal share percentage is. The write door admits
    values under that same rule, so a row this resolver refuses is one the
    door would not have written -- which keeps the two from disagreeing
    about the same stored fact.
    """
    section = resources().user_profile_schema.singleton.section(_SOCIOS_SECTION_KEY)
    declared = {field.key: field for field in section.fields}
    return tuple(
        refusal
        for key, value in sorted(socio.values.items())
        if (field := declared.get(key)) is not None and (refusal := numeric_value_refusal(field, value)) is not None
    )


def _invalid_value_diagnostic(socio: _SocioFacts, refusals: tuple[str, ...]) -> CalculationSourceDiagnostic:
    return _diagnostic(
        f"{_SOCIOS_SECTION_KEY}.{socio.index} is not usable for M184; {'; '.join(refusals)}. "
        "Correct the value on the profile before calculating.",
    )


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
        member_tax_id=tax_id_identity_token(str(socio.values["nif"])),
        member_legal_name=str(socio.values["name"]).strip(),
        transaction_date=date(filing_year, 1, 1),
        share_percentage=_decimal(socio.values["share_pct"]),
        base_imponible_assigned=_decimal(socio.values["base_imponible_assigned"]),
    )


def _detail_row_from_socio(socio: _SocioFacts) -> Modelo184MemberRow:
    return Modelo184MemberRow(
        nif=tax_id_identity_token(str(socio.values["nif"])),
        nombre=str(socio.values["name"]).strip(),
        porcentaje=_decimal(socio.values["share_pct"]),
        importe=_decimal(socio.values["base_imponible_assigned"]),
    )


def _decimal(value: object) -> Decimal:
    """Convert a numeric profile fact, refusing anything that is not one.

    The string branch catches its own parse failure. It used to hand the
    text straight to :class:`~decimal.Decimal`, so a malformed value raised
    a bare :exc:`~decimal.InvalidOperation` from inside a calculation --
    naming neither the field nor the profile -- while this function's own
    instructive refusal only ever fired for a wrong TYPE, which is the case
    that does not occur in practice. The message below was therefore dead
    code for the one input that reaches it.
    """
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return Decimal(value)
    if isinstance(value, str):
        try:
            return Decimal(value.strip())
        except InvalidOperation:
            raise ValueError(
                f"attribution member numeric profile fact must be Decimal-compatible; got {value!r}",
            ) from None
    raise ValueError(f"attribution member numeric profile fact must be Decimal-compatible; got {type(value).__name__}")


def _profile_record_fingerprint(record: UserProfileRecord) -> str:
    return f"sha256:{content_hash_hex(record.model_dump(mode='json'))}"


__all__ = ["AtribucionMemberSourceResolver"]
