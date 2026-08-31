"""Typed read API for modelo registry introspection surfaces.

``RegistryQueryService`` wraps a :class:`ValidatedRegistryAuthority` and exposes
structured report objects for the CLI list, describe, casillas, formulas, and
bindings commands. Queries narrow to a single :class:`ModeloDefinition` and
then to one :class:`ModeloRevision` selected by filing year, period, and
optional revision id.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Mapping
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from ....core.tax_domain import TaxDomain
from ....core.type_adapters import OBJECT_TUPLE_ADAPTER
from ....core.authority_grade import RegistryAuthorityGrade
from ....core.aggregation import BindingSourceKind
from ....core.i18n import output_language
from ....core.modelo import Modelo
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.period import Period, RegistrySelectorPeriodCode
from .authority import ValidatedRegistryAuthority
from .binding_selector_utils import boolean_binding_encoded_values
from .errors import RegistryFailureClassification, RegistryFailureCondition, RegistryValidationError
from .ids import BindingId, RelationId
from .period_selector_match import registry_period_for_request, selector_token_for_request
from .query_reports import (
    BindingSelectorQueryEntry,
    BindingSelectorQueryProjection,
    BindingSelectorQueryValue,
    ModeloBindingQueryRow,
    ModeloBindingsReport,
    ModeloCasillaDetailReport,
    ModeloCasillaRow,
    ModeloCasillasReport,
    ModeloDescribeReport,
    ModeloFormulaRow,
    ModeloFormulasReport,
    ModeloListReport,
    ModeloListRow,
    ModeloSupportMatrixReport,
    RegistrySourceInventoryReport,
    RegistrySourceInventoryRow,
    RegistrySourceSite,
)
from .runtime_graph import (
    enum_consumed_binding_ids,
    expression_binding_refs,
    expression_casilla_refs,
    expression_parameter_refs,
    expression_relation_refs,
)
from .schema import ModeloDefinition, ModeloRevision, filing_period_from_scope
from .schema_input_kind import InputKind
from .schema_surfaces import CasillaDefinition, RelationDefinition
from .support_matrix import build_support_matrix
from .temporal import select_revision_for_year

_PUBLIC_MAPPING_ADAPTER: TypeAdapter[dict[object, object]] = TypeAdapter(
    dict[object, object],
    config=ConfigDict(strict=True),
)

#: Bare registry period tokens (``0A``, ``1T``-``4T``, ``01``-``12``,
#: ``1P``-``4P``, ``EXT-1T``-``EXT-4T``, ``AD-HOC``, ``EVENT-N``) carry
#: no filing year. ``describe`` accepts them to narrow a modelo to a
#: revision that declares the token, without forcing the operator to
#: compose an artificial ``YYYY``-prefixed string.
_BARE_PERIOD_RE = re.compile(
    r"^(?:0A|[1-4]T|[1-4]P|0[1-9]|1[0-2]|EXT-[1-4]T|AD-HOC|EVENT-\d+)$",
    re.I,
)


class ResolvedRegistryQueryContext(BaseModel):
    """One resolved registry query context, returned by both resolution forms.

    ``RegistryQueryService`` reaches a modelo revision by two routes: an
    unscoped lookup that narrows by period token alone, and a scoped lookup
    that resolves a snapshot for an explicit filing year. Both routes return
    this context, so every query method and report builder consumes one typed
    shape instead of two positional tuples whose arity and element meaning
    differed. The unscoped route leaves :attr:`filing_year` unset, which is
    why it stays optional here.

    This is deliberately narrower than a
    :class:`~domain.calculations.registry.RegistrySnapshot`: a snapshot
    requires a filing year and carries the whole legal, source, and
    expectation authority, none of which the unscoped period query has or
    needs to answer a read-only introspection request.
    """

    model_config = STRICT_FROZEN_CONFIG

    definition: ModeloDefinition
    revision: ModeloRevision
    filing_year: int | None = None
    registry_period: RegistrySelectorPeriodCode | None = None


class RegistryQueryService:
    """Stable Python facade over the validated modelo registry authority."""

    def __init__(self, authority: ValidatedRegistryAuthority) -> None:
        """Bind this read-only query service to one validated authority."""
        self._authority = authority

    def list_modelos(
        self,
        *,
        year: int | None = None,
        domain: TaxDomain | None = None,
    ) -> ModeloListReport:
        """Return a catalogue listing of all registered modelos.

        Each entry is a lightweight ``ModeloListRow`` carrying only summary
        fields — no revision details are resolved. The rows are sorted
        ascending by modelo code.

        Args:
            year: When supplied, restricts the listing to modelos that have
                at least one revision whose ``period_selector`` covers the
                given filing year. ``None`` returns all registered modelos.
            domain: When supplied, restricts the listing to modelos whose
                registry :class:`~core.TaxDomain` equals the requested
                tax family (e.g. ``TaxDomain.IVA``). ``None`` returns every
                family. The ``year`` and ``domain`` filters compose: passing
                both narrows to modelos that satisfy each.

        Returns:
            A :class:`~domain.calculations.registry._query_reports.ModeloListReport`
            containing the matching rows.
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
            if (year is None or _modelo_covers_year(modelo, year)) and (domain is None or modelo.tax_domain == domain)
        ]
        # Ordered into a pinned local first: pydantic's generated ``__init__``
        # accepts a mapping for a nested model, so sorting inline would let that
        # permissive parameter type flow back into the lambda and widen ``row``
        # to ``ModeloListRow | Mapping[str, Any]``.
        ordered: tuple[ModeloListRow, ...] = tuple(sorted(rows, key=lambda row: row.code))
        return ModeloListReport(modelos=ordered)

    def source_inventory(self) -> RegistrySourceInventoryReport:
        """Report every :class:`~core.BindingSourceKind` the committed registry declares, and where.

        Walks every committed modelo revision and every binding it declares,
        grouping by the binding's ``source`` kind. The result records, per
        source kind, the committed revisions that declare it and the per-revision
        binding count. This is a pure registry introspection surface — it does
        not consult the live calculation mesh — so it stays inside the domain
        boundary. A caller in the application layer joins this inventory against
        the disposition registry (``build_binding_source_dispositions``) to
        prove that every declared source kind is enrolled or explicitly deferred,
        never silently blank (the ``aeat-calculation-aggregation`` connectivity
        contract).

        Returns:
            A :class:`~domain.calculations.registry._query_reports.RegistrySourceInventoryReport`
            whose rows are sorted by the source kind's string value; each row's
            sites are sorted by ``(modelo, revision_id)``.
        """
        sites_by_source: dict[BindingSourceKind, list[RegistrySourceSite]] = defaultdict(list)
        for modelo in self._authority.modelos:
            for revision in modelo.revisions.values():
                counts: Counter[BindingSourceKind] = Counter(binding.source for binding in revision.bindings)
                for source, count in counts.items():
                    sites_by_source[source].append(
                        RegistrySourceSite(
                            modelo=str(modelo.id),
                            revision_id=str(revision.id),
                            binding_count=count,
                        ),
                    )
        inventory: list[RegistrySourceInventoryRow] = []
        for source, sites in sites_by_source.items():
            ordered_sites: tuple[RegistrySourceSite, ...] = tuple(
                sorted(sites, key=lambda site: (site.modelo, site.revision_id))
            )
            inventory.append(
                RegistrySourceInventoryRow(
                    source_kind=source,
                    sites=ordered_sites,
                    total_binding_count=sum(site.binding_count for site in ordered_sites),
                ),
            )
        ordered_rows: tuple[RegistrySourceInventoryRow, ...] = tuple(
            sorted(inventory, key=lambda row: row.source_kind.value)
        )
        return RegistrySourceInventoryReport(rows=ordered_rows)

    def support_matrix(self) -> ModeloSupportMatrixReport:
        """Return the registry-wide per-modelo support/capability matrix.

        For every modelo the authority can load, builds a :class:`ModeloEntry`
        capturing supported revisions, calc/manifest/export/extractor
        capability flags, declared per-ejercicio casilla renames, declared
        deprecation (support-removal) decisions, and declared AEAT-portal
        cross-references — every field read or folded directly from the
        loaded registry, never hand-maintained (see
        ``aeat-calculation-aggregation`` / ``no-silent-under-declaration``).

        Returns:
            A :class:`~domain.calculations.registry._query_reports.ModeloSupportMatrixReport`
            whose entries are sorted by ``modelo_id``.
        """
        return ModeloSupportMatrixReport(entries=build_support_matrix(self._authority))

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
            A :class:`~domain.calculations.registry._query_reports.ModeloDescribeReport`
            for the resolved revision.

        Raises:
            ``RegistryValidationError``: When ``modelo`` is not registered,
                the period is not declared by any revision, or no revision
                covers the requested scope.
        """
        return _build_modelo_describe_report(self._resolve_revision(modelo, period=period, as_of=as_of))

    def describe_modelo_for_scope(
        self,
        modelo: str,
        *,
        filing_year: int,
        period: str,
        as_of: date | None = None,
    ) -> ModeloDescribeReport:
        """Return a :class:`~domain.calculations.registry._query_reports.ModeloDescribeReport` for a scope."""
        return _build_modelo_describe_report(
            self._resolve_revision_for_scope(modelo, filing_year=filing_year, period=period, as_of=as_of),
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
            A :class:`~domain.calculations.registry._query_reports.ModeloCasillasReport`
            for the resolved revision, containing the filtered casilla rows.

        Raises:
            ``RegistryValidationError``: When the modelo or period is not
                registered, or no revision covers the requested scope.
        """
        return _build_modelo_casillas_report(
            self._resolve_revision(modelo, period=period, as_of=as_of),
            input_kind=input_kind,
            required=required,
            form_number=form_number,
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
        """Return a :class:`~domain.calculations.registry._query_reports.ModeloCasillasReport` for a scope."""
        return _build_modelo_casillas_report(
            self._resolve_revision_for_scope(modelo, filing_year=filing_year, period=period, as_of=as_of),
            input_kind=input_kind,
            required=required,
            form_number=form_number,
        )

    def casilla(
        self,
        modelo: str,
        casilla: str,
        *,
        period: str | None = None,
        as_of: date | None = None,
    ) -> ModeloCasillaDetailReport:
        """Return the full semantic detail for one casilla on a resolved revision.

        Addresses a single casilla by its canonical id or its printed
        ``number`` and surfaces the authoritative label, legal/source
        grounding, input kind, and — when the casilla is computed — the
        resolved formula expression. Revision selection follows the same
        precedence as :meth:`describe_modelo`.

        Args:
            modelo: Short numeric identifier for the modelo (e.g. ``"303"``).
            casilla: Casilla id or printed number to look up.
            period: Optional period narrowing; see :meth:`describe_modelo`.
            as_of: Optional calendar date for validity gating.

        Returns:
            A :class:`~domain.calculations.registry._query_reports.ModeloCasillaDetailReport`
            for the addressed casilla.

        Raises:
            ``RegistryValidationError``: When the modelo or period is not
                registered, no revision covers the requested scope, or the
                casilla id/number is not defined by the resolved revision.
        """
        return _casilla_detail_report(self._resolve_revision(modelo, period=period, as_of=as_of), casilla)

    def casilla_for_scope(
        self,
        modelo: str,
        casilla: str,
        *,
        filing_year: int,
        period: str,
        as_of: date | None = None,
    ) -> ModeloCasillaDetailReport:
        """Return a :class:`~domain.calculations.registry._query_reports.ModeloCasillaDetailReport` for a scope."""
        return _casilla_detail_report(
            self._resolve_revision_for_scope(modelo, filing_year=filing_year, period=period, as_of=as_of),
            casilla,
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
            A :class:`~domain.calculations.registry._query_reports.ModeloBindingsReport`
            for the requested filing scope.
        """
        return _build_modelo_bindings_report(
            self._resolve_revision_for_scope(modelo, filing_year=filing_year, period=period, as_of=as_of),
        )

    def bindings_for_year(
        self,
        modelo: str,
        *,
        filing_year: int,
        as_of: date | None = None,
    ) -> ModeloBindingsReport:
        """Return revision-wide bindings for one filing year and effective date."""
        return _build_modelo_bindings_report(
            self._resolve_revision_for_year(modelo, filing_year=filing_year, as_of=as_of),
        )

    def formulas_for_scope(
        self,
        modelo: str,
        *,
        filing_year: int,
        period: str,
        as_of: date | None = None,
    ) -> ModeloFormulasReport:
        """Return a :class:`~domain.calculations.registry._query_reports.ModeloFormulasReport` for a scope."""
        return _build_modelo_formulas_report(
            self._resolve_revision_for_scope(modelo, filing_year=filing_year, period=period, as_of=as_of),
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
        ``bindings_for_scope`` so the resolved revision matches the one
        the calculation engine will use.

        Args:
            modelo: Short numeric identifier for the modelo (e.g. ``"130"``).
            period: Optional period narrowing; see ``describe_modelo`` for
                accepted forms. When ``None``, the latest revision is used.
            as_of: Optional calendar date for validity gating.

        Returns:
            A :class:`~domain.calculations.registry._query_reports.ModeloBindingsReport`
            for the resolved revision.

        Raises:
            ``RegistryValidationError``: When the modelo or period is not
                registered, or no revision covers the requested scope.
        """
        return _build_modelo_bindings_report(self._resolve_revision(modelo, period=period, as_of=as_of))

    def formulas(
        self,
        modelo: str,
        *,
        period: str | None = None,
        as_of: date | None = None,
    ) -> ModeloFormulasReport:
        """Return the full formula listing for a resolved modelo revision.

        Each row exposes one formula's target_casilla_id and its complete input
        dependency set (casillas, bindings, parameters, and relation
        references), letting contributors inspect what drives a computed
        casilla without reading the raw registry TOML.

        Args:
            modelo: Short numeric identifier for the modelo (e.g. ``"200"``).
            period: Optional period narrowing; see ``describe_modelo`` for
                accepted forms. When ``None``, the latest revision is used.
            as_of: Optional calendar date for validity gating.

        Returns:
            A :class:`~domain.calculations.registry._query_reports.ModeloFormulasReport`
            for the resolved revision.

        Raises:
            ``RegistryValidationError``: When the modelo or period is not
                registered, or no revision covers the requested scope.
        """
        return _build_modelo_formulas_report(self._resolve_revision(modelo, period=period, as_of=as_of))

    def _resolve_revision(
        self,
        modelo: str,
        *,
        period: str | None,
        as_of: date | None,
    ) -> ResolvedRegistryQueryContext:
        if as_of is not None:
            # The unscoped path resolves the latest revision by period and has no
            # filing-year context to gate an as_of date against a revision's
            # validity window, so honouring the argument here is impossible.
            # Refuse explicitly rather than accept-and-ignore (the accepted-parameter
            # lie this contract closes); the *_for_scope queries honour as_of.
            raise RegistryValidationError(
                "as_of point-in-time selection requires a filing-year-scoped query; "
                "the unscoped period query resolves the latest revision by period.",
                registry_failure=RegistryFailureClassification(
                    condition=RegistryFailureCondition.QUERY_FILING_YEAR_SCOPED,
                    facts={
                        "modelo": modelo.strip(),
                        "as_of_supplied": True,
                        "filing_year_supplied": False,
                        "query_scope": "unscoped_period",
                    },
                ),
            )
        definition = self._authority.validate_modelo(modelo.strip())
        if period is None:
            revision = max(definition.revisions.values(), key=lambda item: (item.valid_from, str(item.id)))
            return ResolvedRegistryQueryContext(definition=definition, revision=revision)
        bare = period.strip()
        bare_upper = bare.upper()
        # A bare period token is one of: a registry time-code
        # (``0A``, ``1T``-``4T``, ``01``-``12``, ...) matched by
        # ``_BARE_PERIOD_RE``, or a non-date censo / event token
        # (``alta``, ``modificacion``, ``baja``, ``AD-HOC``, ``EVENT-N``) declared
        # verbatim by a censo modelo's ``period_selector``. Both are
        # resolved by matching the token against each revision's
        # declared periods, so a censo token is accepted on the same
        # path as a quarterly time-code.
        declared_by_revision = tuple(
            token for revision in definition.revisions.values() for token in revision.period_selector.periods
        )
        token_is_declared = selector_token_for_request(declared_by_revision, bare) is not None
        if _BARE_PERIOD_RE.fullmatch(bare_upper) or token_is_declared:
            candidates = [
                revision
                for revision in definition.revisions.values()
                if selector_token_for_request(revision.period_selector.periods, bare) is not None
            ]
            if not candidates:
                declared = sorted(set(declared_by_revision))
                raise RegistryValidationError(
                    f"period {period!r} is not declared by any revision of modelo "
                    f"{definition.id}; declared periods: {', '.join(declared)}",
                )
            revision = max(candidates, key=lambda item: (item.valid_from, str(item.id)))
            # Return the registry's own casing for the period token.
            registry_token = selector_token_for_request(revision.period_selector.periods, bare)
            if registry_token is None:
                raise RegistryValidationError(
                    f"period {period!r} is not declared by revision {revision.id} of modelo {definition.id}",
                )
            return ResolvedRegistryQueryContext(
                definition=definition,
                revision=revision,
                registry_period=registry_token,
            )
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
    ) -> ResolvedRegistryQueryContext:
        definition = self._authority.validate_modelo(modelo.strip())
        requested_period = period.strip()
        declared_by_revision = tuple(
            token for revision in definition.revisions.values() for token in revision.period_selector.periods
        )
        registry_period = (
            registry_period_for_request(declared_by_revision, requested_period) or requested_period.upper()
        )
        # Introspection, not a filing assertion. The FILING rung additionally
        # demands a reviewed revision, a reviewed legal set and an export
        # layout, and this resolver feeds only read reports -- describe,
        # casillas, formulas, bindings. Building at the default rung made every
        # one of them refuse an applicability-grade modelo: `describe 036
        # --period ALTA` raised "declares no export layout" while answering a
        # question about which revision governs an event kind. Every structural
        # check -- legal applicability, reference identity, the revision-scoped
        # legal and source windows -- runs at this rung too, so the reports lose
        # nothing they read.
        snapshot = self._authority.snapshot(
            str(definition.id),
            filing_year=filing_year,
            period=registry_period,
            on=as_of,
            grade=RegistryAuthorityGrade.APPLICABILITY,
        )
        return ResolvedRegistryQueryContext(
            definition=definition,
            revision=snapshot.revision,
            filing_year=filing_year,
            registry_period=registry_period,
        )

    def _resolve_revision_for_year(
        self,
        modelo: str,
        *,
        filing_year: int,
        as_of: date | None,
    ) -> ResolvedRegistryQueryContext:
        definition = self._authority.validate_modelo(modelo.strip())
        revision = select_revision_for_year(definition, filing_year=filing_year, on=as_of)
        if not revision.period_selector.periods:
            raise RegistryValidationError(
                f"modelo {definition.id} revision {revision.id!r} has no period token for filing year {filing_year}",
            )
        return ResolvedRegistryQueryContext(
            definition=definition,
            revision=revision,
            filing_year=filing_year,
            registry_period=revision.period_selector.periods[0],
        )


def _build_modelo_describe_report(context: ResolvedRegistryQueryContext) -> ModeloDescribeReport:
    """Assemble a :class:`ModeloDescribeReport` from a resolved query context."""
    definition = context.definition
    revision = context.revision
    filing_year = context.filing_year
    registry_period = context.registry_period
    return ModeloDescribeReport(
        code=str(definition.id),
        title=definition.get_title(output_language()),
        official_name=definition.get_official_name(output_language()),
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


def _casilla_row_included(
    casilla: CasillaDefinition,
    *,
    input_kind: InputKind | None,
    required: bool | None,
    form_number: str | None,
) -> bool:
    """Return whether a casilla passes the report's optional kind/required/form filters."""
    return (
        (input_kind is None or casilla.input_kind == input_kind)
        and (required is None or casilla.required is required)
        and (form_number is None or casilla.form_number == form_number)
    )


def _build_modelo_casillas_report(
    context: ResolvedRegistryQueryContext,
    *,
    input_kind: InputKind | None,
    required: bool | None,
    form_number: str | None,
) -> ModeloCasillasReport:
    """Assemble a filtered :class:`ModeloCasillasReport` from a resolved query context."""
    definition = context.definition
    revision = context.revision
    rows = [
        ModeloCasillaRow(
            casilla_id=casilla.id,
            number=casilla.number,
            label=casilla.get_label(output_language()),
            help_text=casilla.get_help(output_language()),
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
        if _casilla_row_included(casilla, input_kind=input_kind, required=required, form_number=form_number)
    ]
    return ModeloCasillasReport(
        code=str(definition.id),
        revision=str(revision.id),
        filing_year=context.filing_year,
        filing_period=_query_filing_period(context.filing_year, context.registry_period),
        period=context.registry_period,
        rows=tuple(rows),
    )


def _build_modelo_formulas_report(context: ResolvedRegistryQueryContext) -> ModeloFormulasReport:
    """Assemble a :class:`ModeloFormulasReport` from a resolved query context."""
    definition = context.definition
    revision = context.revision
    rows = tuple(
        ModeloFormulaRow(
            formula_id=str(formula.id),
            target_casilla_id=formula.target_casilla_id,
            input_casilla_ids=tuple(dict.fromkeys(expression_casilla_refs(formula.expression))),
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
        filing_year=context.filing_year,
        filing_period=_query_filing_period(context.filing_year, context.registry_period),
        period=context.registry_period,
        rows=rows,
    )


def _build_modelo_bindings_report(context: ResolvedRegistryQueryContext) -> ModeloBindingsReport:
    """Assemble a :class:`ModeloBindingsReport` from a resolved query context."""
    modelo = str(context.definition.id)
    return ModeloBindingsReport(
        code=modelo,
        revision=str(context.revision.id),
        filing_year=context.filing_year,
        filing_period=_query_filing_period(context.filing_year, context.registry_period),
        period=context.registry_period,
        rows=_binding_rows(context.revision, modelo=modelo, period=context.registry_period),
    )


def relations_by_target_binding(
    revision: ModeloRevision,
) -> dict[BindingId, tuple[RelationDefinition, ...]]:
    """Group declared relations by target binding in declaration order."""
    grouped: dict[BindingId, list[RelationDefinition]] = {}
    for relation in revision.relations:
        grouped.setdefault(relation.target_binding, []).append(relation)
    return {binding_id: tuple(relations) for binding_id, relations in grouped.items()}


def _binding_rows(
    revision: ModeloRevision,
    *,
    modelo: str | None = None,
    period: str | None = None,
) -> tuple[ModeloBindingQueryRow, ...]:
    """Build the typed binding rows for one revision.

    Shared by every ``bindings*`` query so the operator-facing
    ``input_channel`` discriminator is computed once, consistently:
    the channel is ``enum`` only for bindings a dispatch op consumes
    as a string enum key, ``decimal`` for every other binding.
    """
    enum_consumed = enum_consumed_binding_ids(revision)
    relation_inputs_by_target = _relation_inputs_by_target_binding(revision, period=period)
    operator_required = _operator_input_required_by_binding(revision, modelo=modelo, period=period)
    return tuple(
        ModeloBindingQueryRow(
            binding_id=binding.id,
            source=binding.source,
            typed_enum=binding.typed_enum,
            input_channel="enum" if binding.id in enum_consumed else "decimal",
            selector=_public_selector(binding.source, binding.selector),
            aggregation={"op": binding.aggregation.op.value} if binding.aggregation is not None else None,
            legal_refs=tuple(binding.legal_refs),
            source_refs=tuple(binding.source_refs),
            borrador_capable=binding.aeat_prefilled is True,
            relation_inputs=relation_inputs_by_target.get(binding.id, ()),
            encoded_options=boolean_binding_encoded_values(binding),
            operator_input_required=operator_required.get(binding.id, True),
        )
        for binding in revision.bindings
    )


def _casilla_detail_report(context: ResolvedRegistryQueryContext, casilla: str) -> ModeloCasillaDetailReport:
    """Build the single-casilla detail report, resolving the formula expression.

    The casilla is matched by canonical id first, then by printed ``number``
    (the same dual key the ``casillas --number`` filter accepts). An unknown
    casilla raises a :class:`RegistryValidationError` with its observed
    condition and a bounded sample of valid ids.
    A computed casilla's ``formula`` id is resolved against the revision's
    formulas so the structured expression rides the report.
    """
    definition = context.definition
    revision = context.revision
    needle = casilla.strip()
    matched = next(
        (item for item in revision.casillas if str(item.id) == needle or item.number == needle),
        None,
    )
    if matched is None:
        valid_ids = [str(item.id) for item in revision.casillas]
        sample = ", ".join(valid_ids[:20])
        overflow = "" if len(valid_ids) <= 20 else f" (+{len(valid_ids) - 20} more)"
        raise RegistryValidationError(
            f"casilla {casilla!r} is not defined by revision {revision.id} of modelo {definition.id}; "
            f"valid casilla ids include: {sample}{overflow}.",
            registry_failure=RegistryFailureClassification(
                condition=RegistryFailureCondition.QUERY_CASILLA_DECLARED,
                facts={
                    "modelo": str(definition.id),
                    "revision": str(revision.id),
                    "casilla": needle,
                    "casilla_declared": False,
                },
            ),
        )
    formula_expression: Mapping[str, object] | None = None
    if matched.formula is not None:
        formula = next((item for item in revision.formulas if item.id == matched.formula), None)
        if formula is not None:
            formula_expression = _public_mapping(formula.expression.model_dump(mode="json"))
    return ModeloCasillaDetailReport(
        code=str(definition.id),
        revision=str(revision.id),
        filing_year=context.filing_year,
        filing_period=_query_filing_period(context.filing_year, context.registry_period),
        period=context.registry_period,
        casilla_id=matched.id,
        number=matched.number,
        label=matched.get_label(output_language()),
        help_text=matched.get_help(output_language()),
        section=tuple(matched.section),
        data_type=matched.data_type,
        input_kind=matched.input_kind,
        required=matched.required,
        legal_refs=tuple(str(ref) for ref in matched.legal_refs),
        source_refs=tuple(str(ref) for ref in matched.source_refs),
        binding=matched.binding,
        formula_id=matched.formula,
        formula_expression=formula_expression,
    )


def _relation_inputs_by_target_binding(
    revision: ModeloRevision,
    *,
    period: str | None = None,
) -> dict[BindingId, tuple[RelationId, ...]]:
    """Map each binding id to the relation ids whose ``target_binding`` is that binding.

    A ``relation_prefill`` binding's value is materialised by one or more
    registry :class:`RelationDefinition` fold-ins; each declares the
    binding it feeds via ``target_binding``. Inverting that declaration
    makes the feeding relation discoverable from the binding listing
    surface for any modelo, grounded in the resolved revision rather than
    a per-form hardcoded channel table. Relation ids preserve their
    declaration order so the listing is deterministic.
    """
    return {
        target_binding: relation_ids
        for target_binding, relations in relations_by_target_binding(revision).items()
        if (
            relation_ids := tuple(
                relation.id
                for relation in relations
                if period is None or not relation.target_periods or period in relation.target_periods
            )
        )
    }


def _operator_input_required_by_binding(
    revision: ModeloRevision,
    *,
    modelo: str | None,
    period: str | None,
) -> dict[BindingId, bool]:
    """Return missing-input visibility for relation slots with period-scoped defaults."""
    required = {binding.id: True for binding in revision.bindings}
    if modelo != Modelo.M202.value or period is None:
        return required
    relations_by_target = relations_by_target_binding(revision)
    for binding in revision.bindings:
        if binding.source is not BindingSourceKind.RELATION_PREFILL:
            continue
        relations = tuple(relations_by_target.get(binding.id, ()))
        if not relations:
            continue
        if any(not relation.target_periods or period in relation.target_periods for relation in relations):
            continue
        if all(relation.kind == "previous_period" and str(relation.source_modelo) == modelo for relation in relations):
            required[binding.id] = False
    return required


def _modelo_covers_year(modelo: ModeloDefinition, year: int) -> bool:
    return any(revision.period_selector.includes_year(year) for revision in modelo.revisions.values())


def _query_filing_period(filing_year: int | None, period: str | None) -> Period | None:
    if filing_year is None or period is None:
        return None
    return filing_period_from_scope(filing_year, period)


def _public_selector(source: str, selector: object) -> BindingSelectorQueryProjection:
    if isinstance(selector, BaseModel):
        selector = selector.model_dump(exclude={"source"}, exclude_none=True, exclude_unset=True)
    selector_mapping = _public_mapping_items(selector)
    entries = tuple(
        BindingSelectorQueryEntry(key=str(key), value=_public_selector_value(value))
        for key, value in sorted(selector_mapping.items(), key=lambda item: str(item[0]))
    )
    return BindingSelectorQueryProjection(
        source=str(source),
        keys=tuple(entry.key for entry in entries),
        entries=entries,
    )


def _public_mapping(value: object) -> dict[str, object]:
    return {str(key): _public_value(item) for key, item in _public_mapping_items(value).items()}


def _public_mapping_items(value: object) -> dict[object, object]:
    """Validate an untyped mapping before projecting it onto the public query API."""
    mapping = _try_public_mapping(value)
    if mapping is not None:
        return mapping
    raise RegistryValidationError(f"unsupported public mapping value {value!r}")


def _try_public_mapping(value: object) -> dict[object, object] | None:
    """Return a checked public mapping, or ``None`` when the value is not one."""
    if not isinstance(value, Mapping):
        return None
    try:
        return _PUBLIC_MAPPING_ADAPTER.validate_python(value)
    except ValidationError:
        return None


def _public_tuple(value: object) -> tuple[object, ...] | None:
    """Narrow a runtime tuple to object entries for recursive public projection."""
    if not isinstance(value, tuple):
        return None
    return OBJECT_TUPLE_ADAPTER.validate_python(value)


def _public_selector_value(value: object) -> BindingSelectorQueryValue:
    public_value = _public_value(value)
    if isinstance(public_value, str | int | bool):
        return public_value
    tuple_value = _public_tuple(public_value)
    if tuple_value is not None:
        string_items: list[str] = []
        for item in tuple_value:
            if not isinstance(item, str):
                break
            string_items.append(item)
        else:
            return tuple(string_items)
    raise RegistryValidationError(f"unsupported public binding selector value {public_value!r}")


def _public_value(value: object) -> object:
    if isinstance(value, Decimal):
        return format(value, "f")
    tuple_value = _public_tuple(value)
    if tuple_value is not None:
        return tuple(_public_value(item) for item in tuple_value)
    mapping = _try_public_mapping(value)
    if mapping is not None:
        return {str(key): _public_value(item) for key, item in mapping.items()}
    return value


__all__ = [
    "RegistryQueryService",
    "ResolvedRegistryQueryContext",
    "relations_by_target_binding",
]
