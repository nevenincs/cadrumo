"""The drift report tells a revision RENAME apart from real additions and removals.

A rename puts the same string in both halves of the drift report, hundreds of
lines apart, and the report used to describe it as an unrelated key to write
plus an unrelated key to prune. Following that instruction destroys four
authored translations and reserves a slot the honesty ratchet then refuses.

These cases pin the reading that avoids it, at both levels: the classifier that
recognises the pair, and the rendered report an operator actually reads.
"""

from __future__ import annotations

import pytest

from dev.locales import classify_revision_moves
from dev.locales.cli import _echo_file_audit
from dev.locales.manager import _audit_locale_file

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_OLD = "modelo.schema.347.revision.2008-2024.casilla.01"
_NEW = "modelo.schema.347.revision.2011-2024.casilla.01"


def test_a_rename_is_one_move_carrying_both_halves_of_the_drift() -> None:
    """A missing key and an extra key differing only in revision are one move."""
    report = classify_revision_moves("es.yml", [f"{_NEW}.label", f"{_NEW}.help"], [f"{_OLD}.label", f"{_OLD}.help"])

    (candidate,) = report.candidates
    assert candidate.modelo == "347"
    assert candidate.source_revision == "2008-2024"
    assert candidate.destination_revisions == ("2011-2024",)
    assert candidate.key_count == 2
    assert candidate.invocation == "python -m dev.locales move-revision 347 2008-2024 2011-2024"
    assert report.accounted_missing == {f"{_NEW}.label", f"{_NEW}.help"}
    assert report.accounted_extra == {f"{_OLD}.label", f"{_OLD}.help"}


def test_a_split_is_one_move_naming_every_destination_revision() -> None:
    """One source revision feeding two new ones renders as a single invocation."""
    source = "modelo.schema.322.revision.2008-2023.casilla"
    report = classify_revision_moves(
        "es.yml",
        [
            "modelo.schema.322.revision.2023.casilla.01.label",
            "modelo.schema.322.revision.2008-2022.casilla.02.label",
        ],
        [f"{source}.01.label", f"{source}.02.label"],
    )

    (candidate,) = report.candidates
    assert candidate.destination_revisions == ("2008-2022", "2023")
    assert candidate.invocation == "python -m dev.locales move-revision 322 2008-2023 2008-2022 2023"
    assert "split" in candidate.render()


def test_genuine_additions_and_removals_are_not_read_as_a_move() -> None:
    """Only keys agreeing on modelo and on everything after the revision pair up.

    Without this the reading would be worse than the report it replaces: an
    operator told to relocate an unrelated key would move authored prose under
    a casilla that never had it.
    """
    report = classify_revision_moves(
        "es.yml",
        [
            "modelo.schema.347.revision.2011-2024.casilla.99.label",
            "modelo.schema.303.revision.2023.casilla.01.label",
            "cli.config.profile.help",
        ],
        [
            "modelo.schema.347.revision.2008-2024.casilla.01.label",
            "cli.config.retired.help",
        ],
    )

    assert report.candidates == ()
    assert not report.accounted_missing
    assert not report.accounted_extra


def test_the_rendered_report_prints_the_move_once_instead_of_two_key_rows(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The operator reads one relocation row, not the same key twice as unrelated work."""
    codebase_keys = {f"{_NEW}.label", "cli.config.profile.help"}
    catalogue_keys = {f"{_OLD}.label", "cli.config.retired.help"}
    file_result = _audit_locale_file(
        "es.yml",
        dict.fromkeys(catalogue_keys, "value"),
        set(catalogue_keys),
        codebase_keys=codebase_keys,
        all_locale_keys=set(catalogue_keys),
        namespace_prefixes=(),
    )

    _echo_file_audit(file_result)
    printed = capsys.readouterr().out

    assert "moves=1" in printed
    assert "run: python -m dev.locales move-revision 347 2008-2024 2011-2024" in printed
    assert f"  missing {_NEW}.label" not in printed
    assert f"  extra {_OLD}.label" not in printed
    assert "  missing cli.config.profile.help" in printed
    assert "  extra cli.config.retired.help" in printed


def test_a_rename_still_leaves_the_catalogue_not_ok() -> None:
    """Recognising a move never excuses it: the catalogue stays red until it lands.

    The move rows are a READING of the drift, and a reading that flipped the
    verdict to green would retire the only signal that the keys have not been
    carried yet.
    """
    file_result = _audit_locale_file(
        "es.yml",
        {f"{_OLD}.label": "value"},
        {f"{_OLD}.label"},
        codebase_keys={f"{_NEW}.label"},
        all_locale_keys={f"{_OLD}.label"},
        namespace_prefixes=(),
    )

    assert file_result.revision_moves
    assert not file_result.ok
    assert file_result.codebase_missing == (f"{_NEW}.label",)
    assert file_result.codebase_extra == (f"{_OLD}.label",)
