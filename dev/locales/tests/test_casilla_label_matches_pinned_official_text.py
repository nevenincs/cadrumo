"""Every shipped casilla label an adjudication pinned must BE the pinned text.

The M200/2024 adjudication authorities each carry `official_label_sha256`: the
digest of the exact record-design cell that names the box. That digest is what
makes a label grounded rather than plausible -- a label can be written from the
right section, in the right house style, and still be the wrong box's text, and
nothing about reading it would say so.

Casilla numbers are REUSED across record pages in Modelo 200 (00066 is "Entidad
patrimonial" on one page and an AIE/UTE deduction base on another), so picking
the text by searching for the number is exactly the mistake available here.
Matching the digest picks the cell the adjudication actually settled on.

The pins are read from the COMPILED authorities, not from their TOML. That is
the difference between checking a declaration and checking behaviour: the
unique-cohort ledger does not serialise the field at all -- its compiler derives
the digest from the record-design intermediate and the semantic map at compile
time -- so a gate reading raw TOML would have found nothing to assert for that
whole cohort and reported itself green.
"""

from __future__ import annotations

import hashlib
import re

import pytest
import yaml

from ..._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_CATALOGUE = REPO_ROOT / "src" / "cadrumo" / "locales" / "es" / "modelo" / "schema" / "200.yml"


def _pinned_digests() -> dict[str, str]:
    """Compile every M200/2024 adjudication authority and take its pins."""
    from ...registry.analysis.m200_2024_blocker_adjudications import compile_m200_2024_blocker_authority
    from ...registry.analysis.m200_2024_page_resolved_adjudications import (
        compile_m200_2024_page_resolved_authority,
    )
    from ...registry.analysis.m200_2024_template_adjudications import compile_m200_2024_same_template_authority
    from ...registry.analysis.m200_2024_unique_adjudications import compile_m200_2024_unique_authority

    pinned: dict[str, str] = {}
    for compile_authority in (
        compile_m200_2024_blocker_authority,
        compile_m200_2024_same_template_authority,
        compile_m200_2024_unique_authority,
        compile_m200_2024_page_resolved_authority,
    ):
        for row in compile_authority().adjudications:
            if row.official_label_sha256:
                pinned.setdefault(row.casilla_id, row.official_label_sha256)
    return pinned


def _shipped_labels() -> dict[str, str]:
    catalogue = yaml.safe_load(_CATALOGUE.read_text(encoding="utf-8"))
    revision = catalogue["modelo"]["schema"]["200"]["revision"]["2024"]["casilla"]
    return {casilla: entry["label"] for casilla, entry in revision.items() if entry.get("label")}


def _digest(text: str) -> str:
    """Digest a label's words, not the whitespace the extraction happened to keep.

    A record-design cell long enough to wrap carries a newline inside it, and
    the pin is the digest of that raw form. A shipped label must not: an
    operator reads one line, so the catalogue holds the collapsed form. Hashing
    both sides after collapsing runs of whitespace means a line wrap is not
    mistaken for different text, while every difference that is actually a
    difference still shows -- which is the property the pin exists for, and the
    reason this normalises whitespace ONLY.
    """
    return hashlib.sha256(re.sub(r"\s+", " ", text).strip().encode("utf-8")).hexdigest()


def _official_preimages() -> dict[str, str]:
    """The official text behind a pin, where an authority still holds it.

    Only the blocker cohort keeps its worklist text; the others carry the digest
    alone. That is enough, because the wrapped cells all live in that cohort --
    and where no preimage is available the comparison stays the strict digest,
    so this widens nothing it does not have evidence for.
    """
    from ...registry.analysis.m200_2024_blocker_adjudications import build_worklist

    worklist = build_worklist()
    return {
        str(row["casilla_id"]): str(row["official_description"])
        for row in worklist.get("member", ())
        if isinstance(row, dict) and row.get("official_description")
    }


def test_the_shipped_spanish_label_is_the_pinned_official_cell() -> None:
    """A pinned label ships verbatim, or the pin is not what shipped.

    Silent about casillas no authority pinned. Those are grounded some other
    way or not yet grounded at all, and passing them here on a guess is the
    wrong-box error this exists to prevent -- so they are not claimed either
    way.
    """
    shipped = _shipped_labels()
    officials = _official_preimages()
    covered = 0
    wrong: list[str] = []
    for casilla, digest in _pinned_digests().items():
        label = shipped.get(casilla)
        if label is None:
            continue
        covered += 1
        preimage = officials.get(casilla)
        matches = hashlib.sha256(label.encode("utf-8")).hexdigest() == digest or (
            preimage is not None and _digest(label) == _digest(preimage)
        )
        if not matches:
            wrong.append(f"{casilla}: shipped {label!r} does not match its pinned official label")

    assert covered, "no pinned label reached the catalogue, so this proved nothing"
    assert not wrong, "\n".join(wrong)


# A SECOND GATE WAS TRIED HERE AND WITHDRAWN, which is worth recording because
# the idea will occur again. It asserted that where a casilla number appears
# exactly once in the record design, the shipped label IS that cell -- the rule
# used to ground the casillas that carry no adjudication.
#
# The corpus does not follow that rule. Of 2480 uniquely-occurring labelled
# casillas: 1779 match the design cell exactly, 67 differ only in whitespace,
# 381 are ellipsis-truncated, and 253 are deliberately shortened or reworded
# (00096 ships "Innovacion tecnologica (IT). Deduccion pendiente/generada" where
# the design reads "Deducc. para incentivar determ.actividades - 2024
# Innovacion tecnologica (IT) - Deduccion pendiente/generada").
#
# So the rule describes labels written under it, not a project invariant, and a
# gate asserting it would have failed on 701 labels nobody has claimed are
# wrong. The pin stays the single grounding mechanism: it is an explicit
# per-casilla commitment rather than a derivation, which is why it can be
# asserted without contradicting the corpus around it.
