"""Loader and schema behaviour for a revision's declared predecessor edition.

A revision is authored relative to a sibling edition only when it says so. The
properties that must hold before anything can act on the declaration: a revision
without the key loads as a full-copy revision exactly as before, a well-formed
declaration is carried typed rather than as a string, an explicit grounded
"no predecessor exists" stays distinguishable from both, and every malformed,
ungrounded, self-referential, dangling, or misspelled declaration is refused at
the loader boundary instead of being carried for a later consumer to interpret.

Every test drives the real directory loader over a real on-disk TOML tree, and
the corpus test reads the shipped registry.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from dev.registry.compiler.loader import load_modelo_directory
from pydantic import TypeAdapter

from .....tests.registry_tree import bundled_registry_tree
from ..errors import RegistryLoadError
from ..schema import DeclaredPredecessor, DeclaredPredecessorField, NoPredecessor
from ._loader_directory_mode_support import _write_modelo as _shared_write_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SUCCESSOR_ID = "2025"
_PREDECESSOR_ID = "2024"
_LEGAL_REF = "ley-58-2003:art-29"
_NO_PREDECESSOR_REASON = "Parallel scheme variant sharing one validity date with its siblings."
_NO_PREDECESSOR = (
    f'predecessor = {{ none = {{ reason = "{_NO_PREDECESSOR_REASON}", '
    f'legal_refs = ["{_LEGAL_REF}"], source_refs = ["aeat-manual"] }} }}\n'
)
_PARALLEL_SCHEME_MODELO = "369"


def _casilla_fragment(revision_id: str) -> str:
    """One casilla carrying the same lineage in every edition, so a successor's row supersedes its predecessor's."""
    return f"""
[[revisions."{revision_id}".casillas]]
id = "0001"
number = "1"
section = ["liquidacion"]
continuidad_id = "casilla-0001"
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

    with pytest.raises(RegistryLoadError, match=r"predecessor\.revision\.revision_id"):
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


def test_absence_a_predecessor_and_an_explicit_none_are_three_distinct_states(tmp_path: Path) -> None:
    """Each state loads as its own type and dumps to its own shape; none collapses into another."""
    states = {}
    for label, extra in (
        ("absent", ""),
        ("predecessor", f'predecessor = "{_PREDECESSOR_ID}"\n'),
        ("none", _NO_PREDECESSOR),
    ):
        definition = load_modelo_directory(_write_two_edition_modelo(tmp_path / label, successor_manifest_extra=extra))
        successor = definition.revisions[_SUCCESSOR_ID]
        states[label] = (successor.predecessor, successor.model_dump(mode="json").get("predecessor", "<absent>"))

    assert states["absent"] == (None, "<absent>")
    assert states["predecessor"] == (DeclaredPredecessor(revision_id=_PREDECESSOR_ID), _PREDECESSOR_ID)
    assert states["none"] == (
        NoPredecessor(reason=_NO_PREDECESSOR_REASON, legal_refs=(_LEGAL_REF,), source_refs=("aeat-manual",)),
        {"none": {"reason": _NO_PREDECESSOR_REASON, "legal_refs": [_LEGAL_REF], "source_refs": ["aeat-manual"]}},
    )
    assert len({type(declaration) for declaration, _dumped in states.values()}) == 3


def test_an_explicit_none_serialises_as_authored_and_hydrates_back(tmp_path: Path) -> None:
    """The dumped ``none`` nesting is the authored spelling, so it hydrates into the identical declaration."""
    successor = load_modelo_directory(
        _write_two_edition_modelo(tmp_path, successor_manifest_extra=_NO_PREDECESSOR),
    ).revisions[_SUCCESSOR_ID]

    adapter = TypeAdapter(DeclaredPredecessorField)
    assert adapter.validate_python(successor.model_dump(mode="python")["predecessor"]) == successor.predecessor


@pytest.mark.parametrize(
    ("declaration", "refusal"),
    [
        pytest.param(
            f'predecessor = {{ none = {{ legal_refs = ["{_LEGAL_REF}"], source_refs = ["aeat-manual"] }} }}\n',
            r"predecessor\.none\.reason",
            id="missing-reason",
        ),
        pytest.param(
            f'predecessor = {{ none = {{ reason = "", legal_refs = ["{_LEGAL_REF}"], source_refs = ["aeat-manual"] }} }}\n',
            r"predecessor\.none\.reason",
            id="empty-reason",
        ),
        pytest.param(
            'predecessor = { none = { reason = "Parallel.", source_refs = ["aeat-manual"] } }\n',
            r"predecessor\.none\.legal_refs",
            id="missing-legal-refs",
        ),
        pytest.param(
            f'predecessor = {{ none = {{ reason = "Parallel.", legal_refs = ["{_LEGAL_REF}"], source_refs = [] }} }}\n',
            r"predecessor\.none\.source_refs",
            id="empty-source-refs",
        ),
        pytest.param(
            f'predecessor = {{ none = {{ reason = "Parallel.", legal_refs = ["{_LEGAL_REF}"], '
            'source_refs = ["aeat-manual"], revision_id = "2024" } }\n',
            r"predecessor\.none\.revision_id",
            id="unknown-key-inside-none",
        ),
        pytest.param(
            f'predecessor = {{ none = {{ reason = "Parallel.", legal_refs = ["{_LEGAL_REF}"], '
            f'source_refs = ["aeat-manual"] }}, revision_id = "{_PREDECESSOR_ID}" }}\n',
            "predecessor must be the revision id of a sibling edition",
            id="none-beside-a-revision-id",
        ),
        pytest.param("predecessor = { none = true }\n", r"predecessor\.none", id="bare-none-flag"),
    ],
)
def test_an_ungrounded_or_malformed_none_is_refused_and_the_grounded_one_loads(
    tmp_path: Path, declaration: str, refusal: str
) -> None:
    """Both directions on one tree: the plant reds the load, the grounded declaration restores it."""
    modelo_dir = _write_two_edition_modelo(tmp_path, successor_manifest_extra=declaration)

    with pytest.raises(RegistryLoadError, match=refusal):
        load_modelo_directory(modelo_dir)

    _set_successor_extra(modelo_dir, _NO_PREDECESSOR)
    restored = load_modelo_directory(modelo_dir).revisions[_SUCCESSOR_ID]
    assert isinstance(restored.predecessor, NoPredecessor)


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
            declaration = revision.predecessor
            if declaration is None:
                assert "predecessor" not in dumped
            elif isinstance(declaration, DeclaredPredecessor):
                assert dumped["predecessor"] == declaration.revision_id
                assert declaration.revision_id in modelo.revisions
            else:
                assert dumped["predecessor"] == {
                    "none": {
                        "reason": declaration.reason,
                        "legal_refs": list(declaration.legal_refs),
                        "source_refs": list(declaration.source_refs),
                    }
                }


def test_the_parallel_scheme_modelo_declares_every_edition_without_a_predecessor() -> None:
    """Modelo 369's editions are concurrent scheme variants, and each says so on its own manifest.

    Every edition carries the explicit, grounded no-predecessor declaration
    rather than an absent key, and every reference it stands on resolves in the
    bundled legal and source catalogues.
    """
    modelos, catalogues = bundled_registry_tree()
    (modelo,) = (modelo for modelo in modelos if modelo.id == _PARALLEL_SCHEME_MODELO)

    assert len(modelo.revisions) > 1
    for revision_id, revision in modelo.revisions.items():
        declaration = revision.predecessor
        assert isinstance(declaration, NoPredecessor), revision_id
        assert set(declaration.legal_refs) <= set(catalogues.legal), revision_id
        assert set(declaration.source_refs) <= set(catalogues.sources), revision_id
