"""Secret-free requirements for starting an exact-profile AEAT synchronization."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, model_validator

from ...core.auth_provider import AuthProviderKind, ClaveMovilRoute
from ...core.config import Settings, load_settings
from ...core.identity.tax_id import same_tax_identifier
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..user_profile.projections import record_to_path_values
from .certificate_secret_backend import CertificateSecretBackendFactory
from .credentials import ActiveAuthProjectionSnapshot, active_auth_projection_span
from .operator_probe_ports import ClaveIdentityFailure, OperatorProbePorts
from .operator_probes import probe_certificate_bundle
from .operator_scope_ports import OperatorScopePorts
from .probes import ProviderProbeResult
from .sessions import clave_auth_facts_from_profile_values, resolve_clave_credentials


class AuthSyncRequirement(BaseModel):
    """One required field or local condition; contains no credential value."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    field: str
    satisfied: bool
    reason: str
    secret: bool = False


class AuthSyncReadiness(BaseModel):
    """Method-specific requirements derived from the real credential resolvers."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    provider: str = ""
    route: str = ""
    ready: bool = False
    requirements: tuple[AuthSyncRequirement, ...] = ()

    @model_validator(mode="after")
    def _consistent_readiness(self) -> AuthSyncReadiness:
        """Refuse a readiness claim inconsistent with its requirements."""
        if self.ready != (bool(self.requirements) and all(item.satisfied for item in self.requirements)):
            raise ValueError("sync readiness disagrees with requirements")
        return self


def build_auth_sync_readiness(
    provider: str | None = None,
    *,
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    operator_probe_ports: OperatorProbePorts,
    operator_scope_ports: OperatorScopePorts,
    settings: Settings | None = None,
) -> AuthSyncReadiness:
    """Inspect saved profile credentials without contacting AEAT or exposing values."""
    resolved = settings or load_settings()
    with active_auth_projection_span(
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        requested_provider=provider,
        operator_scope_ports=operator_scope_ports,
        settings=resolved,
    ) as snapshot:
        values = record_to_path_values(snapshot.state.active_profile_record()) if snapshot.state is not None else {}
        return project_auth_sync_readiness(
            snapshot, values=values, settings=resolved, operator_probe_ports=operator_probe_ports
        )


def project_auth_sync_readiness(
    snapshot: ActiveAuthProjectionSnapshot,
    *,
    values: Mapping[str, str],
    settings: Settings,
    operator_probe_ports: OperatorProbePorts,
) -> AuthSyncReadiness:
    """Evaluate witnessed profile facts with the same credential rules used by login."""
    resolved = settings
    facts = clave_auth_facts_from_profile_values(values)
    kind = snapshot.provider
    requirements: list[AuthSyncRequirement] = []

    def require(field: str, satisfied: bool, reason: str, *, secret: bool = False) -> None:
        requirements.append(AuthSyncRequirement(field=field, satisfied=satisfied, reason=reason, secret=secret))

    require("identity.tax_id", bool(facts.tax_id), "profile_tax_id_required")
    require("auth.provider", kind is not None, "auth_method_required")
    route = ""
    if kind is AuthProviderKind.CERTIFICATE:
        credentials = snapshot.certificate_credentials
        path = credentials.certificate_path if credentials is not None else None
        require("certificate.file", path is not None and path.is_file(), "certificate_file_required")
        probe = probe_certificate_bundle(
            "", settings=resolved, certificate_credentials=credentials, operator_probe_ports=operator_probe_ports
        )
        healthy = probe.result in {ProviderProbeResult.OK, ProviderProbeResult.EXPIRING}
        require(
            "certificate.passphrase",
            credentials is not None
            and credentials.password is not None
            and bool(credentials.password.get_secret_value()),
            "certificate_passphrase_required",
            secret=True,
        )
        require(
            "certificate.health",
            healthy,
            probe.result.value,
        )
    elif kind is AuthProviderKind.CLAVE_MOVIL or kind is AuthProviderKind.CLAVE_PERMANENTE:
        credentials = resolve_clave_credentials(kind, settings=resolved, facts=facts)
        if credentials is None:
            raise ValueError("Cl@ve credential resolver returned no credentials")
        classification = operator_probe_ports.clave_identity.classify(credentials.dni_nie)
        valid_identity = bool(credentials.dni_nie) and not isinstance(classification, ClaveIdentityFailure)
        require("auth.dni_nie", valid_identity, "clave_identity_required")
        require(
            "auth.identity_alignment",
            bool(facts.tax_id) and valid_identity and same_tax_identifier(facts.tax_id, credentials.dni_nie),
            "profile_identity_must_match",
        )
        if kind is AuthProviderKind.CLAVE_MOVIL:
            selected_route = facts.clave_movil_route or (
                ClaveMovilRoute.APP_REQUEST if resolved.cadrumo_clave_prefer_non_qr else ClaveMovilRoute.QR
            )
            route = selected_route.value
            if selected_route is ClaveMovilRoute.APP_REQUEST:
                is_nie = not isinstance(classification, ClaveIdentityFailure) and classification.kind == "NIE"
                require(
                    "auth.numero_soporte" if is_nie else "auth.fecha_validez",
                    bool(credentials.numero_soporte if is_nie else credentials.fecha_validez),
                    "nie_support_required" if is_nie else "dni_validity_required",
                )
        else:
            password = snapshot.clave_permanente_password
            require(
                "auth.password",
                password is not None and bool(password.get_secret_value()),
                "clave_password_required",
                secret=True,
            )
    return AuthSyncReadiness(
        provider=kind.value if kind is not None else "",
        route=route,
        ready=all(item.satisfied for item in requirements),
        requirements=tuple(requirements),
    )
