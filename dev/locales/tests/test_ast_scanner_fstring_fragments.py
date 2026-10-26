"""A translation-key kwarg holding an interpolating f-string declares no concrete key.

``translated_message=f"application.workflow.errors.resume_refused_{reason.value}"``
names a family of keys whose tail is computed. Its literal head is a fragment, so
enrolling it as a key reports a key no catalogue can carry and that parity then
lists as missing. The family is declared through the f-string registry instead.
A plain dotted literal under the same kwarg, and an f-string with nothing to
interpolate, still declare exactly the key they spell.
"""

from __future__ import annotations

import pathlib

import pytest

from .._ast_scanner import scan_source_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SOURCE = "\n".join(
    (
        "def refuse(reason):",
        '    raise WorkflowError(translated_message=f"application.workflow.errors.resume_refused_{reason.value}")',
        "",
        "def ambiguous():",
        '    raise WorkflowError(translated_message="application.workflow.errors.resume_ambiguous")',
        "",
        "def unchanged():",
        '    raise WorkflowError(translated_message=f"application.workflow.errors.resume_unchanged")',
        "",
    )
)


def _scan(tmp_path: pathlib.Path) -> set[str]:
    (tmp_path / "workflow.py").write_text(_SOURCE, encoding="utf-8")
    return scan_source_tree(tmp_path)


def test_an_interpolating_fstring_fragment_is_not_collected(tmp_path: pathlib.Path) -> None:
    keys = _scan(tmp_path)

    assert "application.workflow.errors.resume_refused_" not in keys
    assert not any(key.startswith("application.workflow.errors.resume_refused") for key in keys)


def test_a_plain_dotted_literal_under_the_same_kwarg_is_collected(tmp_path: pathlib.Path) -> None:
    assert "application.workflow.errors.resume_ambiguous" in _scan(tmp_path)


def test_an_fstring_without_interpolation_is_collected_as_the_key_it_spells(tmp_path: pathlib.Path) -> None:
    assert "application.workflow.errors.resume_unchanged" in _scan(tmp_path)
