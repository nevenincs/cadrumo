"""Guard the Hungarian diacritic quality of operator-facing error strings.

Several ``hu`` ERROR / refusal strings had been ASCII-folded (e.g. "Nincs
aktiv munkaegyseg" — missing á/é/ű) while the narrative strings kept their
diacritics. The fold lived in the locale DATA (there is no ASCII-folding code:
the renderer uses ``ensure_ascii=False``). This test renders the corrected
work-addressing and storage-session error keys through the real ``tr`` pipeline
in the Hungarian output language and asserts the proper accented Hungarian
surfaces, so a future re-fold of these specific operator-hit strings fails
loudly.

Each key is rendered with its real interpolation arguments against the shipped
``hu.yml`` catalogue — no mocks, no stubs.
"""

from __future__ import annotations

import pytest

from ...config import override_settings
from .._render import tr

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# Each entry: (key, interpolation kwargs, substrings that MUST appear,
# ASCII-folded substrings that MUST NOT appear).
_CASES: list[tuple[str, dict[str, object], tuple[str, ...], tuple[str, ...]]] = [
    (
        "cli.app.modelo.work.selector_not_found",
        {},
        ("Nincs aktív munkaegység", "Futtassa először"),
        ("aktiv munkaegyseg", "idoszak", "eloszor"),
    ),
    (
        "cli.app.modelo.work.selector_ambiguous",
        {"candidates": "X"},
        ("Több aktív munkaegység", "nyilvántartási revíziót"),
        ("Tobb aktiv", "nyilvantartasi reviziot"),
    ),
    (
        "application.modelo.errors.export_period_unmappable",
        {"work_unit_id": "wu", "period": "1T"},
        ("munkaegység", "időszakot"),
        ("munkaegyseg", "idoszakot"),
    ),
    (
        "application.modelo.errors.export_operator_name_missing",
        {"missing": "name"},
        ("Az exportáláshoz szükség van", "aktív profilban"),
        ("exportalashoz szukseg", "aktiv profilban"),
    ),
    (
        "application.modelo.errors.work_unit_revision_divergence",
        {
            "work_unit_id": "wu",
            "work_unit_revision": "r1",
            "modelo": "130",
            "filing_year": "2026",
            "period": "1T",
            "law_revision": "r2",
        },
        ("munkaegység", "nyilvántartási revízióval", "törvény által meghatározott"),
        ("munkaegyseg", "nyilvantartasi revizioval", "torveny altal meghatarozott"),
    ),
    (
        "errors.storage.runtime.session_expired",
        {},
        ("Az aktív bucket-munkamenet lejárt", "újraaktiválásához"),
        ("aktiv bucket-munkamenet lejart", "ujraaktivalasahoz"),
    ),
    (
        "errors.refused.modelo_work_selector_no_active_bucket",
        {},
        ("Válasszon aktív profilt", "munkaegység feloldása előtt"),
        ("Valasszon aktiv profilt", "munkaegyseg feloldasa elott"),
    ),
]


@pytest.mark.parametrize(("key", "kwargs", "must_contain", "must_not_contain"), _CASES)
def test_hu_error_strings_render_with_diacritics(
    key: str,
    kwargs: dict[str, object],
    must_contain: tuple[str, ...],
    must_not_contain: tuple[str, ...],
) -> None:
    """The corrected Hungarian error strings render with proper diacritics."""
    with override_settings(aeat_output_language="hu"):
        rendered = tr(key, **kwargs)

    for fragment in must_contain:
        assert fragment in rendered, f"{key}: missing accented fragment {fragment!r} in {rendered!r}"
    for fragment in must_not_contain:
        assert fragment not in rendered, f"{key}: ASCII-folded fragment {fragment!r} re-appeared in {rendered!r}"
