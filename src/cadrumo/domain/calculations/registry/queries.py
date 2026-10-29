"""Typed read API for the legacy validated-model introspection surfaces.

``RegistryQueryService`` wraps a :class:`ValidatedRegistryAuthority` and exposes
structured report objects for the CLI list, describe, casillas, formulas, and
bindings commands. Queries narrow to a single :class:`ModeloDefinition` and
then to one :class:`ModeloRevision` selected by filing year, period, and
optional revision id.

This service is intentionally not the indexed runtime bridge. Production
operations that hold a :class:`~.authority.PinnedAuthorityOperation` call its
typed ``modelo_directory``/``revision_for_context`` methods directly. The
explicit enumeration methods below remain available only for diagnostic
surfaces whose contract genuinely requires the complete validated graph.
"""

from __future__ import annotations

import re
from datetime import date
from typing import TYPE_CHECKING

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.modelo import Modelo
from ....core.period import RegistrySelectorPeriodCode
from ....core.tax_domain import TaxDomain
from .authority import ValidatedRegistryAuthority
from .errors import (
    RegistryFailureClassification,
    RegistryFailureCondition,
    RegistrySnapshotError,
    RegistryValidationError,
)
from .period_selector_match import registry_period_for_request, selector_token_for_request
from .query_builders import (
    ResolvedRegistryQueryContext,
    build_modelo_bindings_report,
    build_modelo_casillas_report,
    build_modelo_describe_report,
    build_modelo_formulas_report,
    casilla_detail_report,
)
from .query_reports import (
    ModeloBindingsReport,
    ModeloCasillaDetailReport,
    ModeloCasillasReport,
    ModeloDescribeReport,
    ModeloFormulasReport,
    ModeloListReport,
    ModeloListRow,
    ModeloSupportMatrixReport,
)
from .schema import ModeloDefinition, ModeloRevision
from .schema_input_kind import InputKind
from .support_matrix import build_support_matrix, build_support_matrix_from_directory_views
from .temporal import (
    ModeloRevisionDirectory,
    select_revision_for_year,
    select_revision_metadata_for_year,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .authority import PinnedAuthorityOperation
    from .schema_references import PeriodSelector


#: Bare registry period tokens (``0A``, ``1T``-``4T``, ``01``-``12``,
#: ``1P``-``4P``, ``EXT-1T``-``EXT-4T``, ``EVENT-N``) carry
#: no filing year. ``describe`` accepts them to narrow a modelo to a
#: revision that declares the token, without forcing the operator to
#: compose an artificial ``YYYY``-prefixed string.
_BARE_PERIOD_RE = re.compile(
    r"^(?:0A|[1-4]T|[1-4]P|0[1-9]|1[0-2]|EXT-[1-4]T|EVENT-\d+)$",
    re.I,
)


def _latest_revision(definition: ModeloDefinition) -> ModeloRevision:
    """Return the latest revision under the query service's deterministic tie-break."""
    return max(definition.revisions.values(), key=lambda item: (item.valid_from, item.id))


def _raise_unscoped_as_of_query(modelo: str) -> None:
    """Refuse a point-in-time argument when no filing year can scope it."""
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


def _period_revision_candidates(
    definition: ModeloDefinition,
    period: str,
) -> tuple[ModeloRevision, ...]:
    """Return revisions declaring ``period`` in the authority's order."""
    return tuple(
        revision
        for revision in definition.revisions.values()
        if selector_token_for_request(revision.period_selector.declared_periods, period) is not None
    )


def _resolve_declared_period_revision(
    definition: ModeloDefinition,
    *,
    period: str,
) -> ResolvedRegistryQueryContext:
    """Resolve a bare declared period to its latest declaring revision."""
    bare = period.strip()
    declared_by_revision = tuple(
        token for revision in definition.revisions.values() for token in revision.period_selector.declared_periods
    )
    token_is_declared = selector_token_for_request(declared_by_revision, bare) is not None
    if not (_BARE_PERIOD_RE.fullmatch(bare.upper()) or token_is_declared):
        raise RegistryValidationError(
            f"period must be a bare registry token; pass the filing year separately; got {period!r}",
        )
    candidates = _period_revision_candidates(definition, bare)
    if not candidates:
        declared = sorted(set(declared_by_revision))
        raise RegistryValidationError(
            f"period {period!r} is not declared by any revision of modelo "
            f"{definition.id}; declared periods: {', '.join(declared)}",
        )
    revision = max(candidates, key=lambda item: (item.valid_from, item.id))
    registry_token = selector_token_for_request(revision.period_selector.declared_periods, bare)
    if registry_token is None:
        raise RegistryValidationError(
            f"period {period!r} is not declared by revision {revision.id} of modelo {definition.id}",
        )
    return ResolvedRegistryQueryContext(
        definition=definition,
        revision=revision,
        registry_period=registry_token,
    )


class RegistryQueryService:
    """Legacy introspection facade over the eager validated authority graph.

    The constructor deliberately accepts only ``ValidatedRegistryAuthority``.
    It must not be widened to accept an indexed reader: indexed consumers use
    the already-pinned operation directly, keeping eager traversal visible and
    preventing a second selection implementation from drifting from the
    canonical runtime contract.
    """

    def __init__(self, authority: ValidatedRegistryAuthority) -> None:
        """Bind this read-only query service to one validated authority."""
        self._authority = authority

    def modelo_codes(self) -> tuple[str, ...]:
        """Return deterministic modelo identifiers from the authority index.

        This is the explicit bulk-enumeration seam for callers that need a
        catalogue of model identifiers.  It deliberately does not expose the
        authority's eager ``modelos`` graph; a subsequent operation must ask
        for the revision it actually needs.
        """
        return tuple(row.code for row in self.list_modelos().modelos)

    def revision_by_id(self, modelo: str, revision_id: str) -> ModeloRevision:
        """Return one exact revision component by canonical identity."""
        normalized = Modelo(modelo).value
        revisions = self.iter_modelo_revisions(modelo_codes=(normalized,))
        if not revisions:
            raise RegistrySnapshotError(
                f"modelo {normalized!r} is not present in the calculation registry",
            )
        for _modelo_id, revision in revisions:
            if revision.id == revision_id:
                return revision
        raise RegistryValidationError(
            f"modelo {normalized!r} has no revision {revision_id!r}",
        )

    def source_exists(self, source_reference_id: str) -> bool:
        """Return whether one source-reference metadata row is enrolled."""
        return source_reference_id in self._authority.catalogues.sources

    def iter_modelo_revisions(
        self,
        *,
        modelo_codes: tuple[str, ...] | None = None,
    ) -> tuple[tuple[str, ModeloRevision], ...]:
        """Explicitly enumerate revision components for diagnostics.

        Bulk walks are intentionally named and deterministic.  They are for
        source inventories and other diagnostics that genuinely need every
        revision; ordinary runtime consumers should use
        :meth:`resolve_revision_for_scope`.
        """
        selected = self._authority.modelos
        if modelo_codes is not None:
            allowed = frozenset(Modelo(code).value for code in modelo_codes)
            selected = tuple(modelo for modelo in selected if modelo.id in allowed)
        return tuple(
            (modelo.id, revision)
            for modelo in sorted(selected, key=lambda item: item.id)
            for revision in sorted(modelo.revisions.values(), key=lambda item: (item.valid_from, item.id))
        )

    def iter_modelo_definitions(self) -> tuple[ModeloDefinition, ...]:
        """Explicitly enumerate complete model metadata for diagnostics.

        This is intentionally separate from point lookup.  Support reports and
        source inventories are declared bulk operations; ordinary calculation
        consumers must use a selected revision method instead.
        """
        return tuple(sorted(self._authority.modelos, key=lambda item: item.id))

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
                registry :class:`~core.tax_domain.TaxDomain` equals the requested
                tax family (e.g. ``TaxDomain("iva")``). ``None`` returns every
                family. The ``year`` and ``domain`` filters compose: passing
                both narrows to modelos that satisfy each.

        Returns:
            A :class:`~domain.calculations.registry.query_reports.ModeloListReport`
            containing the matching rows.
        """
        rows = [
            ModeloListRow(
                code=modelo.id,
                title=modelo.title,
                cadence=modelo.cadence,
                tax_domain=modelo.tax_domain,
                revision_count=len(modelo.revisions),
            )
            for modelo in RegistryQueryService(self._authority).iter_modelo_definitions()
            if (
                year is None
                or _selectors_cover_year((revision.period_selector for revision in modelo.revisions.values()), year)
            )
            and (domain is None or modelo.tax_domain == domain)
        ]
        # Ordered into a pinned local first: pydantic's generated ``__init__``
        # accepts a mapping for a nested model, so sorting inline would let that
        # permissive parameter type flow back into the lambda and widen ``row``
        # to ``ModeloListRow | Mapping[str, Any]``.
        ordered: tuple[ModeloListRow, ...] = tuple(sorted(rows, key=lambda row: row.code))
        return ModeloListReport(modelos=ordered)

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
            A :class:`~domain.calculations.registry.query_reports.ModeloSupportMatrixReport`
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
            A :class:`~domain.calculations.registry.query_reports.ModeloDescribeReport`
            for the resolved revision.

        Raises:
            ``RegistryValidationError``: When ``modelo`` is not registered,
                the period is not declared by any revision, or no revision
                covers the requested scope.
        """
        return build_modelo_describe_report(self._resolve_revision(modelo, period=period, as_of=as_of))

    def describe_modelo_for_scope(
        self,
        modelo: str,
        *,
        filing_year: int,
        period: str,
        as_of: date | None = None,
    ) -> ModeloDescribeReport:
        """Return a :class:`~domain.calculations.registry.query_reports.ModeloDescribeReport` for a scope."""
        return build_modelo_describe_report(
            self.resolve_revision_for_scope(modelo, filing_year=filing_year, period=period, as_of=as_of),
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
            A :class:`~domain.calculations.registry.query_reports.ModeloCasillasReport`
            for the resolved revision, containing the filtered casilla rows.

        Raises:
            ``RegistryValidationError``: When the modelo or period is not
                registered, or no revision covers the requested scope.
        """
        return build_modelo_casillas_report(
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
        """Return a :class:`~domain.calculations.registry.query_reports.ModeloCasillasReport` for a scope."""
        return build_modelo_casillas_report(
            self.resolve_revision_for_scope(modelo, filing_year=filing_year, period=period, as_of=as_of),
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
            A :class:`~domain.calculations.registry.query_reports.ModeloCasillaDetailReport`
            for the addressed casilla.

        Raises:
            ``RegistryValidationError``: When the modelo or period is not
                registered, no revision covers the requested scope, or the
                casilla id/number is not defined by the resolved revision.
        """
        return casilla_detail_report(self._resolve_revision(modelo, period=period, as_of=as_of), casilla)

    def casilla_for_scope(
        self,
        modelo: str,
        casilla: str,
        *,
        filing_year: int,
        period: str,
        as_of: date | None = None,
    ) -> ModeloCasillaDetailReport:
        """Return a :class:`~domain.calculations.registry.query_reports.ModeloCasillaDetailReport` for a scope."""
        return casilla_detail_report(
            self.resolve_revision_for_scope(modelo, filing_year=filing_year, period=period, as_of=as_of),
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
            A :class:`~domain.calculations.registry.query_reports.ModeloBindingsReport`
            for the requested filing scope.
        """
        return build_modelo_bindings_report(
            self.resolve_revision_for_scope(modelo, filing_year=filing_year, period=period, as_of=as_of),
        )

    def bindings_for_year(
        self,
        modelo: str,
        *,
        filing_year: int,
        as_of: date | None = None,
    ) -> ModeloBindingsReport:
        """Return revision-wide bindings for one filing year and effective date."""
        return build_modelo_bindings_report(
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
        """Return a :class:`~domain.calculations.registry.query_reports.ModeloFormulasReport` for a scope."""
        return build_modelo_formulas_report(
            self.resolve_revision_for_scope(modelo, filing_year=filing_year, period=period, as_of=as_of),
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
            A :class:`~domain.calculations.registry.query_reports.ModeloBindingsReport`
            for the resolved revision.

        Raises:
            ``RegistryValidationError``: When the modelo or period is not
                registered, or no revision covers the requested scope.
        """
        return build_modelo_bindings_report(self._resolve_revision(modelo, period=period, as_of=as_of))

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
            A :class:`~domain.calculations.registry.query_reports.ModeloFormulasReport`
            for the resolved revision.

        Raises:
            ``RegistryValidationError``: When the modelo or period is not
                registered, or no revision covers the requested scope.
        """
        return build_modelo_formulas_report(self._resolve_revision(modelo, period=period, as_of=as_of))

    def _resolve_revision(
        self,
        modelo: str,
        *,
        period: str | None,
        as_of: date | None,
    ) -> ResolvedRegistryQueryContext:
        if as_of is not None:
            _raise_unscoped_as_of_query(modelo)
        normalized_modelo = modelo.strip()
        definition = self._authority.validate_modelo(normalized_modelo)
        revision_ids = self._revision_ids(normalized_modelo)
        if period is None:
            return ResolvedRegistryQueryContext(
                definition=definition,
                revision=_latest_revision(definition),
                revision_ids=revision_ids,
            )
        context = _resolve_declared_period_revision(definition, period=period)
        return context.model_copy(update={"revision_ids": revision_ids})

    def resolve_revision_for_scope(
        self,
        modelo: str,
        *,
        filing_year: int,
        period: str,
        as_of: date | None,
        grade: RegistryAuthorityGrade = RegistryAuthorityGrade.APPLICABILITY,
    ) -> ResolvedRegistryQueryContext:
        """Resolve the unique revision governing one explicit filing scope."""
        normalized_modelo = modelo.strip()
        definition = self._authority.validate_modelo(normalized_modelo)
        revision_ids = self._revision_ids(normalized_modelo)
        requested_period = period.strip()
        declared_by_revision = tuple(
            token for revision in definition.revisions.values() for token in revision.period_selector.declared_periods
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
            definition.id,
            filing_year=filing_year,
            period=registry_period,
            on=as_of,
            grade=grade,
        )
        return ResolvedRegistryQueryContext(
            definition=definition,
            revision=snapshot.revision,
            revision_ids=revision_ids,
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
        normalized_modelo = modelo.strip()
        definition = self._authority.validate_modelo(normalized_modelo)
        revision_ids = self._revision_ids(normalized_modelo)
        revision = select_revision_for_year(
            definition,
            filing_year=filing_year,
            on=as_of,
            support=self._authority.catalogues.supported_filing_years,
        )
        year_periods = revision.period_selector.periods_for_year(filing_year)
        if not year_periods:
            raise RegistryValidationError(
                f"modelo {definition.id} revision {revision.id!r} has no period token for filing year {filing_year}",
            )
        return ResolvedRegistryQueryContext(
            definition=definition,
            revision=revision,
            revision_ids=revision_ids,
            filing_year=filing_year,
            registry_period=year_periods[0],
        )

    def _revision_ids(self, modelo: str) -> tuple[str, ...]:
        """Return explicit revision metadata for a model-wide report."""
        return tuple(revision.id for _modelo_id, revision in self.iter_modelo_revisions(modelo_codes=(modelo,)))


class PinnedRegistryQueryService:
    """Report facade over one generation-pinned component operation.

    The legacy :class:`RegistryQueryService` remains the explicit eager
    diagnostic facade.  Application discovery uses this point-loaded variant:
    selector-complete directories provide metadata and each report hydrates
    only the revision selected for that query.
    """

    def __init__(self, operation: PinnedAuthorityOperation) -> None:
        """Bind the facade to one already-leased authority operation."""
        self._operation = operation

    def modelo_codes(self) -> tuple[str, ...]:
        """Return deterministic model identities from the pinned index."""
        return self._operation.modelo_ids()

    def iter_modelo_revisions(
        self,
        *,
        modelo_codes: tuple[str, ...] | None = None,
    ) -> tuple[tuple[str, ModeloRevision], ...]:
        """Explicitly enumerate point-loaded revisions for diagnostics."""
        allowed = None if modelo_codes is None else frozenset(Modelo(code).value for code in modelo_codes)
        rows: list[tuple[str, ModeloRevision]] = []
        for modelo_id in sorted(self._operation.modelo_ids()):
            if allowed is not None and modelo_id not in allowed:
                continue
            directory = self._operation.modelo_directory(modelo_id)
            for metadata in directory.revisions:
                rows.append((modelo_id, self._operation.revision(modelo_id, metadata.id)))
        return tuple(rows)

    def _latest_modelo_views(self) -> tuple[tuple[ModeloRevisionDirectory, ModeloDefinition], ...]:
        """Pair each modelo directory with the view materialized around its latest revision."""
        views: list[tuple[ModeloRevisionDirectory, ModeloDefinition]] = []
        for modelo_id in sorted(self._operation.modelo_ids()):
            directory = self._operation.modelo_directory(modelo_id)
            metadata = max(directory.revisions, key=lambda item: (item.valid_from, item.id))
            views.append(
                (directory, directory.materialize(self._operation.revision(modelo_id, metadata.id))),
            )
        return tuple(views)

    def iter_modelo_definitions(self) -> tuple[ModeloDefinition, ...]:
        """Materialize one latest revision view per modelo for diagnostics."""
        return tuple(definition for _directory, definition in self._latest_modelo_views())

    def list_modelos(
        self,
        *,
        year: int | None = None,
        domain: TaxDomain | None = None,
    ) -> ModeloListReport:
        """Return a metadata catalogue read from the modelo directories alone.

        Every listed field is modelo-level metadata the directory carries, and
        revision count and year coverage come from its complete revision
        metadata, so no revision payload is decoded.
        """
        rows: list[ModeloListRow] = []
        for modelo_id in self._operation.modelo_ids():
            directory = self._operation.modelo_directory(modelo_id)
            modelo = directory.modelo
            selectors = (metadata.period_selector for metadata in directory.revisions)
            if year is not None and not _selectors_cover_year(selectors, year):
                continue
            if domain is not None and TaxDomain(modelo.tax_domain) != domain:
                continue
            rows.append(
                ModeloListRow(
                    code=modelo.id,
                    title=modelo.title,
                    cadence=modelo.cadence,
                    tax_domain=TaxDomain(modelo.tax_domain),
                    revision_count=len(directory.revisions),
                ),
            )
        return ModeloListReport(modelos=tuple(sorted(rows, key=lambda row: row.code)))

    def support_matrix(self) -> ModeloSupportMatrixReport:
        """Build the explicit bulk support inventory from point-loaded views."""
        return ModeloSupportMatrixReport(entries=build_support_matrix_from_directory_views(self._latest_modelo_views()))

    def describe_modelo(
        self,
        modelo: str,
        *,
        period: str | None = None,
        as_of: date | None = None,
    ) -> ModeloDescribeReport:
        """Return one unscoped modelo description report."""
        return build_modelo_describe_report(self._resolve_revision(modelo, period=period, as_of=as_of))

    def describe_modelo_for_scope(
        self,
        modelo: str,
        *,
        filing_year: int,
        period: str,
        as_of: date | None = None,
    ) -> ModeloDescribeReport:
        """Return one filing-year-scoped modelo description report."""
        return build_modelo_describe_report(
            self.resolve_revision_for_scope(modelo, filing_year=filing_year, period=period, as_of=as_of),
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
        """Return the filtered casilla report for one unscoped modelo query."""
        return build_modelo_casillas_report(
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
        """Return the filtered casilla report for one filing-year scope."""
        return build_modelo_casillas_report(
            self.resolve_revision_for_scope(modelo, filing_year=filing_year, period=period, as_of=as_of),
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
        """Return one casilla detail from an unscoped modelo query."""
        return casilla_detail_report(self._resolve_revision(modelo, period=period, as_of=as_of), casilla)

    def casilla_for_scope(
        self,
        modelo: str,
        casilla: str,
        *,
        filing_year: int,
        period: str,
        as_of: date | None = None,
    ) -> ModeloCasillaDetailReport:
        """Return one casilla detail from a filing-year scope."""
        return casilla_detail_report(
            self.resolve_revision_for_scope(modelo, filing_year=filing_year, period=period, as_of=as_of),
            casilla,
        )

    def bindings(
        self,
        modelo: str,
        *,
        period: str | None = None,
        as_of: date | None = None,
    ) -> ModeloBindingsReport:
        """Return bindings for one unscoped modelo query."""
        return build_modelo_bindings_report(self._resolve_revision(modelo, period=period, as_of=as_of))

    def bindings_for_year(
        self,
        modelo: str,
        *,
        filing_year: int,
        as_of: date | None = None,
    ) -> ModeloBindingsReport:
        """Return bindings for one filing year."""
        return build_modelo_bindings_report(
            self._resolve_revision_for_year(modelo, filing_year=filing_year, as_of=as_of),
        )

    def bindings_for_scope(
        self,
        modelo: str,
        *,
        filing_year: int,
        period: str,
        as_of: date | None = None,
    ) -> ModeloBindingsReport:
        """Return bindings for one filing-year scope."""
        return build_modelo_bindings_report(
            self.resolve_revision_for_scope(modelo, filing_year=filing_year, period=period, as_of=as_of),
        )

    def formulas(
        self,
        modelo: str,
        *,
        period: str | None = None,
        as_of: date | None = None,
    ) -> ModeloFormulasReport:
        """Return formulas for one unscoped modelo query."""
        return build_modelo_formulas_report(self._resolve_revision(modelo, period=period, as_of=as_of))

    def formulas_for_scope(
        self,
        modelo: str,
        *,
        filing_year: int,
        period: str,
        as_of: date | None = None,
    ) -> ModeloFormulasReport:
        """Return formulas for one filing-year scope."""
        return build_modelo_formulas_report(
            self.resolve_revision_for_scope(modelo, filing_year=filing_year, period=period, as_of=as_of),
        )

    def _revision_ids(self, directory: ModeloRevisionDirectory) -> tuple[str, ...]:
        return tuple(metadata.id for metadata in directory.revisions)

    def _context(
        self,
        directory: ModeloRevisionDirectory,
        revision: ModeloRevision,
        *,
        filing_year: int | None = None,
        registry_period: RegistrySelectorPeriodCode | None = None,
    ) -> ResolvedRegistryQueryContext:
        return ResolvedRegistryQueryContext(
            definition=directory.materialize(revision),
            revision=revision,
            revision_ids=self._revision_ids(directory),
            filing_year=filing_year,
            registry_period=registry_period,
        )

    def _resolve_revision(
        self,
        modelo: str,
        *,
        period: str | None,
        as_of: date | None,
    ) -> ResolvedRegistryQueryContext:
        if as_of is not None:
            _raise_unscoped_as_of_query(modelo)
        directory = self._operation.modelo_directory(modelo.strip())
        if period is None:
            return self._latest_revision_context(directory)
        return self._period_revision_context(directory, period)

    def _latest_revision_context(self, directory: ModeloRevisionDirectory) -> ResolvedRegistryQueryContext:
        metadata = max(directory.revisions, key=lambda item: (item.valid_from, item.id))
        revision = self._operation.revision(directory.modelo_id, metadata.id)
        return self._context(directory, revision)

    def _period_revision_context(
        self,
        directory: ModeloRevisionDirectory,
        period: str,
    ) -> ResolvedRegistryQueryContext:
        requested = period.strip()
        declared = tuple(token for item in directory.revisions for token in item.period_selector.declared_periods)
        if not (_BARE_PERIOD_RE.fullmatch(requested.upper()) or bool(selector_token_for_request(declared, requested))):
            raise RegistryValidationError(
                f"period must be a bare registry token; pass the filing year separately; got {period!r}",
            )
        candidates = tuple(
            item
            for item in directory.revisions
            if selector_token_for_request(item.period_selector.declared_periods, requested) is not None
        )
        if not candidates:
            raise RegistryValidationError(
                f"period {period!r} is not declared by any revision of modelo {directory.modelo_id}; "
                f"declared periods: {', '.join(sorted(set(declared)))}",
            )
        metadata = max(candidates, key=lambda item: (item.valid_from, item.id))
        registry_period = selector_token_for_request(metadata.period_selector.declared_periods, requested)
        if registry_period is None:
            raise RegistryValidationError(
                f"period {period!r} is not declared by revision {metadata.id} of modelo {directory.modelo_id}",
            )
        return self._context(
            directory,
            self._operation.revision(directory.modelo_id, metadata.id),
            registry_period=registry_period,
        )

    def resolve_revision_for_scope(
        self,
        modelo: str,
        *,
        filing_year: int,
        period: str,
        as_of: date | None,
    ) -> ResolvedRegistryQueryContext:
        """Resolve the unique revision governing one explicit filing scope."""
        directory = self._operation.modelo_directory(modelo.strip())
        requested = period.strip()
        declared = tuple(token for item in directory.revisions for token in item.period_selector.declared_periods)
        registry_period = registry_period_for_request(declared, requested) or requested.upper()
        revision = self._operation.revision_for_context(
            directory.modelo_id,
            filing_year=filing_year,
            period=registry_period,
            on=as_of,
        )
        selected_token = selector_token_for_request(revision.period_selector.declared_periods, requested)
        return self._context(
            directory,
            revision,
            filing_year=filing_year,
            registry_period=selected_token or registry_period,
        )

    def _resolve_revision_for_year(
        self,
        modelo: str,
        *,
        filing_year: int,
        as_of: date | None,
    ) -> ResolvedRegistryQueryContext:
        directory = self._operation.modelo_directory(modelo.strip())
        # The same canonical year selection every other consumer uses, so a
        # year-scoped report names the revision a snapshot of that year selects.
        metadata = select_revision_metadata_for_year(directory, filing_year=filing_year, on=as_of)
        revision = self._operation.revision(directory.modelo_id, metadata.id)
        return self._context(
            directory,
            revision,
            filing_year=filing_year,
            registry_period=metadata.period_selector.periods_for_year(filing_year)[0],
        )


def _selectors_cover_year(selectors: Iterable[PeriodSelector], year: int) -> bool:
    return any(selector.includes_year(year) for selector in selectors)


__all__ = [
    "PinnedRegistryQueryService",
    "RegistryQueryService",
]
