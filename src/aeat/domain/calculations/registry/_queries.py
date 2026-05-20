"""Typed read API for modelo registry introspection surfaces."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

from ._authority import ValidatedRegistryAuthority
from ._errors import RegistryValidationError
from ._runtime_graph import (
    expression_binding_refs,
    expression_casilla_refs,
    expression_parameter_refs,
    expression_relation_refs,
)
from ._schema import ModeloDefinition, ModeloRevision

_PERIOD_RE = re.compile(r"^(?P<year>\d{4})(?:[-]?Q(?P<quarter>[1-4])|-(?P<month>0[1-9]|1[0-2]))?$", re.I)

#: Bare registry period tokens (``0A``, ``1T``-``4T``, ``01``-``12``,
#: ``1P``-``4P``, ``EXT-1T``-``EXT-4T``, ``AD-HOC``, ``EVENT-N``) carry
#: no filing year. ``describe`` accepts them to narrow a modelo to a
#: revision that declares the token, without forcing the operator to
#: compose an artificial ``YYYY``-prefixed string.
_BARE_PERIOD_RE = re.compile(
    r"^(?:0A|[1-4]T|[1-4]P|0[1-9]|1[0-2]|EXT-[1-4]T|AD-HOC|EVENT-\d+)$",
    re.I,
)


class ModeloListRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    title: str
    cadence: str
    tax_domain: str
    revision_count: int


class ModeloListReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    modelos: tuple[ModeloListRow, ...]


class ModeloDescribeReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    title: str
    official_name: str
    tax_domain: str
    cadence: str
    jurisdiction: str
    revision: str
    filing_year: int | None
    period: str | None
    valid_from: date
    valid_to: date | None
    periods: tuple[str, ...]
    casilla_count: int
    manual_casilla_count: int
    bound_casilla_count: int
    computed_casilla_count: int
    binding_count: int
    formula_count: int
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]


class ModeloCasillaRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    casilla_id: str
    number: str
    label: str
    section: tuple[str, ...]
    data_type: str
    input_kind: str
    required: bool
    formula: str | None
    binding: str | None
    form_number: str | None
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]


class ModeloCasillasReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    revision: str
    filing_year: int | None
    period: str | None
    rows: tuple[ModeloCasillaRow, ...]


class ModeloBindingRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    binding_id: str
    source: str
    typed_enum: str | None
    selector: Mapping[str, object]
    aggregation: Mapping[str, object] | None
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    borrador_capable: bool = False


class ModeloBindingsReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    revision: str
    filing_year: int | None
    period: str | None
    rows: tuple[ModeloBindingRow, ...]


class ModeloFormulaRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    formula_id: str
    target: str
    input_casillas: tuple[str, ...]
    input_bindings: tuple[str, ...]
    input_parameters: tuple[str, ...]
    input_relations: tuple[str, ...]
    expression: Mapping[str, object]
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]


class ModeloFormulasReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    revision: str
    filing_year: int | None
    period: str | None
    rows: tuple[ModeloFormulaRow, ...]


class RegistryQueryService:
    """Stable Python facade over the validated modelo registry authority."""

    def __init__(self, authority: ValidatedRegistryAuthority) -> None:
        self._authority = authority

    def list_modelos(self, *, year: int | None = None) -> ModeloListReport:
        rows = [
            ModeloListRow(
                code=str(modelo.id),
                title=modelo.title,
                cadence=modelo.cadence,
                tax_domain=modelo.tax_domain,
                revision_count=len(modelo.revisions),
            )
            for modelo in self._authority.modelos
            if year is None or _modelo_covers_year(modelo, year)
        ]
        return ModeloListReport(modelos=tuple(sorted(rows, key=lambda row: row.code)))

    def describe_modelo(
        self,
        modelo: str,
        *,
        period: str | None = None,
        as_of: date | None = None,
    ) -> ModeloDescribeReport:
        definition, revision, filing_year, registry_period = self._resolve_revision(modelo, period=period, as_of=as_of)
        return ModeloDescribeReport(
            code=str(definition.id),
            title=definition.title,
            official_name=definition.official_name,
            tax_domain=definition.tax_domain,
            cadence=definition.cadence,
            jurisdiction=definition.jurisdiction,
            revision=str(revision.id),
            filing_year=filing_year,
            period=registry_period,
            valid_from=revision.valid_from,
            valid_to=revision.valid_to,
            periods=tuple(revision.period_selector.periods),
            casilla_count=len(revision.casillas),
            manual_casilla_count=sum(1 for casilla in revision.casillas if casilla.input_kind == "manual"),
            bound_casilla_count=sum(1 for casilla in revision.casillas if casilla.input_kind == "bound"),
            computed_casilla_count=sum(1 for casilla in revision.casillas if casilla.input_kind == "computed"),
            binding_count=len(revision.bindings),
            formula_count=len(revision.formulas),
            legal_refs=tuple(str(ref) for ref in revision.legal_refs),
            source_refs=tuple(str(ref) for ref in revision.source_refs),
        )

    def casillas(
        self,
        modelo: str,
        *,
        period: str | None = None,
        as_of: date | None = None,
        input_kind: Literal["manual", "bound", "computed", "informational"] | None = None,
        required: bool | None = None,
        form_number: str | None = None,
    ) -> ModeloCasillasReport:
        definition, revision, filing_year, registry_period = self._resolve_revision(modelo, period=period, as_of=as_of)
        rows = [
            ModeloCasillaRow(
                casilla_id=str(casilla.id),
                number=casilla.number,
                label=casilla.label,
                section=tuple(casilla.section),
                data_type=casilla.data_type,
                input_kind=casilla.input_kind,
                required=casilla.required,
                formula=str(casilla.formula) if casilla.formula is not None else None,
                binding=str(casilla.binding) if casilla.binding is not None else None,
                form_number=casilla.form_number,
                legal_refs=tuple(str(ref) for ref in casilla.legal_refs),
                source_refs=tuple(str(ref) for ref in casilla.source_refs),
            )
            for casilla in revision.casillas
            if (input_kind is None or casilla.input_kind == input_kind)
            and (required is None or casilla.required is required)
            and (form_number is None or casilla.form_number == form_number)
        ]
        return ModeloCasillasReport(
            code=str(definition.id),
            revision=str(revision.id),
            filing_year=filing_year,
            period=registry_period,
            rows=tuple(rows),
        )

    def bindings_for_scope(
        self,
        modelo: str,
        *,
        filing_year: int,
        period: str,
        as_of: date | None = None,
    ) -> ModeloBindingsReport:
        """Return bindings for a specific filing scope (already-parsed year + period).

        Unlike `bindings`, this method accepts the already-parsed ``filing_year``
        integer and registry ``period`` string (e.g. ``"1T"``, ``"01"``) produced
        by the CLI's period-parsing step. This avoids re-parsing a user-facing
        period string when the caller already holds the decomposed values.
        """
        definition = self._authority.validate_modelo(modelo.strip())
        snapshot = self._authority.snapshot(
            str(definition.id),
            filing_year=filing_year,
            period=period,
            on=as_of,
        )
        rows = tuple(
            ModeloBindingRow(
                binding_id=str(binding.id),
                source=binding.source,
                typed_enum=binding.typed_enum,
                selector=_public_mapping(binding.selector),
                aggregation=_public_mapping(binding.aggregation) if binding.aggregation is not None else None,
                legal_refs=tuple(str(ref) for ref in binding.legal_refs),
                source_refs=tuple(str(ref) for ref in binding.source_refs),
                borrador_capable=binding.aeat_prefilled is True,
            )
            for binding in snapshot.revision.bindings
        )
        return ModeloBindingsReport(
            code=str(definition.id),
            revision=str(snapshot.revision.id),
            filing_year=filing_year,
            period=period,
            rows=rows,
        )

    def bindings(
        self,
        modelo: str,
        *,
        period: str | None = None,
        as_of: date | None = None,
    ) -> ModeloBindingsReport:
        definition, revision, filing_year, registry_period = self._resolve_revision(modelo, period=period, as_of=as_of)
        rows = tuple(
            ModeloBindingRow(
                binding_id=str(binding.id),
                source=binding.source,
                typed_enum=binding.typed_enum,
                selector=_public_mapping(binding.selector),
                aggregation=_public_mapping(binding.aggregation) if binding.aggregation is not None else None,
                legal_refs=tuple(str(ref) for ref in binding.legal_refs),
                source_refs=tuple(str(ref) for ref in binding.source_refs),
                borrador_capable=binding.aeat_prefilled is True,
            )
            for binding in revision.bindings
        )
        return ModeloBindingsReport(
            code=str(definition.id),
            revision=str(revision.id),
            filing_year=filing_year,
            period=registry_period,
            rows=rows,
        )

    def formulas(
        self,
        modelo: str,
        *,
        period: str | None = None,
        as_of: date | None = None,
    ) -> ModeloFormulasReport:
        definition, revision, filing_year, registry_period = self._resolve_revision(modelo, period=period, as_of=as_of)
        rows = tuple(
            ModeloFormulaRow(
                formula_id=str(formula.id),
                target=str(formula.target),
                input_casillas=tuple(dict.fromkeys(expression_casilla_refs(formula.expression))),
                input_bindings=tuple(dict.fromkeys(expression_binding_refs(formula.expression))),
                input_parameters=tuple(dict.fromkeys(expression_parameter_refs(formula.expression))),
                input_relations=tuple(dict.fromkeys(expression_relation_refs(formula.expression))),
                expression=_public_mapping(formula.expression.model_dump(mode="json")),
                legal_refs=tuple(str(ref) for ref in formula.legal_refs),
                source_refs=tuple(str(ref) for ref in formula.source_refs),
            )
            for formula in revision.formulas
        )
        return ModeloFormulasReport(
            code=str(definition.id),
            revision=str(revision.id),
            filing_year=filing_year,
            period=registry_period,
            rows=rows,
        )

    def _resolve_revision(
        self,
        modelo: str,
        *,
        period: str | None,
        as_of: date | None,
    ) -> tuple[ModeloDefinition, ModeloRevision, int | None, str | None]:
        definition = self._authority.validate_modelo(modelo.strip())
        if period is None:
            revision = max(definition.revisions.values(), key=lambda item: (item.valid_from, str(item.id)))
            return definition, revision, None, None
        bare = period.strip().upper()
        if _BARE_PERIOD_RE.fullmatch(bare):
            candidates = [
                revision
                for revision in definition.revisions.values()
                if bare in {token.upper() for token in revision.period_selector.periods}
            ]
            if not candidates:
                declared = sorted(
                    {
                        token
                        for revision in definition.revisions.values()
                        for token in revision.period_selector.periods
                    }
                )
                raise RegistryValidationError(
                    f"period {period!r} is not declared by any revision of modelo "
                    f"{definition.id}; declared periods: {', '.join(declared)}"
                )
            revision = max(candidates, key=lambda item: (item.valid_from, str(item.id)))
            return definition, revision, None, bare
        filing_year, registry_period = parse_modelo_period(period)
        snapshot = self._authority.snapshot(
            str(definition.id),
            filing_year=filing_year,
            period=registry_period,
            on=as_of,
        )
        return definition, snapshot.revision, filing_year, registry_period


def parse_modelo_period(raw: str) -> tuple[int, str]:
    """Return ``(filing_year, registry_period)`` for a user-facing period."""

    candidate = raw.strip()
    match = _PERIOD_RE.fullmatch(candidate)
    if match is None:
        raise RegistryValidationError(f"period must be YYYY, YYYYQn, YYYY-Qn, or YYYY-MM; got {raw!r}")
    year = int(match.group("year"))
    quarter = match.group("quarter")
    month = match.group("month")
    if quarter is not None:
        return year, f"{quarter}T"
    if month is not None:
        return year, month
    return year, "0A"


def _modelo_covers_year(modelo: ModeloDefinition, year: int) -> bool:
    return any(revision.period_selector.includes_year(year) for revision in modelo.revisions.values())


def _public_mapping(value: Mapping) -> dict[str, object]:
    return {str(key): _public_value(item) for key, item in value.items()}


def _public_value(value: object) -> object:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, tuple):
        return tuple(_public_value(item) for item in value)
    if isinstance(value, Mapping):
        return _public_mapping(value)
    return value


__all__ = [
    "ModeloBindingRow",
    "ModeloBindingsReport",
    "ModeloCasillaRow",
    "ModeloCasillasReport",
    "ModeloDescribeReport",
    "ModeloFormulaRow",
    "ModeloFormulasReport",
    "ModeloListReport",
    "ModeloListRow",
    "RegistryQueryService",
    "parse_modelo_period",
]
