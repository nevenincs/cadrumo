"""Proof that the probes answer correctly against the real index and forge.

The offline companion proves how an answer is READ. These cases prove the
questions are asked of the right places and understood: the index endpoint
returns 404 for a version nobody carries and 200 for one that exists, the forge
returns the tag and release rows this exemption rule was written for, and the
credential's reach is what decides whether draft releases are in the answer at
all.

They carry the repository's opt-in live marker because they read real external
services, so no offline lane selects them. Without them the shell's contract
with those services is asserted nowhere: a wrong endpoint, a wrong jq
expression, or a renamed field returns an empty tuple, which the guard reads as
"free" and the release proceeds.
"""

from __future__ import annotations

from typing import Final

import pytest

from ..version_identity import (
    VersionIdentityError,
    forge_push_access,
    forge_releases_owning,
    forge_tags_owning,
    pypi_projects_owning,
)

pytestmark = [pytest.mark.aeat_live, pytest.mark.hex_core]

#: This project's forge repository, and a repository the operator can read but
#: not push to, which is the difference draft visibility turns on.
_REPOSITORY: Final[str] = "nevenincs/cadrumo"
_FOREIGN_REPOSITORY: Final[str] = "cli/cli"

#: A released tag and the commit it sits on: immutable forge history, so the
#: exemption can be exercised against the rows it was written for.
_RELEASED: Final[str] = "0.4.0"
_RELEASED_COMMIT: Final[str] = "ec366a7e58d31d836da720126731b5430caea269"
_OTHER_COMMIT: Final[str] = "0" * 40

#: A version no project of this cohort will ever carry, and a third-party
#: release that will always exist because an index version is immutable.
_UNCARRIED: Final[str] = "9.9.9"
_CARRIED_ELSEWHERE: Final[tuple[str, str]] = ("packaging", "23.2")


def test_the_real_index_reports_an_uncarried_version_as_free() -> None:
    """The permit direction against the endpoint that actually answers.

    A probe that read every answer as "carried" -- a wrong endpoint, an
    inverted status comparison -- refuses every release, and a probe that read
    every answer as "free" refuses none. Only a real 404 separates them.
    """
    assert pypi_projects_owning(_UNCARRIED) == ()


def test_the_real_index_reports_a_published_version_as_carried() -> None:
    """The other direction, over a release the index will always hold."""
    project, version = _CARRIED_ELSEWHERE
    assert pypi_projects_owning(version, projects=[project]) == (project,)


def test_the_forge_returns_the_released_tag_and_exempts_only_its_own_commit() -> None:
    """The rows the exemption rule reads, from the namespace that holds them."""
    assert forge_tags_owning(_RELEASED, repository=_REPOSITORY, own_source_commit=_OTHER_COMMIT) == (
        f"v{_RELEASED}",
    )
    assert forge_tags_owning(_RELEASED, repository=_REPOSITORY, own_source_commit=_RELEASED_COMMIT) == ()


def test_the_forge_returns_the_released_release_and_exempts_only_its_own_commit() -> None:
    """The same rule over the release namespace, whose rows carry a target."""
    assert forge_releases_owning(_RELEASED, repository=_REPOSITORY, own_source_commit=_OTHER_COMMIT) == (
        f"v{_RELEASED}",
    )
    assert forge_releases_owning(_RELEASED, repository=_REPOSITORY, own_source_commit=_RELEASED_COMMIT) == ()


def test_an_uncut_version_owns_no_forge_ref() -> None:
    """The permit direction: an unreleased version collides with nothing."""
    assert forge_tags_owning(_UNCARRIED, repository=_REPOSITORY, own_source_commit=_RELEASED_COMMIT) == ()
    assert forge_releases_owning(_UNCARRIED, repository=_REPOSITORY, own_source_commit=_RELEASED_COMMIT) == ()


def test_a_forge_that_cannot_answer_refuses_rather_than_reporting_no_refs() -> None:
    """An unanswerable question is not the answer "nothing owns this".

    A repository nobody can read returns an error, and reading that as an empty
    namespace would clear both forge rules at once.
    """
    with pytest.raises(VersionIdentityError, match="forge check failed"):
        forge_tags_owning(_RELEASED, repository="nevenincs/no-such-repository-exists-here", own_source_commit=_OTHER_COMMIT)


def test_draft_visibility_follows_push_access() -> None:
    """The forge lists drafts only to a caller with push access.

    Both directions from one credential: this repository, where the release
    namespace answer includes drafts, and a repository the same credential can
    only read, where it does not and the run has to say so.
    """
    assert forge_push_access(_REPOSITORY) is True
    assert forge_push_access(_FOREIGN_REPOSITORY) is False
