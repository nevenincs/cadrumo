"""Edition-level source defaults for the keyed families enrolled beyond casillas, bindings and formulas.

An edition declares each keyed family's shared source grounding once on its
manifest -- ``application_link_source_refs`` for ``application_links``,
``applicability_source_refs`` for ``applicability``, and so on for every pair in
``FAMILY_SOURCE_DEFAULT_FIELDS``. The loader fills each into the rows of its OWN
family that state no ``source_refs``, which is the same member-side rule the
binding and formula families already carry.

The enrolment is the pairing table, so the proofs here are that the table is
what the loader reads: every declared key reaches the typed revision, a key
outside the table is still refused, and a member INHERITED from a predecessor
takes the successor edition's default rather than the predecessor's -- source
references are declared per edition, and the defaults run on the materialised
edition for exactly that reason.

Every test drives the real directory loader over an on-disk TOML tree.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.reference_sections import FAMILY_SOURCE_DEFAULT_FIELDS

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
    for _family, default_field in FAMILY_SOURCE_DEFAULT_FIELDS
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


def test_an_inherited_member_takes_the_successors_family_default(tmp_path: Path) -> None:
    """Source references are declared per edition: the row arrives from 2024 and is grounded by 2025."""
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
    assert tuple(str(ref) for ref in inherited.source_refs) == successor_default
    assert tuple(str(ref) for ref in revision.application_link_source_refs or ()) == successor_default
    # The row states no legal_refs default of its own: these families carry no
    # orden_aplicabilidad fill, so its authored legal grounding survives whole.
    assert tuple(str(ref) for ref in inherited.legal_refs) == (_ARTICLE,)


def test_without_the_successors_default_an_inherited_member_stating_no_source_is_refused(tmp_path: Path) -> None:
    """Nothing is inferred and nothing carries forward: the predecessor's default does not reach the successor."""
    modelo_dir = _modelo(tmp_path)
    _write_edition(
        modelo_dir,
        "2024",
        year=2024,
        defaults=_stated(_APPLICATION_LINK_DEFAULT, ("aeat-procedimiento-2024",)),
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

    with pytest.raises(RegistryLoadError, match=r"(?s)invalid revision '2025'.*application_links\.0\.source_refs"):
        load_modelo_directory(modelo_dir)
