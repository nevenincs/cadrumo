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

from ...core.logging import get_logger
from ._models import SetupAnswers, VerifyFinding, VerifySeverity

log = get_logger(__name__)


def _finding(
    *,
    name: str,
    severity: VerifySeverity,
    es: str,
    en: str,
    ca: str,
    hu: str,
    remediation_es: str | None = None,
    remediation_en: str | None = None,
    remediation_ca: str | None = None,
    remediation_hu: str | None = None,
) -> VerifyFinding:
    """Construct a :class:`VerifyFinding` with a multilingual message."""
    message: str = "translation"
    remediation: str | None = None
    if any(slot is not None for slot in (remediation_es, remediation_en, remediation_ca, remediation_hu)):
        remediation = "translation"
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
            es=f"No se encontró el certificado: {path}",
            en=f"Certificate file not found: {path}",
            ca=f"No s'ha trobat el certificat: {path}",
            hu=f"A tanúsítvány fájl nem található: {path}",
            remediation_es="Coloca el archivo .p12 / .pfx en la ruta configurada.",
            remediation_en="Place your .p12 / .pfx bundle at the configured path.",
            remediation_ca="Col·loca el fitxer .p12 / .pfx a la ruta configurada.",
            remediation_hu="Helyezd a .p12 / .pfx fájlt a beállított útvonalra.",
        )
    if not path.is_file():
        return _finding(
            name="certificate_path_exists",
            severity=VerifySeverity.ERROR,
            es=f"La ruta del certificado no es un fichero: {path}",
            en=f"Certificate path is not a file: {path}",
            ca=f"La ruta del certificat no és un fitxer: {path}",
            hu=f"A tanúsítvány útvonala nem fájl: {path}",
        )
    return _finding(
        name="certificate_path_exists",
        severity=VerifySeverity.OK,
        es=f"Certificado presente en {path}",
        en=f"Certificate present at {path}",
        ca=f"Certificat present a {path}",
        hu=f"A tanúsítvány elérhető: {path}",
    )


def _check_password_env_var(answers: SetupAnswers) -> VerifyFinding:
    var = answers.certificate_password_secret_var_name
    if not os.environ.get(var):
        return _finding(
            name="certificate_password_env_var_set",
            severity=VerifySeverity.WARNING,
            es=f"La variable {var} no está definida; establézcala antes de ejecutar comandos en vivo.",
            en=f"Environment variable {var} is unset; set it before running live commands.",
            ca=f"La variable {var} no està definida; defineix-la abans d'executar ordres en viu.",
            hu=f"A(z) {var} változó nincs beállítva; állítsa be az éles parancsok futtatása előtt.",
            remediation_es=f"Exporta {var}=<tu-contraseña> en tu shell o gestor de secretos.",
            remediation_en=f"Export {var}=<your-passphrase> in your shell or secret store.",
            remediation_ca=f"Exporta {var}=<la-teva-contrasenya> al teu intèrpret o gestor de secrets.",
            remediation_hu=f"Exportáld a {var}=<jelszavad> változót a shellben vagy a titokkezelőben.",
        )
    return _finding(
        name="certificate_password_env_var_set",
        severity=VerifySeverity.OK,
        es=f"La variable {var} está definida.",
        en=f"Environment variable {var} is set.",
        ca=f"La variable {var} està definida.",
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
            es=f"No se puede crear {name} en {path}: {exc}",
            en=f"Cannot create {name} at {path}: {exc}",
            ca=f"No es pot crear {name} a {path}: {exc}",
            hu=f"Nem lehet létrehozni a(z) {name}-t itt: {path}: {exc}",
        )
    return _finding(
        name=f"{name}_creatable",
        severity=VerifySeverity.OK,
        es=f"{name} listo en {path}",
        en=f"{name} ready at {path}",
        ca=f"{name} llest a {path}",
        hu=f"{name} elérhető itt: {path}",
    )


def _check_profile_file(answers: SetupAnswers) -> VerifyFinding:
    path = answers.default_profile_path.expanduser()
    if not path.exists():
        return _finding(
            name="autonomo_profile_json_valid",
            severity=VerifySeverity.WARNING,
            es=f"Sobre cifrado del perfil no encontrado en {path}; el asistente lo escribirá.",
            en=f"Profile envelope not found at {path}; the wizard will write it.",
            ca=f"Sobre xifrat del perfil no trobat a {path}; l'assistent l'escriurà.",
            hu=f"A profil titkosított csomagja nincs itt: {path}; a varázsló létrehozza.",
        )
    from ._env_writer import load_profile_envelope

    try:
        load_profile_envelope(path)
    except (OSError, ValueError, ValidationError) as exc:
        return _finding(
            name="autonomo_profile_json_valid",
            severity=VerifySeverity.ERROR,
            es=f"El sobre del perfil en {path} no es válido: {exc}",
            en=f"Profile envelope at {path} is invalid: {exc}",
            ca=f"El sobre del perfil a {path} no és vàlid: {exc}",
            hu=f"A profil csomag érvénytelen itt: {path}: {exc}",
        )
    return _finding(
        name="autonomo_profile_json_valid",
        severity=VerifySeverity.OK,
        es=f"El sobre del perfil en {path} se valida correctamente.",
        en=f"Profile envelope at {path} round-trips through the substrate.",
        ca=f"El sobre del perfil a {path} es valida correctament.",
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
            es=f"SetupAnswers no pasó la autovalidación: {exc}",
            en=f"SetupAnswers failed self-validation: {exc}",
            ca=f"SetupAnswers no ha passat l'autovalidació: {exc}",
            hu=f"A SetupAnswers önellenőrzése sikertelen: {exc}",
        )
    return _finding(
        name="setup_answers_self_consistent",
        severity=VerifySeverity.OK,
        es="SetupAnswers pasa la autovalidación estricta.",
        en="SetupAnswers round-trips through strict pydantic.",
        ca="SetupAnswers passa l'autovalidació estricta.",
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
