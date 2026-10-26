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

from ..pipeline.authority_publication import (
    install_validated_authority_database,
    promote_accepted_authority_database,
)
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


def test_every_coexisting_superseded_generation_is_retired_by_one_publication(tmp_path: Path) -> None:
    """One publication sweeps the whole backlog, not just the generation it directly supersedes.

    Deferred retirement leaves a superseded generation behind whenever a reader
    held it open, so a directory can carry several at once, and each of them is
    roughly eighty megabytes.

    A publication that retired only the generation it directly superseded would
    pass every other test in this file: the sequential run above publishes four
    times with exactly one generation superseded each time, so one-deep
    retirement satisfies it. Staging a backlog that a single publication has to
    clear is what separates an exhaustive sweep from a one-deep one.
    """
    first = install_validated_authority_database(
        publishable_artifact("first"), destination=tmp_path, require_current=lambda: None
    )
    backlog = tuple(tmp_path / f"authority-{str(index) * 64}.sqlite3" for index in range(1, 4))
    for stale in backlog:
        stale.write_bytes(b"superseded generation")

    second = install_validated_authority_database(
        publishable_artifact("second"), destination=tmp_path, require_current=lambda: None
    )

    assert [stale for stale in backlog if stale.exists()] == []
    assert not (tmp_path / first.database).exists()
    assert sorted(path.name for path in tmp_path.glob("authority-*.sqlite3")) == [second.database]


def test_promotion_retires_the_generations_it_supersedes(tmp_path: Path) -> None:
    """Admitting already-accepted bytes sweeps the destination the compiling path does.

    A release promotes an accepted candidate rather than recompiling it, so the
    directory the wheel ships is the one promotion leaves behind. Retirement was
    covered only through the compiling path, which left this one free to accrue
    superseded generations unnoticed.
    """
    candidate_root = tmp_path / "candidate"
    destination = tmp_path / "destination"
    superseded = install_validated_authority_database(
        publishable_artifact("superseded"), destination=destination, require_current=lambda: None
    )
    stale = destination / f"authority-{'a' * 64}.sqlite3"
    stale.write_bytes(b"superseded generation")
    accepted = install_validated_authority_database(
        publishable_artifact("accepted"), destination=candidate_root, require_current=lambda: None
    )

    promoted = promote_accepted_authority_database(candidate_root / "authority.current.json", destination=destination)

    assert promoted.database == accepted.database
    assert not (destination / superseded.database).exists()
    assert not stale.exists()
    assert sorted(path.name for path in destination.glob("authority-*.sqlite3")) == [promoted.database]


def test_the_publication_lock_sidecar_survives_and_is_never_a_retirement_target(tmp_path: Path) -> None:
    """The retained zero-byte sidecar is not a generation and not litter.

    ``exclusive_file_lock`` creates ``authority.current.json.lock`` beside the
    descriptor and deliberately keeps it after release: ownership lives in the
    OS against the open descriptor, so deleting the sidecar while another
    process races to acquire it would open a window where two publishers each
    believe they hold the lock. A surviving empty sidecar therefore says
    nothing about whether a publication finished, and retirement must leave it
    alone rather than treat it as a superseded generation.

    This records intent and guards cleanup written outside the publisher; it is
    not a demonstrated detector. Retirement runs inside the publication lock
    with the descriptor open, so a publisher that tried to delete its own
    sidecar is refused by the operating system and fails outright instead of
    publishing a directory without one. No in-publisher defect is reachable for
    this assertion to catch, and it should not be read later as proof that one
    was caught.
    """
    install_validated_authority_database(
        publishable_artifact("first"), destination=tmp_path, require_current=lambda: None
    )
    sidecar = tmp_path / "authority.current.json.lock"
    assert sidecar.is_file(), "the publication lock sidecar was not retained"

    install_validated_authority_database(
        publishable_artifact("second"), destination=tmp_path, require_current=lambda: None
    )

    assert sidecar.is_file()
    assert sidecar.stat().st_size == 0, "the sidecar carries no ownership metadata"
