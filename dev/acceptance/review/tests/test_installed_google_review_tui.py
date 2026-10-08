"""Public evidence cannot prove a different saved source or an unverified link."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import override

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from cadrumo.core.external_constants import OutputLanguage
from cadrumo.entrypoints.review_publication_labels import GoogleReviewLabels

from ..installed_google_review_tui import (
    GoogleReviewTuiAcceptanceError,
    _until,
    google_document_id,
    read_public_disclosure,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _disclosure(language: OutputLanguage) -> tuple[GoogleReviewLabels, str]:
    labels = GoogleReviewLabels(language)
    values = {
        "calculation_revision_id": "a" * 64,
        "root_folder_id": "synthetic-managed-folder",
        "snapshot_digest": "b" * 64,
        "publication_id": "66666666-7777-4888-9999-000000000000",
    }
    return labels, "\n".join(labels(f"google_review.label.{key}") + ": " + value for key, value in values.items())


@pytest.mark.parametrize("language", tuple(OutputLanguage))
def test_localized_disclosure_exposes_the_exact_saved_source(language: OutputLanguage) -> None:
    labels, text = _disclosure(language)
    evidence = read_public_disclosure(text, labels=labels, calculation_revision_id="a" * 64)
    assert evidence.snapshot_digest == "b" * 64
    assert evidence.root_folder_id == "synthetic-managed-folder"


@pytest.mark.parametrize("defect", ("wrong_source", "missing_root", "duplicate", "bad_digest", "bad_publication"))
def test_ambiguous_or_changed_disclosure_refuses_publication(defect: str) -> None:
    labels, text = _disclosure(OutputLanguage.EN)
    if defect == "wrong_source":
        text = text.replace("a" * 64, "c" * 64)
    elif defect == "missing_root":
        text = "\n".join(line for line in text.splitlines() if "synthetic-managed-folder" not in line)
    elif defect == "duplicate":
        text += "\n" + text.splitlines()[0]
    elif defect == "bad_digest":
        text = text.replace("b" * 64, "short")
    else:
        text = text.replace("66666666-7777-4888-9999-000000000000", "invalid")
    with pytest.raises(GoogleReviewTuiAcceptanceError):
        read_public_disclosure(text, labels=labels, calculation_revision_id="a" * 64)


@pytest.mark.parametrize(
    "url",
    (
        "http://docs.google.com/spreadsheets/d/abc/edit",
        "https://docs.google.com.attacker.example/spreadsheets/d/abc/edit",
        "https://docs.google.com/spreadsheets/d/abc/edit?unverified=1",
        "https://docs.google.com/spreadsheets/d/abc/edit#fragment",
        "https://user@docs.google.com/spreadsheets/d/abc/edit",
        "https://docs.google.com/spreadsheets/d//edit",
    ),
)
def test_noncanonical_settled_link_is_not_accepted(url: str) -> None:
    with pytest.raises(GoogleReviewTuiAcceptanceError):
        google_document_id(url)


def test_canonical_settled_link_preserves_exact_document_identity() -> None:
    assert google_document_id("https://docs.google.com/spreadsheets/d/Abc_12-xyz/edit") == "Abc_12-xyz"


class _RefusedSurface(App[None]):
    @override
    def compose(self) -> ComposeResult:
        yield Static("This frontend cannot publish this review", id="saved-google-review-notice")


@pytest.mark.parametrize("refused", (True, False))
def test_refusal_or_timeout_captures_public_failure_without_publication(tmp_path: Path, refused: bool) -> None:
    app = _RefusedSurface()

    async def run() -> None:
        async with app.run_test() as pilot:
            with pytest.raises(GoogleReviewTuiAcceptanceError):
                await _until(
                    pilot,
                    lambda: False,
                    deadline=0,
                    stage="registered human disclosure",
                    output_dir=tmp_path,
                    refusal=(lambda: "frontend_denied") if refused else None,
                )

    asyncio.run(run())
    failure = json.loads((tmp_path / "failure.json").read_text())
    assert failure["reason"] == ("frontend_denied" if refused else "stage_timeout")
    assert failure["screen_type"] == "Screen"
    assert failure["public_notices"] == {
        "saved-google-review-notice": "This frontend cannot publish this review",
    }
    assert not failure["publication_attempt_exists"]
    assert (tmp_path / "05-failure.svg").is_file()
