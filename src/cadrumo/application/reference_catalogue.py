"""Bundled public reference reads shared by every frontend.

The published tax authority, the category vocabularies, the portal catalogue,
the authentication providers and the representative scopes are public data that
ships with the product. Each read here takes only the pinned authority
operation it needs, reads no profile and no private state, and contacts no
network, so the command line, the harness and the terminal interface answer the
same question with the same typed projection and no session.

Coordinates follow one rule for every registry read: a filing year is composed
with a period token into one typed :class:`~cadrumo.core.period.Period`; a
period token alone selects the latest revision; a year alone is incomplete.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from ..core.errors.hierarchy import CadrumoError
from ..core.i18n.render import tr
from ..core.modelo import Modelo
from ..core.period import Period, PeriodError, is_filing_period_token
from ..core.tax_domain import TaxDomain
from ..domain.auth.apoderamientos.catalogue import load_default_catalogue
from ..domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ..domain.calculations.registry.authority_artifact import AuthorityGenerationPin
from ..domain.calculations.registry.query_reports import ModeloCasillasReport, ModeloListRow
from ..domain.calculations.registry.schema_input_kind import InputKind
from ..domain.portals.categories import PortalCategory
from ..domain.portals.metadata import PortalMetadata
from .auth.output import AuthProviderRow, AuthProvidersResult
from .modelo.registry_discovery import (
    declared_modelo_period_tokens,
    registry_casilla,
    registry_casilla_for_registry_scope,
    registry_casillas,
    registry_casillas_for_registry_scope,
    registry_describe_modelo,
    registry_describe_modelo_for_registry_scope,
    registry_formulas,
    registry_formulas_for_registry_scope,
    registry_list_modelos,
    registry_support_matrix,
)
from .modelo.work_create_policy import ceded_autonomic_modelo_locale_key, modelo_work_create_refusal_locale_key
from .reference_catalogue_contracts import (
    ApoderadoScopesListResult,
    CasillaRowPayload,
    FormulaPayload,
    FormulasResult,
    LedgerCategoriesResult,
    LedgerIrpfCategoryPayload,
    ModeloCasillaResult,
    ModeloCasillasResult,
    ModeloDescribeResult,
    ModeloListResult,
    ModeloPortalCompatibilityRefPayload,
    ModeloRenamePayload,
    ModeloRowPayload,
    ModeloSupportMatrixEntryPayload,
    ModeloSupportMatrixResult,
    PortalEntryPayload,
    PortalsListResult,
    PortalsViewResult,
    SpendingCategoryFamilyPayload,
    printed_local_work_status,
)


class ReferenceQueryError(CadrumoError):
    """A reference read whose coordinates the reader must correct."""


class CededAutonomicModeloError(ReferenceQueryError):
    """The modelo is a ceded autonomic tax filed with a Comunidad Autonoma, not an AEAT modelo.

    ITP-AJD (``600`` / ``620``) and ISD (``650`` / ``660``) are absent from the
    calculation registry, so a lookup would otherwise surface a generic
    not-present error. ``locale_key`` names the instructive redirect and
    ``modelo`` is the requested code with whitespace removed.
    """

    def __init__(self, *, modelo: str, locale_key: str) -> None:
        """Retain the requested code and the redirect that explains it."""
        super().__init__(tr(locale_key, modelo=modelo))
        self.modelo = modelo
        self.locale_key = locale_key


class DiscoveryScopeIncompleteError(ReferenceQueryError):
    """A filing year was given without the period token it is composed with."""

    def __init__(self) -> None:
        """Name the missing coordinate."""
        super().__init__("a filing year requires a period")


class DiscoveryPeriodTokenError(ReferenceQueryError):
    """A filing year and period token do not compose into a filing period.

    ``declared_tokens`` lists every token any revision of the modelo declares,
    empty when the modelo is unknown, so a reader can correct the token.
    ``detail`` is the typed period's own refusal.
    """

    def __init__(
        self,
        *,
        filing_year: int,
        period_code: str,
        modelo: str,
        declared_tokens: tuple[str, ...],
        detail: str,
    ) -> None:
        """Retain the coordinates and the tokens the modelo declares."""
        super().__init__(self._message(filing_year, period_code, modelo, declared_tokens, detail))
        self.filing_year = filing_year
        self.period_code = period_code
        self.modelo = modelo
        self.declared_tokens = declared_tokens
        self.detail = detail

    @staticmethod
    def _message(filing_year: int, period_code: str, modelo: str, declared_tokens: tuple[str, ...], detail: str) -> str:
        if not declared_tokens:
            return detail
        return tr(
            "cli.app.modelo.work.period_token_invalid",
            token=period_code,
            modelo=modelo,
            year=filing_year,
            tokens=", ".join(declared_tokens),
        )


class PortalFilterConflictError(ReferenceQueryError):
    """A portal listing was filtered by category and by modelo at once."""

    def __init__(self) -> None:
        """Say that the two filters exclude each other."""
        super().__init__(tr("cli.app.live.portals.category_modelo_exclusive"))


@dataclass(frozen=True, slots=True)
class PinnedReferenceRead[ReportT]:
    """A public reference report and the published generation that answered it."""

    report: ReportT
    generation: AuthorityGenerationPin


def read_pinned_reference[ReportT](read: Callable[[PinnedAuthorityOperation], ReportT]) -> PinnedReferenceRead[ReportT]:
    """Answer one public reference read under a single pin of the published authority.

    The generation is taken while the pin is still held, so the report and the
    provenance it is returned with always name the same publication. A missing
    or corrupt publication refuses here; no source tree is read in its place.
    """
    with bundled_indexed_authority().operation() as operation:
        return PinnedReferenceRead(report=read(operation), generation=operation.generation)


@dataclass(frozen=True, slots=True)
class _RegistryScope:
    filing_year: int
    period: str


def refuse_ceded_autonomic_modelo(modelo: str) -> None:
    """Raise the regional redirect when ``modelo`` is a ceded autonomic tax.

    A no-op for every registry-backed or genuinely unknown code.
    """
    code = modelo.strip()
    locale_key = ceded_autonomic_modelo_locale_key(code)
    if locale_key is not None:
        raise CededAutonomicModeloError(modelo=code, locale_key=locale_key)


def _declared_tokens(modelo: str, operation: PinnedAuthorityOperation) -> tuple[str, ...]:
    try:
        return declared_modelo_period_tokens(modelo, operation=operation)
    except CadrumoError:
        return ()


def _registry_scope(
    modelo: str, *, filing_year: int | None, period: str | None, operation: PinnedAuthorityOperation
) -> _RegistryScope | None:
    """Compose a filing year and a period token, or report that neither scopes the read.

    A token that is no filing period, such as a census event, scopes the read
    as the registry declares it when the modelo declares it.
    """
    if filing_year is None:
        return None
    if period is None or not period.strip():
        raise DiscoveryScopeIncompleteError
    token = period.strip()
    try:
        composed = Period.from_year_and_code(filing_year, token)
    except PeriodError as error:
        declared_tokens = _declared_tokens(modelo, operation)
        if not is_filing_period_token(token) and token in declared_tokens:
            return _RegistryScope(filing_year=filing_year, period=token)
        raise DiscoveryPeriodTokenError(
            filing_year=filing_year,
            period_code=period,
            modelo=modelo,
            declared_tokens=declared_tokens,
            detail=str(error),
        ) from error
    return _RegistryScope(filing_year=composed.filing_year, period=composed.registry_token)


def _modelo_row_payload(row: ModeloListRow) -> ModeloRowPayload:
    locale_key = modelo_work_create_refusal_locale_key(row.code)
    local_work_supported = locale_key is None
    return ModeloRowPayload(
        code=row.code,
        title=row.title,
        cadence=row.cadence,
        tax_domain=row.tax_domain,
        revision_count=row.revision_count,
        local_work_supported=local_work_supported,
        local_work_status=printed_local_work_status(supported=local_work_supported),
        local_work_guidance=None if locale_key is None else tr(locale_key, modelo=row.code),
    )


def list_modelos(
    *, year: int | None = None, domain: TaxDomain | None = None, operation: PinnedAuthorityOperation
) -> ModeloListResult:
    """List the registry's modelos, optionally for one filing year or tax family."""
    report = registry_list_modelos(year=year, domain=domain, operation=operation)
    return ModeloListResult(
        year_filter=year,
        domain_filter=domain.value if domain is not None else None,
        modelo_count=len(report.modelos),
        modelos=[_modelo_row_payload(row) for row in report.modelos],
    )


def describe_modelo(
    modelo: str,
    *,
    year: int | None = None,
    period: str | None = None,
    as_of: date | None = None,
    operation: PinnedAuthorityOperation,
) -> ModeloDescribeResult:
    """Describe one modelo revision, for an exact filing year and period or the latest by period."""
    refuse_ceded_autonomic_modelo(modelo)
    scope = _registry_scope(modelo, filing_year=year, period=period, operation=operation)
    if scope is None:
        report = registry_describe_modelo(modelo, period=period, as_of=as_of, operation=operation)
    else:
        report = registry_describe_modelo_for_registry_scope(
            modelo, filing_year=scope.filing_year, period=scope.period, as_of=as_of, operation=operation
        )
    return ModeloDescribeResult.from_report(report)


def _casilla_row_payloads(report: ModeloCasillasReport, casilla_number: str | None) -> list[CasillaRowPayload]:
    number_filter = casilla_number.strip() if casilla_number is not None else None
    return [
        CasillaRowPayload(
            casilla_id=row.casilla_id,
            number=row.number,
            input_kind=row.input_kind,
            required=bool(row.required),
            label=row.label,
            help_text=row.help_text,
            section=tuple(row.section),
            data_type=row.data_type,
            binding=row.binding,
            formula=row.formula,
            form_number=row.form_number,
            legal_refs=tuple(row.legal_refs),
            source_refs=tuple(row.source_refs),
        )
        for row in report.rows
        if not (number_filter is not None and number_filter)
        or row.number == number_filter
        or row.casilla_id == number_filter
    ]


def list_casillas(
    modelo: str,
    *,
    year: int | None = None,
    period: str | None = None,
    as_of: date | None = None,
    input_kind: InputKind | None = None,
    required: bool = False,
    form_number: str | None = None,
    casilla_number: str | None = None,
    operation: PinnedAuthorityOperation,
) -> ModeloCasillasResult:
    """List the casillas of one modelo revision, narrowed by kind, requiredness, form box or number."""
    refuse_ceded_autonomic_modelo(modelo)
    scope = _registry_scope(modelo, filing_year=year, period=period, operation=operation)
    if scope is None:
        report = registry_casillas(
            modelo,
            period=period,
            as_of=as_of,
            input_kind=input_kind,
            required=True if required else None,
            form_number=form_number,
            operation=operation,
        )
    else:
        report = registry_casillas_for_registry_scope(
            modelo,
            filing_year=scope.filing_year,
            period=scope.period,
            as_of=as_of,
            input_kind=input_kind,
            required=True if required else None,
            form_number=form_number,
            operation=operation,
        )
    rows = _casilla_row_payloads(report, casilla_number)
    return ModeloCasillasResult(
        code=report.code,
        modelo=report.code,
        revision=report.revision,
        filing_year=report.filing_year,
        filing_period=report.filing_period,
        period=report.period,
        casilla_count=len(rows),
        rows=rows,
    )


def describe_casilla(
    modelo: str,
    casilla: str,
    *,
    year: int | None = None,
    period: str | None = None,
    as_of: date | None = None,
    operation: PinnedAuthorityOperation,
) -> ModeloCasillaResult:
    """Describe one casilla: its label, grounding, input kind and, when computed, its formula."""
    refuse_ceded_autonomic_modelo(modelo)
    scope = _registry_scope(modelo, filing_year=year, period=period, operation=operation)
    if scope is None:
        report = registry_casilla(modelo, casilla, period=period, as_of=as_of, operation=operation)
    else:
        report = registry_casilla_for_registry_scope(
            modelo, casilla, filing_year=scope.filing_year, period=scope.period, as_of=as_of, operation=operation
        )
    return ModeloCasillaResult(
        code=report.code,
        modelo=report.code,
        revision=report.revision,
        filing_year=report.filing_year,
        filing_period=report.filing_period,
        period=report.period,
        casilla_id=report.casilla_id,
        number=report.number,
        label=report.label,
        help_text=report.help_text,
        section=tuple(report.section),
        data_type=report.data_type,
        input_kind=str(report.input_kind),
        required=bool(report.required),
        legal_refs=tuple(report.legal_refs),
        source_refs=tuple(report.source_refs),
        binding=report.binding,
        formula_id=report.formula_id,
        formula_expression=dict(report.formula_expression) if report.formula_expression is not None else None,
    )


def list_formulas(
    modelo: str,
    *,
    year: int | None = None,
    period: str | None = None,
    as_of: date | None = None,
    operation: PinnedAuthorityOperation,
) -> FormulasResult:
    """List the formulas of one modelo revision with their inputs and grounding."""
    refuse_ceded_autonomic_modelo(modelo)
    scope = _registry_scope(modelo, filing_year=year, period=period, operation=operation)
    if scope is None:
        report = registry_formulas(modelo, period=period, as_of=as_of, operation=operation)
    else:
        report = registry_formulas_for_registry_scope(
            modelo, filing_year=scope.filing_year, period=scope.period, as_of=as_of, operation=operation
        )
    return FormulasResult(
        code=report.code,
        revision=report.revision,
        filing_year=report.filing_year,
        filing_period=report.filing_period,
        period=report.period,
        formula_count=len(report.rows),
        rows=tuple(
            FormulaPayload(
                formula_id=row.formula_id,
                target_casilla_id=row.target_casilla_id,
                input_casilla_ids=tuple(row.input_casilla_ids),
                input_bindings=tuple(row.input_bindings),
                input_parameters=tuple(row.input_parameters),
                input_relations=tuple(row.input_relations),
                expression=dict(row.expression),
                legal_refs=tuple(row.legal_refs),
                source_refs=tuple(row.source_refs),
            )
            for row in report.rows
        ),
    )


def read_support_matrix(*, operation: PinnedAuthorityOperation) -> ModeloSupportMatrixResult:
    """Read the registry-wide per-modelo support and capability matrix."""
    entries = [
        ModeloSupportMatrixEntryPayload(
            modelo_id=entry.modelo_id,
            title=entry.title,
            calculation_class=entry.calculation_class,
            revision_count=entry.revision_count,
            latest_revision_id=entry.latest_revision_id,
            latest_revision_valid_from=entry.latest_revision_valid_from.isoformat(),
            supported_revision_ids=list(entry.supported_revision_ids),
            calc_grade=entry.calc_grade,
            has_completeness_manifest=entry.has_completeness_manifest,
            has_fixed_width_export=entry.has_fixed_width_export,
            has_xml_dictionary_export=entry.has_xml_dictionary_export,
            has_extractor=entry.has_extractor,
            extraction_profile_count=entry.extraction_profile_count,
            renames=[
                ModeloRenamePayload(
                    continuidad_id=rename.continuidad_id,
                    from_revision=rename.from_revision,
                    to_revision=rename.to_revision,
                    evolution_kind=rename.evolution_kind,
                )
                for rename in entry.renames
            ],
            portal_compatibility_refs=[
                ModeloPortalCompatibilityRefPayload(id=ref.id, surface=ref.surface, evidence_tier=ref.evidence_tier)
                for ref in entry.portal_compatibility_refs
            ],
        )
        for entry in registry_support_matrix(operation=operation).entries
    ]
    return ModeloSupportMatrixResult(modelo_count=len(entries), entries=entries)


def read_ledger_categories() -> LedgerCategoriesResult:
    """Read the spending-category families and the IRPF categories a ledger row may carry."""
    from ..domain.categories.spending_category import SpendingCategoryFamily, categories_for_family
    from ..domain.categories.spending_category_catalogue import spending_category_tokens
    from ..domain.transactions.irpf_categories import ledger_irpf_category_catalogue

    families = [
        SpendingCategoryFamilyPayload(family=family.value, category_ids=[member.value for member in members])
        for family in SpendingCategoryFamily
        if (members := categories_for_family(family))
    ]
    irpf_categories = [
        LedgerIrpfCategoryPayload(
            id=category.id,
            purpose=category.purpose,
            directions=[direction.value for direction in category.directions],
            net_paid_invoice=category.net_paid,
            related_category_ids=list(category.related_ids),
        )
        for category in ledger_irpf_category_catalogue()
    ]
    return LedgerCategoriesResult(
        families=families,
        category_ids=[category.value for category in spending_category_tokens()],
        irpf_categories=irpf_categories,
        irpf_category_ids=[category.id for category in irpf_categories],
        net_paid_withholding_irpf_category_ids=[
            category.id for category in irpf_categories if category.net_paid_invoice
        ],
        income_requires_category=False,
    )


def _portal_payload(metadata: PortalMetadata) -> PortalEntryPayload:
    from ..domain.portals.hosts import portal_host_name

    # `metadata.label` and `metadata.purpose` are translation keys, so they are
    # rendered here rather than handed on as raw key paths.
    return PortalEntryPayload(
        portal=metadata.portal.value,
        category=metadata.category.value,
        subdomain=portal_host_name(metadata.subdomain),
        url=str(metadata.url),
        auth_methods=",".join(sorted(method.value for method in metadata.auth_methods)),
        url_stability=metadata.url_stability.value,
        label=tr(str(metadata.label)),
        purpose=tr(str(metadata.purpose)),
        active=metadata.active,
    )


def list_portals(*, category: PortalCategory | None = None, modelo: Modelo | None = None) -> PortalsListResult:
    """List the local AEAT portal catalogue, optionally for one category or one modelo.

    Raises:
        PortalFilterConflictError: When both filters are given.
        PortalRegistryError: When the catalogue cannot answer the filter.
    """
    from ..domain.portals.registry import PORTAL_REGISTRY, portals_by_category, portals_for_modelo

    if category is not None and modelo is not None:
        raise PortalFilterConflictError
    if category is not None:
        entries = portals_by_category(category)
    elif modelo is not None:
        entries = portals_for_modelo(modelo)
    else:
        entries = tuple(PORTAL_REGISTRY.values())
    rows = [_portal_payload(entry) for entry in entries]
    return PortalsListResult(count=len(rows), rows=rows)


def view_portal(portal_id: str) -> PortalsViewResult:
    """Read one portal-catalogue entry by its portal id.

    Raises:
        PortalRegistryError: When the id names no catalogued portal.
    """
    from ..domain.portals.registry import get_portal

    return PortalsViewResult(**_portal_payload(get_portal(portal_id)).model_dump())


def list_auth_providers() -> AuthProvidersResult:
    """List the supported authentication providers with their labels in the output language."""
    from .auth.operator import list_operator_auth_providers

    # `label` and `description` are translation keys; rendering them here keeps the
    # structured answer and any text derived from it in the same words.
    return AuthProvidersResult(
        providers=[
            AuthProviderRow(id=provider.id, label=tr(str(provider.label)), description=tr(str(provider.description)))
            for provider in list_operator_auth_providers().providers
        ]
    )


def list_apoderado_scopes(*, operation: PinnedAuthorityOperation) -> ApoderadoScopesListResult:
    """List the representative scopes the published catalogue defines."""
    catalogue = load_default_catalogue(operation=operation)
    # Field by field: a JSON round trip hands the strict schema lists where the
    # catalogue holds tuples, and the schema correctly refuses them.
    return ApoderadoScopesListResult(catalogue_version=catalogue.catalogue_version, scopes=list(catalogue.scopes))
