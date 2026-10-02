"""Safe settled authentication configuration facts for every frontend."""

from typing import Literal

from pydantic import BaseModel

from ...core.auth_provider import AuthProviderKind
from ...core.models import STRICT_FROZEN_CONFIG
from ..operations.models import OperationTerminalReceipt
from ..operator_actions.models import PreconditionVerdict
from .operator_result_projections import incomplete_auth_configuration_verdict
from .operator_results import AuthConfigureResult


class AuthConfigurePublicResultV1(BaseModel):
    """No credential, taxpayer identifier, private path, or rendered prose."""

    model_config = STRICT_FROZEN_CONFIG

    provider: AuthProviderKind
    changed: bool
    certificate_file_provided: bool
    complete: bool
    profile_tax_id_present: bool
    provider_identity_present: bool
    identity_alignment: Literal[
        "not_applicable",
        "matches",
        "mismatch",
        "clave_identity_missing",
        "profile_tax_id_missing",
        "profile_tax_id_missing_and_clave_identity_missing",
    ]

    @property
    def precondition_verdict(self) -> PreconditionVerdict | None:
        """Derive canonical recovery evidence from the finite public facts."""
        if self.complete:
            return None
        return incomplete_auth_configuration_verdict(
            provider=self.provider.value,
            certificate_file_provided=self.certificate_file_provided,
            profile_tax_id_present=self.profile_tax_id_present,
            provider_identity_present=self.provider_identity_present,
            identity_alignment=self.identity_alignment,
        )


def project_auth_configuration(result: BaseModel, _receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Explicitly allow only configuration readiness evidence into the envelope."""
    if not isinstance(result, AuthConfigureResult):
        raise TypeError("authentication configuration result has the wrong registered type")
    return AuthConfigurePublicResultV1.model_validate(
        {
            "provider": AuthProviderKind(result.provider),
            "changed": result.changed,
            "certificate_file_provided": bool(result.file),
            "complete": result.complete,
            "profile_tax_id_present": result.profile_tax_id_present,
            "provider_identity_present": result.provider_identity_present,
            "identity_alignment": result.identity_alignment,
        },
        strict=True,
    )
