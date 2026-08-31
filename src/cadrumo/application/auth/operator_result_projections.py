"""Result projections for the operator-facing auth application services."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ...core.auth_provider import AuthProviderKind
from ...core.config import load_settings
from ...core.i18n import tr
from ...core.identity import tax_id_identity_token
from ...core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ..operator_actions._models import PreconditionVerdict
from ..operator_actions._preconditions import no_action_precondition_verdict
from .operator_results import AuthConfigureResult, AuthStatusResult
from .sessions import clave_auth_facts_from_profile_values, resolve_clave_credentials

if TYPE_CHECKING:
    from ..state_projection import OperatorStateProjection
    from ..workflow.state_models import WorkflowState


def auth_status_from_projection(projection: OperatorStateProjection) -> AuthStatusResult:
    """Project the canonical state projection into the ``AuthStatusResult`` emit shape.

    The :class:`AuthStatusResult` is a CLI emit shape derived from the
    one :class:`OperatorStateProjection`; it is not a second
    state-assembly path. ``backend_configured`` mirrors the single
    canonical ``configured``, and ``backend_available`` mirrors the
    single canonical ``available``.
    """
    auth = projection.auth
    active = projection.active_profile
    return AuthStatusResult(
        provider=auth.provider,
        configured=auth.configured,
        authenticated=auth.authenticated,
        available=auth.available,
        active_profile=active.label or active.profile_id or "",
        active_profile_status=active.health_status,
        active_profile_registered=active.registered_bucket,
        active_profile_record_present=active.record_present,
        active_profile_precondition_verdict=active.precondition_verdict,
        backend_configured=auth.configured,
        backend_available=auth.available,
        certificate_path=auth.certificate_path,
        health_severity=auth.health_severity,
        health_summary=auth.health_summary,
    )


def auth_configure_result(
    *,
    state: WorkflowState,
    provider: str,
    certificate_path: Path | None,
) -> AuthConfigureResult:
    """Build a redacted configuration result that exposes identity readiness."""
    from ..user_profile.projections import record_to_path_values

    record = state.active_profile_record()
    values = record_to_path_values(record)
    profile_tax_id = tax_id_identity_token(values.get("identity.tax_id") or "")
    settings = load_settings()
    provider_identity = ""
    if provider == AuthProviderKind.CLAVE_MOVIL.value:
        # The profile's own values are already in hand, so the shared
        # resolver is fed directly rather than re-reading the record.
        credentials = resolve_clave_credentials(
            AuthProviderKind.CLAVE_MOVIL,
            settings=settings,
            facts=clave_auth_facts_from_profile_values(values),
        )
        provider_identity = credentials.dni_nie if credentials is not None else ""
    alignment = "not_applicable"
    alignment_detail = ""
    if provider == AuthProviderKind.CLAVE_MOVIL.value:
        from .operator_probes import classify_identity_alignment

        alignment = classify_identity_alignment(profile_tax_id, provider_identity)
        alignment_detail = identity_alignment_detail(
            alignment,
            profile_tax_id=profile_tax_id,
            provider_identity=provider_identity,
        )
    complete, incomplete_reason = certificate_completeness(provider, certificate_path)
    if provider == AuthProviderKind.CLAVE_MOVIL.value and alignment != "matches":
        complete = False
        incomplete_reason = alignment_detail
    return AuthConfigureResult(
        provider=provider,
        file=str(certificate_path) if certificate_path is not None else "",
        complete=complete,
        incomplete_reason=incomplete_reason,
        profile_tax_id_present=bool(profile_tax_id),
        provider_identity_present=bool(provider_identity) if provider == AuthProviderKind.CLAVE_MOVIL.value else True,
        identity_alignment=alignment,
        identity_alignment_detail=alignment_detail,
        precondition_verdict=(
            incomplete_auth_configuration_verdict(
                provider=provider,
                certificate_path=certificate_path,
                profile_tax_id_present=bool(profile_tax_id),
                provider_identity_present=bool(provider_identity),
                identity_alignment=alignment,
            )
            if not complete
            else None
        ),
    )


def incomplete_auth_configuration_verdict(
    *,
    provider: str,
    certificate_path: Path | None,
    profile_tax_id_present: bool,
    provider_identity_present: bool,
    identity_alignment: str,
) -> PreconditionVerdict:
    """Record an incomplete configuration without inventing a recovery command.

    Choosing a certificate file or changing one of two competing identities is
    an operator decision. The application records the exact failed condition,
    but cannot honestly materialise a single executable command from those
    facts.
    """
    if provider == AuthProviderKind.CERTIFICATE.value:
        condition_id = "auth.certificate.file_ready"
        evidence_id = "auth.configure.certificate.file_readiness"
        facts = {
            "certificate_file_provided": certificate_path is not None,
            "certificate_file_resolves": False,
            "provider": provider,
        }
    elif provider == AuthProviderKind.CLAVE_MOVIL.value:
        condition_id = "auth.clave_movil.identity_aligned"
        evidence_id = "auth.configure.clave_movil.identity_alignment"
        facts = {
            "identity_alignment": identity_alignment,
            "profile_tax_id_present": profile_tax_id_present,
            "provider": provider,
            "provider_identity_present": provider_identity_present,
        }
    else:
        raise RuntimeError(f"unsupported incomplete auth provider: {provider}")
    return no_action_precondition_verdict(
        condition_id=condition_id,
        evidence_id=evidence_id,
        facts=facts,
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def identity_alignment_detail(
    alignment: str,
    *,
    profile_tax_id: str,
    provider_identity: str,
) -> str:
    """Explain a Cl@ve identity-alignment verdict in operator language."""
    if alignment == "matches" or alignment == "not_applicable":
        return ""
    if alignment == "mismatch":
        return tr(
            "application.auth.operator.alignment.mismatch_detail",
            clave_identity=provider_identity,
            profile_tax_id=profile_tax_id,
        )
    if alignment == "clave_identity_missing":
        return tr("application.auth.operator.alignment.clave_identity_missing_detail")
    if alignment == "profile_tax_id_missing":
        return tr("application.auth.operator.alignment.profile_tax_id_missing_detail")
    if alignment == "profile_tax_id_missing_and_clave_identity_missing":
        return tr("application.auth.operator.alignment.both_missing_detail")
    return ""


def certificate_completeness(
    provider: str,
    certificate_path: Path | None,
) -> tuple[bool, str]:
    """Report whether a configured provider is operationally complete."""
    if provider != AuthProviderKind.CERTIFICATE.value:
        return True, ""
    if certificate_path is None:
        return False, tr("application.auth.operator.errors.certificate_file_required")
    try:
        resolves = certificate_path.is_file()
    except OSError:
        resolves = False
    if not resolves:
        return False, tr(
            "application.auth.operator.errors.certificate_file_unresolved",
            certificate_path=str(certificate_path),
        )
    return True, ""
