"""A governance stamp must be replaceable when the previous one spans several lines.

``reviewed_by`` carries a reviewer's scope statement, which grows long enough that it
is routinely authored as a TOML multi-line basic string. The manifest writer edits
whole ``key = value`` lines so a hand-authored file stays reviewable, and it once
assumed a scalar assignment is always ONE physical line. A triple-quoted value breaks
that assumption: removing only the line carrying the key orphans the prose and the
closing delimiter, and a reviewer note opening ``agent: ...`` then parses as a key
with a colon where an equals belongs.
"""

from __future__ import annotations

import shutil
import tomllib
from datetime import date
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path

from ..stamp import stamp_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_MODELO = "232"
_REVISION = "2018-y-siguientes"
_REVIEWED_BY_LINE = 'reviewed_by = "agent-prepared-pending-operator"\n'


def _copy_modelo(tmp_path: Path) -> Path:
    registry_root = tmp_path / "registry" / "aeat"
    shutil.copytree(
        bundled_path("registry", "aeat", "modelos", _MODELO),
        registry_root / "modelos" / _MODELO,
    )
    return registry_root


def _manifest_path(registry_root: Path) -> Path:
    return registry_root / "modelos" / _MODELO / "revisions" / _REVISION / "revision.toml"


def _prepared_registry(tmp_path: Path, reviewed_by_block: str, *, suffix: str = "") -> Path:
    registry_root = _copy_modelo(tmp_path)
    manifest = _manifest_path(registry_root)
    text = manifest.read_bytes().decode("utf-8")
    assert text.count(_REVIEWED_BY_LINE) == 1
    manifest.write_bytes(text.replace(_REVIEWED_BY_LINE, reviewed_by_block, 1).encode("utf-8"))
    if suffix:
        manifest.write_bytes(manifest.read_bytes() + suffix.encode("utf-8"))
    return registry_root


def _stamp_replacement(tmp_path: Path, reviewed_by_block: str, *, suffix: str = "") -> Path:
    registry_root = _prepared_registry(tmp_path, reviewed_by_block, suffix=suffix)
    result = stamp_revision(
        _MODELO,
        _REVISION,
        review_status="agent_reviewed",
        reviewed_by="agent: replacement",
        reviewed_at=date(2026, 8, 20),
        registry_root=registry_root,
    )
    return result.manifest


def test_a_multiline_reviewer_note_is_replaced_whole(tmp_path: Path) -> None:
    manifest = _stamp_replacement(
        tmp_path,
        'reviewed_by = """\nagent: first line; second clause\nand a third\n"""\n',
    )

    rewritten = manifest.read_bytes().decode("utf-8")
    parsed = tomllib.loads(rewritten)["revisions"][_REVISION]
    assert parsed["reviewed_by"] == "agent: replacement"
    # The orphan is what broke it: prose surviving with no key to belong to.
    assert "first line" not in rewritten
    assert "and a third" not in rewritten


def test_a_single_line_reviewer_note_is_still_replaced(tmp_path: Path) -> None:
    """The control. A fix that only handled the multi-line form would pass the test above."""
    manifest = _stamp_replacement(tmp_path, 'reviewed_by = "agent: one line"\n')
    rewritten = manifest.read_bytes().decode("utf-8")

    parsed = tomllib.loads(rewritten)["revisions"][_REVISION]
    assert parsed["reviewed_by"] == "agent: replacement"
    assert "one line" not in rewritten


def test_neighbouring_declarations_survive_the_removal(tmp_path: Path) -> None:
    """The span must stop at the closing delimiter, not run on into the rest of the table."""
    manifest = _stamp_replacement(tmp_path, 'reviewed_by = """\nagent: note\n"""\n')
    rewritten = manifest.read_bytes().decode("utf-8")

    parsed = tomllib.loads(rewritten)["revisions"][_REVISION]
    assert parsed["authority_grade"] == "applicability"
    assert "orden-hfp-816-2017:art-1" in parsed["legal_refs"]


def test_a_bracket_initial_prose_line_does_not_end_the_revision_table(tmp_path: Path) -> None:
    """A wrapped reviewer line starting with "[" is prose, not a table header.

    Modelo 840's reviewed_by cites AEAT box numbers, and the writer's wrap put
    ``[13]. VERIFIED -- ...`` at the start of a physical line. The table-end scan
    looked for the next line beginning with a bracket, took that prose line for a
    new TOML table, and truncated the revision table thirty lines early; the
    rebuild then emitted the remaining prose and the trailing declarations
    outside any table, so the manifest stopped parsing and the revision was
    unstampable while its neighbours stamped cleanly.
    """
    block = (
        'reviewed_by = """\n'
        "agent: coverage 0 -> 15 of 108. AEAT prints them as [14] at @270+4 and\n"
        "[13]. VERIFIED -- the wrap put a bracket at the start of this line\n"
        "and the scan must not read it as a table header.\n"
        '"""\n'
    )
    neighbour = f'\n[revisions."{_REVISION}".family_dispositions.formulas]\nreason = "unchanged neighbour"\n'

    manifest = _stamp_replacement(
        tmp_path,
        block,
        suffix=neighbour,
    )
    rewritten = manifest.read_bytes().decode("utf-8")

    parsed = tomllib.loads(rewritten)["revisions"][_REVISION]
    assert parsed["reviewed_by"] == "agent: replacement"
    # The whole prose span goes, including the bracket-initial line.
    assert "VERIFIED" not in rewritten
    assert "@270+4" not in rewritten
    # The real table that follows is untouched.
    assert parsed["family_dispositions"]["formulas"]["reason"] == "unchanged neighbour"
