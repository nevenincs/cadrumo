"""Pydantic contracts for workspace initialization."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class InitializeWorkspaceCommand(BaseModel):
    """Command to initialize a new active workspace profile and bucket."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    profile_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] = Field(
        default="default",
        description="Name of the profile to create. Will be used as the bucket_id.",
    )
    tax_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] = Field(
        description="NIF/NIE of the operator.",
    )
    activity: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] = Field(
        description="Description of the primary economic activity.",
    )
    iva_regime: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] = Field(
        description="IVA regime (e.g., 'general', 'recargo_equivalencia', 'exento').",
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
    output_language: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] | None = Field(
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
    """Result of successful workspace initialization."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    profile_id: str
    bucket_id: str
    auth_configured: bool
