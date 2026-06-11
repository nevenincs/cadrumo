"""Typed read API for modelo registry introspection surfaces.

``RegistryQueryService`` wraps a :class:`ValidatedRegistryAuthority` and exposes
structured report objects for the CLI list, describe, casillas, formulas, and
bindings commands. Queries narrow to a single :class:`ModeloDefinition` and
then to one :class:`ModeloRevision` selected by filing year, period, and
optional revision id.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from ....core import Period
from ._authority import ValidatedRegistryAuthority
from ._errors import RegistryValidationError
from ._ids import BindingId, CasillaId, FormulaId
from ._runtime_graph import (
    enum_consumed_binding_ids,
    expression_binding_refs,
    expression_casilla_refs,
    expression_parameter_refs,
    expression_relation_refs,
)
from ._schema import InputKind, ModeloDefinition, ModeloRevision, filing_period_from_scope

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
    """One entry in a ``modelo`` catalogue listing.

    A *modelo* is an AEAT tax form or declaration (e.g. ``"100"``, ``"303"``).
    Each row summarises a single modelo without resolving any particular
    revision — it is suitable for tabular output and autocompletion.

    Attributes:
        code: Short numeric identifier for the modelo (e.g. ``"100"``).
        title: Human-readable display name from the registry.
        cadence: Filing cadence declared by the registry (e.g. ``"anual"``,
            ``"trimestral"``).
        tax_domain: Broad tax category the modelo belongs to (e.g. ``"IRPF"``).
        revision_count: Number of versioned revisions declared for this modelo.
    """

    model_config = ConfigDict(frozen=True)

    code: str
    title: str
    cadence: str
    tax_domain: str
    revision_count: int


class ModeloListReport(BaseModel):
    """Complete result set for a ``modelo`` catalogue query.

    Wraps an ordered tuple of ``ModeloListRow`` entries, sorted by
    modelo code, as returned by ``RegistryQueryService.list_modelos``.

    Attributes:
        modelos: All matching modelo rows, sorted ascending by ``code``.
    """

    model_config = ConfigDict(frozen=True)

    modelos: tuple[ModeloListRow, ...]


class ModeloDescribeReport(BaseModel):
    """Full describe view for one resolved modelo revision.

    A *modelo* is an AEAT tax form or declaration; a *revision* is a dated
    version of its definition. This report is returned by
    ``RegistryQueryService.describe_modelo`` and surfaces structural
    statistics alongside provenance citations for the resolved revision.

    Attributes:
        code: Short numeric identifier for the modelo (e.g. ``"303"``).
        title: Human-readable display name from the registry.
        official_name: Formal name as published in the BOE or AEAT guides.
        tax_domain: Broad tax category (e.g. ``"IRPF"``, ``"IVA"``).
        cadence: Filing cadence declared by the registry (e.g. ``"anual"``).
        jurisdiction: Geographic or administrative jurisdiction.
        revision: Registry identifier of the revision this report describes.
        revision_ids: Every declared revision id for the modelo, oldest
            ``valid_from`` first. ``revision`` names the single revision
            the describe query resolved against; ``revision_ids`` lists all
            valid ``--revision`` values an operator can pass to
            ``modelo work create``, so the id is discoverable up front
            rather than only after a failed guess.
        filing_year: Filing year used for revision selection, or ``None``
            when the query was not scoped to a year.
        period: Filing-period code (e.g. ``"1T"`` for the first quarter),
            or ``None`` when the query resolved the latest revision.
        valid_from: Date from which this revision is effective.
        valid_to: Date after which this revision is no longer effective,
            or ``None`` when it has no end date.
        periods: All period codes declared by this revision's
            ``period_selector``.
        casilla_count: Total number of casillas (numbered boxes) in the
            revision.
        manual_casilla_count: Number of casillas that require manual input.
        bound_casilla_count: Number of casillas populated from an external
            financial-data source (bindings).
        computed_casilla_count: Number of casillas computed by a formula.
        binding_count: Number of financial-data bindings declared.
        formula_count: Number of formulas declared.
        legal_refs: Regulatory citations (BOE articles, RD references)
            grounding the revision's definition.
        source_refs: Internal source references linking to AEAT publications
            or working documents.
    """

    model_config = ConfigDict(frozen=True)

    code: str
    title: str
    official_name: str
    tax_domain: str
    cadence: str
    jurisdiction: str
    revision: str
    revision_ids: tuple[str, ...]
    """Every declared revision id for the modelo, oldest valid_from first.

    ``revision`` names the single revision the describe query resolved
    against; ``revision_ids`` lists all valid ``--revision`` values an
    operator can pass to ``modelo work create``, so the id is
    discoverable up front rather than only after a failed guess.
    """
    filing_year: int | None
    filing_period: Period | None = None
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
    """One row in a ``casilla`` listing for a resolved modelo revision.

    A *casilla* is a numbered input box on an AEAT tax form. Each row
    describes a single casilla's metadata, data type, and provenance
    citations as exposed by the registry query surface.

    Attributes:
        casilla_id: Stable registry identifier for the casilla (distinct
            from the form-printed ``number``).
        number: Short numeric or alphanumeric label printed on the form
            (e.g. ``"0552"``).
        label: Human-readable description of what the casilla captures.
        section: Ordered breadcrumb path locating the casilla within the
            form's section hierarchy.
        data_type: Raw value type declared by the registry
            (e.g. ``"decimal"``, ``"integer"``).
        input_kind: Whether the casilla is manually entered, computed by
            a formula, or *bound* — populated from an external
            financial-data source (see the binding concept).
        required: ``True`` when the casilla must be supplied for a valid
            filing.
        formula: Registry identifier of the formula that computes this
            casilla, or ``None`` when not computed.
        binding: Registry identifier of the binding that populates this
            casilla from an external source, or ``None`` when not bound.
        form_number: Physical page or sub-form number on multi-page
            declarations, or ``None`` when not applicable.
        legal_refs: Regulatory citations (BOE articles, RD references)
            grounding this casilla's definition.
        source_refs: Internal source references linking to AEAT
            publications or working documents.
    """

    model_config = ConfigDict(frozen=True)

    casilla_id: CasillaId
    number: str
    label: str
    section: tuple[str, ...]
    data_type: str
    input_kind: InputKind
    required: bool
    formula: str | None
    binding: str | None
    form_number: str | None
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    localized_labels: dict[str, str] = Field(default_factory=dict)
    localized_help: dict[str, str] = Field(default_factory=dict)


class ModeloCasillasReport(BaseModel):
    """Full casilla listing for a single resolved modelo revision.

    Returned by ``RegistryQueryService.casillas``. The ``revision``,
    ``filing_year``, and ``period`` fields record which version of the
    form the query selected, so callers can show the user exactly which
    revision the rows came from.

    Attributes:
        code: Modelo identifier (e.g. ``"303"``).
        revision: Registry revision identifier that was resolved.
        filing_year: Filing year used for revision selection, or ``None``
            when no year-scoped period was supplied.
        period: Filing-period code (e.g. ``"1T"`` for the first quarter),
            or ``None`` when the query resolved the latest revision
            without a period.
        rows: Ordered tuple of casilla rows for the resolved revision.
    """

    model_config = ConfigDict(frozen=True)

    code: str
    revision: str
    filing_year: int | None
    filing_period: Period | None = None
    period: str | None
    rows: tuple[ModeloCasillaRow, ...]


class ModeloBindingRow(BaseModel):
    """One row in a binding listing for a resolved modelo revision.

    A *binding* maps a financial-data source (such as an aggregated ledger
    figure) to a casilla or formula input. Each row describes one binding's
    selector, aggregation rule, and how the formula engine consumes it.

    Attributes:
        binding_id: Stable registry identifier for this binding.
        source: Financial-data source namespace the binding pulls from.
        typed_enum: When non-``None``, the closed set of string values the
            binding accepts as an enum-typed input.
        input_channel: Engine channel a ``--binding KEY=VALUE`` override for
            this binding feeds. ``decimal`` means the registry's formulas
            consume the binding as a numeric operand: a ``--binding``
            override must be a Decimal, even when ``typed_enum`` is set.
            ``enum`` means a dispatch op consumes the binding as a string
            enum key, so the override is a string. The channel is a
            property of *how the formula consumes the binding*, not of the
            ``typed_enum`` annotation -- a binding may carry ``typed_enum``
            yet still be a ``decimal`` channel binding (the Modelo 100
            estimación-directa modality binding is compared against a
            numeric literal).
        selector: Structured selector mapping the binding applies against
            the financial-data source to aggregate its input.
        aggregation: Optional aggregation rule applied after selection, or
            ``None`` when the selector yields a scalar directly.
        legal_refs: Regulatory citations grounding this binding's
            definition.
        source_refs: Internal source references linking to AEAT
            publications or working documents.
        borrador_capable: ``True`` when this binding is eligible for AEAT
            borrador (pre-filled return) data.
    """

    model_config = ConfigDict(frozen=True)

    binding_id: BindingId
    source: str
    typed_enum: str | None
    input_channel: Literal["decimal", "enum"]
    """Engine channel a ``--binding KEY=VALUE`` override for this binding feeds.

    ``decimal`` means the registry's formulas consume the binding as a
    numeric operand: a ``--binding`` override must be a Decimal, even
    when ``typed_enum`` is set. ``enum`` means a dispatch op consumes
    the binding as a string enum key, so the override is a string. The
    channel is a property of *how the formula consumes the binding*,
    not of the ``typed_enum`` annotation — a binding may carry
    ``typed_enum`` yet still be a ``decimal`` channel binding (the
    Modelo 100 estimación-directa modality binding is compared against
    a numeric literal).
    """
    selector: Mapping[str, object]
    aggregation: Mapping[str, object] | None
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    borrador_capable: bool = False


class ModeloBindingsReport(BaseModel):
    """Full binding listing for a single resolved modelo revision.

    A *binding* maps a financial-data source (e.g. an aggregated ledger
    figure) to a casilla or formula input. This report is the full
    binding listing for a single resolved modelo revision, returned by
    the binding-listing methods on ``RegistryQueryService``.

    Attributes:
        code: Modelo identifier (e.g. ``"130"``).
        revision: Registry revision identifier that was resolved.
        filing_year: Filing year used for revision selection, or ``None``
            when the query was not scoped to a filing year.
        period: Filing-period code (e.g. ``"1T"`` for the first quarter),
            or ``None`` when the query resolved without a period.
        rows: Ordered tuple of binding rows for the resolved revision.
    """

    model_config = ConfigDict(frozen=True)

    code: str
    revision: str
    filing_year: int | None
    filing_period: Period | None = None
    period: str | None
    rows: tuple[ModeloBindingRow, ...]


class ModeloFormulaRow(BaseModel):
    """One row in a formula listing for a resolved modelo revision.

    Lists every input the formula depends on, so contributors can
    inspect what drives a computed casilla without reading the raw
    registry TOML.

    Attributes:
        formula_id: Unique registry identifier for this formula.
        target: Identifier of the casilla this formula writes its result
            into.
        input_casillas: Casilla identifiers referenced in the formula
            expression, deduplicated in order of first appearance.
        input_bindings: Binding identifiers referenced in the expression,
            deduplicated in order of first appearance.
        input_parameters: Parameter names referenced in the expression,
            deduplicated in order of first appearance.
        input_relations: Relation identifiers referenced in the
            expression (cross-casilla or cross-revision links),
            deduplicated in order of first appearance.
        expression: A structured, JSON-serialisable representation of the
            formula's calculation logic, with ``Decimal`` values rendered
            as strings.
        legal_refs: Regulatory citations grounding the formula's
            calculation rule.
        source_refs: Internal source references linking to AEAT
            publications or working documents.
    """

    model_config = ConfigDict(frozen=True)

    formula_id: FormulaId
    target: str
    input_casillas: tuple[str, ...]
    input_bindings: tuple[str, ...]
    input_parameters: tuple[str, ...]
    input_relations: tuple[str, ...]
    expression: Mapping[str, object]
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]


class ModeloFormulasReport(BaseModel):
    """Full formula listing for a single resolved modelo revision.

    Returned by ``RegistryQueryService.formulas``. Each row exposes one
    formula's target casilla and its complete input dependency set.

    Attributes:
        code: Modelo identifier (e.g. ``"200"``).
        revision: Registry revision identifier that was resolved.
        filing_year: Filing year used for revision selection, or ``None``
            when no year-scoped period was supplied.
        period: Filing-period code (e.g. ``"0A"`` for the annual period),
            or ``None`` when the query resolved the latest revision
            without a period.
        rows: Ordered tuple of formula rows for the resolved revision.
    """

    model_config = ConfigDict(frozen=True)

    code: str
    revision: str
    filing_year: int | None
    filing_period: Period | None = None
    period: str | None
    rows: tuple[ModeloFormulaRow, ...]


class RegistryQueryService:
    """Stable Python facade over the validated modelo registry authority."""

    def __init__(self, authority: ValidatedRegistryAuthority) -> None:
        self._authority = authority

    def list_modelos(self, *, year: int | None = None) -> ModeloListReport:
        """Return a catalogue listing of all registered modelos.

        Each entry is a lightweight ``ModeloListRow`` carrying only summary
        fields — no revision details are resolved. The rows are sorted
        ascending by modelo code.

        Args:
            year: When supplied, restricts the listing to modelos that have
                at least one revision whose ``period_selector`` covers the
                given filing year. ``None`` returns all registered modelos.

        Returns:
            A :class:`ModeloListReport` containing the matching rows.
        """
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
        """Return a full describe report for one modelo and its resolved revision.

        Resolves the revision using the same precedence logic as the other
        query methods: when ``period`` is a bare registry token (e.g. ``"1T"``,
        ``"0A"``), the revision that declares it is selected; when ``period``
        is ``None``, the latest revision by ``valid_from`` is returned. Use
        ``describe_modelo_for_scope`` when the filing year must participate in
        revision selection.

        Args:
            modelo: Short numeric identifier for the modelo (e.g. ``"303"``).
            period: Optional period narrowing. Accepted forms are bare
                registry period tokens (``"1T"``, ``"0A"``, ``"01"``-``"12"``)
                or declared non-date tokens such as ``"alta"``.
            as_of: Optional calendar date for validity gating. Defaults to
                today when ``None``.

        Returns:
            A :class:`ModeloDescribeReport` for the resolved revision.

        Raises:
            ``RegistryValidationError``: When ``modelo`` is not registered,
                the period is not declared by any revision, or no revision
                covers the requested scope.
        """
        definition, revision, filing_year, registry_period = self._resolve_revision(modelo, period=period, as_of=as_of)
        return ModeloDescribeReport(
            code=str(definition.id),
            title=definition.title,
            official_name=definition.official_name,
            tax_domain=definition.tax_domain,
            cadence=definition.cadence,
            jurisdiction=definition.jurisdiction,
            revision=str(revision.id),
            revision_ids=tuple(
                str(item.id)
                for item in sorted(
                    definition.revisions.values(),
                    key=lambda candidate: (candidate.valid_from, str(candidate.id)),
                )
            ),
            filing_year=filing_year,
            filing_period=_query_filing_period(filing_year, registry_period),
            period=registry_period,
            valid_from=revision.valid_from,
            valid_to=revision.valid_to,
            periods=tuple(revision.period_selector.periods),
            casilla_count=len(revision.casillas),
            manual_casilla_count=sum(1 for casilla in revision.casillas if casilla.input_kind == InputKind.MANUAL),
            bound_casilla_count=sum(1 for casilla in revision.casillas if casilla.input_kind == InputKind.BOUND),
            computed_casilla_count=sum(1 for casilla in revision.casillas if casilla.input_kind == InputKind.COMPUTED),
            binding_count=len(revision.bindings),
            formula_count=len(revision.formulas),
            legal_refs=tuple(str(ref) for ref in revision.legal_refs),
            source_refs=tuple(str(ref) for ref in revision.source_refs),
        )

    def describe_modelo_for_scope(
        self,
        modelo: str,
        *,
        filing_year: int,
        period: str,
        as_of: date | None = None,
    ) -> ModeloDescribeReport:
        """Return a describe report for an exact ``(filing_year, period)`` scope."""
        definition, revision, registry_period = self._resolve_revision_for_scope(
            modelo,
            filing_year=filing_year,
            period=period,
            as_of=as_of,
        )
        return ModeloDescribeReport(
            code=str(definition.id),
            title=definition.title,
            official_name=definition.official_name,
            tax_domain=definition.tax_domain,
            cadence=definition.cadence,
            jurisdiction=definition.jurisdiction,
            revision=str(revision.id),
            revision_ids=tuple(
                str(item.id)
                for item in sorted(
                    definition.revisions.values(),
                    key=lambda candidate: (candidate.valid_from, str(candidate.id)),
                )
            ),
            filing_year=filing_year,
            filing_period=_query_filing_period(filing_year, registry_period),
            period=registry_period,
            valid_from=revision.valid_from,
            valid_to=revision.valid_to,
            periods=tuple(revision.period_selector.periods),
            casilla_count=len(revision.casillas),
            manual_casilla_count=sum(1 for casilla in revision.casillas if casilla.input_kind == InputKind.MANUAL),
            bound_casilla_count=sum(1 for casilla in revision.casillas if casilla.input_kind == InputKind.BOUND),
            computed_casilla_count=sum(1 for casilla in revision.casillas if casilla.input_kind == InputKind.COMPUTED),
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
        input_kind: InputKind | None = None,
        required: bool | None = None,
        form_number: str | None = None,
    ) -> ModeloCasillasReport:
        """Return the casilla (numbered-box) listing for a resolved modelo revision.

        A *casilla* is a numbered input box on an AEAT tax form. The listing
        includes every casilla in the resolved revision, optionally filtered to
        a subset by kind, required flag, or form page number.

        Args:
            modelo: Short numeric identifier for the modelo (e.g. ``"303"``).
            period: Optional period narrowing; see ``describe_modelo`` for
                accepted forms.
            as_of: Optional calendar date for validity gating.
            input_kind: When supplied, restricts rows to casillas of the
                given ``InputKind`` (e.g. ``InputKind.MANUAL``,
                ``InputKind.COMPUTED``).
            required: When supplied, restricts rows to casillas whose
                ``required`` flag matches this value.
            form_number: When supplied, restricts rows to casillas on the
                given physical form page or sub-form.

        Returns:
            A :class:`ModeloCasillasReport` for the resolved revision, containing
            the filtered casilla rows.

        Raises:
            ``RegistryValidationError``: When the modelo or period is not
                registered, or no revision covers the requested scope.
        """
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
                localized_labels=dict(casilla.localized_labels),
                localized_help=dict(casilla.localized_help),
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
            filing_period=_query_filing_period(filing_year, registry_period),
            period=registry_period,
            rows=tuple(rows),
        )

    def casillas_for_scope(
        self,
        modelo: str,
        *,
        filing_year: int,
        period: str,
        as_of: date | None = None,
        input_kind: InputKind | None = None,
        required: bool | None = None,
        form_number: str | None = None,
    ) -> ModeloCasillasReport:
        """Return casillas for an exact ``(filing_year, period)`` scope."""
        definition, revision, registry_period = self._resolve_revision_for_scope(
            modelo,
            filing_year=filing_year,
            period=period,
            as_of=as_of,
        )
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
                localized_labels=dict(casilla.localized_labels),
                localized_help=dict(casilla.localized_help),
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
            filing_period=_query_filing_period(filing_year, registry_period),
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

        Returns:
            A :class:`ModeloBindingsReport` for the requested filing scope.
        """
        definition = self._authority.validate_modelo(modelo.strip())
        snapshot = self._authority.snapshot(
            str(definition.id),
            filing_year=filing_year,
            period=period,
            on=as_of,
        )
        return ModeloBindingsReport(
            code=str(definition.id),
            revision=str(snapshot.revision.id),
            filing_year=filing_year,
            filing_period=filing_period_from_scope(filing_year, period),
            period=period,
            rows=_binding_rows(snapshot.revision),
        )

    def formulas_for_scope(
        self,
        modelo: str,
        *,
        filing_year: int,
        period: str,
        as_of: date | None = None,
    ) -> ModeloFormulasReport:
        """Return formulas for an exact ``(filing_year, period)`` scope."""
        definition, revision, registry_period = self._resolve_revision_for_scope(
            modelo,
            filing_year=filing_year,
            period=period,
            as_of=as_of,
        )
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
            filing_period=_query_filing_period(filing_year, registry_period),
            period=registry_period,
            rows=rows,
        )

    def bindings_for_year(
        self,
        modelo: str,
        *,
        filing_year: int,
        as_of: date | None = None,
    ) -> ModeloBindingsReport:
        """Return a :class:`ModeloBindingsReport` for the revision that covers ``filing_year``.

        ``bindings`` with no period resolves the *latest* revision,
        which for a multi-revision modelo (e.g. Modelo 100, one
        revision per renta year) reports binding ids for the wrong
        year. This method instead selects the revision whose
        ``period_selector`` covers ``filing_year`` — the same revision
        a work unit created for the same ``(modelo, filing_year)``
        resolves — so the reported binding ids are the ones the
        calculation will accept.
        """
        definition = self._authority.validate_modelo(modelo.strip())
        covering = [
            revision
            for revision in definition.revisions.values()
            if revision.period_selector.includes_year(filing_year)
            and (
                as_of is None
                or (revision.valid_from <= as_of and (revision.valid_to is None or revision.valid_to >= as_of))
            )
        ]
        if not covering:
            raise RegistryValidationError(f"modelo {definition.id} has no revision covering filing year {filing_year}")
        revision = max(covering, key=lambda item: (item.valid_from, str(item.id)))
        return ModeloBindingsReport(
            code=str(definition.id),
            revision=str(revision.id),
            filing_year=filing_year,
            filing_period=None,
            period=None,
            rows=_binding_rows(revision),
        )

    def bindings(
        self,
        modelo: str,
        *,
        period: str | None = None,
        as_of: date | None = None,
    ) -> ModeloBindingsReport:
        """Return the full binding listing for a resolved modelo revision.

        A *binding* maps a financial-data source to a casilla or formula
        input. For year-specific binding ids (e.g. when a multi-revision
        modelo publishes different binding names per renta year) prefer
        ``bindings_for_year`` or ``bindings_for_scope`` so the resolved
        revision matches the one the calculation engine will use.

        Args:
            modelo: Short numeric identifier for the modelo (e.g. ``"130"``).
            period: Optional period narrowing; see ``describe_modelo`` for
                accepted forms. When ``None``, the latest revision is used.
            as_of: Optional calendar date for validity gating.

        Returns:
            A :class:`ModeloBindingsReport` for the resolved revision.

        Raises:
            ``RegistryValidationError``: When the modelo or period is not
                registered, or no revision covers the requested scope.
        """
        definition, revision, filing_year, registry_period = self._resolve_revision(modelo, period=period, as_of=as_of)
        return ModeloBindingsReport(
            code=str(definition.id),
            revision=str(revision.id),
            filing_year=filing_year,
            filing_period=_query_filing_period(filing_year, registry_period),
            period=registry_period,
            rows=_binding_rows(revision),
        )

    def formulas(
        self,
        modelo: str,
        *,
        period: str | None = None,
        as_of: date | None = None,
    ) -> ModeloFormulasReport:
        """Return the full formula listing for a resolved modelo revision.

        Each row exposes one formula's target casilla and its complete input
        dependency set (casillas, bindings, parameters, and relation
        references), letting contributors inspect what drives a computed
        casilla without reading the raw registry TOML.

        Args:
            modelo: Short numeric identifier for the modelo (e.g. ``"200"``).
            period: Optional period narrowing; see ``describe_modelo`` for
                accepted forms. When ``None``, the latest revision is used.
            as_of: Optional calendar date for validity gating.

        Returns:
            A :class:`ModeloFormulasReport` for the resolved revision.

        Raises:
            ``RegistryValidationError``: When the modelo or period is not
                registered, or no revision covers the requested scope.
        """
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
            filing_period=_query_filing_period(filing_year, registry_period),
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
        bare = period.strip()
        bare_upper = bare.upper()
        # A bare period token is one of: a registry time-code
        # (``0A``, ``1T``-``4T``, ``01``-``12``, ...) matched by
        # ``_BARE_PERIOD_RE``, or a non-date censo / event token
        # (``alta``, ``modificacion``, ``baja``, ``AD-HOC``) declared
        # verbatim by a censo modelo's ``period_selector``. Both are
        # resolved by matching the token against each revision's
        # declared periods, so a censo token is accepted on the same
        # path as a quarterly time-code.
        declared_by_revision = {
            token for revision in definition.revisions.values() for token in revision.period_selector.periods
        }
        token_is_declared = any(token.upper() == bare_upper for token in declared_by_revision)
        if _BARE_PERIOD_RE.fullmatch(bare_upper) or token_is_declared:
            candidates = [
                revision
                for revision in definition.revisions.values()
                if bare_upper in {token.upper() for token in revision.period_selector.periods}
            ]
            if not candidates:
                declared = sorted(declared_by_revision)
                raise RegistryValidationError(
                    f"period {period!r} is not declared by any revision of modelo "
                    f"{definition.id}; declared periods: {', '.join(declared)}",
                )
            revision = max(candidates, key=lambda item: (item.valid_from, str(item.id)))
            # Return the registry's own casing for the period token.
            registry_token = next(token for token in revision.period_selector.periods if token.upper() == bare_upper)
            return definition, revision, None, registry_token
        raise RegistryValidationError(
            f"period must be a bare registry token; pass the filing year separately; got {period!r}",
        )

    def _resolve_revision_for_scope(
        self,
        modelo: str,
        *,
        filing_year: int,
        period: str,
        as_of: date | None,
    ) -> tuple[ModeloDefinition, ModeloRevision, str]:
        definition = self._authority.validate_modelo(modelo.strip())
        requested_period = period.strip()
        declared_by_revision = {
            token for revision in definition.revisions.values() for token in revision.period_selector.periods
        }
        declared_by_upper = {token.upper(): token for token in declared_by_revision}
        registry_period = declared_by_upper.get(requested_period.upper(), requested_period.upper())
        snapshot = self._authority.snapshot(
            str(definition.id),
            filing_year=filing_year,
            period=registry_period,
            on=as_of,
        )
        return definition, snapshot.revision, registry_period

def _binding_rows(revision: ModeloRevision) -> tuple[ModeloBindingRow, ...]:
    """Build the typed binding rows for one revision.

    Shared by every ``bindings*`` query so the operator-facing
    ``input_channel`` discriminator is computed once, consistently:
    the channel is ``enum`` only for bindings a dispatch op consumes
    as a string enum key, ``decimal`` for every other binding.
    """
    enum_consumed = enum_consumed_binding_ids(revision)
    return tuple(
        ModeloBindingRow(
            binding_id=str(binding.id),
            source=binding.source,
            typed_enum=binding.typed_enum,
            input_channel="enum" if str(binding.id) in enum_consumed else "decimal",
            selector=_public_mapping(binding.selector),
            aggregation=_public_mapping(binding.aggregation) if binding.aggregation is not None else None,
            legal_refs=tuple(str(ref) for ref in binding.legal_refs),
            source_refs=tuple(str(ref) for ref in binding.source_refs),
            borrador_capable=binding.aeat_prefilled is True,
        )
        for binding in revision.bindings
    )


def _modelo_covers_year(modelo: ModeloDefinition, year: int) -> bool:
    return any(revision.period_selector.includes_year(year) for revision in modelo.revisions.values())


def _query_filing_period(filing_year: int | None, period: str | None) -> Period | None:
    if filing_year is None or period is None:
        return None
    return filing_period_from_scope(filing_year, period)


def _public_mapping(value: Mapping[str, object]) -> dict[str, object]:
    return {str(key): _public_value(item) for key, item in value.items()}


def _public_value(value: object) -> object:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, tuple):
        return tuple(_public_value(item) for item in value)
    if isinstance(value, Mapping):
        # CAST-RATIONALE-TOML-STR-KEYS: all registry and pydantic mappings use str keys;
        # isinstance(value, Mapping) erases the key type; cast restores it.
        return _public_mapping(cast("Mapping[str, object]", value))
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
]
