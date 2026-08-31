"""Application policies for creating modelo work units.

The work-create command runs these guards before provisioning a work unit. They
cover three distinct policy surfaces: modelo codes that are still stub-only in
the local work-unit flow, modelos that do not apply to the active profile's
taxpayer model, and active profiles whose CCAA points at a foral tax regime.

Stub-only checks are locale-key lookups over :class:`Modelo` members and a few
registry-known numeric forms. Applicability checks derive a profile projection
from the active workflow state, then ask the registry-owned applicability rules
whether the requested modelo is excluded. The foral check delegates to the
canonical tax-region parser so the CLI renders the same refusal text as profile
setup. Once these CLI policy guards pass,
:func:`cadrumo.application.modelo.create_work_unit` performs the application
readiness and registry revision checks before inserting the
:class:`~WorkUnit`.

See Also:
    :mod:`cadrumo.entrypoints.cli._modelo_work_lifecycle_cli`:
        Calls these guards from ``app modelo work create``.
    :func:`cadrumo.domain.calculations.registry.derive_modelo_applicability`:
        Registry-owned modelo applicability classifier used by this guard.
    :func:`cadrumo.domain.contribuyente.parse_tax_region`:
        Canonical CCAA parser that raises foral-regime refusals.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import ValidationError

from ...core.config import load_settings
from ...core.modelo import Modelo

STUB_MODELO_LOCALE_KEYS: dict[str, str] = {
    Modelo.M151.value: "cli.app.modelo.work.create_stub_modelo_151_refused",
    Modelo.M210.value: "cli.app.modelo.work.create_stub_modelo_210_refused",
    "600": "cli.app.modelo.work.create_stub_modelo_600_refused",
    "620": "cli.app.modelo.work.create_stub_modelo_620_refused",
    "650": "cli.app.modelo.work.create_stub_modelo_650_refused",
    "660": "cli.app.modelo.work.create_stub_modelo_660_refused",
    Modelo.M714.value: "cli.app.modelo.work.create_stub_modelo_714_refused",
    Modelo.M721.value: "cli.app.modelo.work.create_stub_modelo_refused",
}

STUB_ONLY_MODELOS: frozenset[str] = frozenset(STUB_MODELO_LOCALE_KEYS)

#: Ceded autonomic-tax modelos that are administered by the Comunidades
#: Autónomas rather than the AEAT, and are therefore absent from the
#: calculation registry entirely: ITP-AJD (``600``, ``620``) and ISD (``650``,
#: ``660``) are tributos cedidos. A registry discovery lookup for one of these
#: codes must redirect the operator to the competent regional Hacienda / CCAA
#: instead of surfacing a generic not-present-in-registry error. The values
#: reuse the work-create refusal copy, which already names the ceded tax, its
#: enabling law, and the regional filing route in every locale.
CEDED_AUTONOMIC_MODELO_LOCALE_KEYS: dict[str, str] = {
    "600": "cli.app.modelo.work.create_stub_modelo_600_refused",
    "620": "cli.app.modelo.work.create_stub_modelo_620_refused",
    "650": "cli.app.modelo.work.create_stub_modelo_650_refused",
    "660": "cli.app.modelo.work.create_stub_modelo_660_refused",
}

CEDED_AUTONOMIC_MODELOS: frozenset[str] = frozenset(CEDED_AUTONOMIC_MODELO_LOCALE_KEYS)


def ceded_autonomic_modelo_locale_key(modelo: str) -> str | None:
    """Return the instructive autonomic-redirect locale key for a ceded modelo.

    ITP-AJD (``600`` / ``620``) and ISD (``650`` / ``660``) are ceded autonomic
    taxes administered by the Comunidades Autónomas, not AEAT modelos present in
    the calculation registry. Discovery surfaces (``describe`` / ``casillas`` /
    ``formulas``) must redirect an operator who references one of these codes to
    the competent regional Hacienda / CCAA rather than surface a generic
    not-present error. Whitespace is normalised; ``None`` is returned for any
    other modelo, including registry-backed and genuinely unknown codes.

    See Also:
        :func:`modelo_work_create_refusal_locale_key`:
            The sibling work-create refusal this discovery redirect mirrors.
    """
    return CEDED_AUTONOMIC_MODELO_LOCALE_KEYS.get(modelo.strip())


@dataclass(frozen=True, slots=True)
class ModeloWorkCreateApplicabilityRefusal:
    """Application refusal for a modelo the active profile should not file.

    ``modelo`` is the stripped requested modelo code. ``reason`` is the
    registry-derived applicability reason surfaced by the CLI together with its
    ``--allow-not-applicable`` escape hatch.
    """

    modelo: str
    reason: str


def modelo_work_create_refusal_locale_key(modelo: str) -> str | None:
    """Return the locale key for a refused stub-modelo create request.

    The lookup normalises whitespace and returns ``None`` when the modelo is not
    in :data:`STUB_ONLY_MODELOS`. Modelo 210 is conditionally released when the
    ``cadrumo_m210_engine_live`` setting is enabled; all other entries remain
    refused by this policy surface.

    See Also:
        :class:`cadrumo.core.Modelo`:
            Closed modelo enum used for the core stub-only entries.
        :mod:`cadrumo.entrypoints.cli._modelo_work_lifecycle_cli`:
            Converts the locale key into a typed CLI refusal.
    """
    modelo_code = modelo.strip()
    if modelo_code not in STUB_ONLY_MODELOS:
        return None
    if modelo_code == Modelo.M210 and load_settings().cadrumo_m210_engine_live:
        return None
    return STUB_MODELO_LOCALE_KEYS[modelo_code]


def modelo_work_create_applicability_refusal(
    modelo: str,
    *,
    allow_not_applicable: bool,
) -> ModeloWorkCreateApplicabilityRefusal | None:
    """Return an applicability refusal for the active profile, if one applies.

    When ``allow_not_applicable`` is true, the guard deliberately returns
    ``None`` so the CLI can provision the work unit and record that the operator
    bypassed the applicability guard. Otherwise the active profile record is
    projected into :class:`cadrumo.domain.deadlines.TaxpayerProfile` facts and
    checked against the registry-owned applicability rules. Only
    ``NOT_APPLICABLE`` and ``ATTRIBUTION_PASS_THROUGH`` verdicts block creation.

    Returns:
        A :class:`ModeloWorkCreateApplicabilityRefusal` for a blocking verdict,
        or ``None`` when the modelo is applicable, unsupported by an explicit
        rule, or deliberately bypassed.

    See Also:
        :func:`cadrumo.domain.calculations.registry.derive_modelo_applicability`:
            Registry-owned applicability classifier used by this guard.
        :func:`cadrumo.application.user_profile.projection_for_taxpayer`:
            Builds the taxpayer profile consumed by the classifier.
    """
    if allow_not_applicable:
        return None

    from ...application.user_profile.projections import projection_for_taxpayer
    from ...domain.calculations.registry.applicability import derive_modelo_applicability
    from ..workflow.persistence import workflow_state_repository
    from ._profile_readiness_gate import BLOCKING_APPLICABILITY_VERDICTS

    state = workflow_state_repository().load()
    record = state.active_profile_record()
    try:
        profile = projection_for_taxpayer(record or {})
    except ValidationError:
        return None
    applicability = derive_modelo_applicability(profile, modelo.strip())
    if applicability.verdict not in BLOCKING_APPLICABILITY_VERDICTS:
        return None
    return ModeloWorkCreateApplicabilityRefusal(modelo=modelo.strip(), reason=applicability.reason)


def guard_active_profile_foral_ccaa() -> None:
    """Raise the canonical foral-regime refusal for the active profile, if present.

    The guard reads ``tax_residence.ccaa`` from the active profile and delegates
    to :func:`cadrumo.domain.contribuyente.parse_tax_region`. Common-regime CCAA
    values pass through; foral values raise the domain refusal before work-unit
    creation reaches the generic unsupported-modelo checks.
    """
    from ...application.user_profile.projections import fact_value
    from ...domain.contribuyente.tax_residence import parse_tax_region
    from ..workflow.persistence import workflow_state_repository

    state = workflow_state_repository().load()
    record = state.active_profile_record()
    raw_ccaa = fact_value(record, "tax_residence.ccaa")
    if raw_ccaa:
        parse_tax_region(raw_ccaa)


__all__ = [
    "CEDED_AUTONOMIC_MODELOS",
    "CEDED_AUTONOMIC_MODELO_LOCALE_KEYS",
    "STUB_MODELO_LOCALE_KEYS",
    "STUB_ONLY_MODELOS",
    "ModeloWorkCreateApplicabilityRefusal",
    "ceded_autonomic_modelo_locale_key",
    "guard_active_profile_foral_ccaa",
    "modelo_work_create_applicability_refusal",
    "modelo_work_create_refusal_locale_key",
]
