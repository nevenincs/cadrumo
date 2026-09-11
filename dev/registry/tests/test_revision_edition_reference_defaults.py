"""Edition-level reference defaults filled into the casilla rows that state none.

An edition declares its casilla rows' default source grounding once, as
``casilla_source_refs`` in its manifest, and its approving ordenes once, as
``orden_aplicabilidad``. The loader fills the first into every casilla row and
row ``constraints`` table stating no ``source_refs``, and the second into every
one stating no ``legal_refs``. A stated value is kept whole. A row or
constraints table stating ``additional_source_refs`` takes the default followed
by those additions. Defaults apply after predecessor inheritance, so an
inherited row takes the edition it now sits in's defaults, extended by its own
additions.

Every test drives the real directory loader or the real registry authority over
an on-disk TOML tree, and each accepted shape is paired with the refusal it
replaces, so a test cannot pass because the defaults were never consulted.
"""

from __future__ import annotations

import json
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Final

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryLoadError, RegistryValidationError
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from ..compiler.authority import compile_validated_authority
from ..compiler.loader import load_modelo_directory
from ..conformance.tests._loader_directory_mode_support import _write_standard_manifest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO_ID: Final = "999"
_ARTICLE: Final = "ley-58-2003:art-29"
_ORDEN_2024: Final = "orden-hac-100-2023:art-1"
_ORDEN_2025: Final = "orden-hac-200-2024:art-1"
_SOURCE_2024: Final = "aeat-dr-999-2024"
_SOURCE_2025: Final = "aeat-dr-999-2025"
_OWN_SOURCE: Final = "aeat-instrucciones-999"
_BUNDLED_REGISTRY: Final = bundled_path("registry", "aeat")


def _casilla(
    revision_id: str,
    casilla_id: str,
    *,
    lineage: str,
    legal_refs: tuple[str, ...] | None = None,
    source_refs: tuple[str, ...] | None = None,
    additional_source_refs: tuple[str, ...] | None = None,
    constraints: str | None = None,
) -> str:
    lines = [
        f'[[revisions."{revision_id}".casillas]]',
        f'id = "{casilla_id}"',
        f'number = "{casilla_id}"',
        'section = ["liquidacion"]',
        f'continuidad_id = "{lineage}"',
    ]
    if constraints is not None:
        lines.append(f"constraints = {{ {constraints} }}")
    if legal_refs is not None:
        lines.append(f"legal_refs = {json.dumps(list(legal_refs))}")
    if source_refs is not None:
        lines.append(f"source_refs = {json.dumps(list(source_refs))}")
    if additional_source_refs is not None:
        lines.append(f"additional_source_refs = {json.dumps(list(additional_source_refs))}")
    return "\n".join(lines) + "\n\n"


def _write_edition(
    modelo_dir: Path,
    revision_id: str,
    *,
    year: int,
    orden: str,
    casillas: str,
    source_default: str | None,
    manifest_extra: str = "",
) -> None:
    revision_dir = modelo_dir / "revisions" / revision_id
    (revision_dir / "casillas").mkdir(parents=True)
    default_line = f'casilla_source_refs = ["{source_default}"]\n' if source_default is not None else ""
    (revision_dir / "revision.toml").write_text(
        f'[revisions."{revision_id}"]\n'
        f"valid_from = {year}-01-01\n"
        f"valid_to = {year}-12-31\n"
        f'period_selector = {{ years = [{year}], periods = ["0A"] }}\n'
        f'legal_refs = ["{_ARTICLE}"]\n'
        'source_refs = ["aeat-manual"]\n'
        f'orden_aplicabilidad = ["{orden}"]\n'
        f"{default_line}{manifest_extra}",
        encoding="utf-8",
        newline="\n",
    )
    (revision_dir / "casillas" / "0001-casillas.toml").write_text(casillas, encoding="utf-8", newline="\n")


def _modelo_root(root: Path) -> Path:
    modelo_dir = root / _MODELO_ID
    modelo_dir.mkdir(parents=True)
    _write_standard_manifest(modelo_dir, "Test")
    return modelo_dir


def _refs(revision: ModeloRevision, casilla_id: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    (casilla,) = (item for item in revision.casillas if item.id == casilla_id)
    return tuple(casilla.legal_refs), tuple(casilla.source_refs)


def _constraint_refs(revision: ModeloRevision, casilla_id: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    (casilla,) = (item for item in revision.casillas if item.id == casilla_id)
    assert casilla.constraints is not None, casilla_id
    return tuple(casilla.constraints.legal_refs), tuple(casilla.constraints.source_refs)


# ── one edition ─────────────────────────────────────────────────────────────


def _single_edition(root: Path, *, source_default: str | None) -> Path:
    modelo_dir = _modelo_root(root)
    _write_edition(
        modelo_dir,
        "2025",
        year=2025,
        orden=_ORDEN_2025,
        source_default=source_default,
        casillas=(
            _casilla("2025", "01", lineage="silente")
            + _casilla("2025", "02", lineage="propia", legal_refs=(_ARTICLE,), source_refs=(_OWN_SOURCE,))
            + _casilla("2025", "03", lineage="solo-fuente", source_refs=(_OWN_SOURCE,))
            + _casilla(
                "2025",
                "04",
                lineage="con-restriccion",
                legal_refs=(_ARTICLE,),
                source_refs=(_OWN_SOURCE,),
                constraints='sign = "non_negative"',
            )
            + _casilla(
                "2025",
                "05",
                lineage="restriccion-propia",
                constraints=f'sign = "non_negative", legal_refs = ["{_ARTICLE}"], source_refs = ["{_OWN_SOURCE}"]',
            )
        ),
    )
    return modelo_dir


def test_a_row_stating_none_takes_the_editions_defaults_and_a_row_stating_its_own_keeps_them(
    tmp_path: Path,
) -> None:
    """Replace, never merge: each field is decided independently, and a stated value survives whole."""
    revision = load_modelo_directory(_single_edition(tmp_path, source_default=_SOURCE_2025)).revisions["2025"]

    assert _refs(revision, "01") == ((_ORDEN_2025,), (_SOURCE_2025,))
    assert _refs(revision, "02") == ((_ARTICLE,), (_OWN_SOURCE,))
    assert _refs(revision, "03") == ((_ORDEN_2025,), (_OWN_SOURCE,))
    assert revision.casilla_source_refs == (_SOURCE_2025,)


def test_a_constraints_table_is_defaulted_from_the_edition_not_from_its_row(tmp_path: Path) -> None:
    """Row 04 states its own source; its constraints state none and take the edition's, not the row's."""
    revision = load_modelo_directory(_single_edition(tmp_path, source_default=_SOURCE_2025)).revisions["2025"]

    assert _constraint_refs(revision, "04") == ((_ORDEN_2025,), (_SOURCE_2025,))
    assert _refs(revision, "04") == ((_ARTICLE,), (_OWN_SOURCE,))
    assert _constraint_refs(revision, "05") == ((_ARTICLE,), (_OWN_SOURCE,))
    assert _refs(revision, "05") == ((_ORDEN_2025,), (_SOURCE_2025,))


def test_without_a_declared_source_default_a_row_stating_no_source_is_refused(tmp_path: Path) -> None:
    """The teeth of the proofs above: nothing is inferred when the edition declares no default."""
    with pytest.raises(
        RegistryLoadError, match=r"(?s)invalid revision '2025'.*casillas\.0\.source_refs\s+Field required"
    ):
        load_modelo_directory(_single_edition(tmp_path, source_default=None))


def test_an_explicitly_empty_row_value_is_refused_rather_than_defaulted(tmp_path: Path) -> None:
    modelo_dir = _modelo_root(tmp_path)
    _write_edition(
        modelo_dir,
        "2025",
        year=2025,
        orden=_ORDEN_2025,
        source_default=_SOURCE_2025,
        casillas=_casilla("2025", "01", lineage="vacia", source_refs=()),
    )

    with pytest.raises(RegistryLoadError, match=r"casillas\.0\.source_refs\s+Tuple should have at least 1 item"):
        load_modelo_directory(modelo_dir)


def test_the_source_default_is_refused_outside_the_manifest(tmp_path: Path) -> None:
    """A default grounding every row of the edition must be readable in ``revision.toml``."""
    modelo_dir = _single_edition(tmp_path, source_default=None)
    fragment = modelo_dir / "revisions" / "2025" / "casillas" / "0001-casillas.toml"
    fragment.write_text(
        fragment.read_text(encoding="utf-8") + f'[revisions."2025"]\ncasilla_source_refs = ["{_SOURCE_2025}"]\n',
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(RegistryLoadError, match=re.escape("must be declared in the revision's revision.toml")):
        load_modelo_directory(modelo_dir)


def test_an_edition_declaring_no_default_dumps_without_the_field(tmp_path: Path) -> None:
    """Absent reads as ``None`` and is excluded, so an undeclared edition dumps as it did before the key existed."""
    modelo_dir = _modelo_root(tmp_path)
    _write_edition(
        modelo_dir,
        "2025",
        year=2025,
        orden=_ORDEN_2025,
        source_default=None,
        casillas=_casilla("2025", "01", lineage="propia", legal_refs=(_ARTICLE,), source_refs=(_OWN_SOURCE,)),
    )
    revision = load_modelo_directory(modelo_dir).revisions["2025"]

    assert revision.casilla_source_refs is None
    assert "casilla_source_refs" not in revision.model_dump()
    assert (
        "casilla_source_refs"
        in load_modelo_directory(_single_edition(tmp_path / "declared", source_default=_SOURCE_2025))
        .revisions["2025"]
        .model_dump()
    )


# ── inheritance ─────────────────────────────────────────────────────────────


def _two_editions(root: Path) -> Path:
    """2024 grounds its rows through its own defaults; 2025 names it as predecessor and restates nothing."""
    modelo_dir = _modelo_root(root)
    _write_edition(
        modelo_dir,
        "2024",
        year=2024,
        orden=_ORDEN_2024,
        source_default=_SOURCE_2024,
        casillas=(
            _casilla("2024", "01", lineage="silente", constraints='sign = "non_negative"')
            + _casilla("2024", "02", lineage="propia", legal_refs=(_ARTICLE,), source_refs=(_OWN_SOURCE,))
        ),
    )
    _write_edition(
        modelo_dir,
        "2025",
        year=2025,
        orden=_ORDEN_2025,
        source_default=_SOURCE_2025,
        manifest_extra='predecessor = "2024"\n',
        casillas=_casilla("2025", "03", lineage="nueva"),
    )
    return modelo_dir


def test_an_inherited_row_stating_none_takes_the_successors_defaults(tmp_path: Path) -> None:
    """Defaults run after inheritance: the predecessor's own defaults never travel with its rows.

    Were the defaults filled before inheritance, row 01 would reach 2025 already
    carrying 2024's orden and source, and its constraints 2024's source; each
    assertion on 2025 below would then name the 2024 value instead.
    """
    definition = load_modelo_directory(_two_editions(tmp_path))
    predecessor, successor = definition.revisions["2024"], definition.revisions["2025"]

    assert [casilla.id for casilla in successor.casillas] == ["01", "02", "03"]
    assert _refs(predecessor, "01") == ((_ORDEN_2024,), (_SOURCE_2024,))
    assert _constraint_refs(predecessor, "01") == ((_ORDEN_2024,), (_SOURCE_2024,))
    assert _refs(successor, "01") == ((_ORDEN_2025,), (_SOURCE_2025,))
    assert _constraint_refs(successor, "01") == ((_ORDEN_2025,), (_SOURCE_2025,))
    assert _refs(successor, "03") == ((_ORDEN_2025,), (_SOURCE_2025,))


def test_an_inherited_row_stating_its_own_refs_keeps_them(tmp_path: Path) -> None:
    """The predecessor author grounded row 02 explicitly, and inheritance carries that statement unchanged."""
    successor = load_modelo_directory(_two_editions(tmp_path)).revisions["2025"]

    assert _refs(successor, "02") == ((_ARTICLE,), (_OWN_SOURCE,))


def test_a_successor_without_a_source_default_cannot_ground_an_inherited_silent_row(tmp_path: Path) -> None:
    """Teeth for the ordering: the predecessor's default does not rescue a successor that declares none."""
    modelo_dir = _two_editions(tmp_path)
    manifest = modelo_dir / "revisions" / "2025" / "revision.toml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(f'casilla_source_refs = ["{_SOURCE_2025}"]\n', ""),
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(
        RegistryLoadError, match=r"(?s)invalid revision '2025'.*casillas\.0\.source_refs\s+Field required"
    ):
        load_modelo_directory(modelo_dir)


# ── source references in addition to the default ────────────────────────────


def _additions_edition(root: Path, *, source_default: str | None, row: str) -> Path:
    modelo_dir = _modelo_root(root)
    _write_edition(
        modelo_dir,
        "2025",
        year=2025,
        orden=_ORDEN_2025,
        source_default=source_default,
        casillas=row + _casilla("2025", "02", lineage="propia", source_refs=(_OWN_SOURCE,)),
    )
    return modelo_dir


def test_additions_extend_the_default_with_the_default_first_and_each_reference_once(tmp_path: Path) -> None:
    """Additions follow the default; a stated full value beside them still replaces it."""
    row = _casilla(
        "2025",
        "01",
        lineage="con-procedimiento",
        additional_source_refs=(_OWN_SOURCE, _SOURCE_2025),
        constraints=f'sign = "non_negative", additional_source_refs = ["{_OWN_SOURCE}"]',
    )
    revision = load_modelo_directory(_additions_edition(tmp_path, source_default=_SOURCE_2025, row=row)).revisions[
        "2025"
    ]

    assert _refs(revision, "01") == ((_ORDEN_2025,), (_SOURCE_2025, _OWN_SOURCE))
    assert _constraint_refs(revision, "01") == ((_ORDEN_2025,), (_SOURCE_2025, _OWN_SOURCE))
    assert _refs(revision, "02") == ((_ORDEN_2025,), (_OWN_SOURCE,))
    assert "additional_source_refs" not in revision.model_dump()["casillas"][0]


_ADDITIONS_ROW: Final = _casilla("2025", "01", lineage="con-procedimiento", additional_source_refs=(_OWN_SOURCE,))


@pytest.mark.parametrize(
    ("row", "source_default", "refusal"),
    [
        pytest.param(
            _casilla(
                "2025", "01", lineage="con-procedimiento", source_refs=(_OWN_SOURCE,), additional_source_refs=("x",)
            ),
            _SOURCE_2025,
            r"casilla '01' states both source_refs and additional_source_refs",
            id="both-on-the-row",
        ),
        pytest.param(
            _casilla(
                "2025",
                "01",
                lineage="con-procedimiento",
                constraints=f'sign = "non_negative", source_refs = ["{_OWN_SOURCE}"], additional_source_refs = ["x"]',
            ),
            _SOURCE_2025,
            r"casilla '01' constraints states both source_refs and additional_source_refs",
            id="both-on-the-constraints",
        ),
        pytest.param(
            _casilla("2025", "01", lineage="con-procedimiento", additional_source_refs=()),
            _SOURCE_2025,
            r"casilla '01' additional_source_refs must be a non-empty array of source reference ids",
            id="empty-additions",
        ),
        pytest.param(
            _ADDITIONS_ROW,
            None,
            r"casilla '01' states additional_source_refs, but the edition declares no casilla_source_refs",
            id="no-default-to-extend",
        ),
    ],
)
def test_additions_are_refused_where_they_cannot_extend_a_default_and_the_repaired_tree_loads(
    tmp_path: Path, row: str, source_default: str | None, refusal: str
) -> None:
    with pytest.raises(RegistryLoadError, match=rf"revision '2025': {refusal}"):
        load_modelo_directory(_additions_edition(tmp_path / "refused", source_default=source_default, row=row))

    repaired = load_modelo_directory(
        _additions_edition(tmp_path / "repaired", source_default=_SOURCE_2025, row=_ADDITIONS_ROW)
    )
    assert _refs(repaired.revisions["2025"], "01") == ((_ORDEN_2025,), (_SOURCE_2025, _OWN_SOURCE))


def test_additions_inherit_with_the_row_and_extend_the_successors_default(tmp_path: Path) -> None:
    """The additions are the row's own and travel with it; the default they extend is the successor's.

    Were the predecessor's materialised value inherited instead, row 01 would
    reach 2025 citing 2024's design; were the additions dropped, it would cite
    2025's design alone.
    """
    modelo_dir = _modelo_root(tmp_path)
    _write_edition(
        modelo_dir,
        "2024",
        year=2024,
        orden=_ORDEN_2024,
        source_default=_SOURCE_2024,
        casillas=_casilla(
            "2024",
            "01",
            lineage="con-procedimiento",
            additional_source_refs=(_OWN_SOURCE,),
            constraints=f'sign = "non_negative", additional_source_refs = ["{_OWN_SOURCE}"]',
        ),
    )
    _write_edition(
        modelo_dir,
        "2025",
        year=2025,
        orden=_ORDEN_2025,
        source_default=_SOURCE_2025,
        manifest_extra='predecessor = "2024"\n',
        casillas=_casilla("2025", "03", lineage="nueva"),
    )
    definition = load_modelo_directory(modelo_dir)
    predecessor, successor = definition.revisions["2024"], definition.revisions["2025"]

    assert _refs(predecessor, "01") == ((_ORDEN_2024,), (_SOURCE_2024, _OWN_SOURCE))
    assert _constraint_refs(predecessor, "01") == ((_ORDEN_2024,), (_SOURCE_2024, _OWN_SOURCE))
    assert _refs(successor, "01") == ((_ORDEN_2025,), (_SOURCE_2025, _OWN_SOURCE))
    assert _constraint_refs(successor, "01") == ((_ORDEN_2025,), (_SOURCE_2025, _OWN_SOURCE))
    assert _refs(successor, "03") == ((_ORDEN_2025,), (_SOURCE_2025,))


# ── real corpus ─────────────────────────────────────────────────────────────


def _copy_registry(destination: Path, modelo_id: str) -> Path:
    modelos = _BUNDLED_REGISTRY / "modelos"

    def ignore(directory: str, names: list[str]) -> list[str]:
        return [name for name in names if name != modelo_id] if Path(directory) == modelos else []

    shutil.copytree(_BUNDLED_REGISTRY, destination, ignore=ignore)
    return destination


def _toml_array(values: tuple[str, ...]) -> str:
    return json.dumps(list(values), ensure_ascii=False)


def _lift_restated_references(modelo_dir: Path, reference: dict[str, ModeloRevision]) -> Counter[str]:
    """Delete every row or constraints value equal to its edition's default, and declare that default once.

    The default is each edition's modal row ``source_refs``. A value on its own
    line belongs to a casilla row or to a ``constraints`` sub-table, both of
    which take the defaults; a value closing an inline table is a
    ``constraints`` inline table. Returns how many statements of each spelling
    were deleted, so a caller can prove it deleted any.
    """
    removed: Counter[str] = Counter()
    for revision_id, revision in reference.items():
        modal = Counter(tuple(casilla.source_refs) for casilla in revision.casillas).most_common(1)[0][0]
        edition_dir = modelo_dir / "revisions" / revision_id
        line_source = f"\nsource_refs = {_toml_array(modal)}\n"
        line_orden = f"\nlegal_refs = {_toml_array(tuple(revision.orden_aplicabilidad))}\n"
        inline_source = f", source_refs = {_toml_array(modal)} }}"
        for fragment in sorted((edition_dir / "casillas").glob("*.toml")):
            text = fragment.read_text(encoding="utf-8")
            removed["line source_refs"] += text.count(line_source)
            removed["line legal_refs"] += text.count(line_orden)
            removed["inline source_refs"] += text.count(inline_source)
            text = text.replace(line_source, "\n").replace(line_orden, "\n").replace(inline_source, " }")
            fragment.write_text(text, encoding="utf-8", newline="\n")
        _declare_in_manifest(edition_dir, f"casilla_source_refs = {_toml_array(modal)}\n")
    return removed


def _declare_in_manifest(edition_dir: Path, declaration: str) -> None:
    manifest = edition_dir / "revision.toml"
    name = re.escape(edition_dir.name)
    header = re.compile(rf'^\[revisions\.(?:"{name}"|{name})\]\n', re.MULTILINE)
    text = manifest.read_text(encoding="utf-8")
    (match,) = header.finditer(text)
    manifest.write_text(text[: match.end()] + declaration + text[match.end() :], encoding="utf-8", newline="\n")


def _load(registry_root: Path, modelo_id: str) -> dict[str, ModeloRevision]:
    return dict(compile_validated_authority(registry_root, bundled_path()).modelo(modelo_id).revisions)


@pytest.mark.parametrize(
    ("modelo_id", "lifted_kinds"),
    [
        pytest.param(
            "303", {"line source_refs", "line legal_refs", "inline source_refs"}, id="303-constraint-references"
        ),
        pytest.param("840", {"line source_refs", "line legal_refs"}, id="840-orden-legal-refs"),
    ],
)
def test_lifting_restated_references_to_the_edition_leaves_every_edition_unchanged(
    tmp_path: Path, modelo_id: str, lifted_kinds: set[str]
) -> None:
    """A real modelo authored with the defaults means exactly what its fully restated form meant.

    Every edition's dump, apart from the new declaration itself, and every
    casilla's locale key chain are compared with the modelo as shipped.
    """
    reference = _load(_copy_registry(tmp_path / "reference" / "registry" / "aeat", modelo_id), modelo_id)
    live_root = _copy_registry(tmp_path / "live" / "registry" / "aeat", modelo_id)
    removed = _lift_restated_references(live_root / "modelos" / modelo_id, reference)

    assert {kind for kind, count in removed.items() if count} == lifted_kinds, removed
    live = _load(live_root, modelo_id)
    assert list(live) == list(reference)
    for revision_id, before in reference.items():
        after = live[revision_id]
        assert after.casilla_source_refs is not None, revision_id
        assert after.model_dump(exclude={"casilla_source_refs"}) == before.model_dump(), revision_id
        assert [casilla.localization_keys for casilla in after.casillas] == [
            casilla.localization_keys for casilla in before.casillas
        ], revision_id


def test_lifting_a_value_that_is_not_the_editions_default_changes_the_row(tmp_path: Path) -> None:
    """Teeth for the equivalence: a row whose stated source differs from the default is not left alone."""
    reference = _load(_copy_registry(tmp_path / "reference" / "registry" / "aeat", "303"), "303")
    live_root = _copy_registry(tmp_path / "live" / "registry" / "aeat", "303")
    _lift_restated_references(live_root / "modelos" / "303", reference)
    revision_id = "2025"
    modal = Counter(tuple(casilla.source_refs) for casilla in reference[revision_id].casillas).most_common(1)[0][0]
    outliers = [casilla for casilla in reference[revision_id].casillas if tuple(casilla.source_refs) != modal]
    assert outliers, "modelo 303 2025 has no row off its modal source"
    outlier = outliers[0]
    edition_dir = live_root / "modelos" / "303" / "revisions" / revision_id
    stated = f"\nsource_refs = {_toml_array(tuple(outlier.source_refs))}\n"
    fragments = [
        path for path in sorted((edition_dir / "casillas").glob("*.toml")) if stated in path.read_text("utf-8")
    ]
    assert fragments, outlier.id
    for fragment in fragments:
        fragment.write_text(fragment.read_text("utf-8").replace(stated, "\n"), encoding="utf-8", newline="\n")

    changed = {
        casilla.id
        for casilla, before in zip(
            _load(live_root, "303")[revision_id].casillas, reference[revision_id].casillas, strict=True
        )
        if casilla.model_dump() != before.model_dump()
    }
    assert outlier.id in changed
    assert all(tuple(before.source_refs) != modal for before in reference[revision_id].casillas if before.id in changed)


# ── catalogue resolution ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("declared", "failure"),
    [
        pytest.param("aeat-dr-111-2019-v18", None, id="known-source"),
        pytest.param(
            "no-such-source",
            "revision casilla_source_refs references unknown source id 'no-such-source'",
            id="unknown-source",
        ),
    ],
)
def test_the_source_default_resolves_against_the_catalogue_even_when_no_row_takes_it(
    tmp_path: Path, declared: str, failure: str | None
) -> None:
    """Every modelo 111 row states its own sources, so only the edition-level check can see the default."""
    root = _copy_registry(tmp_path / "registry" / "aeat", "111")
    _declare_in_manifest(
        root / "modelos" / "111" / "revisions" / "2019-y-siguientes", f'casilla_source_refs = ["{declared}"]\n'
    )

    if failure is not None:
        with pytest.raises(RegistryValidationError, match=re.escape(failure)):
            compile_validated_authority(root, bundled_path())
        return
    revision = compile_validated_authority(root, bundled_path()).modelo("111").revisions["2019-y-siguientes"]
    assert revision.casilla_source_refs == (declared,)
