"""Pure verifier for the first-run setup wizard (#61).

Each check is a small pure function that returns a
:class:`VerifyFinding`. No check ever mutates state; running the
verifier against a production-looking env file is safe.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import ValidationError

from ..i18n import Translatable
from ..logging import get_logger
from ._models import SetupAnswers, VerifyFinding, VerifySeverity

log = get_logger(__name__)


def _finding(
    *,
    name: str,
    severity: VerifySeverity,
    en: str,
    es: str,
    hu: str,
    remediation_en: str | None = None,
) -> VerifyFinding:
    """Construct a :class:`VerifyFinding` with a trilingual message."""
    message: Translatable = {"en": en, "es": es, "hu": hu}
    remediation: Translatable | None = None
    if remediation_en is not None:
        remediation = {"en": remediation_en, "es": remediation_en, "hu": remediation_en}
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
            en=f"Certificate file not found: {path}",
            es=f"No se encontró el certificado: {path}",
            hu=f"A tanúsítvány fájl nem található: {path}",
            remediation_en="Place your .p12 / .pfx bundle at the configured path.",
        )
    if not path.is_file():
        return _finding(
            name="certificate_path_exists",
            severity=VerifySeverity.ERROR,
            en=f"Certificate path is not a file: {path}",
            es=f"La ruta del certificado no es un fichero: {path}",
            hu=f"A tanúsítvány útvonala nem fájl: {path}",
        )
    return _finding(
        name="certificate_path_exists",
        severity=VerifySeverity.OK,
        en=f"Certificate present at {path}",
        es=f"Certificado presente en {path}",
        hu=f"A tanúsítvány elérhető: {path}",
    )


def _check_password_env_var(answers: SetupAnswers) -> VerifyFinding:
    var = answers.certificate_password_secret_var_name
    if not os.environ.get(var):
        return _finding(
            name="certificate_password_env_var_set",
            severity=VerifySeverity.WARNING,
            en=f"Environment variable {var} is unset; set it before running live commands.",
            es=f"La variable {var} no está definida; establézcala antes de ejecutar comandos en vivo.",
            hu=f"A(z) {var} változó nincs beállítva; állítsa be az éles parancsok futtatása előtt.",
            remediation_en=f"Export {var}=<your-passphrase> in your shell or secret store.",
        )
    return _finding(
        name="certificate_password_env_var_set",
        severity=VerifySeverity.OK,
        en=f"Environment variable {var} is set.",
        es=f"La variable {var} está definida.",
        hu=f"A(z) {var} változó be van állítva.",
    )


def _check_directory(name: str, path: Path) -> VerifyFinding:
    path = path.expanduser()
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return _finding(
            name=f"{name}_creatable",
            severity=VerifySeverity.ERROR,
            en=f"Cannot create {name} at {path}: {exc}",
            es=f"No se puede crear {name} en {path}: {exc}",
            hu=f"Nem lehet létrehozni a(z) {name}-t itt: {path}: {exc}",
        )
    return _finding(
        name=f"{name}_creatable",
        severity=VerifySeverity.OK,
        en=f"{name} ready at {path}",
        es=f"{name} listo en {path}",
        hu=f"{name} elérhető itt: {path}",
    )


def _check_profile_file(answers: SetupAnswers) -> VerifyFinding:
    path = answers.default_profile_path.expanduser()
    if not path.exists():
        return _finding(
            name="autonomo_profile_json_valid",
            severity=VerifySeverity.WARNING,
            en=f"Profile envelope not found at {path}; the wizard will write it.",
            es=f"Sobre cifrado del perfil no encontrado en {path}; el asistente lo escribirá.",
            hu=f"A profil titkosított csomagja nincs itt: {path}; a varázsló létrehozza.",
        )
    from ._env_writer import load_profile_envelope

    try:
        load_profile_envelope(path)
    except (OSError, ValueError, ValidationError) as exc:
        return _finding(
            name="autonomo_profile_json_valid",
            severity=VerifySeverity.ERROR,
            en=f"Profile envelope at {path} is invalid: {exc}",
            es=f"El sobre del perfil en {path} no es válido: {exc}",
            hu=f"A profil csomag érvénytelen itt: {path}: {exc}",
        )
    return _finding(
        name="autonomo_profile_json_valid",
        severity=VerifySeverity.OK,
        en=f"Profile envelope at {path} round-trips through the substrate.",
        es=f"El sobre del perfil en {path} se valida correctamente.",
        hu=f"A profil csomag itt: {path} érvényes.",
    )


def _check_answers_self_consistency(answers: SetupAnswers) -> VerifyFinding:
    """Smoke test: re-validate the answers via model_validate_json."""
    try:
        SetupAnswers.model_validate_json(answers.model_dump_json())
    except ValidationError as exc:
        return _finding(
            name="setup_answers_self_consistent",
            severity=VerifySeverity.ERROR,
            en=f"SetupAnswers failed self-validation: {exc}",
            es=f"SetupAnswers no pasó la autovalidación: {exc}",
            hu=f"A SetupAnswers önellenőrzése sikertelen: {exc}",
        )
    return _finding(
        name="setup_answers_self_consistent",
        severity=VerifySeverity.OK,
        en="SetupAnswers round-trips through strict pydantic.",
        es="SetupAnswers pasa la autovalidación estricta.",
        hu="A SetupAnswers érvényes szigorú pydantic szerint.",
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
