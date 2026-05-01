"""The :class:`SetupWizard` orchestrator for the first-run setup flow (#61).

The wizard walks through every :class:`SetupStep` in order, calling
into the :class:`Prompter` Protocol for interactive answers and the
:class:`FirstRunRunner` Protocol for the optional read-only workflow check
(#59). In non-interactive mode, a fully-populated :class:`SetupAnswers`
short-circuits every prompt.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from ...adapters.outbound.aeat.auth import CertificateBackend
from ...core.config import load_settings
from ...core.i18n import Language, Translatable, get_translation
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
    return datetime.now(UTC)


def _t(es: str, en: str, hu: str) -> Translatable:
    return {"es": es, "en": en, "hu": hu}


def _setup_text(message: Translatable) -> str:
    try:
        language = Language(load_settings().aeat_output_language)
    except (KeyError, ValueError):
        language = Language.ES
    return get_translation(message, language)


class SetupWizard:
    """Orchestrates the ten-step first-run setup flow."""

    def __init__(self, *, verifier: Verifier | None = None) -> None:
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
            non_interactive: If True, consume ``defaults`` without
                prompting. ``defaults`` must be supplied.
            defaults: Pre-populated :class:`SetupAnswers`. Required for
                non-interactive mode; seeds prompter defaults in
                interactive mode.
            prompter: Interactive-mode only. The prompter driving the
                state machine.
            first_run_runner: Optional read-only workflow check (#59).
                If ``None``, the ``FIRST_RUN`` step is skipped cleanly.
            now: Clock injection point. Defaults to
                ``datetime.now(UTC)``.

        Returns:
            A :class:`SetupResult` describing the run.

        Raises:
            SetupError: If the arguments are inconsistent (e.g.
                non-interactive mode without defaults).
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

        # FIXTURE_PROVISIONING — captured opt-in; we never invoke the
        # external script from within the wizard, we only record the
        # choice.
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
            except Exception as exc:  # pragma: no cover - runner-specific
                log.warning("setup: first-run read-only check failed: %s", exc)
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
            message="aeat setup — configure this workstation for the first run.",
        )

        tax_id = prompter.prompt_text(
            key="tax_id",
            prompt="NIF / NIE",
            default=defaults.tax_id if defaults else None,
        )
        iva_regime_raw = prompter.prompt_choice(
            key="iva_regime",
            prompt="IVA regime",
            choices=tuple(r.value for r in IVARegime),
            default=(defaults.iva_regime.value if defaults else IVARegime.GENERAL.value),
        )
        has_employees = prompter.prompt_bool(
            key="has_employees",
            prompt="Do you pay salaries with retención?",
            default=defaults.has_employees if defaults else False,
        )
        pays_professionals_with_retencion = prompter.prompt_bool(
            key="pays_professionals_with_retencion",
            prompt="Do you pay professional fees with retención?",
            default=defaults.pays_professionals_with_retencion if defaults else False,
        )
        professional_income_withholding_ge_70pct = prompter.prompt_bool(
            key="professional_income_withholding_ge_70pct",
            prompt="Was at least 70% of your prior-year professional income already subject to withholding?",
            default=defaults.professional_income_withholding_ge_70pct if defaults else False,
        )
        pays_rent_with_retencion = prompter.prompt_bool(
            key="pays_rent_with_retencion",
            prompt="Do you pay alquiler de local with retención?",
            default=defaults.pays_rent_with_retencion if defaults else False,
        )
        does_intracomunitario = prompter.prompt_bool(
            key="does_intracomunitario",
            prompt="Do you conduct operaciones intracomunitarias?",
            default=defaults.does_intracomunitario if defaults else False,
        )
        third_party_transactions_above_347_threshold = prompter.prompt_bool(
            key="third_party_transactions_above_347_threshold",
            prompt="Did you exceed the Modelo 347 threshold with any third party last year?",
            default=defaults.third_party_transactions_above_347_threshold if defaults else False,
        )
        bienes_extranjero = prompter.prompt_bool(
            key="bienes_extranjero_above_threshold",
            prompt="Do you hold bienes en el extranjero above the 720 threshold?",
            default=defaults.bienes_extranjero_above_threshold if defaults else False,
        )
        tax_residence_raw = prompter.prompt_choice(
            key="tax_residence_ccaa",
            prompt=_setup_text(
                _t(
                    "CCAA de residencia fiscal para RENTA",
                    "Tax-residence CCAA for RENTA",
                    "Adoilletosegi CCAA a RENTA-hoz",
                )
            ),
            choices=tuple(ccaa.value for ccaa in CCAA),
            default=(defaults.tax_residence_ccaa.value if defaults else CCAA.MADRID.value),
        )

        cert_path = prompter.prompt_path(
            key="certificate_path",
            prompt="Path to your PKCS#12 (.p12/.pfx) bundle",
            default=defaults.certificate_path if defaults else None,
        )
        cert_password_var = prompter.prompt_text(
            key="certificate_password_secret_var_name",
            prompt="Name of the env var that holds your PKCS#12 passphrase",
            default=(defaults.certificate_password_secret_var_name if defaults else "AEAT_CERTIFICATE_PASSWORD_SECRET"),
        )
        cert_friendly_name = prompter.prompt_text(
            key="certificate_friendly_name",
            prompt="Optional friendly label for this certificate",
            default=(defaults.certificate_friendly_name or "") if defaults else "",
        )
        cert_backend_raw = prompter.prompt_choice(
            key="certificate_backend",
            prompt="Certificate backend",
            choices=tuple(b.value for b in CertificateBackend),
            default=(defaults.certificate_backend.value if defaults else CertificateBackend.PLAYWRIGHT_CONTEXT.value),
        )

        default_lang_raw = prompter.prompt_choice(
            key="default_language",
            prompt="Default language",
            choices=tuple(lang.value for lang in Language),
            default=(defaults.default_language.value if defaults else Language.EN.value),
        )
        output_lang_raw = prompter.prompt_choice(
            key="output_language",
            prompt="User-facing output language",
            choices=tuple(lang.value for lang in Language),
            default=(defaults.output_language.value if defaults else Language.ES.value),
        )

        drafts_dir = prompter.prompt_path(
            key="aeat_drafts_dir",
            prompt="Directory for filing drafts",
            default=defaults.aeat_drafts_dir if defaults else Path("var/drafts"),
        )
        submissions_dir = prompter.prompt_path(
            key="aeat_submissions_dir",
            prompt="Directory for submission audit records",
            default=defaults.aeat_submissions_dir if defaults else Path("var/submissions"),
        )
        manuals_root = prompter.prompt_path(
            key="aeat_manuals_root",
            prompt="Root of the Manual práctico corpus",
            default=defaults.aeat_manuals_root if defaults else Path("corpus/manuals"),
        )
        profile_path = prompter.prompt_path(
            key="default_profile_path",
            prompt="Where should the AutonomoProfile JSON live?",
            default=defaults.default_profile_path if defaults else Path("env/profile.json"),
        )

        live_tests = prompter.prompt_bool(
            key="aeat_live_tests_enabled",
            prompt="Opt in to @pytest.mark.live_read tests?",
            default=defaults.aeat_live_tests_enabled if defaults else False,
        )
        live_tests_google = prompter.prompt_bool(
            key="aeat_live_tests_google",
            prompt="Opt in to Google Workspace live fixture tests?",
            default=defaults.aeat_live_tests_google if defaults else False,
        )
        provision_fixtures = prompter.prompt_bool(
            key="provision_google_fixtures",
            prompt="Run the Google Workspace fixture provisioner after setup?",
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
            default_language=Language(default_lang_raw),
            output_language=Language(output_lang_raw),
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
