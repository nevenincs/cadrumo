"""Casilla fragment filenames must tell the truth about their content.

Every fragment under ``modelos/<m>/revisions/<r>/casillas/`` is named
``<ordinal>-c<first>[__c<last>].toml``: a zero-padded merge ordinal (the
position the loader's sorted walk assigns the file), a ``-``, then the declared
casilla span with an explicit ``c`` prefix per id. The prefix is load-bearing:
without it a name like ``0469-0529.toml`` reads as a casilla range while the
leading token is actually a merge ordinal that can collide with a *different*
fragment's casilla id — the historical corpus carried ~10,800 such misleading
names across six coexisting conventions. Windows forbids ``:`` in filenames, so
``+`` stands in for ``:`` inside an id (``DP200014B:00592`` files as
``cDP200014B+00592``); ``+`` occurs in no casilla id, so the mapping is
unambiguous and reversible.

The gate re-derives the expected name for every fragment from its parsed
content and merge position, so a renamed casilla, a re-fragmented file, or a
new revision landing with an ad-hoc name fails loudly with the exact expected
name in the message. Cross-revision stem stability is intentionally NOT
enforced: the ordinal tracks merge position by design, and stabilising stems
across revisions is a separate, order-affecting decision.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

from .....core.resources import bundled_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")

_CANONICAL = re.compile(r"^(?P<ordinal>\d{4,})-c(?P<body>.+)$")
_SPAN_JOIN = "__c"
_FILENAME_SUBSTITUTIONS = {":": "+"}

# The corpus this gate protects is large; a walk that suddenly finds far fewer
# fragments means the gate is looking at the wrong tree, not that the tree is
# clean. Floors are deliberately far below the real counts (12,663 fragments in
# 90 directories at introduction) so ordinary growth or pruning never trips them.
_MIN_FRAGMENTS = 5_000
_MIN_DIRECTORIES = 40


def _sanitize(casilla_id: str) -> str:
    out = casilla_id
    for hostile, safe in _FILENAME_SUBSTITUTIONS.items():
        out = out.replace(hostile, safe)
    return out


def _declared_ids(path: Path) -> list[str]:
    """Casilla ids declared by one fragment, in declaration (merge) order."""
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    ids: list[str] = []
    revisions = data.get("revisions")
    if not isinstance(revisions, dict):
        return ids
    for _, body in sorted(revisions.items()):
        if not isinstance(body, dict):
            continue
        entries = body.get("casillas")
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, dict) and entry.get("id") is not None:
                ids.append(str(entry["id"]))
    return ids


def _expected_stem(ordinal: int, width: int, declared: list[str]) -> str:
    first = _sanitize(declared[0])
    last = _sanitize(declared[-1])
    body = f"c{first}" if len(declared) == 1 or first == last else f"c{first}__c{last}"
    return f"{ordinal:0{width}d}-{body}"


def _naming_violations(root: Path) -> tuple[list[str], int, int]:
    """Scan every casillas fragment directory; return (violations, files, dirs)."""
    violations: list[str] = []
    total_files = 0
    directories = 0
    for directory in sorted((root / "modelos").glob("*/revisions/*/casillas")):
        if not directory.is_dir():
            continue
        directories += 1
        files = sorted(directory.rglob("*.toml"))
        width = max(4, len(str(len(files))))
        seen_ordinals: set[int] = set()
        for position, path in enumerate(files, start=1):
            total_files += 1
            rel = path.relative_to(root).as_posix()
            declared = _declared_ids(path)
            if not declared and re.fullmatch(r"\d{4,}-casillas", path.stem):
                # The new-modelo scaffolder's sanctioned skeleton: an EMPTY
                # fragment may keep the placeholder name; authoring content
                # into it forces the canonical content-derived name below.
                continue
            match = _CANONICAL.match(path.stem)
            if match is None:
                hint = (
                    _expected_stem(position, width, declared) if declared else "<no casillas declared>"
                )
                violations.append(f"{rel}: not canonical; expected stem {hint!r}")
                continue
            ordinal = int(match.group("ordinal"))
            if ordinal in seen_ordinals:
                violations.append(f"{rel}: duplicate merge ordinal {ordinal}")
            seen_ordinals.add(ordinal)
            if not declared:
                violations.append(f"{rel}: canonical name but the file declares no casillas")
                continue
            expected = _expected_stem(ordinal, len(match.group("ordinal")), declared)
            if path.stem != expected:
                violations.append(f"{rel}: name/content mismatch; expected stem {expected!r}")
            if ordinal != position:
                violations.append(
                    f"{rel}: ordinal {ordinal} is not this fragment's merge position {position}"
                )
    return violations, total_files, directories


def test_every_casilla_fragment_name_is_canonical_and_truthful() -> None:
    violations, total_files, directories = _naming_violations(_REGISTRY_ROOT)
    assert total_files >= _MIN_FRAGMENTS and directories >= _MIN_DIRECTORIES, (
        f"gate scanned only {total_files} fragments in {directories} directories; "
        f"the walk no longer covers the corpus, so a green result would be vacuous"
    )
    assert not violations, (
        f"{len(violations)} casilla fragment naming violation(s); rename the file to the "
        f"expected stem (or fix its content) so the name keeps telling the truth:\n"
        + "\n".join(violations[:20])
    )


def _write_fragment(directory: Path, name: str, casilla_ids: list[str]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    blocks = "\n\n".join(
        f'[[revisions."2024".casillas]]\nid = "{cid}"\nlabel = "x"' for cid in casilla_ids
    )
    (directory / name).write_text(blocks + "\n", encoding="utf-8")


def test_gate_fires_on_each_violation_class(tmp_path: Path) -> None:
    """Positive controls: a gate that has never fired cannot be trusted green."""
    casillas = tmp_path / "modelos" / "999" / "revisions" / "2024" / "casillas"

    _write_fragment(casillas, "0001-0002.toml", ["0002"])  # pre-convention name
    violations, *_ = _naming_violations(tmp_path)
    assert any("not canonical" in v and "'0001-c0002'" in v for v in violations)

    (casillas / "0001-0002.toml").rename(casillas / "0001-c0002.toml")
    violations, *_ = _naming_violations(tmp_path)
    assert not violations

    _write_fragment(casillas, "0002-c9999.toml", ["0003"])  # name lies about content
    violations, *_ = _naming_violations(tmp_path)
    assert any("name/content mismatch" in v for v in violations)

    (casillas / "0002-c9999.toml").rename(casillas / "0003-c0003.toml")  # wrong position
    violations, *_ = _naming_violations(tmp_path)
    assert any("not this fragment's merge position" in v for v in violations)


def test_scaffold_skeleton_is_tolerated_only_while_empty(tmp_path: Path) -> None:
    """The new-modelo scaffolder's empty placeholder keeps its name; content
    landing in it immediately forces the canonical content-derived name."""
    casillas = tmp_path / "modelos" / "999" / "revisions" / "2024" / "casillas"
    casillas.mkdir(parents=True)
    (casillas / "0001-casillas.toml").write_text("# scaffolded skeleton\n", encoding="utf-8")
    violations, *_ = _naming_violations(tmp_path)
    assert not violations

    _write_fragment(casillas, "0001-casillas.toml", ["0007"])
    violations, *_ = _naming_violations(tmp_path)
    assert any("'0001-c0007'" in v for v in violations), violations


def test_colon_ids_round_trip_through_the_plus_substitution(tmp_path: Path) -> None:
    casillas = tmp_path / "modelos" / "200" / "revisions" / "2024" / "casillas"
    _write_fragment(casillas, "0001-cDP200014B+00592.toml", ["DP200014B:00592"])
    violations, *_ = _naming_violations(tmp_path)
    assert not violations
