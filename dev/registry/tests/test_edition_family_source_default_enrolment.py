"""Edition-level source defaults for the keyed families enrolled beyond casillas, bindings and formulas.

An edition declares each keyed family's shared source grounding once on its
manifest -- ``application_link_source_refs`` for ``application_links``,
``applicability_source_refs`` for ``applicability``, and so on for every pair in
``CANONICAL_FAMILY_SPECS``. The loader fills each into the rows of its OWN
family that state no ``source_refs``, which is the same member-side rule the
binding and formula families already carry.

The enrolment is the pairing table, so the proofs here are that the table is
what the loader reads: every declared key reaches the typed revision, a key
outside the table is still refused, and a member INHERITED from a predecessor
keeps the default effective where it was stated rather than taking the
successor's -- a source that never saw the row cannot be made to attest it, so
inheritance pins the grounding and the successor's default fills only the rows
the successor states.

Every test drives the real directory loader over an on-disk TOML tree.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.keyed_families import (
    CANONICAL_FAMILY_SPECS,
    CASILLAS_FAMILY,
    family_source_default_fields,
    inline_family_source_default,
)
from cadrumo.domain.calculations.registry.schema import REVISION_MANIFEST_ONLY_FIELDS, ModeloRevision

from ..compiler.loader import load_modelo_directory
from ..conformance.loader_directory_mode_support import write_standard_manifest as _write_standard_manifest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO_ID: Final = "999"
_ARTICLE: Final = "ley-58-2003:art-29"
_ORDEN: Final = "orden-hac-200-2024:art-1"
_CASILLA_SOURCE: Final = "aeat-dr-999"

#: One declared value per enrolled family, distinct per key so a family taking
#: another family's default is a visibly wrong value rather than a pass.
_DECLARED: Final[dict[str, tuple[str, ...]]] = {
    default_field: (f"aeat-{default_field.replace('_', '-')}",)
    for _family, default_field in family_source_default_fields()
}
_APPLICATION_LINK_DEFAULT: Final = "application_link_source_refs"


def _stated(key: str, refs: tuple[str, ...]) -> str:
    return f"{key} = {json.dumps(list(refs))}\n"


def _casilla(casilla_id: str) -> str:
    return (
        f'id = "{casilla_id}"\n'
        f'number = "{casilla_id}"\n'
        'section = ["liquidacion"]\n'
        f'continuidad_id = "linaje-{casilla_id}"\n'
    )


def _application_link(identifier: str, refs: str) -> str:
    return (
        f'id = "{identifier}"\n'
        'surface = "filing"\n'
        'consumer = "cadrumo.application.filing"\n'
        "requires_snapshot = true\n"
        f'legal_refs = ["{_ARTICLE}"]\n'
        f"{refs}"
    )


def _write_edition(
    modelo_dir: Path,
    revision_id: str,
    *,
    year: int,
    defaults: str,
    casilla_ids: tuple[str, ...],
    application_links: tuple[str, ...] = (),
    extra: str = "",
) -> None:
    revision_dir = modelo_dir / "revisions" / revision_id
    (revision_dir / "casillas").mkdir(parents=True)
    (revision_dir / "revision.toml").write_text(
        f'[revisions."{revision_id}"]\n'
        f"valid_from = {year}-01-01\n"
        f"valid_to = {year}-12-31\n"
        f'period_selector = {{ years = [{year}], periods = ["0A"] }}\n'
        f'legal_refs = ["{_ARTICLE}"]\n'
        'source_refs = ["aeat-manual"]\n'
        f'orden_aplicabilidad = ["{_ORDEN}"]\n' + _stated("casilla_source_refs", (_CASILLA_SOURCE,)) + defaults + extra,
        encoding="utf-8",
        newline="\n",
    )
    (revision_dir / "casillas" / "0001-casillas.toml").write_text(
        "".join(f'[[revisions."{revision_id}".casillas]]\n{_casilla(casilla_id)}\n' for casilla_id in casilla_ids),
        encoding="utf-8",
        newline="\n",
    )
    if application_links:
        section = revision_dir / "application_links"
        section.mkdir()
        (section / "0001-application-links.toml").write_text(
            "".join(f'[[revisions."{revision_id}".application_links]]\n{row}\n' for row in application_links),
            encoding="utf-8",
            newline="\n",
        )


def _modelo(tmp_path: Path) -> Path:
    modelo_dir = tmp_path / _MODELO_ID
    modelo_dir.mkdir()
    _write_standard_manifest(modelo_dir, "Test")
    return modelo_dir


def test_every_enrolled_family_default_reaches_the_typed_revision(tmp_path: Path) -> None:
    """The manifest keys are the model's own fields, so each declared value arrives whole and on its own field."""
    modelo_dir = _modelo(tmp_path)
    _write_edition(
        modelo_dir,
        "2025",
        year=2025,
        defaults="".join(_stated(key, refs) for key, refs in _DECLARED.items()),
        casilla_ids=("01",),
    )

    revision = load_modelo_directory(modelo_dir).revisions["2025"]

    assert {key: tuple(str(ref) for ref in getattr(revision, key)) for key in _DECLARED} == _DECLARED


def test_a_manifest_key_outside_the_enrolment_is_still_refused(tmp_path: Path) -> None:
    """The teeth of the proof above: the manifest is not an open bag, so the keys are enrolment and not looseness."""
    modelo_dir = _modelo(tmp_path)
    _write_edition(
        modelo_dir,
        "2025",
        year=2025,
        defaults=_stated("deadline_window_source_refs", ("aeat-plazos",)),
        casilla_ids=("01",),
    )

    with pytest.raises(RegistryLoadError, match="deadline_window_source_refs"):
        load_modelo_directory(modelo_dir)


def test_an_inherited_member_keeps_the_grounding_effective_at_its_origin(tmp_path: Path) -> None:
    """An inherited row keeps the source default of the edition that stated it.

    The successor's default fills the rows the successor states; it does not
    re-ground a row it inherited unchanged. Re-grounding would assert that the
    successor's source attests a row that source never saw, which is inventing
    evidence from shared payload. ``_pin_family_source_default`` binds the row
    to its origin's default during inheritance, so the edition default later
    finds it already grounded and leaves it alone.

    This asserted the opposite while only casillas were inherited, and casillas
    are still not pinned: they carry their own lineage and are re-grounded by
    the edition they land in.
    """
    modelo_dir = _modelo(tmp_path)
    predecessor_default = ("aeat-procedimiento-2024",)
    successor_default = ("aeat-procedimiento-2025",)
    _write_edition(
        modelo_dir,
        "2024",
        year=2024,
        defaults=_stated(_APPLICATION_LINK_DEFAULT, predecessor_default),
        casilla_ids=("01",),
        application_links=(_application_link("enlace-filing", ""),),
    )
    _write_edition(
        modelo_dir,
        "2025",
        year=2025,
        defaults=_stated(_APPLICATION_LINK_DEFAULT, successor_default),
        casilla_ids=("01",),
        extra='predecessor = "2024"\n',
    )

    revision = load_modelo_directory(modelo_dir).revisions["2025"]

    (inherited,) = revision.application_links
    assert str(inherited.id) == "enlace-filing"
    assert tuple(str(ref) for ref in inherited.source_refs) == predecessor_default
    assert tuple(str(ref) for ref in revision.application_link_source_refs or ()) == successor_default
    # The row states no legal_refs default of its own: these families carry no
    # orden_aplicabilidad fill, so its authored legal grounding survives whole.
    assert tuple(str(ref) for ref in inherited.legal_refs) == (_ARTICLE,)


def test_a_member_no_edition_ever_grounded_is_refused(tmp_path: Path) -> None:
    """Pinning carries a stated grounding forward; it never invents one.

    The origin declares no default either, so the inherited row reaches typed
    construction with no ``source_refs`` at all and is refused there. This is
    the tooth of the pin above: without it, "keeps its origin's grounding"
    would be satisfiable by a row that has none.
    """
    modelo_dir = _modelo(tmp_path)
    _write_edition(
        modelo_dir,
        "2024",
        year=2024,
        defaults="",
        casilla_ids=("01",),
        application_links=(_application_link("enlace-filing", ""),),
    )
    _write_edition(
        modelo_dir,
        "2025",
        year=2025,
        defaults="",
        casilla_ids=("01",),
        extra='predecessor = "2024"\n',
    )

    # Refused on 2024, where the ungrounded row is stated, rather than on the
    # edition that inherits it: the defect is the statement, not the inheritance.
    with pytest.raises(RegistryLoadError, match=r"(?s)invalid revision '2024'.*application_links\.0\.source_refs"):
        load_modelo_directory(modelo_dir)


def test_the_enrolment_is_the_family_table_and_names_real_manifest_fields() -> None:
    """The pairing has one home, so a family's default cannot drift from its policy.

    Each pair comes from the family's own ``source_default_key``, and each key
    must be a field an edition can actually declare on its manifest. A pair
    naming a field the schema does not carry would be an enrolment the loader
    fills from and the author can never state.
    """
    pairs = family_source_default_fields()

    assert pairs == tuple(
        (spec.section, spec.source_default_key)
        for spec in CANONICAL_FAMILY_SPECS
        if spec.source_default_key is not None and spec.section != CASILLAS_FAMILY
    )
    for section, default_field in pairs:
        assert default_field in ModeloRevision.model_fields, default_field
        assert default_field in REVISION_MANIFEST_ONLY_FIELDS, default_field
        assert section in ModeloRevision.model_fields, section


def test_no_two_families_are_grounded_from_one_declared_default() -> None:
    """A family's grounding is its own document, so one key can never serve two.

    The teeth of the pairing: bindings cite a record design and formulas the
    approving orden's instructions, so a shared key would let one family attest
    from a source that describes the other.
    """
    default_fields = [default_field for _section, default_field in family_source_default_fields()]
    sections = [section for section, _default_field in family_source_default_fields()]

    assert len(set(default_fields)) == len(default_fields)
    assert len(set(sections)) == len(sections)
    assert CASILLAS_FAMILY not in sections


def test_a_member_stating_its_own_grounding_keeps_it_whole() -> None:
    """A stated ``source_refs`` replaces the edition default rather than merging with it."""
    member = {"id": "enlace", "source_refs": ("aeat-row-own",)}
    edition = {_APPLICATION_LINK_DEFAULT: ("aeat-edition",)}

    bound = inline_family_source_default(member, edition, _APPLICATION_LINK_DEFAULT)

    assert bound is member


def test_a_member_stating_additions_takes_the_default_first_then_its_own() -> None:
    """Additions extend the edition's grounding; the default leads and each reference appears once."""
    member = {"id": "enlace", "additional_source_refs": ("aeat-extra", "aeat-edition")}
    edition = {_APPLICATION_LINK_DEFAULT: ("aeat-edition",)}

    bound = inline_family_source_default(member, edition, _APPLICATION_LINK_DEFAULT)

    assert bound["source_refs"] == ("aeat-edition", "aeat-extra")
    assert "additional_source_refs" not in bound


def test_an_edition_declaring_no_default_binds_nothing() -> None:
    """Nothing to bind leaves the member exactly as authored, for typed construction to judge.

    Identity, not equality: the loader tells whether an edition changed a row by
    whether the row it gets back is the row it passed in.
    """
    member = {"id": "enlace"}

    assert inline_family_source_default(member, {}, _APPLICATION_LINK_DEFAULT) is member
    assert inline_family_source_default(member, {_APPLICATION_LINK_DEFAULT: ()}, _APPLICATION_LINK_DEFAULT) is member
    assert inline_family_source_default(member, {_APPLICATION_LINK_DEFAULT: ("aeat-edition",)}, None) is member
