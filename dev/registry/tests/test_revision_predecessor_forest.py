"""The predecessor forest rule over a modelo's editions.

Declared predecessor edges must form trees rooted at editions that either
declare no predecessor or, for exactly one edition, omit the key. Every planted
defect here is proven in both directions on the same tree: the plant refuses the
load, the repair loads, and re-planting refuses again, so no test can pass
because the fixture is broken in some unrelated way.

Tests drive the real directory loader over real on-disk TOML trees, call the
rule itself where a shape cannot reach it through the typed loader, and read the
shipped registry for the corpus properties.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryLoadError, RegistryValidationError
from cadrumo.domain.calculations.registry.revision_predecessor_forest import validate_predecessor_forest
from cadrumo.domain.calculations.registry.schema import DeclaredPredecessor, ModeloDefinition, NoPredecessor
from cadrumo.domain.calculations.registry.tests.registry_tree import bundled_registry_tree

from ..compiler.loader import load_modelo_directory
from ..conformance.loader_directory_mode_support import write_standard_manifest as _write_standard_manifest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_LEGAL_REF = "ley-58-2003:art-29"
_NONE = (
    'predecessor = { none = { reason = "Parallel scheme variant sharing one validity date.", '
    f'legal_refs = ["{_LEGAL_REF}"], source_refs = ["aeat-manual"] }} }}\n'
)
_PARALLEL_SCHEME_MODELO = "369"


@dataclass(frozen=True, slots=True)
class _Edition:
    revision_id: str
    year: int
    manifest_extra: str = ""
    fragment_extra: str = ""


def _names(target: str) -> str:
    return f'predecessor = "{target}"\n'


def _write_editions(root: Path, *editions: _Edition) -> Path:
    """Materialise modelo ``999`` with one fragmented directory per edition."""
    modelo_dir = root / "999"
    modelo_dir.mkdir(parents=True)
    _write_standard_manifest(modelo_dir, "Test")
    for edition in editions:
        _write_edition(modelo_dir, edition)
    return modelo_dir


def _write_edition(modelo_dir: Path, edition: _Edition) -> None:
    """Write one edition stating a single casilla keyed by its year.

    A distinct casilla per year keeps a successor's stated row from colliding
    with the row it inherits, so a declared edge materialises cleanly.
    """
    revision_dir = modelo_dir / "revisions" / edition.revision_id
    (revision_dir / "casillas").mkdir(parents=True, exist_ok=True)
    (revision_dir / "revision.toml").write_text(
        (
            f'[revisions."{edition.revision_id}"]\n'
            f"valid_from = {edition.year}-01-01\n"
            f"valid_to = {edition.year}-12-31\n"
            f'period_selector = {{ years = [{edition.year}], periods = ["0A"] }}\n'
            f'legal_refs = ["{_LEGAL_REF}"]\n'
            'source_refs = ["aeat-manual"]\n'
            f"{edition.manifest_extra}"
        ),
        encoding="utf-8",
        newline="\n",
    )
    (revision_dir / "casillas" / "0001-casillas.toml").write_text(
        (
            f'[[revisions."{edition.revision_id}".casillas]]\n'
            f'id = "{edition.year:04d}"\n'
            f'number = "{edition.year - 2000}"\n'
            'section = ["liquidacion"]\n'
            f'legal_refs = ["{_LEGAL_REF}"]\n'
            'source_refs = ["aeat-manual"]\n'
            f"{edition.fragment_extra}"
        ),
        encoding="utf-8",
        newline="\n",
    )


def _chain(third_extra: str, *, second_extra: str = _names("2024")) -> tuple[_Edition, ...]:
    """A 2024 first edition, a 2025 successor, and a 2026 edition under test."""
    return (
        _Edition("2024", 2024),
        _Edition("2025", 2025, manifest_extra=second_extra),
        _Edition("2026", 2026, manifest_extra=third_extra),
    )


def test_a_successor_omitting_the_key_is_a_second_root_naming_both(tmp_path: Path) -> None:
    """The silent case: a forgotten key on a successor refuses, naming both key-less editions."""
    two_roots = re.escape("has 2 editions omitting the predecessor key: '2024' and '2026'")
    modelo_dir = _write_editions(tmp_path, *_chain(""))

    with pytest.raises(RegistryLoadError, match=two_roots):
        load_modelo_directory(modelo_dir)

    _write_edition(modelo_dir, _Edition("2026", 2026, manifest_extra=_names("2025")))
    restored = load_modelo_directory(modelo_dir)
    assert restored.revisions["2026"].predecessor == DeclaredPredecessor(revision_id="2025")
    assert restored.revisions["2024"].predecessor is None

    _write_edition(modelo_dir, _Edition("2026", 2026))
    with pytest.raises(RegistryLoadError, match=two_roots):
        load_modelo_directory(modelo_dir)


def test_parallel_editions_each_declaring_no_predecessor_load_without_an_order(tmp_path: Path) -> None:
    """Explicit roots are a legal set of any size; only key-less roots are capped at one."""
    variants = ("esquema-a", "esquema-b", "esquema-c")
    modelo_dir = _write_editions(tmp_path, *(_Edition(variant, 2025, manifest_extra=_NONE) for variant in variants))

    parallel = load_modelo_directory(modelo_dir)
    assert len({revision.valid_from for revision in parallel.revisions.values()}) == 1
    assert all(isinstance(parallel.revisions[variant].predecessor, NoPredecessor) for variant in variants)

    # One key-less edition beside explicit roots is still the unique undeclared first edition.
    _write_edition(modelo_dir, _Edition("esquema-c", 2025))
    assert load_modelo_directory(modelo_dir).revisions["esquema-c"].predecessor is None

    _write_edition(modelo_dir, _Edition("esquema-b", 2025))
    with pytest.raises(RegistryLoadError, match=re.escape("'esquema-b' and 'esquema-c'")):
        load_modelo_directory(modelo_dir)

    _write_edition(modelo_dir, _Edition("esquema-b", 2025, manifest_extra=_NONE))
    assert isinstance(load_modelo_directory(modelo_dir).revisions["esquema-b"].predecessor, NoPredecessor)


def test_the_parallel_scheme_modelo_loads_as_three_parallel_roots() -> None:
    """Modelo 369's editions are roots declaring no predecessor, with no edge between them."""
    modelos, _catalogues = bundled_registry_tree()
    (modelo,) = (modelo for modelo in modelos if modelo.id == _PARALLEL_SCHEME_MODELO)

    assert len(modelo.revisions) == 3
    assert all(isinstance(revision.predecessor, NoPredecessor) for revision in modelo.revisions.values())
    assert len({revision.valid_from for revision in modelo.revisions.values()}) == 1
    validate_predecessor_forest(
        modelo.id,
        named={},
        declared_roots=frozenset(modelo.revisions),
        keyless=frozenset(),
    )


def test_a_predecessor_cycle_is_refused(tmp_path: Path) -> None:
    cycle = re.escape("form a cycle '2025' -> '2026' -> '2025'")
    modelo_dir = _write_editions(tmp_path, *_chain(_names("2025"), second_extra=_names("2026")))

    with pytest.raises(RegistryLoadError, match=cycle):
        load_modelo_directory(modelo_dir)

    _write_edition(modelo_dir, _Edition("2025", 2025, manifest_extra=_names("2024")))
    assert load_modelo_directory(modelo_dir).revisions["2025"].predecessor == DeclaredPredecessor(revision_id="2024")

    _write_edition(modelo_dir, _Edition("2025", 2025, manifest_extra=_names("2026")))
    with pytest.raises(RegistryLoadError, match=cycle):
        load_modelo_directory(modelo_dir)


def test_a_cycle_with_no_key_less_edition_is_refused_rather_than_read_as_rootless() -> None:
    """Every edition naming a sibling leaves no root at all; the cycle refusal names the loop."""
    with pytest.raises(RegistryValidationError, match=re.escape("'a' -> 'b' -> 'c' -> 'a'")):
        validate_predecessor_forest(
            "999", named={"a": "b", "b": "c", "c": "a"}, declared_roots=frozenset(), keyless=frozenset()
        )

    validate_predecessor_forest("999", named={"b": "a", "c": "b"}, declared_roots=frozenset(), keyless=frozenset({"a"}))


def test_a_self_target_is_refused_at_the_loader_and_by_the_forest_rule(tmp_path: Path) -> None:
    """The typed revision refuses it first; the rule refuses it too for untyped callers."""
    self_target = re.escape("'2026' declares itself as its own predecessor")
    modelo_dir = _write_editions(tmp_path, *_chain(_names("2026")))

    with pytest.raises(RegistryLoadError, match=self_target):
        load_modelo_directory(modelo_dir)
    with pytest.raises(RegistryValidationError, match=self_target):
        validate_predecessor_forest(
            "999", named={"2025": "2024", "2026": "2026"}, declared_roots=frozenset(), keyless=frozenset({"2024"})
        )

    _write_edition(modelo_dir, _Edition("2026", 2026, manifest_extra=_names("2025")))
    assert load_modelo_directory(modelo_dir).revisions["2026"].predecessor is not None
    validate_predecessor_forest(
        "999", named={"2025": "2024", "2026": "2025"}, declared_roots=frozenset(), keyless=frozenset({"2024"})
    )


def test_an_unknown_target_is_refused(tmp_path: Path) -> None:
    unknown = re.escape("declares predecessor '2023', which is not a revision of this modelo")
    modelo_dir = _write_editions(tmp_path, *_chain(_names("2023")))

    with pytest.raises(RegistryLoadError, match=unknown):
        load_modelo_directory(modelo_dir)

    _write_edition(modelo_dir, _Edition("2026", 2026, manifest_extra=_names("2025")))
    assert load_modelo_directory(modelo_dir).revisions["2026"].predecessor is not None

    _write_edition(modelo_dir, _Edition("2026", 2026, manifest_extra=_names("2023")))
    with pytest.raises(RegistryLoadError, match=unknown):
        load_modelo_directory(modelo_dir)


def test_a_section_fragment_declaring_the_predecessor_is_refused(tmp_path: Path) -> None:
    """Placement, not content: the identical declaration loads from the manifest."""
    misplaced = re.escape("revision field 'predecessor' must be declared in the revision's revision.toml")
    in_fragment = _Edition("2025", 2025, fragment_extra='\n[revisions."2025"]\npredecessor = "2024"\n')
    modelo_dir = _write_editions(tmp_path, _Edition("2024", 2024), in_fragment)

    with pytest.raises(RegistryLoadError, match=misplaced):
        load_modelo_directory(modelo_dir)

    _write_edition(modelo_dir, _Edition("2025", 2025, manifest_extra=_names("2024")))
    assert load_modelo_directory(modelo_dir).revisions["2025"].predecessor == DeclaredPredecessor(revision_id="2024")

    _write_edition(modelo_dir, in_fragment)
    with pytest.raises(RegistryLoadError, match=misplaced):
        load_modelo_directory(modelo_dir)


def test_the_rule_binds_a_modelo_only_once_an_edition_declares_the_key(tmp_path: Path) -> None:
    """Where the rule stops: an all-full-copy modelo is unbound, and one declaration binds it.

    Every edition omitting the key is the full-copy format, each edition its own
    root, and it loads unchanged. The first declaration on any edition, of
    either kind, moves the modelo into the forest, where the other key-less
    editions are then more than one undeclared root.
    """
    modelo_dir = _write_editions(tmp_path, *_chain("", second_extra=""), _Edition("2027", 2027))
    full_copy = load_modelo_directory(modelo_dir)
    assert len(full_copy.revisions) == 4
    assert all(revision.predecessor is None for revision in full_copy.revisions.values())

    _write_edition(modelo_dir, _Edition("2025", 2025, manifest_extra=_NONE))
    with pytest.raises(RegistryLoadError, match=re.escape("has 3 editions omitting the predecessor key")):
        load_modelo_directory(modelo_dir)

    _write_edition(modelo_dir, _Edition("2025", 2025))
    assert load_modelo_directory(modelo_dir).revisions["2025"].predecessor is None


def test_an_edition_carrying_two_declaration_states_is_refused() -> None:
    with pytest.raises(RegistryValidationError, match="carry more than one predecessor declaration state"):
        validate_predecessor_forest("999", named={"b": "a"}, declared_roots=frozenset({"b"}), keyless=frozenset({"a"}))


def test_the_shipped_bound_set_is_the_modelos_declaring_the_key() -> None:
    """Loading the corpus is the forest proof; this pins which modelos the rule binds.

    Asserted as membership rather than a tally, so migrating a modelo into the
    declared format extends the set without editing this test.
    """
    modelos: tuple[ModeloDefinition, ...] = tuple(bundled_registry_tree()[0])
    declaring = {
        modelo.id
        for modelo in modelos
        if any(revision.predecessor is not None for revision in modelo.revisions.values())
    }

    assert _PARALLEL_SCHEME_MODELO in declaring
