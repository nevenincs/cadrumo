"""Production composition helpers for submission preflight tests."""

from __future__ import annotations

from datetime import UTC, datetime
from functools import cache

from pydantic import SecretStr

from ......application.auth.providers import AuthProvider, select_provider
from ......application.modelo._workflow_gate import build_revision_deadline_window_checker
from ......core.auth_provider import AuthProviderKind
from ......core.config import Settings
from ......core.period import Period
from ......domain.calculations.registry.schema_references import RegistrySnapshotRef
from ......domain.deadlines.engine import DeadlineEngine
from ......domain.deadlines.models import IVARegime, TaxpayerProfile
from ......domain.filing.schema import ModeloDraft, ModeloValidationFinding
from ......domain.submission._protocols import DeadlineWindowChecker, ModeloDraftStatus

_DRAFT_TIME = datetime(2026, 4, 10, 12, 0, tzinfo=UTC)


def modelo_draft(
    *,
    status: ModeloDraftStatus = ModeloDraftStatus.APROBADO,
    findings: tuple[ModeloValidationFinding, ...] = (),
) -> ModeloDraft:
    """Build a real filing-domain draft at a stable registry coordinate."""
    return ModeloDraft(
        draft_id="submission-preflight-draft",
        modelo="130",
        period=Period.from_year_and_code(2026, "1T"),
        profile_tax_id="X1234567L",
        subject_tax_id="X1234567L",
        snapshot_ref=RegistrySnapshotRef(
            modelo="130",
            revision_id="2025",
            modelo_year=2026,
            period="1T",
        ),
        status=status,
        values=(),
        findings=findings,
        created_at=_DRAFT_TIME,
        updated_at=_DRAFT_TIME,
        schema_version="registry:130:2025",
    )


@cache
def deadline_checker() -> DeadlineWindowChecker:
    """Return the production registry-backed filing-window adapter."""
    profile = TaxpayerProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )
    return build_revision_deadline_window_checker(profile=profile, engine=DeadlineEngine())


def clave_movil_provider(*, identity: str | None) -> AuthProvider:
    """Select the real Cl@ve Móvil provider for a configured or empty identity."""
    settings = Settings(
        cadrumo_auth_provider=AuthProviderKind.CLAVE_MOVIL,
        cadrumo_clave_movil_dni_nie=SecretStr(identity or ""),
    )
    return select_provider(AuthProviderKind.CLAVE_MOVIL, settings=settings)
