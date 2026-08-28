"""Render-language coverage for the review verbs (David round-10 gap #529).

The parity gate (``test_output_language_parity``) proves the
``--output-language`` flag is *registered* on ``app review queue`` /
``app review view`` and ``app modelo work create``. This module proves the
review render path *honours* the resolved language: the same operator-facing
queue prose renders in English under an English override and in Spanish
under the Spanish override (and the clean-install default).

The assertions drive the real render function ``_queue_lines`` through the
real ``override_settings`` seam — the exact seam
``activate_subcommand_output_language`` enters when the operator supplies
``--output-language`` — with the real locale catalogues and no test doubles,
so a regression in the language threading fails the assertion.
"""

from __future__ import annotations

import pytest

from ....application.review.operator import ReviewQueueReport
from ....core.config import override_settings
from ....tests.clean_install_fixtures import _clean_install
from .._review import _queue_lines

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_EMPTY_REPORT = ReviewQueueReport(rows=())


def _rendered(language: str | None) -> str:
    """Return the joined ``review queue`` render for *language*.

    ``language`` of None exercises the clean-install default (Spanish)
    with no override applied.
    """
    if language is None:
        return "\n".join(_queue_lines(_EMPTY_REPORT))
    with override_settings(cadrumo_output_language=language):
        return "\n".join(_queue_lines(_EMPTY_REPORT))


__all__ = ["_clean_install"]


def test_review_queue_renders_english_under_english_override() -> None:
    """An English override renders the queue header and empty message in English."""
    rendered = _rendered("en")
    assert "Kind" in rendered, rendered
    assert "Severity" in rendered, rendered
    assert "No items pending review." in rendered, rendered
    assert "Tipo" not in rendered, rendered


def test_review_queue_renders_spanish_under_spanish_override() -> None:
    """A Spanish override renders the queue header and empty message in Spanish."""
    rendered = _rendered("es")
    assert "Tipo" in rendered, rendered
    assert "Severidad" in rendered, rendered
    assert "pendientes de revisi" in rendered, rendered
    assert "Severity" not in rendered, rendered


@pytest.mark.usefixtures("_clean_install")
def test_review_queue_defaults_to_spanish() -> None:
    """With no language override a clean install defaults the queue to Spanish."""
    rendered = _rendered(None)
    assert "Tipo" in rendered, rendered
    assert "pendientes de revisi" in rendered, rendered
    assert "No items pending review." not in rendered, rendered
