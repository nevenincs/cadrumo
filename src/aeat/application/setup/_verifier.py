"""Pure verifier for the first-run setup wizard.

Each check is a small pure function that returns a
:class:`VerifyFinding`. No check ever mutates state; running the
verifier against a production-looking env file is safe.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import ValidationError

from ...core.i18n import tr
from ...core.logging import get_logger
from ._models import SetupAnswers, VerifyFinding, VerifySeverity

log = get_logger(__name__)


def _finding(
    *,
    name: str,
    severity: VerifySeverity,
    message: str,
    remediation: str | None = None,
) -> VerifyFinding:
    """Construct a :class:`VerifyFinding` with a translatable message."""
    return VerifyFinding(
        name=name,
        severity=severity,
        message=message,
        remediation=remediation,
    )


def _check_certificate_path(answers: SetupAnswers) -> VerifyFinding:
    path = answers.certificate_path.expanduser()
    if not path.exists():
        return _finding(
            name="certificate_path_exists",
            severity=VerifySeverity.ERROR,
            message=tr("setup.verifier.t_501723", path=str(path)),
            remediation=tr("setup.verifier.t_193582"),
        )
    if not path.is_file():
        return _finding(
            name="certificate_path_exists",
            severity=VerifySeverity.ERROR,
            message=tr("setup.verifier.t_049382", path=str(path)),
        )
    return _finding(
        name="certificate_path_exists",
        severity=VerifySeverity.OK,
        message=tr("setup.verifier.t_749321", path=str(path)),
    )


def _check_password_env_var(answers: SetupAnswers) -> VerifyFinding:
    var = answers.certificate_password_secret_var_name
    if not os.environ.get(var):
        return _finding(
            name="certificate_password_env_var_set",
            severity=VerifySeverity.WARNING,
            message=tr("setup.verifier.t_938472", var=var),
            remediation=tr("setup.verifier.t_394821", var=var),
        )
    return _finding(
        name="certificate_password_env_var_set",
        severity=VerifySeverity.OK,
        message=tr("setup.verifier.t_104932", var=var),
    )


def _check_directory(name: str, path: Path) -> VerifyFinding:
    path = path.expanduser()
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return _finding(
            name=f"{name}_creatable",
            severity=VerifySeverity.ERROR,
            message=tr("setup.verifier.t_649302", name=name, path=str(path), exc=str(exc)),
        )
    return _finding(
        name=f"{name}_creatable",
        severity=VerifySeverity.OK,
        message=tr("setup.verifier.t_204938", name=name, path=str(path)),
    )


def _check_profile_file(answers: SetupAnswers) -> VerifyFinding:
    path = answers.default_profile_path.expanduser()
    if not path.exists():
        return _finding(
            name="autonomo_profile_json_valid",
            severity=VerifySeverity.WARNING,
            message=tr("setup.verifier.t_394827", path=str(path)),
        )
    from ._env_writer import load_profile_envelope

    try:
        load_profile_envelope(path)
    except (OSError, ValueError, ValidationError) as exc:
        return _finding(
            name="autonomo_profile_json_valid",
            severity=VerifySeverity.ERROR,
            message=tr("setup.verifier.t_837462", path=str(path), exc=str(exc)),
        )
    return _finding(
        name="autonomo_profile_json_valid",
        severity=VerifySeverity.OK,
        message=tr("setup.verifier.t_104938", path=str(path)),
    )


def _check_answers_self_consistency(answers: SetupAnswers) -> VerifyFinding:
    """Smoke test: re-validate the answers via model_validate_json."""
    try:
        SetupAnswers.model_validate_json(answers.model_dump_json())
    except ValidationError as exc:
        return _finding(
            name="setup_answers_self_consistent",
            severity=VerifySeverity.ERROR,
            message=tr("setup.verifier.t_938475", exc=str(exc)),
        )
    return _finding(
        name="setup_answers_self_consistent",
        severity=VerifySeverity.OK,
        message=tr("setup.verifier.t_293847"),
    )


class Verifier:
    """Pure verifier that inspects a fully-populated :class:`SetupAnswers`.

    Usage::

        findings = Verifier().run(answers)

    The verifier never mutates state except for the idempotent
    ``mkdir`` call in :func:`_check_directory`, which is how the
    check actually learns whether the directory is creatable.
    """

    def run(self, answers: SetupAnswers) -> tuple[VerifyFinding, ...]:
        """Execute every check against ``answers`` and return their findings."""
        findings: list[VerifyFinding] = []
        findings.append(_check_answers_self_consistency(answers))
        findings.append(_check_certificate_path(answers))
        findings.append(_check_password_env_var(answers))
        findings.append(_check_directory("drafts_dir", answers.aeat_drafts_dir))
        findings.append(_check_directory("submissions_dir", answers.aeat_submissions_dir))
        findings.append(_check_directory("manuals_root", answers.aeat_manuals_root))
        findings.append(_check_profile_file(answers))
        log.info(
            "setup: verifier produced %d findings (%d ERROR, %d WARNING)",
            len(findings),
            sum(1 for f in findings if f.severity is VerifySeverity.ERROR),
            sum(1 for f in findings if f.severity is VerifySeverity.WARNING),
        )
        return tuple(findings)

    @staticmethod
    def has_error(findings: tuple[VerifyFinding, ...]) -> bool:
        """Return True if any finding has severity ``ERROR``."""
        return any(f.severity is VerifySeverity.ERROR for f in findings)


def load_answers_from_file(path: Path) -> SetupAnswers:
    """Load a :class:`SetupAnswers` payload from a JSON file.

    Args:
        path: Absolute path to the JSON file.

    Returns:
        The parsed :class:`SetupAnswers` record.

    Raises:
        SetupAnswersError: If the file is missing or its contents do
            not validate.
    """
    from ._errors import SetupAnswersError

    if not path.exists():
        raise SetupAnswersError(f"answers file not found: {path}")
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SetupAnswersError(f"cannot read answers file {path}: {exc}") from exc
    try:
        return SetupAnswers.model_validate_json(raw)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise SetupAnswersError(f"invalid answers file {path}: {exc}") from exc
