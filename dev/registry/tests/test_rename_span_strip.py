"""Behaviour of the fixed-width span strip and the shared rewrite guards.

Every case builds an isolated temporary registry tree and writes only inside it,
so the contributor's working tree is never touched and the detector teeth are
proven against real fragments rather than against a patched module. The
fragments are authored here rather than copied wholesale, because what is under
test is the rule -- which binding ids restate their own provider address, and
which rewrites are refused outright -- and an authored fixture states each case
in one place a reader can check against the assertion.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..rename_formula_binding_identifiers import (
    ChainedRenameMapError,
    apply_span_strip,
    plan_span_strip,
    rewrite_identifier_references,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

MODELO = "131"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.lstrip("\n"), encoding="utf-8")


def _binding(edition: str, identifier: str, *, offset: int, length: int) -> str:
    return (
        f'[[revisions."{edition}".bindings]]\n'
        f'id = "{identifier}"\n'
        f'provider = {{ kind = "authored_layout", offset = {offset}, length = {length} }}\n\n'
    )


def _seed_edition(root: Path, edition: str, bindings: str) -> Path:
    edition_dir = root / MODELO / "revisions" / edition
    _write(edition_dir / "revision.toml", f'[revisions."{edition}"]\nvalid_from = 2024-01-01\n')
    _write(edition_dir / "bindings" / "0001-bindings.toml", bindings)
    return edition_dir


# ---------------------------------------------------------------------------
# The strip itself
# ---------------------------------------------------------------------------


def test_a_span_its_provider_declares_is_stripped(tmp_path: Path) -> None:
    """The id's copy of the address goes; the provider's typed copy stays."""
    _seed_edition(tmp_path, "2024", _binding("2024", "modelo-131.page1.109-112.epigrafe", offset=109, length=4))

    plan = plan_span_strip(MODELO, modelos_root=tmp_path)

    assert plan.rename_map == {"modelo-131.page1.109-112.epigrafe": "modelo-131.page1.epigrafe"}
    assert not plan.collisions
    assert not plan.refusals


def test_a_span_the_provider_does_not_declare_is_refused(tmp_path: Path) -> None:
    """A span-shaped run no provider proves may be a year range or a norm pair."""
    _seed_edition(tmp_path, "2024", _binding("2024", "modelo-131.page1.2019-2021.epigrafe", offset=109, length=4))

    plan = plan_span_strip(MODELO, modelos_root=tmp_path)

    assert plan.rename_map == {}
    assert plan.refusals


# ---------------------------------------------------------------------------
# The cross-edition post-image screen, shared with the family collapse
# ---------------------------------------------------------------------------


def test_a_strip_colliding_in_a_sibling_edition_is_refused(tmp_path: Path) -> None:
    """The rewrite is textual and corpus-wide, so a sibling edition can collide.

    The same binding id is declared in both editions. In 2024 its provider
    proves the address and the strip is planned; in 2025 the provider sits
    elsewhere, so that edition plans no strip of its own -- and 2025 separately
    declares the stripped name already. The 2025 gate therefore sees nothing: it
    projects only the strips 2025 itself planned, which is none. But the rewrite
    is textual, so applying 2024's strip renames the id in BOTH editions and
    leaves 2025 with two bindings sharing one name. Only the modelo's whole
    post-image shows it, which is exactly the projection the family collapse
    runs and the reason the two rules share one screen instead of two.
    """
    _seed_edition(tmp_path, "2024", _binding("2024", "modelo-131.page1.109-112.epigrafe", offset=109, length=4))
    _seed_edition(
        tmp_path,
        "2025",
        _binding("2025", "modelo-131.page1.109-112.epigrafe", offset=200, length=4)
        + _binding("2025", "modelo-131.page1.epigrafe", offset=300, length=4),
    )

    plan = plan_span_strip(MODELO, modelos_root=tmp_path)

    assert plan.rename_map == {}
    assert plan.collisions
    assert any("modelo-131.page1.epigrafe" in collision for collision in plan.collisions)


def test_a_strip_with_no_sibling_conflict_survives_the_screen(tmp_path: Path) -> None:
    """The screen withdraws colliding renames only, and leaves the rest standing.

    Stated separately so a screen that withdrew everything -- which would also
    make the case above pass -- is caught.
    """
    _seed_edition(tmp_path, "2024", _binding("2024", "modelo-131.page1.109-112.epigrafe", offset=109, length=4))
    _seed_edition(tmp_path, "2025", _binding("2025", "modelo-131.page1.200-203.otro", offset=200, length=4))

    plan = plan_span_strip(MODELO, modelos_root=tmp_path)

    assert plan.rename_map == {
        "modelo-131.page1.109-112.epigrafe": "modelo-131.page1.epigrafe",
        "modelo-131.page1.200-203.otro": "modelo-131.page1.otro",
    }
    assert not plan.collisions


def test_the_surviving_strip_is_applied_to_the_authored_fragment(tmp_path: Path) -> None:
    """End to end: the plan that passes the screen rewrites the declaration."""
    edition_dir = _seed_edition(
        tmp_path, "2024", _binding("2024", "modelo-131.page1.109-112.epigrafe", offset=109, length=4)
    )

    plan = plan_span_strip(MODELO, modelos_root=tmp_path)
    touched, hits = apply_span_strip(plan, modelos_root=tmp_path, mappings_root=tmp_path / "absent", code_files=())

    text = (edition_dir / "bindings" / "0001-bindings.toml").read_text(encoding="utf-8")
    assert 'id = "modelo-131.page1.epigrafe"' in text
    assert "109-112" not in text
    assert hits == 1
    assert len(touched) == 1


# ---------------------------------------------------------------------------
# The chained-map refusal in the shared rewrite
# ---------------------------------------------------------------------------


def test_a_chained_rename_map_is_refused_before_anything_is_written(tmp_path: Path) -> None:
    """``a -> b`` beside ``b -> c`` has no single-pass answer, so it is refused.

    The rewrite makes ONE textual pass per file and applies the pairs
    longest-source-first, so ``a`` would reach ``c`` or stop at ``b`` depending
    on which pair the pass happened to apply first. Silently picking one is a
    corpus-wide rename decided by sort order; the caller composes the map
    instead.
    """
    edition_dir = _seed_edition(tmp_path, "2024", _binding("2024", "modelo-131.page1.alpha", offset=1, length=4))
    fragment = edition_dir / "bindings" / "0001-bindings.toml"
    before = fragment.read_text(encoding="utf-8")

    with pytest.raises(ChainedRenameMapError) as refusal:
        rewrite_identifier_references(
            {"modelo-131.page1.alpha": "modelo-131.page1.beta", "modelo-131.page1.beta": "modelo-131.page1.gamma"},
            tmp_path,
            tmp_path / "absent",
            code_files=(),
        )

    assert "modelo-131.page1.beta" in str(refusal.value)
    assert "modelo-131.page1.gamma" in str(refusal.value)
    # Refused before the pass, so not one file was half rewritten.
    assert fragment.read_text(encoding="utf-8") == before


def test_an_unchained_map_still_rewrites(tmp_path: Path) -> None:
    """The guard refuses chains, not every map with more than one pair."""
    edition_dir = _seed_edition(
        tmp_path,
        "2024",
        _binding("2024", "modelo-131.page1.alpha", offset=1, length=4)
        + _binding("2024", "modelo-131.page1.beta", offset=5, length=4),
    )

    touched, hits = rewrite_identifier_references(
        {"modelo-131.page1.alpha": "modelo-131.page1.uno", "modelo-131.page1.beta": "modelo-131.page1.dos"},
        tmp_path,
        tmp_path / "absent",
        code_files=(),
    )

    text = (edition_dir / "bindings" / "0001-bindings.toml").read_text(encoding="utf-8")
    assert 'id = "modelo-131.page1.uno"' in text
    assert 'id = "modelo-131.page1.dos"' in text
    assert hits == 2
    assert len(touched) == 1
