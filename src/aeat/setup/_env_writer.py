"""Env-file and profile-file writers for the first-run setup wizard.

The writer delegates the line-level work to
:func:`aeat.env_io.write_env_vars`, inheriting its comment
preservation, idempotent rewrite, and unrelated-key preservation
behaviour for free. The wizard only supplies a fixed, enumerated set
of keys — see :func:`owned_env_keys`.

The PKCS#12 password is **never** a field in the env writer's
payload. Only the name of the env var that holds it is recorded, and
only as an informational comment line.
"""

from __future__ import annotations

from pathlib import Path

from ..deadlines import AutonomoProfile
from ..env_io import write_env_vars
from ..logging import get_logger
from ._models import SetupAnswers

log = get_logger(__name__)


_PASSWORD_COMMENT_PREFIX = "# PKCS#12 password sourced from env var: "


def owned_env_keys() -> tuple[str, ...]:
    """Return the fixed set of env-var keys the setup wizard owns.

    Returns:
        A tuple of uppercase env-var names, in the order the wizard
        writes them. Any key not in this tuple is treated as "unrelated"
        by the writer and is left untouched in the target file.
    """
    return (
        "AEAT_CERTIFICATE_PATH",
        "AEAT_CERTIFICATE_FRIENDLY_NAME",
        "AEAT_CERTIFICATE_BACKEND",
        "AEAT_CERTIFICATE_VERIFY_URL",
        "AEAT_OUTPUT_LANGUAGE",
        "AEAT_DEFAULT_PROFILE_PATH",
        "AEAT_DRAFTS_DIR",
        "AEAT_SUBMISSIONS_DIR",
        "AEAT_MANUALS_ROOT",
        "AEAT_LIVE_TESTS_ENABLED",
        "AEAT_LIVE_TESTS_GOOGLE",
    )


def _posix(path: Path) -> str:
    """Render ``path`` as a POSIX-style absolute string for env-file storage."""
    return path.expanduser().resolve().as_posix()


def _answers_to_env_mapping(answers: SetupAnswers) -> dict[str, str]:
    """Materialise the subset of env-var values the wizard owns."""
    return {
        "AEAT_CERTIFICATE_PATH": _posix(answers.certificate_path),
        "AEAT_CERTIFICATE_FRIENDLY_NAME": answers.certificate_friendly_name or "",
        "AEAT_CERTIFICATE_BACKEND": answers.certificate_backend.value,
        "AEAT_CERTIFICATE_VERIFY_URL": answers.certificate_verify_url,
        "AEAT_OUTPUT_LANGUAGE": answers.output_language.value,
        "AEAT_DEFAULT_PROFILE_PATH": _posix(answers.default_profile_path),
        "AEAT_DRAFTS_DIR": _posix(answers.aeat_drafts_dir),
        "AEAT_SUBMISSIONS_DIR": _posix(answers.aeat_submissions_dir),
        "AEAT_MANUALS_ROOT": _posix(answers.aeat_manuals_root),
        "AEAT_LIVE_TESTS_ENABLED": "true" if answers.aeat_live_tests_enabled else "false",
        "AEAT_LIVE_TESTS_GOOGLE": "true" if answers.aeat_live_tests_google else "false",
    }


def _ensure_password_comment(path: Path, env_var_name: str) -> None:
    """Append or replace the password-source comment line in ``path``.

    The comment records the *name* of the env var that holds the
    PKCS#12 passphrase. The value is never written. The comment is
    idempotent: re-running with the same env var name produces a
    byte-equal file.
    """
    target_line = f"{_PASSWORD_COMMENT_PREFIX}{env_var_name}"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = existing.splitlines()
    replaced = False
    rewritten: list[str] = []
    for raw_line in lines:
        if raw_line.strip().startswith(_PASSWORD_COMMENT_PREFIX):
            if not replaced:
                rewritten.append(target_line)
                replaced = True
            # drop any duplicate password-comment lines
            continue
        rewritten.append(raw_line)
    if not replaced:
        rewritten.append(target_line)
    text = "\n".join(rewritten)
    if text and not text.endswith("\n"):
        text += "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_env_file(answers: SetupAnswers, target: Path) -> None:
    """Persist the wizard's owned env vars to ``target`` in place.

    The writer never emits the PKCS#12 passphrase. It only writes the
    fixed set of keys returned by :func:`owned_env_keys`, and then
    appends (or replaces) a single informational comment line
    recording the *name* of the env var the operator chose to hold
    the passphrase.

    Re-running this function with the same ``answers`` and ``target``
    is byte-equal idempotent. Keys the wizard does not own are
    preserved verbatim.

    Args:
        answers: Validated :class:`SetupAnswers` payload.
        target: Absolute path to the env file (e.g. ``env/.env``).
    """
    mapping = _answers_to_env_mapping(answers)
    write_env_vars(target, mapping)
    _ensure_password_comment(target, answers.certificate_password_secret_var_name)
    log.info("setup: wrote %d env keys to %s", len(mapping), target)


def write_profile_file(answers: SetupAnswers, target: Path) -> None:
    """Persist the user's :class:`AutonomoProfile` as JSON at ``target``.

    The profile file is consumed by ``aeat deadlines`` and is separate
    from the env file so the wizard never has to hand-craft JSON for
    a nested record.

    Args:
        answers: Validated :class:`SetupAnswers` payload.
        target: Absolute path where the profile JSON should be
            written.
    """
    profile = AutonomoProfile(
        tax_id=answers.tax_id,
        iva_regime=answers.iva_regime,
        has_employees=answers.has_employees,
        pays_rent_with_retencion=answers.pays_rent_with_retencion,
        does_intracomunitario=answers.does_intracomunitario,
        bienes_extranjero_above_threshold=answers.bienes_extranjero_above_threshold,
        notes=answers.notes,
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
    log.info("setup: wrote AutonomoProfile JSON to %s", target)
