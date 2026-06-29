"""Pydantic contracts for workspace initialization.

:class:`InitializeWorkspaceCommand` carries the first-run profile facts,
including :class:`IVARegime` and :class:`OutputLanguage` selections, without
allocating storage itself. :class:`InitializeWorkspaceResult` reports the
generated :class:`ProfileId` and matching :class:`BucketId` created by the
setup service.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints

from ...core.external_constants import OutputLanguage
from ...core.identity import BucketId, ProfileId
from ...domain.deadlines import IVARegime


def _normalise_iva_regime(value: object) -> object:
    """Upper-case a string IVA-regime token so ``general`` resolves to ``IVARegime.GENERAL``."""
    return value.upper() if isinstance(value, str) else value


class InitializeWorkspaceCommand(BaseModel):
    """Command to initialize a new active workspace profile and bucket.

    The profile facts are consumed by
    :func:`aeat.application.setup.initialize_workspace`; enum fields preserve
    the domain vocabulary of :class:`IVARegime` and :class:`OutputLanguage`.
    ``profile_name`` is an operator-facing display label; the service mints
    the immutable :class:`ProfileId` / :class:`BucketId` storage identity.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    profile_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] = Field(
        default="default",
        description="Operator-facing profile label; the service generates the bucket identity.",
    )
    tax_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] = Field(
        description="NIF/NIE of the operator.",
    )
    activity: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] = Field(
        description="Description of the primary economic activity.",
    )
    iva_regime: Annotated[IVARegime, BeforeValidator(_normalise_iva_regime)] = Field(
        description="IVA regime; one of the IVARegime members (case-insensitive input).",
    )
    tax_residence_ccaa: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] | None = Field(
        default=None,
        description="Autonomous community of tax residence.",
    )
    auth_provider: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] = Field(
        default="none",
        description="Authentication provider (e.g., 'certificate', 'clave_movil', 'none').",
    )
    certificate_path: Path | None = Field(
        default=None,
        description="Path to the PKCS#12 certificate file if auth_provider is 'certificate'.",
    )
    certificate_password_env: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] | None = Field(
        default=None,
        description="Environment variable containing the certificate password.",
    )
    output_language: OutputLanguage | None = Field(
        default=None,
        description="Preferred output language code (e.g., 'es', 'ca', 'gl', 'eu').",
    )
    drafts_dir: Path | None = Field(
        default=None,
        description="Path to the directory where drafts are stored.",
    )
    submissions_dir: Path | None = Field(
        default=None,
        description="Path to the directory where submissions are stored.",
    )
    manuals_root: Path | None = Field(
        default=None,
        description="Path to the local manuals corpus.",
    )


class InitializeWorkspaceResult(BaseModel):
    """Result of successful workspace initialization.

    The generated :class:`ProfileId` is also the initial storage
    :class:`BucketId`, matching the UUID bucket-provisioning contract; the
    operator profile name remains a decoupled display label.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    profile_id: ProfileId
    bucket_id: BucketId
    auth_configured: bool
