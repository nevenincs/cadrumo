"""Each bundled excerpt is classified by how checkable its consolidated-version claim is."""

from __future__ import annotations

from pathlib import Path

import pytest

from ..corpus_vigencia_claims import CLAIM_STATES, Excerpt, main, survey, verify

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_API = "https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/BOE-A-1992-28740/texto/bloque/a80"


def test_each_header_shape_lands_in_its_state(tmp_path: Path) -> None:
    headers = {
        "a-unanchored.html": "<p>An excerpt with no provenance.</p>",
        "b-undated.html": "<!-- Document: BOE-A-1992-28740 -->",
        "c-claimed.html": "<!-- Document: BOE-A-1992-28740, in force from 2024-01-01 -->",
        "d-verifiable.html": f"<!-- Document: BOE-A-1992-28740, in force from 2024-01-01, {_API} -->",
    }
    for name, header in headers.items():
        (tmp_path / name).write_text(header, encoding="utf-8")

    excerpts = {excerpt.name: excerpt for excerpt in survey(tmp_path)}

    assert [excerpts[name].state for name in sorted(headers)] == list(CLAIM_STATES)
    assert excerpts["c-claimed.html"].claimed == "2024-01-01"
    assert excerpts["c-claimed.html"].api_url is None
    assert excerpts["d-verifiable.html"].api_url == _API


def test_verification_declines_what_it_cannot_check_without_fetching() -> None:
    assert verify(Excerpt("claimed.html", "claimed", "2024-01-01", None)) == (True, "not verifiable")
    foreign = Excerpt("foreign.html", "verifiable", "2024-01-01", "https://example.invalid/bloque/a80")
    assert verify(foreign) == (True, "unsupported URL")


def test_the_live_survey_classifies_every_bundled_excerpt(capsys: pytest.CaptureFixture[str]) -> None:
    excerpts = tuple(survey())

    assert excerpts, "no bundled excerpt was surveyed, so the classification measured nothing"
    assert all(excerpt.state in CLAIM_STATES for excerpt in excerpts)
    assert main(["--json"]) == 0
    assert '"counts"' in capsys.readouterr().out
