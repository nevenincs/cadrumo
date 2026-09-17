"""Real-behaviour tests for the SIGNO sign-position coverage screen.

The text reader and the field join are exercised on inputs whose answer is
known, then the screen runs over the compiled registry so its findings are
checked against the contract every screen finding keeps.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority

from ..analysis.sign_position_coverage import (
    UndeclaredSignPosition,
    screen_authority,
    sign_positions_in_design_text,
    undeclared_sign_positions,
)
from ..compiler.authority import compiled_bundled_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def authority() -> ValidatedRegistryAuthority:
    return compiled_bundled_authority()


def test_design_text_yields_each_printed_signo_position() -> None:
    """Both printed spellings count; a position inside a printed range does not."""
    text = "145 SIGNO: campo alfabetico\n176. SIGNO: campo alfabetico\n200-210 SIGNO del importe"

    assert sign_positions_in_design_text(text) == frozenset({145, 176})


def test_only_an_undeclared_money_field_on_a_signo_position_is_reported() -> None:
    """The detector: a money field starting on the SIGNO byte without sign_position."""
    fields = (
        ("undeclared-money", 145, "money", None),
        ("declared-money", 145, "money", "blank_or_n"),
        ("text-on-signo", 145, "text", None),
        ("money-elsewhere", 150, "money", None),
    )

    assert undeclared_sign_positions(fields, frozenset({145})) == [("undeclared-money", 145)]


def test_the_screen_reports_findings_that_name_their_modelo_and_revision(
    authority: ValidatedRegistryAuthority,
) -> None:
    findings = screen_authority(authority)

    assert all(isinstance(finding, UndeclaredSignPosition) for finding in findings)
    for finding in findings:
        assert finding.revision in authority.modelo(finding.modelo).revisions
        assert finding.subject == f"{finding.modelo}/{finding.revision}"
