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

from ..record_design_labels import design_slot_name, read_record_design
from ..rename_formula_binding_identifiers import (
    ChainedRenameMapError,
    ReferenceOutsideEditionError,
    UnownedFragmentDirectoryError,
    _selector,
    apply_span_strip,
    plan_span_strip,
    references_outside_rewritten_editions,
    remove_emptied_fragment_directories,
    rewrite_identifier_references,
    unreadable_selectors,
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


def test_a_sibling_edition_declaring_the_target_name_is_not_disturbed(tmp_path: Path) -> None:
    """The rewrite is scoped to the declaring edition, so a sibling's spelling is its own business.

    The same binding id is declared in both editions. In 2024 its provider proves
    the address and the strip is planned; in 2025 the provider sits elsewhere, and
    2025 separately declares the stripped name already. A corpus-wide textual
    rewrite would rename the id in BOTH editions and leave 2025 with two bindings
    sharing one name -- the hazard this suite used to assert. The rewrite is now
    edition-scoped, which is what lets two editions mean different things by one
    spelling, so 2024 is renamed and 2025 is left exactly as authored.
    """
    _seed_edition(tmp_path, "2024", _binding("2024", "modelo-131.page1.109-112.epigrafe", offset=109, length=4))
    sibling = _seed_edition(
        tmp_path,
        "2025",
        _binding("2025", "modelo-131.page1.109-112.epigrafe", offset=200, length=4)
        + _binding("2025", "modelo-131.page1.epigrafe", offset=300, length=4),
    )
    before = (sibling / "bindings" / "0001-bindings.toml").read_text(encoding="utf-8")

    plan = plan_span_strip(MODELO, modelos_root=tmp_path)
    apply_span_strip(plan, modelos_root=tmp_path, mappings_root=tmp_path / "absent")

    assert plan.renames_by_edition == {"2024": {"modelo-131.page1.109-112.epigrafe": "modelo-131.page1.epigrafe"}}
    assert not plan.collisions
    # The sibling edition is untouched: both of its declarations still stand.
    assert (sibling / "bindings" / "0001-bindings.toml").read_text(encoding="utf-8") == before


def test_an_edition_scoped_rewrite_refuses_when_an_occurrence_sits_outside_the_modelo(tmp_path: Path) -> None:
    """Detector teeth: scoping is correct only while this modelo's editions hold every occurrence.

    ANOTHER modelo's construct quotes the id. That reference resolves against
    the declaring revision, so renaming inside modelo 131 would leave it
    pointing at a declaration that no longer exists. A sibling EDITION of the
    same modelo is a different matter and is allowed -- it is its own namespace,
    rewritten under its own map -- which is why the hazard is stated across
    modelos rather than across editions.
    """
    _seed_edition(tmp_path, "2024", _binding("2024", "modelo-131.page1.109-112.epigrafe", offset=109, length=4))
    _write(
        tmp_path / "200" / "revisions" / "2024" / "constructs" / "0001-constructs.toml",
        '[[revisions."2024".constructs]]\n'
        'id = "modelo-200.construct"\n'
        'binding_refs = ["modelo-131.page1.109-112.epigrafe"]\n',
    )
    plan = plan_span_strip(MODELO, modelos_root=tmp_path)

    with pytest.raises(ReferenceOutsideEditionError) as refusal:
        apply_span_strip(plan, modelos_root=tmp_path, mappings_root=tmp_path / "absent")

    assert "modelo-131.page1.109-112.epigrafe" in str(refusal.value)
    assert "0001-constructs.toml" in str(refusal.value)


def test_the_generated_address_map_is_never_rewritten(tmp_path: Path) -> None:
    """The map records OLD ids on purpose; rewriting it would erase the only record of them."""
    _seed_edition(tmp_path, "2024", _binding("2024", "modelo-131.page1.109-112.epigrafe", offset=109, length=4))
    generated = tmp_path / MODELO / "revisions" / "2025" / "714-binding-id-address-map.json"
    _write(generated, '{"bindings": [{"old_id": "modelo-131.page1.109-112.epigrafe"}]}\n')

    outside = references_outside_rewritten_editions(
        {"modelo-131.page1.109-112.epigrafe"}, MODELO, ["2024"], tmp_path, tmp_path / "absent", tmp_path
    )

    assert outside == {}


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

    # Both are withdrawn and named. Neither is more entitled to the surviving
    # spelling, and re-appending an offset to separate them is the restatement
    # the rule removes; the corpus keeps two names a reader can still tell apart.
    assert plan.rename_map == {}
    assert not plan.refused_modelo
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
    assert not plan.refused_modelo
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


def test_a_fragment_directory_this_pass_emptied_is_removed(tmp_path: Path) -> None:
    """The loader walks directories, so an empty family directory is a failed load, not silence."""
    modelo_dir = tmp_path / MODELO
    applicability = modelo_dir / "revisions" / "2024" / "applicability"
    fragment = applicability / "0001-applicability.toml"
    _write(fragment, "# removed by this pass\n")
    _write(modelo_dir / "revisions" / "2024" / "bindings" / "0001-bindings.toml", "# kept\n")
    fragment.unlink()

    removed = remove_emptied_fragment_directories(modelo_dir, removed_files={fragment})

    assert removed == [applicability]
    assert not applicability.exists()
    # The family that still declares something is untouched.
    assert (modelo_dir / "revisions" / "2024" / "bindings" / "0001-bindings.toml").is_file()


def test_an_empty_directory_this_pass_did_not_empty_is_left_in_place(tmp_path: Path) -> None:
    """Detector teeth: ownership is proven from this run's own removals, not from a version-control index.

    An empty directory nobody here emptied is the visible half of somebody
    else's change. Removing it would finish a change this tool cannot see the
    rest of, so it is reported instead -- and the proof needs no external tool,
    which is what makes it unfoolable by a staged or unstaged state.
    """
    modelo_dir = tmp_path / MODELO
    applicability = modelo_dir / "revisions" / "2024" / "applicability"
    applicability.mkdir(parents=True)

    with pytest.raises(UnownedFragmentDirectoryError) as refusal:
        remove_emptied_fragment_directories(modelo_dir, removed_files=set())

    assert refusal.value.directory == applicability
    assert applicability.is_dir()


def test_a_directory_emptied_by_another_path_is_not_claimed(tmp_path: Path) -> None:
    """A removal this pass DID make elsewhere does not license removing an unrelated directory."""
    modelo_dir = tmp_path / MODELO
    mine = modelo_dir / "revisions" / "2024" / "bindings" / "0001-bindings.toml"
    _write(mine, "# mine\n")
    mine.unlink()
    theirs = modelo_dir / "revisions" / "2024" / "applicability"
    theirs.mkdir(parents=True)

    with pytest.raises(UnownedFragmentDirectoryError) as refusal:
        remove_emptied_fragment_directories(modelo_dir, removed_files={mine})

    assert refusal.value.directory == theirs


def test_a_design_label_names_the_slot_the_offset_stood_in_for(tmp_path: Path) -> None:
    """The name an ingestion never recorded comes from the design, not from a derivation."""
    sidecar = tmp_path / "design.md"
    _write(
        sidecar,
        "# r1 Patrimonio\n"
        "N\u00ba | Posic. | Lon | Tipo | Comp | Descripci\u00f3n\n"
        "25 | 290 | 13 | Num | C | (1) Valores no exentos - N\u00ba Valores 3\n",
    )

    rows = read_record_design(sidecar)

    assert rows[("r1", 290)].length == 13
    assert design_slot_name(rows[("r1", 290)].label) == "valores-no-exentos-no-valores-3"


def test_a_design_label_keeps_the_percent_it_states(tmp_path: Path) -> None:
    """``% Titularidad 7`` and ``Titularidad 7`` are different fields and must stay different names."""
    sidecar = tmp_path / "design.md"
    _write(
        sidecar,
        "# r1 Patrimonio\n"
        "N\u00ba | Posic. | Lon | Tipo | Descripci\u00f3n\n"
        "1 | 10 | 5 | Num | % Titularidad 7\n"
        "2 | 20 | 5 | Num | Titularidad 7\n",
    )

    rows = read_record_design(sidecar)

    assert design_slot_name(rows[("r1", 10)].label) == "porcentaje-titularidad-7"
    assert design_slot_name(rows[("r1", 20)].label) == "titularidad-7"


def test_the_label_column_is_read_from_the_header_not_a_fixed_index(tmp_path: Path) -> None:
    """Detector teeth: two records in one design declare different column sets."""
    sidecar = tmp_path / "design.md"
    _write(
        sidecar,
        "# r0 Patrimonio\n"
        "N\u00ba | Posic. | Long. | Tipo | Descripci\u00f3n\n"
        "1 | 1 | 17 | An | Constante de cabecera\n"
        "# r1 Patrimonio\n"
        "N\u00ba | Posic. | Lon | Tipo | Comp | Descripci\u00f3n\n"
        "1 | 1 | 2 | An | C | Inicio del identificador\n",
    )

    rows = read_record_design(sidecar)

    # A fixed index would have read "An" or "C" as the label for one of these.
    assert rows[("r0", 1)].label == "Constante de cabecera"
    assert rows[("r1", 1)].label == "Inicio del identificador"


def test_the_strict_decode_is_what_keeps_the_ordinal_mark_intact(tmp_path: Path) -> None:
    """Detector teeth for the encoding: the same bytes read as Latin-1 name the slot wrongly.

    A tolerant or wrong decode does not raise here -- it yields ``nao-valores-3``
    where the design says ``No Valores 3``, which is a plausible-looking name for
    a field that does not exist. The reader states UTF-8 once; this proves the
    statement is doing work.
    """
    sidecar = tmp_path / "design.md"
    _write(
        sidecar,
        "# r1 Patrimonio\nNº | Posic. | Lon | Tipo | Descripción\n1 | 290 | 13 | Num | Nº Valores 3\n",
    )

    correct = design_slot_name(read_record_design(sidecar)[("r1", 290)].label)
    mis_decoded = design_slot_name(sidecar.read_bytes().decode("latin-1").splitlines()[-1].split("|")[-1].strip())

    assert correct == "no-valores-3"
    assert mis_decoded != correct


# ---------------------------------------------------------------------------
# Reading the declared period selector
# ---------------------------------------------------------------------------


def test_a_selector_declaring_period_overrides_is_typed(tmp_path: Path) -> None:
    """The retype reaches the arrays nested inside ``period_overrides``.

    Each override is an inline table carrying its own ``periods`` array, so a
    retype that stops at the outermost array leaves a ``list`` where the model
    declares a tuple, strict validation refuses it, and the whole edition reads
    as an unreadable selector -- which silently narrows the year set the caller
    reports.
    """
    edition_dir = tmp_path / MODELO / "revisions" / "2025"
    _write(
        edition_dir / "revision.toml",
        '[revisions."2025"]\n'
        "valid_from = 2025-01-01\n"
        '[revisions."2025".period_selector]\n'
        "year_from = 2025\n"
        'periods = ["01", "02", "03"]\n'
        'period_overrides = [{ year = 2026, periods = ["02", "03"] }]\n',
    )

    selector = _selector(edition_dir)

    assert selector is not None
    assert selector.periods == ("01", "02", "03")
    assert selector.periods_for_year(2026) == ("02", "03")
    assert selector.periods_for_year(2025) == ("01", "02", "03")
    assert unreadable_selectors(tmp_path / MODELO) == ()


def test_a_selector_without_overrides_is_typed_unchanged(tmp_path: Path) -> None:
    """The recursion leaves the override-free selector exactly as it read before."""
    edition_dir = tmp_path / MODELO / "revisions" / "2024"
    _write(
        edition_dir / "revision.toml",
        '[revisions."2024"]\n'
        "valid_from = 2024-01-01\n"
        '[revisions."2024".period_selector]\n'
        "year_from = 2024\n"
        'periods = ["1T"]\n',
    )

    selector = _selector(edition_dir)

    assert selector is not None
    assert selector.periods == ("1T",)
    assert selector.period_overrides == ()
    assert selector.periods_for_year(2026) == ("1T",)
