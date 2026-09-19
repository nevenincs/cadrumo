"""Retirement of superseded authority generations, on every platform.

The published directory ships whole in the wheel, so a generation left behind
after cutover is roughly eighty megabytes of withdrawn authority inside a
release artefact, and the packaging gate that requires the archive to hold the
descriptor plus the database it names fails on it. Deferred retirement while a
reader holds a generation open is a Windows property and is proven beside the
held-reader cases; what this file holds is the part that is true everywhere.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..pipeline.authority_publication import install_validated_authority_database
from ._authority_generation_support import publishable_artifact

pytestmark = [pytest.mark.integration, pytest.mark.hex_domain]


def test_cutover_retires_the_generation_it_supersedes(tmp_path: Path) -> None:
    """Nothing holds the first generation, so publishing the second removes it.

    This is the case the POSIX branch used to decline outright: retirement ran
    only on Windows, so on the cells that build the release every publication
    added a generation that nothing would ever remove.
    """
    first = install_validated_authority_database(
        publishable_artifact("first"), destination=tmp_path, require_current=lambda: None
    )
    assert (tmp_path / first.database).is_file(), "the first generation was not installed"

    second = install_validated_authority_database(
        publishable_artifact("second"), destination=tmp_path, require_current=lambda: None
    )

    assert second.database != first.database, "the two publications produced one generation, so nothing was superseded"
    assert not (tmp_path / first.database).exists()
    assert (tmp_path / second.database).is_file()


def test_only_the_selected_generation_survives_a_run_of_publications(tmp_path: Path) -> None:
    """The directory holds the descriptor's selection and nothing else it names."""
    for label in ("first", "second", "third", "fourth"):
        descriptor = install_validated_authority_database(
            publishable_artifact(label), destination=tmp_path, require_current=lambda: None
        )

    surviving = sorted(path.name for path in tmp_path.glob("authority-*.sqlite3"))

    assert surviving == [descriptor.database]


def test_an_unrelated_file_beside_the_generations_is_never_retired(tmp_path: Path) -> None:
    """Retirement targets content-addressed generations, not whatever shares the directory."""
    bystander = tmp_path / "authority-notes.txt"
    bystander.write_text("operator notes", encoding="utf-8")
    install_validated_authority_database(
        publishable_artifact("first"), destination=tmp_path, require_current=lambda: None
    )

    install_validated_authority_database(
        publishable_artifact("second"), destination=tmp_path, require_current=lambda: None
    )

    assert bystander.read_text(encoding="utf-8") == "operator notes"
