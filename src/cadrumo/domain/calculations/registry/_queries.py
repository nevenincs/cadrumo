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

from pydantic import BaseModel

from ....core import BindingSourceKind, Modelo, Period, TaxDomain
from ._authority import ValidatedRegistryAuthority
from ._binding_selector_utils import boolean_binding_encoded_values
from ._errors import AmbiguousRevisionSelectionError, RegistryValidationError
from ._ids import BindingId, RelationId
from ._period_selector_match import registry_period_for_request, selector_token_for_request
from ._query_reports import (
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
from ._runtime_graph import (
    enum_consumed_binding_ids,
    expression_binding_refs,
    expression_casilla_refs,
    expression_parameter_refs,
    expression_relation_refs,
)
from ._schema import ModeloDefinition, ModeloRevision, RelationDefinition, filing_period_from_scope
from ._schema_input_kind import InputKind
from ._support_matrix import build_support_matrix

#: Bare registry period tokens (``0A``, ``1T``-``4T``, ``01``-``12``,
#: ``1P``-``4P``, ``EXT-1T``-``EXT-4T``, ``AD-HOC``, ``EVENT-N``) carry
#: no filing year. ``describe`` accepts them to narrow a modelo to a
#: revision that declares the token, without forcing the operator to
#: compose an artificial ``YYYY``-prefixed string.
_BARE_PERIOD_RE = re.compile(
    r"^(?:0A|[1-4]T|[1-4]P|0[1-9]|1[0-2]|EXT-[1-4]T|AD-HOC|EVENT-\d+)$",
    re.I,
)


class RegistryQueryService:
    """Stable Python facade over the validated modelo registry authority."""

    def __init__(self, authority: ValidatedRegistryAuthority) -> None:
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
        return ModeloListReport(modelos=tuple(sorted(rows, key=lambda row: row.code)))

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
        never silently blank (the ``no-dormant-source-resolvers`` connectivity
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
        rows = tuple(
            RegistrySourceInventoryRow(
                source_kind=source,
                sites=tuple(sorted(sites, key=lambda site: (site.modelo, site.revision_id))),
                total_binding_count=sum(site.binding_count for site in sites),
            )
            for source, sites in sites_by_source.items()
        )
        return RegistrySourceInventoryReport(rows=tuple(sorted(rows, key=lambda row: row.source_kind.value)))

    def support_matrix(self) -> ModeloSupportMatrixReport:
        """Return the registry-wide per-modelo support/capability matrix.

        For every modelo the authority can load, builds a :class:`ModeloEntry`
        capturing supported revisions, calc/manifest/export/extractor
        capability flags, declared per-ejercicio casilla renames, declared
        deprecation (support-removal) decisions, and declared AEAT-portal
        cross-references — every field read or folded directly from the
        loaded registry, never hand-maintained (see
        ``no-dormant-source-resolvers`` / ``no-silent-under-declaration``).

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
        definition, revision, filing_year, registry_period = self._resolve_revision(modelo, period=period, as_of=as_of)
        return _build_modelo_describe_report(
            definition,
            revision,
            filing_year=filing_year,
            registry_period=registry_period,
        )

    def describe_modelo_for_scope(
        self,
        modelo: str,
        *,
        filing_year: int,
        period: str,
        as_of: date | None = None,
    ) -> ModeloDescribeReport:
        """Return a :class:`~domain.calculations.registry._query_reports.ModeloDescribeReport` for a scope."""
        definition, revision, registry_period = self._resolve_revision_for_scope(
            modelo,
            filing_year=filing_year,
            period=period,
            as_of=as_of,
        )
        return _build_modelo_describe_report(
            definition,
            revision,
            filing_year=filing_year,
            registry_period=registry_period,
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
        definition, revision, filing_year, registry_period = self._resolve_revision(modelo, period=period, as_of=as_of)
        return _build_modelo_casillas_report(
            definition,
            revision,
            filing_year=filing_year,
            registry_period=registry_period,
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
        definition, revision, registry_period = self._resolve_revision_for_scope(
            modelo,
            filing_year=filing_year,
            period=period,
            as_of=as_of,
        )
        return _build_modelo_casillas_report(
            definition,
            revision,
            filing_year=filing_year,
            registry_period=registry_period,
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
        definition, revision, filing_year, registry_period = self._resolve_revision(modelo, period=period, as_of=as_of)
        return _casilla_detail_report(definition, revision, casilla, filing_year, registry_period)

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
        definition, revision, registry_period = self._resolve_revision_for_scope(
            modelo,
            filing_year=filing_year,
            period=period,
            as_of=as_of,
        )
        return _casilla_detail_report(definition, revision, casilla, filing_year, registry_period)

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
            rows=_binding_rows(snapshot.revision, modelo=str(definition.id), period=period),
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
        definition, revision, registry_period = self._resolve_revision_for_scope(
            modelo,
            filing_year=filing_year,
            period=period,
            as_of=as_of,
        )
        return _build_modelo_formulas_report(
            definition,
            revision,
            filing_year=filing_year,
            registry_period=registry_period,
        )

    def bindings_for_year(
        self,
        modelo: str,
        *,
        filing_year: int,
        as_of: date | None = None,
    ) -> ModeloBindingsReport:
        """Return a :class:`~domain.calculations.registry._query_reports.ModeloBindingsReport` for ``filing_year``.

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
        if len(covering) > 1:
            raise AmbiguousRevisionSelectionError(
                modelo_id=str(definition.id),
                candidate_ids=tuple(revision.id for revision in covering),
            )
        revision = covering[0]
        return ModeloBindingsReport(
            code=str(definition.id),
            revision=str(revision.id),
            filing_year=filing_year,
            filing_period=None,
            period=None,
            rows=_binding_rows(revision, modelo=str(definition.id)),
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
            A :class:`~domain.calculations.registry._query_reports.ModeloBindingsReport`
            for the resolved revision.

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
            rows=_binding_rows(revision, modelo=str(definition.id), period=registry_period),
        )

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
        definition, revision, filing_year, registry_period = self._resolve_revision(modelo, period=period, as_of=as_of)
        return _build_modelo_formulas_report(
            definition,
            revision,
            filing_year=filing_year,
            registry_period=registry_period,
        )

    def _resolve_revision(
        self,
        modelo: str,
        *,
        period: str | None,
        as_of: date | None,
    ) -> tuple[ModeloDefinition, ModeloRevision, int | None, str | None]:
        if as_of is not None:
            # The unscoped path resolves the latest revision by period and has no
            # filing-year context to gate an as_of date against a revision's
            # validity window, so honouring the argument here is impossible.
            # Refuse explicitly rather than accept-and-ignore (the accepted-parameter
            # lie this contract closes); the *_for_scope queries honour as_of.
            raise RegistryValidationError(
                "as_of point-in-time selection is not honoured by the unscoped period query, "
                "which resolves the latest revision by period; resolve with an explicit filing "
                "year so the as_of date is gated against each revision's validity window.",
            )
        definition = self._authority.validate_modelo(modelo.strip())
        if period is None:
            revision = max(definition.revisions.values(), key=lambda item: (item.valid_from, str(item.id)))
            return definition, revision, None, None
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
        declared_by_revision = tuple(
            token for revision in definition.revisions.values() for token in revision.period_selector.periods
        )
        registry_period = (
            registry_period_for_request(declared_by_revision, requested_period) or requested_period.upper()
        )
        snapshot = self._authority.snapshot(
            str(definition.id),
            filing_year=filing_year,
            period=registry_period,
            on=as_of,
        )
        return definition, snapshot.revision, registry_period


def _build_modelo_describe_report(
    definition: ModeloDefinition,
    revision: ModeloRevision,
    *,
    filing_year: int | None,
    registry_period: str | None,
) -> ModeloDescribeReport:
    """Assemble a :class:`ModeloDescribeReport` from a resolved definition/revision."""
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


def _build_modelo_casillas_report(
    definition: ModeloDefinition,
    revision: ModeloRevision,
    *,
    filing_year: int | None,
    registry_period: str | None,
    input_kind: InputKind | None,
    required: bool | None,
    form_number: str | None,
) -> ModeloCasillasReport:
    """Assemble a filtered :class:`ModeloCasillasReport` from a resolved revision."""
    rows = [
        ModeloCasillaRow(
            casilla_id=casilla.id,
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


def _build_modelo_formulas_report(
    definition: ModeloDefinition,
    revision: ModeloRevision,
    *,
    filing_year: int | None,
    registry_period: str | None,
) -> ModeloFormulasReport:
    """Assemble a :class:`ModeloFormulasReport` from a resolved revision."""
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
        filing_year=filing_year,
        filing_period=_query_filing_period(filing_year, registry_period),
        period=registry_period,
        rows=rows,
    )


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


def _casilla_detail_report(
    definition: ModeloDefinition,
    revision: ModeloRevision,
    casilla: str,
    filing_year: int | None,
    registry_period: str | None,
) -> ModeloCasillaDetailReport:
    """Build the single-casilla detail report, resolving the formula expression.

    The casilla is matched by canonical id first, then by printed ``number``
    (the same dual key the ``casillas --number`` filter accepts). An unknown
    casilla raises an instructive :class:`RegistryValidationError` naming a
    bounded sample of valid ids and the ``casillas`` verb that lists them all.
    A computed casilla's ``formula`` id is resolved against the revision's
    formulas so the structured expression rides the report.
    """
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
            f"valid casilla ids include: {sample}{overflow}. "
            f"Run 'aeat app modelo casillas {definition.id}' to list every casilla id and number.",
        )
    formula_expression: Mapping[str, object] | None = None
    if matched.formula is not None:
        formula = next((item for item in revision.formulas if item.id == matched.formula), None)
        if formula is not None:
            formula_expression = _public_mapping(formula.expression.model_dump(mode="json"))
    return ModeloCasillaDetailReport(
        code=str(definition.id),
        revision=str(revision.id),
        filing_year=filing_year,
        filing_period=_query_filing_period(filing_year, registry_period),
        period=registry_period,
        casilla_id=matched.id,
        number=matched.number,
        label=matched.label,
        localized_labels=dict(matched.localized_labels),
        localized_help=dict(matched.localized_help),
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
    by_target: dict[BindingId, list[RelationId]] = {}
    for relation in revision.relations:
        if period is not None and relation.target_periods and period not in relation.target_periods:
            continue
        by_target.setdefault(relation.target_binding, []).append(relation.id)
    return {target: tuple(relation_ids) for target, relation_ids in by_target.items()}


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
    relations_by_target: dict[BindingId, list[RelationDefinition]] = {}
    for relation in revision.relations:
        relations_by_target.setdefault(relation.target_binding, []).append(relation)
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
    if not isinstance(selector, Mapping):
        raise RegistryValidationError(
            f"binding selector projection requires a mapping or model, got {type(selector).__name__}",
        )
    entries = tuple(
        BindingSelectorQueryEntry(key=str(key), value=_public_selector_value(value))
        for key, value in sorted(selector.items(), key=lambda item: str(item[0]))
    )
    return BindingSelectorQueryProjection(
        source=str(source),
        keys=tuple(entry.key for entry in entries),
        entries=entries,
    )


def _public_mapping(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise RegistryValidationError(f"unsupported public mapping value {value!r}")
    return {str(key): _public_value(item) for key, item in value.items()}


def _public_selector_value(value: object) -> BindingSelectorQueryValue:
    public_value = _public_value(value)
    if isinstance(public_value, str | int | bool):
        return public_value
    if isinstance(public_value, tuple):
        string_items: list[str] = []
        for item in public_value:
            if not isinstance(item, str):
                break
            string_items.append(item)
        else:
            return tuple(string_items)
    raise RegistryValidationError(f"unsupported public binding selector value {public_value!r}")


def _public_value(value: object) -> object:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, tuple):
        return tuple(_public_value(item) for item in value)
    if isinstance(value, Mapping):
        return _public_mapping(value)
    return value


__all__ = [
    "BindingSelectorQueryEntry",
    "BindingSelectorQueryProjection",
    "ModeloBindingQueryRow",
    "ModeloBindingsReport",
    "ModeloCasillaDetailReport",
    "ModeloCasillaRow",
    "ModeloCasillasReport",
    "ModeloDescribeReport",
    "ModeloFormulaRow",
    "ModeloFormulasReport",
    "ModeloListReport",
    "ModeloListRow",
    "ModeloSupportMatrixReport",
    "RegistryQueryService",
]
