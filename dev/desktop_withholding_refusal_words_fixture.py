"""Generate the desktop's withholding refusal words from the sentences the backend serves.

The suffered-withholding record operation and the absence-attestation operation each serve a
finished sentence with every refusal, one per reason, in the operation's output language. This
reads each sentence through the same functions the operations call, for every reason of both
operations in every language, so the browser fixture shows what the backend serves and holds no
text of its own. Run after changing the served refusal catalogue keys or the reasons.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import TypeAdapter

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

LANGUAGES = ("en", "es", "ca", "hu")
_Words = dict[str, dict[str, dict[str, dict[str, str]]]]
_WORDS = TypeAdapter(_Words)


def _worded(reasons: tuple[str, ...], word: Callable[[str], tuple[str, str]]) -> dict[str, dict[str, dict[str, str]]]:
    """Word each reason as its operation serves it, in every language."""
    from cadrumo.core.config import override_settings

    words: dict[str, dict[str, dict[str, str]]] = {}
    for reason in reasons:
        words[reason] = {}
        for language in LANGUAGES:
            with override_settings(cadrumo_output_language=language):
                sentence, served_language = word(reason)
            if served_language != language:
                raise SystemExit(f"{reason} was worded in {served_language}, not {language}")
            words[reason][language] = {"refusal_words": sentence, "refusal_words_language": language}
    return words


def render_fixture() -> str:
    """Word every refusal of both operations as the backend serves it, in every language."""
    from typing import cast, get_args

    from cadrumo.application.retencion_soportada_absence.contracts import (
        RETENCION_SOPORTADA_ABSENCE_REFUSAL_CODE,
        RETENCION_SOPORTADA_ABSENCE_REVISION_REFUSAL_CODE,
        RetencionSoportadaAbsenceOperationRefusalReason,
    )
    from cadrumo.application.retencion_soportada_absence.refusal_words import served_absence_refusal_words
    from cadrumo.application.retencion_soportada_certificado.contracts import (
        RETENCION_SOPORTADA_REVISION_REFUSAL_CODE,
        RETENCION_SOPORTADA_WRITE_REFUSAL_CODE,
        RetencionSoportadaCertificadoRefusalReason,
    )
    from cadrumo.application.retencion_soportada_certificado.refusal_words import served_refusal_words

    record_reasons = cast(
        tuple[RetencionSoportadaCertificadoRefusalReason, ...],
        get_args(RetencionSoportadaCertificadoRefusalReason.__value__),
    )
    absence_reasons = cast(
        tuple[RetencionSoportadaAbsenceOperationRefusalReason, ...],
        get_args(RetencionSoportadaAbsenceOperationRefusalReason.__value__),
    )

    def record(reason: str) -> tuple[str, str]:
        typed = cast(RetencionSoportadaCertificadoRefusalReason, reason)
        code = (
            RETENCION_SOPORTADA_REVISION_REFUSAL_CODE
            if typed == "stale_revision"
            else RETENCION_SOPORTADA_WRITE_REFUSAL_CODE
        )
        sentence, served = served_refusal_words(typed, error_code=code)
        return sentence, served.value

    def absence(reason: str) -> tuple[str, str]:
        typed = cast(RetencionSoportadaAbsenceOperationRefusalReason, reason)
        code = (
            RETENCION_SOPORTADA_ABSENCE_REVISION_REFUSAL_CODE
            if typed == "stale_revision"
            else RETENCION_SOPORTADA_ABSENCE_REFUSAL_CODE
        )
        sentence, served = served_absence_refusal_words(typed, error_code=code)
        return sentence, served.value

    words: _Words = {
        "record": _worded(record_reasons, record),
        "absence": _worded(absence_reasons, absence),
    }
    return json.dumps(words, ensure_ascii=False, indent=2) + "\n"


def _comparable(text: str) -> Mapping[str, object]:
    return _WORDS.validate_json(text)


def main() -> None:
    """Write or verify the checked-in browser fixture."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    target = (
        Path(__file__).resolve().parents[1]
        / "native/desktop/frontend/src/dev/fixtures/ledgerWithholdingRefusalWords.json"
    )
    rendered = render_fixture()
    if args.check:
        if not target.is_file() or _comparable(target.read_text(encoding="utf-8")) != _comparable(rendered):
            raise SystemExit(
                "Withholding refusal words are stale; run "
                "uv run --no-sync python -m dev.desktop_withholding_refusal_words_fixture"
            )
    else:
        target.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
