"""CLI transport access to the root-composed state-projection ports."""

from __future__ import annotations

from typing import cast

import typer

from ...application.auth.certificate_secret_backend import CertificateSecretBackendFactory
from ...application.auth.operator_probe_ports import OperatorProbePorts
from ...application.auth.operator_scope_ports import OperatorScopePorts
from ...application.live.expedientes_ports import ExpedientesPortsFactory
from ...application.ledger.evidence_ports import LedgerEvidencePortsFactory
from ...application.modelo.amendment_action_ports import AmendmentActionPortsFactory
from ...application.modelo.calculation_action_ports import CalculationActionPortsFactory
from ...application.modelo.filing_action_ports import FilingActionPortsFactory
from ...application.modelo.export_ports import ModeloExportPortsFactory
from ...application.modelo.history_ports import ModeloHistoryPortsFactory
from ...application.modelo.recipient_encryption import RecipientEncryptionCapabilityFactory
from ...application.modelo.verification_repository_ports import VerificationRepositoryBundleFactory
from ...application.state_projection_ports import StateProjectionReadPorts

_STATE_PROJECTION_PORTS_KEY = "state_projection_read_ports"
_CERTIFICATE_SECRET_BACKEND_FACTORY_KEY = "certificate_secret_backend_factory"
_OPERATOR_PROBE_PORTS_KEY = "operator_probe_ports"
_OPERATOR_SCOPE_PORTS_KEY = "operator_scope_ports"
_VERIFICATION_REPOSITORY_BUNDLE_FACTORY_KEY = "verification_repository_bundle_factory"
_CALCULATION_ACTION_PORTS_FACTORY_KEY = "calculation_action_ports_factory"
_AMENDMENT_ACTION_PORTS_FACTORY_KEY = "amendment_action_ports_factory"
_FILING_ACTION_PORTS_FACTORY_KEY = "filing_action_ports_factory"
_EXPEDIENTES_PORTS_FACTORY_KEY = "expedientes_ports_factory"
_LEDGER_EVIDENCE_PORTS_FACTORY_KEY = "ledger_evidence_ports_factory"
_MODELO_EXPORT_PORTS_FACTORY_KEY = "modelo_export_ports_factory"
_MODELO_HISTORY_PORTS_FACTORY_KEY = "modelo_history_ports_factory"
_RECIPIENT_ENCRYPTION_CAPABILITY_FACTORY_KEY = "recipient_encryption_capability_factory"


def state_projection_read_ports(ctx: typer.Context) -> StateProjectionReadPorts:
    """Return the required bundle composed by the executable CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    value = root_state.get(_STATE_PROJECTION_PORTS_KEY)
    if not isinstance(value, StateProjectionReadPorts):
        raise RuntimeError("state projection read ports were not composed")
    return value


def certificate_secret_backend_factory(ctx: typer.Context) -> CertificateSecretBackendFactory:
    """Return the certificate-secret factory supplied by the CLI composition root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(CertificateSecretBackendFactory, root_state[_CERTIFICATE_SECRET_BACKEND_FACTORY_KEY])


def operator_probe_ports(ctx: typer.Context) -> OperatorProbePorts:
    """Return the operator-probe capabilities supplied by the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    value = root_state.get(_OPERATOR_PROBE_PORTS_KEY)
    if not isinstance(value, OperatorProbePorts):
        raise RuntimeError("operator probe ports were not composed")
    return value


def operator_scope_ports(ctx: typer.Context) -> OperatorScopePorts:
    """Return the operator-scope capabilities supplied by the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    value = root_state.get(_OPERATOR_SCOPE_PORTS_KEY)
    if not isinstance(value, OperatorScopePorts):
        raise RuntimeError("operator scope ports were not composed")
    return value


def verification_repository_bundle_factory(ctx: typer.Context) -> VerificationRepositoryBundleFactory:
    """Return the required verification bundle factory from the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(VerificationRepositoryBundleFactory, root_state[_VERIFICATION_REPOSITORY_BUNDLE_FACTORY_KEY])


def calculation_action_ports_factory(ctx: typer.Context) -> CalculationActionPortsFactory:
    """Return the required calculation bundle factory from the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(CalculationActionPortsFactory, root_state[_CALCULATION_ACTION_PORTS_FACTORY_KEY])


def amendment_action_ports_factory(ctx: typer.Context) -> AmendmentActionPortsFactory:
    """Return the required amendment bundle factory from the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(AmendmentActionPortsFactory, root_state[_AMENDMENT_ACTION_PORTS_FACTORY_KEY])


def filing_action_ports_factory(ctx: typer.Context) -> FilingActionPortsFactory:
    """Return the required filing bundle factory from the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(FilingActionPortsFactory, root_state[_FILING_ACTION_PORTS_FACTORY_KEY])


def expedientes_ports_factory(ctx: typer.Context) -> ExpedientesPortsFactory:
    """Return the required expedientes bundle factory from the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(ExpedientesPortsFactory, root_state[_EXPEDIENTES_PORTS_FACTORY_KEY])


def ledger_evidence_ports_factory(ctx: typer.Context) -> LedgerEvidencePortsFactory:
    """Return the required ledger-evidence bundle factory from the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(LedgerEvidencePortsFactory, root_state[_LEDGER_EVIDENCE_PORTS_FACTORY_KEY])


def modelo_export_ports_factory(ctx: typer.Context) -> ModeloExportPortsFactory:
    """Return the required Modelo export bundle factory from the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(ModeloExportPortsFactory, root_state[_MODELO_EXPORT_PORTS_FACTORY_KEY])


def modelo_history_ports_factory(ctx: typer.Context) -> ModeloHistoryPortsFactory:
    """Return the history capabilities supplied by the CLI composition root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(ModeloHistoryPortsFactory, root_state[_MODELO_HISTORY_PORTS_FACTORY_KEY])


def recipient_encryption_capability_factory(ctx: typer.Context) -> RecipientEncryptionCapabilityFactory:
    """Return the recipient-encryption capability factory composed by the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(RecipientEncryptionCapabilityFactory, root_state[_RECIPIENT_ENCRYPTION_CAPABILITY_FACTORY_KEY])


__all__ = [
    "certificate_secret_backend_factory",
    "amendment_action_ports_factory",
    "calculation_action_ports_factory",
    "filing_action_ports_factory",
    "expedientes_ports_factory",
    "ledger_evidence_ports_factory",
    "modelo_export_ports_factory",
    "modelo_history_ports_factory",
    "operator_probe_ports",
    "operator_scope_ports",
    "recipient_encryption_capability_factory",
    "state_projection_read_ports",
    "verification_repository_bundle_factory",
]
