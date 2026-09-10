"""Loader and schema behaviour for a revision's declared predecessor edition.

A revision is authored relative to a sibling edition only when it says so. The
properties that must hold before anything can act on the declaration: a revision
without the key loads as a full-copy revision exactly as before, a well-formed
declaration is carried typed rather than as a string, and every malformed,
self-referential, dangling, or misspelled declaration is refused at the loader
boundary instead of being carried for a later consumer to interpret.

Every test drives the real directory loader over a real on-disk TOML tree, and
the corpus test reads the shipped registry.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from .....tests.registry_tree import bundled_registry_tree
from ..errors import RegistryLoadError
from ..loader import load_modelo_directory
from ..schema import DeclaredPredecessor, DeclaredPredecessorField
from ._loader_directory_mode_support import _write_modelo as _shared_write_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SUCCESSOR_ID = "2025"
_PREDECESSOR_ID = "2024"
_LEGAL_REF = "ley-58-2003:art-29"


def _casilla_fragment(revision_id: str) -> str:
    return f"""
[[revisions."{revision_id}".casillas]]
id = "0001"
number = "1"
section = ["liquidacion"]
legal_refs = ["{_LEGAL_REF}"]
source_refs = ["aeat-manual"]
""".lstrip()


def _write_two_edition_modelo(root: Path, *, successor_manifest_extra: str = "") -> Path:
    """Materialise a modelo with a 2024 edition and a 2025 edition.

    ``successor_manifest_extra`` is appended to the 2025 ``revision.toml``, the
    one place a test plants or removes a predecessor declaration.
    """
    modelo_dir = _shared_write_modelo(
        root,
        casilla_fragment=_casilla_fragment(_SUCCESSOR_ID),
        revision_id=_SUCCESSOR_ID,
        manifest_extra=successor_manifest_extra,
    )
    predecessor_dir = modelo_dir / "revisions" / _PREDECESSOR_ID
    (predecessor_dir / "casillas").mkdir(parents=True)
    (predecessor_dir / "revision.toml").write_text(
        (
            f'[revisions."{_PREDECESSOR_ID}"]\n'
            "valid_from = 2024-01-01\n"
            "valid_to = 2024-12-31\n"
            'period_selector = { years = [2024], periods = ["0A"] }\n'
            f'legal_refs = ["{_LEGAL_REF}"]\n'
            'source_refs = ["aeat-manual"]\n'
        ),
        encoding="utf-8",
        newline="\n",
    )
    (predecessor_dir / "casillas" / "0001-casillas.toml").write_text(
        _casilla_fragment(_PREDECESSOR_ID), encoding="utf-8", newline="\n"
    )
    return modelo_dir


def _set_successor_extra(modelo_dir: Path, extra: str) -> None:
    """Rewrite the 2025 manifest's trailing declaration in place."""
    manifest = modelo_dir / "revisions" / _SUCCESSOR_ID / "revision.toml"
    preamble = manifest.read_text(encoding="utf-8").split("\npredecessor", 1)[0].rstrip("\n") + "\n"
    manifest.write_text(preamble + extra, encoding="utf-8", newline="\n")


def test_a_revision_without_the_key_is_a_full_copy_revision(tmp_path: Path) -> None:
    """Absence is not inferred into a predecessor, and it leaves the dump untouched.

    The serialised form carrying no ``predecessor`` key at all is what makes an
    undeclaring revision dump exactly as it did before the key existed.
    """
    definition = load_modelo_directory(_write_two_edition_modelo(tmp_path))

    for revision in definition.revisions.values():
        assert revision.predecessor is None
        assert "predecessor" not in revision.model_dump(mode="json")
        assert "predecessor" not in json.loads(revision.model_dump_json())


def test_a_declared_predecessor_is_carried_typed_and_serialises_as_authored(tmp_path: Path) -> None:
    definition = load_modelo_directory(
        _write_two_edition_modelo(tmp_path, successor_manifest_extra=f'predecessor = "{_PREDECESSOR_ID}"\n'),
    )

    successor = definition.revisions[_SUCCESSOR_ID]
    assert successor.predecessor == DeclaredPredecessor(revision_id=_PREDECESSOR_ID)
    assert isinstance(successor.predecessor, DeclaredPredecessor)
    assert definition.revisions[_PREDECESSOR_ID].predecessor is None
    assert successor.model_dump(mode="json")["predecessor"] == _PREDECESSOR_ID

    # The serialised spelling hydrates back into the identical declaration.
    adapter = TypeAdapter(DeclaredPredecessorField)
    assert adapter.validate_python(successor.model_dump(mode="python")["predecessor"]) == successor.predecessor


def test_a_malformed_predecessor_id_is_refused_and_the_well_formed_one_loads(tmp_path: Path) -> None:
    """Both directions on one tree: the plant reds the load, removing it restores it."""
    modelo_dir = _write_two_edition_modelo(tmp_path, successor_manifest_extra='predecessor = "Edición 2024"\n')

    with pytest.raises(RegistryLoadError, match=r"predecessor\.revision_id"):
        load_modelo_directory(modelo_dir)

    _set_successor_extra(modelo_dir, f'predecessor = "{_PREDECESSOR_ID}"\n')
    restored = load_modelo_directory(modelo_dir).revisions[_SUCCESSOR_ID]
    assert restored.predecessor == DeclaredPredecessor(revision_id=_PREDECESSOR_ID)


@pytest.mark.parametrize(
    "declaration",
    [
        pytest.param(f'predecessor = {{ revision_id = "{_PREDECESSOR_ID}" }}\n', id="table-spelling"),
        pytest.param("predecessor = 2024\n", id="integer"),
        pytest.param(f'predecessor = ["{_PREDECESSOR_ID}"]\n', id="array"),
    ],
)
def test_a_non_string_predecessor_is_refused(tmp_path: Path, declaration: str) -> None:
    """The declaration has one authored spelling; an equivalent table is not a second one."""
    with pytest.raises(RegistryLoadError, match="predecessor must be the revision id of a sibling edition"):
        load_modelo_directory(_write_two_edition_modelo(tmp_path, successor_manifest_extra=declaration))


def test_a_revision_naming_itself_as_predecessor_is_refused(tmp_path: Path) -> None:
    modelo_dir = _write_two_edition_modelo(tmp_path, successor_manifest_extra=f'predecessor = "{_SUCCESSOR_ID}"\n')

    with pytest.raises(RegistryLoadError, match="declares itself as its own predecessor"):
        load_modelo_directory(modelo_dir)

    _set_successor_extra(modelo_dir, f'predecessor = "{_PREDECESSOR_ID}"\n')
    assert load_modelo_directory(modelo_dir).revisions[_SUCCESSOR_ID].predecessor is not None


def test_a_predecessor_naming_no_sibling_edition_is_refused(tmp_path: Path) -> None:
    """A well-formed id that resolves to nothing in the modelo is a dangling declaration."""
    modelo_dir = _write_two_edition_modelo(tmp_path, successor_manifest_extra='predecessor = "2023"\n')

    with pytest.raises(RegistryLoadError, match="'2023', which is not a revision of this modelo"):
        load_modelo_directory(modelo_dir)

    _set_successor_extra(modelo_dir, f'predecessor = "{_PREDECESSOR_ID}"\n')
    assert load_modelo_directory(modelo_dir).revisions[_SUCCESSOR_ID].predecessor is not None


def test_a_misspelled_key_is_refused_rather_than_read_as_a_full_copy(tmp_path: Path) -> None:
    """The model stays closed: a typo cannot silently mean "no predecessor declared"."""
    with pytest.raises(RegistryLoadError, match="predecesor"):
        load_modelo_directory(
            _write_two_edition_modelo(tmp_path, successor_manifest_extra=f'predecesor = "{_PREDECESSOR_ID}"\n'),
        )


def test_every_shipped_revision_serialises_the_key_exactly_when_it_declares_one() -> None:
    """The optional key describes the shipped tree without reshaping it.

    Asserted as a property over whatever the corpus holds rather than a tally: an
    undeclaring revision's dump carries no trace of the key, and a declaring one
    names a sibling edition of its own modelo.
    """
    modelos, _catalogues = bundled_registry_tree()

    assert any(modelo.revisions for modelo in modelos), "the bundled registry must load at least one revision"
    for modelo in modelos:
        for revision in modelo.revisions.values():
            dumped = revision.model_dump(mode="json")
            if revision.predecessor is None:
                assert "predecessor" not in dumped
            else:
                assert dumped["predecessor"] == revision.predecessor.revision_id
                assert revision.predecessor.revision_id in modelo.revisions
