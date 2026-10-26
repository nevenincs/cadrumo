"""The repository-id shape rule refuses exactly empty, separator and dot-prefixed ids."""

from __future__ import annotations

import pytest

from ..repository_id import RepositoryIdViolation, repository_id_violation

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize(
    ("token", "expected"),
    (
        ("", RepositoryIdViolation.EMPTY),
        ("a/b", RepositoryIdViolation.SEPARATOR),
        ("a\\b", RepositoryIdViolation.SEPARATOR),
        ("/", RepositoryIdViolation.SEPARATOR),
        (".", RepositoryIdViolation.LEADING_DOT),
        ("..", RepositoryIdViolation.LEADING_DOT),
        (".hidden", RepositoryIdViolation.LEADING_DOT),
        ("./x", RepositoryIdViolation.SEPARATOR),
    ),
)
def test_refused_shapes_name_their_violation(token: str, expected: RepositoryIdViolation) -> None:
    assert repository_id_violation(token) is expected


@pytest.mark.parametrize("token", ("303", "2026:1T", "a.b", "name-with-dash", "C:x", "uuid-0000", "a "))
def test_admissible_shapes_pass(token: str) -> None:
    assert repository_id_violation(token) is None


def test_violation_values_are_the_stable_diagnostic_identifiers() -> None:
    assert {violation.value for violation in RepositoryIdViolation} == {
        "empty_repository_id",
        "repository_id_separator",
        "repository_id_dot_token",
    }
