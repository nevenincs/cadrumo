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
    DirtyFragmentDirectoryError,
    apply_span_strip,
    plan_span_strip,
    remove_emptied_fragment_directories,
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


# ---------------------------------------------------------------------------
# No id may carry its provider offset in ANY spelling
# ---------------------------------------------------------------------------


def _addressed_binding(edition: str, identifier: str, *, offset: int, length: int, field: str) -> str:
    """A binding whose provider states a record, a field name and an address."""
    return (
        f'[[revisions."{edition}".bindings]]\n'
        f'id = "{identifier}"\n'
        f'provider = {{ kind = "manual_input", record = "r1", field = "{field}", '
        f"offset = {offset}, length = {length} }}\n\n"
    )


def test_a_trailing_bare_offset_is_dropped_without_any_span_run(tmp_path: Path) -> None:
    """The rule is the address, not the ``<from>-<to>`` shape it is sometimes spelled in."""
    _seed_edition(
        tmp_path,
        "2024",
        _addressed_binding("2024", "modelo-131.r1.saldo-290", offset=290, length=13, field="saldo-290"),
    )

    plan = plan_span_strip(MODELO, modelos_root=tmp_path)

    assert plan.rename_map == {"modelo-131.r1.saldo-290": "modelo-131.r1.saldo"}
    assert not plan.collisions


def test_a_restored_field_that_re_states_the_offset_is_stripped_again(tmp_path: Path) -> None:
    """Restoring the whole field puts the address back; the tail drop takes it off again.

    This is the defect the rule closes: the id spelled its span AND a truncated
    slot, the slot was restored from ``provider.field``, and that field itself
    ends in the offset -- so the address survived the strip under a second
    spelling.
    """
    _seed_edition(
        tmp_path,
        "2024",
        _addressed_binding(
            "2024",
            "modelo-131.r1.290-302.saldo",
            offset=290,
            length=13,
            field="saldo-medio-290",
        ),
    )

    plan = plan_span_strip(MODELO, modelos_root=tmp_path)

    assert plan.rename_map == {"modelo-131.r1.290-302.saldo": "modelo-131.r1.saldo-medio"}


def test_a_trailing_number_that_is_not_the_offset_stays(tmp_path: Path) -> None:
    """A repetition index and an address look identical; only the provider tells them apart."""
    _seed_edition(
        tmp_path,
        "2024",
        _addressed_binding("2024", "modelo-131.r1.epigrafe-1", offset=290, length=13, field="epigrafe-1"),
    )

    plan = plan_span_strip(MODELO, modelos_root=tmp_path)

    assert plan.rename_map == {}
    assert not plan.collisions


def test_two_slots_named_by_their_offsets_alone_refuse_the_whole_modelo(tmp_path: Path) -> None:
    """Detector teeth: an offset-only corpus collapses onto one name and is refused, not renumbered."""
    _seed_edition(
        tmp_path,
        "2024",
        _addressed_binding("2024", "modelo-131.r1.bloque-14", offset=14, length=1, field="bloque-14")
        + _addressed_binding("2024", "modelo-131.r1.bloque-15", offset=15, length=5, field="bloque-15"),
    )

    plan = plan_span_strip(MODELO, modelos_root=tmp_path)

    assert plan.rename_map == {}
    assert plan.refused_modelo
    collision = "".join(plan.collisions)
    assert "modelo-131.r1.bloque" in collision
    assert "modelo-131.r1.bloque-14" in collision
    assert "modelo-131.r1.bloque-15" in collision


def test_two_mid_word_truncated_slots_sharing_a_prefix_are_refused(tmp_path: Path) -> None:
    """Injectivity over the POST-image: two different labels truncated to one prefix collide.

    An id derived from a provider field truncated at a fixed width can land on
    the same spelling as a different label truncated the same way. The gate
    compares the whole post-strip namespace, so the pair is named rather than
    silently merged.
    """
    _seed_edition(
        tmp_path,
        "2024",
        _addressed_binding("2024", "modelo-131.r1.situado-en-el-termin-20", offset=20, length=4, field="x-20")
        + _addressed_binding("2024", "modelo-131.r1.situado-en-el-termin", offset=90, length=4, field="y"),
    )

    plan = plan_span_strip(MODELO, modelos_root=tmp_path)

    assert plan.rename_map == {}
    assert plan.refused_modelo
    assert any("modelo-131.r1.situado-en-el-termin" in collision for collision in plan.collisions)


def test_an_unexplained_span_run_does_not_veto_the_offset_tail_drop(tmp_path: Path) -> None:
    """The run stays and is reported; the address the provider DOES prove still goes.

    The two segments are judged separately because they are proven separately:
    a run the provider does not declare may be a page label or a year range, and
    letting it block a removal proven elsewhere in the same id would leave the
    row carrying its own address for an unrelated reason.
    """
    _seed_edition(
        tmp_path,
        "2024",
        _addressed_binding("2024", "modelo-131.131-02.saldo-290", offset=290, length=13, field="saldo-290"),
    )

    plan = plan_span_strip(MODELO, modelos_root=tmp_path)

    assert plan.rename_map == {"modelo-131.131-02.saldo-290": "modelo-131.131-02.saldo"}
    assert any("131-02" in refusal for refusal in plan.refusals)


# ---------------------------------------------------------------------------
# Emptied fragment directories
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> None:
    """Run one git command inside an isolated scratch repository."""
    import subprocess

    subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _scratch_repo(tmp_path: Path) -> Path:
    """An isolated git repository, so the contributor's own worktree is never consulted."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "test")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "-qm", "seed")
    return repo


def test_a_fragment_directory_the_pass_emptied_is_removed(tmp_path: Path) -> None:
    """The loader walks directories, so an empty family directory is a failed load, not silence."""
    repo = _scratch_repo(tmp_path)
    modelo_dir = repo / "modelos" / MODELO
    (modelo_dir / "revisions" / "2024" / "applicability").mkdir(parents=True)
    _write(modelo_dir / "revisions" / "2024" / "bindings" / "0001-bindings.toml", "# kept\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "corpus")

    removed = remove_emptied_fragment_directories(modelo_dir, repo_root=repo)

    assert removed == [modelo_dir / "revisions" / "2024" / "applicability"]
    assert not (modelo_dir / "revisions" / "2024" / "applicability").exists()
    # The family that still declares something is untouched.
    assert (modelo_dir / "revisions" / "2024" / "bindings" / "0001-bindings.toml").is_file()


def test_an_emptied_directory_carrying_pending_work_is_left_in_place(tmp_path: Path) -> None:
    """Detector teeth: a pending deletion under the directory is another contributor's change."""
    repo = _scratch_repo(tmp_path)
    modelo_dir = repo / "modelos" / MODELO
    applicability = modelo_dir / "revisions" / "2024" / "applicability"
    _write(applicability / "0001-applicability.toml", "# tracked\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "corpus")
    # Someone else's in-flight removal: tracked, deleted in the worktree, not committed.
    (applicability / "0001-applicability.toml").unlink()

    with pytest.raises(DirtyFragmentDirectoryError) as refusal:
        remove_emptied_fragment_directories(modelo_dir, repo_root=repo)

    assert refusal.value.directory == applicability
    assert applicability.is_dir()
