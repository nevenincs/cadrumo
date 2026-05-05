"""The :class:`SetupWizard` orchestrator for the first-run setup flow.

The wizard walks through every :class:`SetupStep` in order, calling
into the :class:`Prompter` Protocol for interactive answers and the
:class:`FirstRunRunner` Protocol for the optional read-only workflow
check.

In non-interactive mode, a fully-populated :class:`SetupAnswers`
short-circuits every prompt and the wizard runs the linear sequence
without any I/O against the user.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from ...adapters.outbound.aeat.auth import CertificateBackend
from ...core.i18n import Translatable as tr  # noqa: N813
from ...core.logging import get_logger
from ...domain.deadlines import IVARegime
from ...domain.profile import CCAA
from ._env_writer import write_env_file, write_profile_file
from ._errors import SetupError
from ._models import (
    SetupAnswers,
    SetupOutcome,
    SetupResult,
    SetupStep,
    VerifyFinding,
)
from ._protocols import FirstRunRunner, Prompter
from ._verifier import Verifier

log = get_logger(__name__)


_DEFAULT_ENV_FILE = Path("env") / ".env"


def _utcnow() -> datetime:
    """Return the current timezone-aware UTC instant."""
    return datetime.now(UTC)


class SetupWizard:
    """Orchestrates the ten-step first-run setup flow.

    Drives the wizard through every :class:`SetupStep` in order,
    delegating user interaction to a :class:`Prompter` and the optional
    end-of-flow workflow check to a :class:`FirstRunRunner`. The pure
    post-write verifier is supplied via constructor injection.
    """

    def __init__(self, *, verifier: Verifier | None = None) -> None:
        """Construct the wizard with an optional pre-built verifier.

        Args:
            verifier: Override for the :class:`Verifier` instance the
                wizard runs at the VERIFY step. Defaults to a fresh
                :class:`Verifier`.
        """
        self._verifier = verifier or Verifier()

    def run(
        self,
        *,
        env_file: Path | None = None,
        non_interactive: bool = False,
        defaults: SetupAnswers | None = None,
        prompter: Prompter | None = None,
        first_run_runner: FirstRunRunner | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> SetupResult:
        """Run the wizard end-to-end and return a :class:`SetupResult`.

        Args:
            env_file: Target path for the env file. Defaults to
                ``env/.env`` relative to the current working directory.
            non_interactive: If ``True``, consume ``defaults`` without
                prompting. ``defaults`` must be supplied.
            defaults: Pre-populated :class:`SetupAnswers`. Required for
                non-interactive mode; seeds prompter defaults in
                interactive mode.
            prompter: Interactive-mode only — the prompter driving the
                state machine.
            first_run_runner: Optional read-only workflow check. If
                ``None``, the ``FIRST_RUN`` step is skipped cleanly.
            now: Clock injection point. Defaults to
                ``datetime.now(UTC)``.

        Returns:
            A :class:`SetupResult` describing the run.

        Raises:
            SetupError: When the arguments are inconsistent — for
                example, non-interactive mode without ``defaults``, or
                interactive mode without a ``prompter``.
        """
        clock = now or _utcnow
        started_at = clock()
        target_env = (env_file or _DEFAULT_ENV_FILE).expanduser()

        if non_interactive:
            if defaults is None:
                raise SetupError("non-interactive mode requires defaults= to be supplied")
            answers = defaults
        else:
            if prompter is None:
                raise SetupError("interactive mode requires prompter= to be supplied")
            answers = self._collect_interactive(prompter=prompter, defaults=defaults)

        completed: list[SetupStep] = []
        skipped: list[SetupStep] = []

        # WELCOME — informational only.
        if SetupStep.WELCOME in answers.steps_to_skip:
            skipped.append(SetupStep.WELCOME)
        else:
            completed.append(SetupStep.WELCOME)

        # PROFILE → LIVE_TESTS_OPT_IN all ran as part of answer collection.
        for step in (
            SetupStep.PROFILE,
            SetupStep.CERTIFICATE,
            SetupStep.LANGUAGE,
            SetupStep.OUTPUT_DIRS,
            SetupStep.LIVE_TESTS_OPT_IN,
        ):
            if step in answers.steps_to_skip:
                skipped.append(step)
            else:
                completed.append(step)

        # FIXTURE_PROVISIONING captures the operator's opt-in only; the
        # wizard never invokes the external provisioning script itself.
        if SetupStep.FIXTURE_PROVISIONING in answers.steps_to_skip:
            skipped.append(SetupStep.FIXTURE_PROVISIONING)
        else:
            completed.append(SetupStep.FIXTURE_PROVISIONING)

        # Side effects: write profile JSON first (so the verifier can
        # re-validate it), then the env file.
        write_profile_file(answers, answers.default_profile_path)
        write_env_file(answers, target_env)

        # VERIFY.
        findings: tuple[VerifyFinding, ...]
        if SetupStep.VERIFY in answers.steps_to_skip:
            skipped.append(SetupStep.VERIFY)
            findings = tuple()
        else:
            findings = self._verifier.run(answers)
            completed.append(SetupStep.VERIFY)

        # FIRST_RUN — optional.
        if SetupStep.FIRST_RUN in answers.steps_to_skip or first_run_runner is None:
            skipped.append(SetupStep.FIRST_RUN)
        else:
            try:
                summary = first_run_runner.run_read_only()
                log.info("setup: first-run read-only summary: %s", summary)
                completed.append(SetupStep.FIRST_RUN)
            except Exception:  # pragma: no cover — runner surface is pluggable; any failure degrades to skipped
                log.warning("setup: first-run read-only check failed", exc_info=True)
                skipped.append(SetupStep.FIRST_RUN)

        # DONE.
        completed.append(SetupStep.DONE)

        outcome = SetupOutcome.ABORTED_VERIFY_FAILED if Verifier.has_error(findings) else SetupOutcome.COMPLETED

        return SetupResult(
            outcome=outcome,
            started_at=started_at,
            ended_at=clock(),
            steps_completed=tuple(completed),
            steps_skipped=tuple(skipped),
            env_file_path=target_env,
            profile_file_path=answers.default_profile_path,
            verify_findings=findings,
            notes=answers.notes,
        )

    # ── interactive collection ───────────────────────────────────────────

    def _collect_interactive(
        self,
        *,
        prompter: Prompter,
        defaults: SetupAnswers | None,
    ) -> SetupAnswers:
        """Walk the prompter through every answer field.

        When ``defaults`` is supplied its values seed the prompter
        defaults (supporting the "re-run on existing env" path). When
        ``defaults`` is ``None`` the prompter is expected to supply
        every answer itself.
        """
        prompter.announce(
            key="welcome",
            message=tr("setup.wizard.welcome"),
        )

        tax_id = prompter.prompt_text(
            key="tax_id",
            prompt=tr("setup.wizard.tax_id_prompt"),
            default=defaults.tax_id if defaults else None,
        )
        iva_regime_raw = prompter.prompt_choice(
            key="iva_regime",
            prompt=tr("setup.wizard.iva_regime_prompt"),
            choices=tuple(r.value for r in IVARegime),
            default=(defaults.iva_regime.value if defaults else IVARegime.GENERAL.value),
        )
        has_employees = prompter.prompt_bool(
            key="has_employees",
            prompt=tr("setup.wizard.has_employees_prompt"),
            default=defaults.has_employees if defaults else False,
        )
        pays_professionals_with_retencion = prompter.prompt_bool(
            key="pays_professionals_with_retencion",
            prompt=tr("setup.wizard.pays_professionals_with_retencion_prompt"),
            default=defaults.pays_professionals_with_retencion if defaults else False,
        )
        professional_income_withholding_ge_70pct = prompter.prompt_bool(
            key="professional_income_withholding_ge_70pct",
            prompt=tr("setup.wizard.professional_income_withholding_ge_70pct_prompt"),
            default=defaults.professional_income_withholding_ge_70pct if defaults else False,
        )
        pays_rent_with_retencion = prompter.prompt_bool(
            key="pays_rent_with_retencion",
            prompt=tr("setup.wizard.pays_rent_with_retencion_prompt"),
            default=defaults.pays_rent_with_retencion if defaults else False,
        )
        does_intracomunitario = prompter.prompt_bool(
            key="does_intracomunitario",
            prompt=tr("setup.wizard.does_intracomunitario_prompt"),
            default=defaults.does_intracomunitario if defaults else False,
        )
        third_party_transactions_above_347_threshold = prompter.prompt_bool(
            key="third_party_transactions_above_347_threshold",
            prompt=tr("setup.wizard.third_party_transactions_above_347_threshold_prompt"),
            default=defaults.third_party_transactions_above_347_threshold if defaults else False,
        )
        bienes_extranjero = prompter.prompt_bool(
            key="bienes_extranjero_above_threshold",
            prompt=tr("setup.wizard.bienes_extranjero_above_threshold_prompt"),
            default=defaults.bienes_extranjero_above_threshold if defaults else False,
        )
        tax_residence_raw = prompter.prompt_choice(
            key="tax_residence_ccaa",
            prompt=tr("setup.wizard.tax_residence_ccaa_prompt"),
            choices=tuple(ccaa.value for ccaa in CCAA),
            default=(defaults.tax_residence_ccaa.value if defaults else CCAA.MADRID.value),
        )

        cert_path = prompter.prompt_path(
            key="certificate_path",
            prompt=tr("setup.wizard.certificate_path_prompt"),
            default=defaults.certificate_path if defaults else None,
        )
        cert_password_var = prompter.prompt_text(
            key="certificate_password_secret_var_name",
            prompt=tr("setup.wizard.certificate_password_secret_var_name_prompt"),
            default=(defaults.certificate_password_secret_var_name if defaults else "AEAT_CERTIFICATE_PASSWORD_SECRET"),
        )
        cert_friendly_name = prompter.prompt_text(
            key="certificate_friendly_name",
            prompt=tr("setup.wizard.certificate_friendly_name_prompt"),
            default=(defaults.certificate_friendly_name or "") if defaults else "",
        )
        cert_backend_raw = prompter.prompt_choice(
            key="certificate_backend",
            prompt=tr("setup.wizard.certificate_backend_prompt"),
            choices=tuple(b.value for b in CertificateBackend),
            default=(defaults.certificate_backend.value if defaults else CertificateBackend.PLAYWRIGHT_CONTEXT.value),
        )

        default_lang_raw = prompter.prompt_choice(
            key="default_language",
            prompt=tr("setup.wizard.default_language_prompt"),
            choices=("es", "en", "ca", "hu"),
            default=(defaults.default_language if defaults else "en"),
        )
        output_lang_raw = prompter.prompt_choice(
            key="output_language",
            prompt=tr("setup.wizard.output_language_prompt"),
            choices=("es", "en", "ca", "hu"),
            default=(defaults.output_language if defaults else "es"),
        )

        drafts_dir = prompter.prompt_path(
            key="aeat_drafts_dir",
            prompt=tr("setup.wizard.aeat_drafts_dir_prompt"),
            default=defaults.aeat_drafts_dir if defaults else Path("var/drafts"),
        )
        submissions_dir = prompter.prompt_path(
            key="aeat_submissions_dir",
            prompt=tr("setup.wizard.aeat_submissions_dir_prompt"),
            default=defaults.aeat_submissions_dir if defaults else Path("var/submissions"),
        )
        manuals_root = prompter.prompt_path(
            key="aeat_manuals_root",
            prompt=tr("setup.wizard.aeat_manuals_root_prompt"),
            default=defaults.aeat_manuals_root if defaults else Path("corpus/manuals"),
        )
        profile_path = prompter.prompt_path(
            key="default_profile_path",
            prompt=tr("setup.wizard.default_profile_path_prompt"),
            default=defaults.default_profile_path if defaults else Path("env/profile.json"),
        )

        live_tests = prompter.prompt_bool(
            key="aeat_live_tests_enabled",
            prompt=tr("setup.wizard.aeat_live_tests_enabled_prompt"),
            default=defaults.aeat_live_tests_enabled if defaults else False,
        )
        live_tests_google = prompter.prompt_bool(
            key="aeat_live_tests_google",
            prompt=tr("setup.wizard.aeat_live_tests_google_prompt"),
            default=defaults.aeat_live_tests_google if defaults else False,
        )
        provision_fixtures = prompter.prompt_bool(
            key="provision_google_fixtures",
            prompt=tr("setup.wizard.provision_google_fixtures_prompt"),
            default=defaults.provision_google_fixtures if defaults else False,
        )

        return SetupAnswers(
            tax_id=tax_id,
            iva_regime=IVARegime(iva_regime_raw),
            has_employees=has_employees,
            pays_professionals_with_retencion=pays_professionals_with_retencion,
            professional_income_withholding_ge_70pct=professional_income_withholding_ge_70pct,
            pays_rent_with_retencion=pays_rent_with_retencion,
            does_intracomunitario=does_intracomunitario,
            third_party_transactions_above_347_threshold=third_party_transactions_above_347_threshold,
            bienes_extranjero_above_threshold=bienes_extranjero,
            tax_residence_ccaa=CCAA(tax_residence_raw),
            certificate_path=cert_path,
            certificate_password_secret_var_name=cert_password_var,
            certificate_friendly_name=cert_friendly_name or None,
            certificate_backend=CertificateBackend(cert_backend_raw),
            default_language=str(default_lang_raw),
            output_language=str(output_lang_raw),
            aeat_drafts_dir=drafts_dir,
            aeat_submissions_dir=submissions_dir,
            aeat_manuals_root=manuals_root,
            default_profile_path=profile_path,
            aeat_live_tests_enabled=live_tests,
            aeat_live_tests_google=live_tests_google,
            provision_google_fixtures=provision_fixtures,
            steps_to_skip=defaults.steps_to_skip if defaults else frozenset(),
            notes=defaults.notes if defaults else "",
        )
