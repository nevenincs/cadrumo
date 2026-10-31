"""Registry-grounded modelo-applicability derivation from the taxpayer model.

The overview surfaces (``explain`` / ``calendar`` / ``agenda`` /
``backlog``) used to treat every profile as an *autónomo en estimación
directa*: the :class:`~domain.deadlines.engine.DeadlineEngine` produces an
obligation for every modelo with a registered deadline window, and no
layer asked *which kind of taxpayer this is*. A pure landlord was told
Modelo 130 was overdue.

This module is the derivation layer: each modelo's ``applicable``
verdict is DERIVED from the three-axis
:class:`~domain.deadlines.models.TaxpayerProfile` model (entity type,
IRPF income categories, estimation regime) through a registry-grounded
rule table. The autónomo-by-default assumption is removed.

Four verdicts are possible:

* :attr:`ApplicabilityVerdict.APPLICABLE` — the taxpayer model
  triggers this modelo.
* :attr:`ApplicabilityVerdict.NOT_APPLICABLE` — the taxpayer model
  positively excludes this modelo (a landlord has no Modelo 130;
  an S.L. has no Modelo 100).
* :attr:`ApplicabilityVerdict.ATTRIBUTION_PASS_THROUGH` — the
  profile is an *attribution entity* (comunidad de bienes, sociedad
  civil sin objeto mercantil) and the modelo asked about is a cuota
  self-assessment (the IRPF Modelo 100 / 130 or the IS Modelo
  200 / 202). An attribution entity runs no IS and no IRPF cuota of
  its own — the régimen de atribución de rentas (LIRPF Title X
  Section 2) attributes the income to the members, who file the
  substantive tax. The honest answer to "what is my cuota" is
  "none — taxed in the members' returns". This is structurally
  distinct from a plain ``NOT_APPLICABLE``: a salaried-only natural
  person is positively excluded from Modelo 200 because they file a
  *different* cuota (Modelo 100); an attribution entity files *no*
  cuota at all.
* :attr:`ApplicabilityVerdict.INCOMPLETE` — the taxpayer model is
  undeclared (no ``entity_type`` and, for a natural person, no income
  categories), or the entity form is recognised-but-unsupported. The
  engine refuses to guess: it never reports a confident wrong
  obligation, and it never runs an IRPF cuota for a company or an IS
  cuota for an attribution entity.

The entity-type axis selects the *income-tax* route: a legal entity
routes to the IS path (Modelo 200 / 202), a natural person to the IRPF
path (Modelo 100 / 130), and an attribution entity to member
pass-through for cuota self-assessments. IVA and payer-fact modelos are
then decided by their own declared profile facts (IVA regime,
withholding-payer facts, trade thresholds). The engine routing contract
does not treat pass-through income taxation as an exemption from
non-income-tax obligations.

**Canonical applicability authority: modelo level.**
The rule a revision declares in the registry is the single source for modelo-level
applicability. Any question of the form "does this taxpayer ever owe this modelo?" is
answered through :func:`derive_modelo_applicability`; code does not hold a second copy.

**Relation to ``applicability_conditions`` on ``ModeloDeadlineWindow``.**
``ModeloDeadlineWindow`` carries a
``applicability_conditions`` mapping that governs *window-level*
scheduling — which specific deadline window applies for a profile
within the set of applicable windows (e.g. Modelo 202 uses different
modality windows for the April / October / December instalments, and
some windows filter by ``entity_size``). These conditions are
COMPLEMENTARY to the modelo-level rules, not replacements:
``applicability_conditions`` operates after the modelo-level gate
confirms the modelo applies at all; it never overrides the modelo-level
verdict. Adding a condition to a deadline window does not affect the
``ApplicabilityVerdict`` returned by :func:`derive_modelo_applicability`.

Every rule carries ``legal_refs``: scoped registry citation keys in the ``law-slug:art-N``
form that resolve against the legal tables of the registry. A modelo whose revisions declare
no rule is reported INCOMPLETE with a rationale that says so.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from .authority import PinnedAuthorityOperation, ValidatedRegistryAuthority
    from .schema import ModeloRevision

from ....core.i18n.render import tr
from ....core.modelo import Modelo
from ....core.time.clock import today_madrid
from ...contribuyente.entity_type import (
    entity_type_natural_person_token,
    require_entity_type,
)
from ...contribuyente.renta_codes import FiscalResidency
from ...deadlines.models import (
    TaxpayerProfile,
)
from .applicability_models import (
    NO_LEDGER_PAYER_FACTS,
    ApplicabilityEvidenceDisagreement,
    ApplicabilityProvenance,
    ApplicabilityVerdict,
    LedgerPayerFactDerivation,
    ModeloApplicability,
    ModeloApplicabilityExclusion,
    ModeloApplicabilityRule,
    incomplete_applicability,
    registry_applicability_reason,
)
from .applicability_payer_facts import (
    PayerFactProjection,
    resolve_payer_fact,
)
from .applicability_routes import TaxRoute, tax_route_for_entity_type
from .errors import RegistryValidationError
from .form_codes import resolve_form_codes
from .ids import LegalRefId
from .irpf_income_categories import (
    irpf_income_category_actividad_economica_token,
    require_irpf_income_category,
)
from .irpf_regimes import require_irpf_estimation_regime
from .iva_regime_vocabulary import require_iva_regime
from .schema_revision_members import ApplicabilityExclusionDefinition, ApplicabilityRuleDefinition
from .third_party_declaration_roles import resolve_third_party_declaration_role_catalogue


def _hydrate_applicability_exclusion(fragment: ApplicabilityExclusionDefinition) -> ModeloApplicabilityExclusion:
    """Hydrate one exclusion, refusing a fact that cannot tell a declared no from an unanswered one."""
    payer_fact = resolve_payer_fact(fragment.payer_fact) if fragment.payer_fact is not None else None
    if payer_fact is not None and not (isinstance(payer_fact, PayerFactProjection) and payer_fact.three_state):
        raise RegistryValidationError(
            f"exclusion {fragment.id!r} reads payer fact {fragment.payer_fact!r}, which cannot tell a declared no "
            "from an unanswered question",
        )
    selection = fragment.declaration_role_selection
    return ModeloApplicabilityExclusion(
        id=fragment.id,
        outcome=ApplicabilityVerdict(fragment.outcome),
        entity_types=frozenset(require_entity_type(value) for value in fragment.entity_types),
        iva_regimes=frozenset(require_iva_regime(value) for value in fragment.iva_regimes),
        lacking_income_categories=frozenset(
            require_irpf_income_category(value) for value in fragment.lacking_income_categories
        ),
        declaration_roles=(
            None if selection is None else resolve_third_party_declaration_role_catalogue().roles_for_clave(selection)
        ),
        payer_fact=payer_fact,
        payer_fact_declared=fragment.payer_fact_declared,
        reason=fragment.reason,
        legal_refs=fragment.legal_refs,
    )


def hydrate_applicability_rule(modelo: Modelo, fragment: ApplicabilityRuleDefinition) -> ModeloApplicabilityRule:
    """Hydrate a registry-authored applicability fragment into the runtime rule.

    The loader boundary for the ``applicability`` schema family: every
    free-form TOML string on ``fragment`` is resolved
    here to its typed registry token (or :class:`PayerFactValue`),
    never left as a raw string for a downstream branch to compare against.
    An unknown token raises :class:`RegistryValidationError` naming the
    offending rule and the underlying enum-coercion error, mirroring the
    coercion-boundary shape :data:`~._schema_base.RevisionReviewStatusField`
    and its siblings already use.

    Args:
        modelo: The modelo the owning revision belongs to; the fragment
            carries no self-referential ``modelo`` field to avoid a value
            that could silently diverge from the revision it is nested in.
        fragment: The validated :class:`ApplicabilityRuleDefinition` to hydrate.

    Returns:
        The equivalent :class:`ModeloApplicabilityRule`.

    Raises:
        RegistryValidationError: A field names a token not declared by the
            selected facts registry.
    """
    try:
        return ModeloApplicabilityRule(
            modelo=modelo.value,
            applicable_entity_types=frozenset(require_entity_type(value) for value in fragment.applicable_entity_types),
            required_income_categories=frozenset(
                require_irpf_income_category(value) for value in fragment.required_income_categories
            ),
            required_estimation_regimes=frozenset(
                require_irpf_estimation_regime(value) for value in fragment.required_estimation_regimes
            ),
            applicable_fiscal_residencies=frozenset(
                FiscalResidency.from_registry(value) for value in fragment.applicable_fiscal_residencies
            ),
            applicable_iva_regimes=frozenset(require_iva_regime(value) for value in fragment.applicable_iva_regimes),
            required_payer_fact=resolve_payer_fact(fragment.required_payer_fact)
            if fragment.required_payer_fact is not None
            else None,
            applicable_reason=fragment.applicable_reason,
            not_applicable_reason=fragment.not_applicable_reason,
            cuota_bearing=fragment.cuota_bearing,
            exclusions=tuple(_hydrate_applicability_exclusion(exclusion) for exclusion in fragment.exclusions),
            legal_refs=fragment.legal_refs,
        )
    except (ValueError, RegistryValidationError) as exc:
        raise RegistryValidationError(
            f"applicability rule {fragment.id!r} for modelo {modelo.value!r} does not hydrate: {exc}",
        ) from exc


_IMPATRIADO_M720_LEGAL_REFS: tuple[LegalRefId, ...] = (
    "ley-35-2006:art-93",  # LIRPF Art. 93 — régimen especial impatriados.
    "ley-7-2012:da-1",  # Ley 7/2012 DA 1ª — obligación Modelo 720.
    "orden-hap-72-2013:art-1",  # Orden HAP/72/2013 — aprobación Modelo 720.
)
"""Legal refs grounding the IRPF Art. 93 impatriado Modelo 720 exemption.

An impatriado under LIRPF Art. 93 is taxed as a non-resident (IRNR) for
the duration of the special regime. Modelo 720 (bienes en el extranjero)
is an obligation reserved for IRPF residents; it does not extend to
non-residents or to IRPF taxpayers who have opted into the IRNR-rate
regime. The general Art. 93 key resolves in the registry table
``legal/irpf-impatriados.toml``; the two Modelo 720 keys resolve in the
table ``legal/modelo-720.toml``.
"""

_IMPATRIADO_M151_ROUTE_LEGAL_REFS: tuple[LegalRefId, ...] = (
    "ley-35-2006:art-93",  # LIRPF Art. 93 — impatriados opt into IRNR taxation.
    "rd-439-2007:art-115",  # RIRPF Art. 115 — duration of the special regime.
    "rd-439-2007:art-116",  # RIRPF Art. 116 — option exercise / start-date selector.
    # Form orders for the Modelo 151 declaration, both eras. This was a single
    # ref to `orden-eha-2887-2008:modelo-151`, which the registry retired as a
    # stub whose document_id never resolved to real text; it grounded nothing and
    # was absent from the legal catalogue, so this tuple carried a dangling id.
    # The real instruments are bundled: Orden HAP/2783/2015 governs 2015-2022 and
    # Orden HFP/1338/2023 governs ejercicio 2023 onward, per its own Disposicion
    # Final Segunda(a). Both are cited because the route's grounding spans the
    # whole regime rather than one filing year.
    "orden-hap-2783-2015:art-1",
    "orden-hfp-1338-2023:art-1",
)
"""Legal refs grounding the Art. 93 Modelo 151 route and M100 suppression."""

_IMPATRIADO_M100_SUPPRESSED_REASON_LOCALE_KEY = "filing.applicability.impatriado_m100_suppressed"
"""``NOT_APPLICABLE`` rationale for suppressing M100 during Art. 93."""

_IMPATRIADO_M151_APPLICABLE_REASON_LOCALE_KEY = "filing.applicability.impatriado_m151_applicable"
"""``APPLICABLE`` rationale for the active Art. 93 Modelo 151 route."""

_IMPATRIADO_M151_NOT_APPLICABLE_REASON_LOCALE_KEY = "filing.applicability.impatriado_m151_not_applicable"
"""``NOT_APPLICABLE`` rationale for M151 outside the active Art. 93 window."""


_ROUTES_FACT: Final = "modelo-applicability-routes"
"""The fact naming the forms the art. 93 regime reroutes while its window is open."""


def resolve_applicability_rule_from_authority(
    authority: ValidatedRegistryAuthority,
    modelo: Modelo,
) -> ModeloApplicabilityRule:
    """Resolve one modelo's applicability rule from an already-loaded authority.

    Reads the UNVALIDATED :class:`~._schema.ModeloDefinition`
    (``authority.modelo(...)``), not ``validate_modelo``/``snapshot``:
    applicability derivation is a pervasive, taxpayer-facing read on every
    profile view, and coupling its availability to full business-rule
    validation or the review-status filing gate would make an unrelated
    validation defect elsewhere in the tree break every taxpayer's
    applicability answer. The fragment was already validated once, when the
    registry authority was built and published.

    This is a deliberate asymmetry with :class:`~._schema.RegistrySnapshot`,
    which carries a same-shaped projection for every OTHER schema family:
    applicability answers "is this modelo due, and to whom" -- the floor rung
    of the authority-grade ladder, scheduling reach, not filing authority.
    ``RegistrySnapshot`` is a filing-context projection one rung up. Resolving
    applicability without filing-grade review is correct per that ladder, not
    a gate dodged; coupling it to snapshot construction would wrongly tie a
    floor-rung fact to filing authority it does not need.

    Applicability content is uniform across a modelo's declared revisions
    today (the migrator authors the identical rule into every one), so any
    revision carrying the family answers the question -- the first one found
    is used.

    Split out from :func:`_resolve_registry_applicability_rule` so the real
    logic takes its authority as a parameter and is testable against a
    scratch :class:`ValidatedRegistryAuthority` without touching the bundled
    tree or monkeypatching anything; the production wrapper leases the indexed
    generation only when a caller has not already supplied an operation.

    Raises:
        RegistryValidationError: No declared revision carries an
            ``applicability`` rule, or the rule fails to hydrate.
    """
    from .queries import RegistryQueryService

    for _modelo_id, revision in RegistryQueryService(authority).iter_modelo_revisions(
        modelo_codes=(modelo.value,),
    ):
        if revision.applicability:
            return hydrate_applicability_rule(modelo, revision.applicability[0])
    raise RegistryValidationError(f"no declared revision of modelo {modelo.value!r} carries an applicability rule")


def _declared_applicability_rule(
    operation: PinnedAuthorityOperation,
    modelo: Modelo,
) -> ModeloApplicabilityRule | None:
    """Return the rule a pinned revision of ``modelo`` declares, or ``None`` when none does."""
    if modelo.value not in operation.modelo_ids():
        return None
    for metadata in operation.modelo_directory(modelo.value).revisions:
        revision = operation.revision(modelo.value, metadata.id)
        if revision.applicability:
            return hydrate_applicability_rule(modelo, revision.applicability[0])
    return None


def _authority_revisions(authority: ValidatedRegistryAuthority, modelo: Modelo) -> Iterable[tuple[str, ModeloRevision]]:
    from .queries import RegistryQueryService

    return RegistryQueryService(authority).iter_modelo_revisions(modelo_codes=(modelo.value,))


def _resolve_registry_applicability_rule(
    modelo: Modelo,
    *,
    authority: ValidatedRegistryAuthority | None = None,
    operation: PinnedAuthorityOperation | None = None,
) -> ModeloApplicabilityRule | None:
    """Resolve one modelo's applicability rule from the pinned registry generation.

    The import is function-local by necessity, not preference: ``_authority``
    transitively imports THIS module already, through the build-validation
    dispatch chain (``_authority`` -> ``_snapshot`` -> ``_validate`` ->
    ``_validate_revision_sections`` -> ``validate_applicability_section`` ->
    here), so a module-level authority import would close a real cycle.
    Resolving on first call, long after both
    modules have finished importing, is the same discipline
    used by the shared-catalogue compiler -- module-body evaluation is the
    hazard, first-call resolution is not.

    No local cache sits in front of this call: the indexed operation already
    owns generation pinning and storage validation. Caching here would bypass
    the caller's generation boundary and re-introduce a path-only registry
    cache, exactly the defect that consolidation removed.
    """
    if authority is not None:
        if not any(revision.applicability for _id, revision in _authority_revisions(authority, modelo)):
            return None
        return resolve_applicability_rule_from_authority(authority, modelo)
    if operation is not None:
        return _declared_applicability_rule(operation, modelo)

    from .authority import bundled_indexed_authority

    with bundled_indexed_authority().operation() as indexed_operation:
        return _declared_applicability_rule(indexed_operation, modelo)


def _modelo_applicability_rule(
    modelo: str,
    *,
    authority: ValidatedRegistryAuthority | None = None,
    operation: PinnedAuthorityOperation | None = None,
) -> ModeloApplicabilityRule | None:
    """Return ``modelo``'s applicability rule from the registry; asking about an unruled modelo is no error."""
    return _resolve_registry_applicability_rule(Modelo(modelo), authority=authority, operation=operation)


def iter_modelo_applicability_rules(
    *,
    operation: PinnedAuthorityOperation | None = None,
) -> tuple[ModeloApplicabilityRule, ...]:
    """Return every registry-declared :class:`ModeloApplicabilityRule`.

    The returned tuple is ordered by modelo id for deterministic audits and
    tests. Callers receive rule objects, not the mutable module-level
    dictionary, so the registry rule table remains read-only from the public
    API.

    Every registry rule is read from one generation: the caller's ``operation``
    when it holds one, otherwise a single lease taken for the whole table. A
    lease per modelo re-verified the published database for each of them and
    could read two modelos from two generations.
    """
    if operation is None:
        from .authority import bundled_indexed_authority

        with bundled_indexed_authority().operation() as leased:
            return _applicability_rules(_known_modelos(leased), operation=leased)
    return _applicability_rules(_known_modelos(operation), operation=operation)


def _known_modelos(operation: PinnedAuthorityOperation) -> list[str]:
    return sorted(operation.modelo_ids())


def _applicability_rules(
    modelos: list[str],
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[ModeloApplicabilityRule, ...]:
    return tuple(
        rule for modelo in modelos if (rule := _modelo_applicability_rule(modelo, operation=operation)) is not None
    )


def modelo_requires_iva_regime(modelo: str, *, operation: PinnedAuthorityOperation | None = None) -> bool:
    """Return whether the modelo's applicability rule depends on IVA regime.

    Calendar completeness is a consumer of the same applicability predicate
    that determines whether a taxpayer can have the modelo obligation.  Keep
    that classification here rather than maintaining a second calendar or
    core-constants set.
    """
    rule = _modelo_applicability_rule(modelo, operation=operation)
    return rule is not None and bool(rule.applicable_iva_regimes)


def taxpayer_model_is_declared(profile: TaxpayerProfile) -> bool:
    """Return whether the profile carries a usable taxpayer model.

    The taxpayer model is "declared" when the operator has set an
    ``entity_type`` and — for a natural person — at least one IRPF
    income category. Without these, modelo applicability cannot be
    derived: the engine must report ``INCOMPLETE`` rather than assume
    autónomo. A legal / attribution entity needs no income category;
    the ``entity_type`` alone selects its tax.

    Args:
        profile: The :class:`TaxpayerProfile` to inspect.
    """
    if profile.entity_type is None:
        return False
    if profile.entity_type == entity_type_natural_person_token():
        return bool(profile.irpf_income_categories)
    return True


def derive_tax_route(profile: TaxpayerProfile) -> TaxRoute:
    """Return the tax branch ``profile`` routes to.

    The routing contract: the ``entity_type`` axis selects the tax. A
    legal-entity profile routes to the Impuesto sobre Sociedades
    (Modelo 200 / 202); a natural person to the IRPF (Modelo
    100 / 130 / 303); an attribution entity to the member pass-through.
    An undeclared ``entity_type`` yields :attr:`TaxRoute.INCOMPLETE` —
    the engine never runs an IRPF cuota for a company or an IS cuota
    for an attribution entity, and never defaults a tax for a profile
    that declared none.

    Args:
        profile: The :class:`TaxpayerProfile` whose ``entity_type``
            axis selects the tax branch.

    Returns:
        The :class:`TaxRoute` branch the profile's ``entity_type``
        selects, or :attr:`TaxRoute.INCOMPLETE` when ``entity_type``
        is undeclared.
    """
    if profile.entity_type is None:
        return TaxRoute.INCOMPLETE
    return tax_route_for_entity_type(profile.entity_type)


def derive_modelo_applicability(
    profile: TaxpayerProfile,
    modelo: str,
    *,
    today: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
    operation: PinnedAuthorityOperation | None = None,
    ledger_payer_facts: Mapping[str, LedgerPayerFactDerivation] = NO_LEDGER_PAYER_FACTS,
) -> ModeloApplicability:
    """Derive a modelo's applicability from the taxpayer model.

    The verdict is DERIVED from the three-axis
    :class:`~domain.deadlines.models.TaxpayerProfile` model — never
    assumed. An undeclared taxpayer model yields an explicit
    :attr:`ApplicabilityVerdict.INCOMPLETE` answer; the engine never
    reports a confident wrong obligation.

    A modelo whose revisions declare no rule is also reported ``INCOMPLETE``
    so the operator is never told a confident yes/no the registry cannot justify.

    Args:
        profile: The operator's three-axis taxpayer model.
        modelo: The AEAT modelo identifier to decide.
        today: Reference date for the Beckham window check. Defaults to
            the Europe/Madrid civil date (``today_madrid()``) when ``None`` —
            the six-year window is a Spanish-calendar boundary. Pass an explicit
            date in tests so results are deterministic.
        authority: Already-resolved validated authority to reuse. Omitting it
            preserves the standalone fingerprint-bounded bundled-tree lookup.
        operation: Already-pinned indexed operation to reuse for point-loaded
            applicability facts. Omitting it leases the bundled indexed
            generation for this call.
        ledger_payer_facts: The ledger derivations of payer facts for the
            filing year ``profile`` was projected for. A derivation of the
            rule's payer fact is combined with the profile answer as
            :meth:`ModeloApplicabilityRule.evaluate` describes.

    Returns:
        The :class:`ModeloApplicability` for ``modelo`` and ``profile``.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.authority.ValidatedRegistryAuthority`.
    """
    _today = today if today is not None else today_madrid()
    beckham_window_active = profile.beckham_window_active(_today)

    # The Art. 93 impatriado route is a modelo-level switch while the
    # six-year Beckham window is active: the annual declaration is Modelo
    # 151, and the ordinary Renta self-assessment (Modelo 100) is not the
    # filing route. Once the window expires, both modelos fall back to their
    # ordinary applicability rules: M100 through its declared rule, M151
    # to a positive NOT_APPLICABLE.
    routes = resolve_form_codes(_ROUTES_FACT, authority=operation)
    if beckham_window_active and modelo == routes.code("impatriado.suppressed"):
        return ModeloApplicability(
            modelo=Modelo(modelo),
            verdict=ApplicabilityVerdict.NOT_APPLICABLE,
            reason=tr(_IMPATRIADO_M100_SUPPRESSED_REASON_LOCALE_KEY),
            legal_refs=_IMPATRIADO_M151_ROUTE_LEGAL_REFS,
        )
    if modelo == routes.code("impatriado.route"):
        return ModeloApplicability(
            modelo=Modelo(modelo),
            verdict=(ApplicabilityVerdict.APPLICABLE if beckham_window_active else ApplicabilityVerdict.NOT_APPLICABLE),
            reason=(
                tr(
                    _IMPATRIADO_M151_APPLICABLE_REASON_LOCALE_KEY
                    if beckham_window_active
                    else _IMPATRIADO_M151_NOT_APPLICABLE_REASON_LOCALE_KEY,
                )
            ),
            legal_refs=_IMPATRIADO_M151_ROUTE_LEGAL_REFS,
        )

    # An impatriado (LIRPF Art. 93 special regime) is taxed as a non-resident
    # for the duration of the six-year Beckham window (RIRPF Art. 116.1) and
    # is therefore exempt from IRPF-resident obligations. Modelo 720 (bienes
    # en el extranjero) is one of those obligations: it applies to IRPF
    # residents, not to non-resident taxpayers under Art. 93. Enforce the
    # exemption before the rule table so the payer-fact gate is never reached.
    # Year-7+ filers whose window has expired revert to the general IRPF
    # regime and owe M720 again — the window-expiry check is wired here.
    if modelo == routes.code("impatriado.exempt") and beckham_window_active:
        return ModeloApplicability(
            modelo=Modelo(modelo),
            verdict=ApplicabilityVerdict.NOT_APPLICABLE,
            reason=registry_applicability_reason("impatriado_m720_exempt.reason", operation=operation),
            legal_refs=_IMPATRIADO_M720_LEGAL_REFS,
        )
    rule = _modelo_applicability_rule(modelo, authority=authority, operation=operation)
    if rule is None:
        return incomplete_applicability(modelo, unruled=True)
    return rule.evaluate(profile, ledger_payer_facts=ledger_payer_facts)


def derive_taxpayer_files_economic_activity(profile: TaxpayerProfile) -> bool | None:
    """Whether the taxpayer files actividad-económica pagos fraccionados (130/131).

    Reads the :class:`TaxpayerProfile` income-category declarations. ``True``
    when the profile declares actividad-económica income; ``False`` when it
    declares income categories that exclude it (a salaried/rental-only filer
    never files 130/131); ``None`` when income categories are undeclared
    (fail-closed: the 130/131 dependency stays enforced). LIRPF art. 99 /
    RIRPF art. 109.
    """
    if not profile.irpf_income_categories:
        return None
    return irpf_income_category_actividad_economica_token() in profile.irpf_income_categories


__all__ = [
    "ApplicabilityEvidenceDisagreement",
    "ApplicabilityProvenance",
    "ApplicabilityVerdict",
    "LedgerPayerFactDerivation",
    "ModeloApplicability",
    "ModeloApplicabilityExclusion",
    "ModeloApplicabilityRule",
    "derive_modelo_applicability",
    "derive_tax_route",
    "derive_taxpayer_files_economic_activity",
    "iter_modelo_applicability_rules",
    "modelo_requires_iva_regime",
    "taxpayer_model_is_declared",
]
