"""Pydantic v2 strict models for the first-run setup wizard (#61).

Every record that crosses the subpackage boundary lives here as a
strict, frozen :class:`pydantic.BaseModel` (or :class:`enum.StrEnum`
for closed enumerations). No dataclasses; no bare ``dict[str, Any]``.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ..auth import CertificateBackend
from ..deadlines import IVARegime
from ..i18n import Language, Translatable

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class SetupStep(StrEnum):
    """Closed catalogue of the wizard's ten linear steps.

    ``WELCOME`` greets the user. ``PROFILE`` through ``LIVE_TESTS_OPT_IN``
    capture typed answers. ``FIXTURE_PROVISIONING`` records the Google
    Workspace fixture opt-in. ``VERIFY`` runs the pure verifier.
    ``FIRST_RUN`` optionally hands off to the workflow-engine runner
    (Protocol-stubbed until #59 lands). ``DONE`` is terminal.
    """

    WELCOME = "WELCOME"
    PROFILE = "PROFILE"
    CERTIFICATE = "CERTIFICATE"
    LANGUAGE = "LANGUAGE"
    OUTPUT_DIRS = "OUTPUT_DIRS"
    LIVE_TESTS_OPT_IN = "LIVE_TESTS_OPT_IN"
    FIXTURE_PROVISIONING = "FIXTURE_PROVISIONING"
    VERIFY = "VERIFY"
    FIRST_RUN = "FIRST_RUN"
    DONE = "DONE"


class SetupOutcome(StrEnum):
    """Terminal outcome of a :meth:`SetupWizard.run` call.

    ``COMPLETED`` means every non-skipped step ran and the verifier
    produced no ``ERROR`` findings. ``SKIPPED`` is reserved for
    future use. ``ABORTED_BY_USER`` means the user asked to exit mid
    flow. ``ABORTED_VERIFY_FAILED`` means the verifier raised at least
    one ``ERROR`` finding and the wizard refused to mark the env file
    as ready.
    """

    COMPLETED = "COMPLETED"
    SKIPPED = "SKIPPED"
    ABORTED_BY_USER = "ABORTED_BY_USER"
    ABORTED_VERIFY_FAILED = "ABORTED_VERIFY_FAILED"


class VerifySeverity(StrEnum):
    """Severity levels for :class:`VerifyFinding` records."""

    OK = "OK"
    WARNING = "WARNING"
    ERROR = "ERROR"


class VerifyFinding(BaseModel):
    """One verdict produced by the pure :class:`Verifier`.

    Attributes:
        name: Short machine-readable identifier for the check.
        severity: One of :class:`VerifySeverity`.
        message: Trilingual human-readable message.
        remediation: Optional trilingual remediation hint.
    """

    model_config = _STRICT_FROZEN

    name: str = Field(min_length=1)
    severity: VerifySeverity
    message: Translatable
    remediation: Translatable | None = None


class SetupAnswers(BaseModel):
    """Every answer the user (or a scripted run) gave the wizard.

    ``certificate_password_secret_var_name`` is the *name* of the
    environment variable that holds the PKCS#12 passphrase. The
    wizard never captures or persists the passphrase itself.
    """

    model_config = _STRICT_FROZEN

    # ── profile ──────────────────────────────────────────────────────────
    tax_id: str = Field(min_length=1)
    iva_regime: IVARegime
    has_employees: bool = False
    pays_professionals_with_retencion: bool = False
    professional_income_withholding_ge_70pct: bool = False
    pays_rent_with_retencion: bool = False
    does_intracomunitario: bool = False
    third_party_transactions_above_347_threshold: bool = False
    bienes_extranjero_above_threshold: bool = False

    # ── certificate (NEVER the password value) ───────────────────────────
    certificate_path: Path
    certificate_password_secret_var_name: str = Field(min_length=1)
    certificate_friendly_name: str | None = None
    certificate_backend: CertificateBackend = CertificateBackend.PLAYWRIGHT_CONTEXT
    certificate_verify_url: str = "https://sede.agenciatributaria.gob.es/"

    # ── language ─────────────────────────────────────────────────────────
    default_language: Language = Language.EN
    output_language: Language = Language.ES

    # ── output directories ───────────────────────────────────────────────
    aeat_drafts_dir: Path
    aeat_submissions_dir: Path
    aeat_manuals_root: Path

    # ── profile JSON target ──────────────────────────────────────────────
    default_profile_path: Path

    # ── opt-ins ──────────────────────────────────────────────────────────
    aeat_live_tests_enabled: bool = False
    aeat_live_tests_google: bool = False
    provision_google_fixtures: bool = False

    # ── control ──────────────────────────────────────────────────────────
    steps_to_skip: frozenset[SetupStep] = frozenset()
    notes: str = ""


class SetupResult(BaseModel):
    """Structured outcome of a :meth:`SetupWizard.run` call.

    Attributes:
        outcome: Terminal :class:`SetupOutcome`.
        started_at: Timezone-aware UTC start timestamp.
        ended_at: Timezone-aware UTC end timestamp.
        steps_completed: Steps that ran to completion.
        steps_skipped: Steps that the wizard or the user elected to skip.
        env_file_path: Path to the env file the wizard wrote.
        profile_file_path: Path to the ``AutonomoProfile`` JSON file the
            wizard wrote.
        verify_findings: Every :class:`VerifyFinding` emitted by the
            verifier.
        notes: Free-form notes propagated from the answers.
    """

    model_config = _STRICT_FROZEN

    outcome: SetupOutcome
    started_at: datetime
    ended_at: datetime
    steps_completed: tuple[SetupStep, ...]
    steps_skipped: tuple[SetupStep, ...]
    env_file_path: Path
    profile_file_path: Path
    verify_findings: tuple[VerifyFinding, ...]
    notes: str = ""
