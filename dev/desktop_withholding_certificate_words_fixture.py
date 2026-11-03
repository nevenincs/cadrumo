"""Generate the desktop's withholding certificate refusal words from the real refusal wording.

The suffered-withholding record operation serves the finished sentence for the three
certificate refusals it words (a document custody does not hold, a file that cannot be read
and a fingerprint that is not the file's). The sentence is the one the operation error
detail builds for the typed refusal, in the operation's output language. This reads each
sentence through that same wording in every language, so the browser fixture shows what the
backend serves and holds no text of its own. Run after changing the refusal catalogue keys.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import TypeAdapter

if TYPE_CHECKING:
    from collections.abc import Mapping

    from cadrumo.application.aggregation.retencion_soportada_repository import RetencionSoportadaRefusalReason

LANGUAGES = ("en", "es", "ca", "hu")
#: The refusals the record operation serves a sentence for.
REASONS: tuple[RetencionSoportadaRefusalReason, ...] = (
    "certificate_not_in_custody",
    "certificate_file_unreadable",
    "certificate_fingerprint_mismatch",
)
#: The ejercicio the refusals are worded for; the sentence names no year.
EJERCICIO = 2025
_WORDS = TypeAdapter(dict[str, dict[str, dict[str, str]]])


def render_fixture() -> str:
    """Word each refusal as the operation serves it, in every language."""
    from cadrumo.application.aggregation.retencion_soportada_repository import RetencionSoportadaWriteRefusedError
    from cadrumo.application.operations.error_detail import operation_refusal_words
    from cadrumo.core.config import override_settings

    words: dict[str, dict[str, dict[str, str]]] = {}
    for reason in REASONS:
        words[reason] = {}
        for language in LANGUAGES:
            with override_settings(cadrumo_output_language=language):
                served = operation_refusal_words(RetencionSoportadaWriteRefusedError(reason, ejercicio=EJERCICIO))
            if served is None:
                raise SystemExit(f"{reason} serves no words in {language}")
            sentence, served_language = served
            if served_language.value != language:
                raise SystemExit(f"{reason} was worded in {served_language.value}, not {language}")
            words[reason][language] = {"refusal_words": sentence, "refusal_words_language": language}
    return json.dumps(words, ensure_ascii=False, indent=2) + "\n"


def _comparable(text: str) -> Mapping[str, object]:
    return _WORDS.validate_json(text)


def main() -> None:
    """Write or verify the checked-in browser fixture."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    target = (
        Path(__file__).resolve().parents[1] / "native/desktop/frontend/src/dev/fixtures/ledgerWithholdingWords.json"
    )
    rendered = render_fixture()
    if args.check:
        if not target.is_file() or _comparable(target.read_text(encoding="utf-8")) != _comparable(rendered):
            raise SystemExit(
                "Withholding certificate refusal words are stale; run "
                "uv run --no-sync python -m dev.desktop_withholding_certificate_words_fixture"
            )
    else:
        target.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
