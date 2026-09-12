"""An edition's authored statement that a family source default is underivable.

``casilla_source_refs`` and the per-family default key of every family enrolled
in ``FAMILY_SOURCE_DEFAULT_FIELDS``
lift a family's shared grounding onto the manifest, but only when a leading run
of references opens two of the family's statements. An edition whose rows share
no such run has nothing to lift, and a MISSING key cannot say whether that is
the case or whether nobody has lifted it yet.

``source_default_dispositions`` is the edition saying which. It is refused when
it names a family that carries no edition default at all, and when it calls
underivable a default the same edition declares -- the two directions in which
the key would read as an explanation while explaining nothing.

Every test drives the real directory loader over an on-disk TOML tree.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryLoadError

from ..compiler.loader import load_modelo_directory
from ..conformance.loader_directory_mode_support import write_standard_manifest as _write_standard_manifest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO_ID: Final = "999"
_REVISION: Final = "2025"
_ARTICLE: Final = "ley-58-2003:art-29"
_ORDEN: Final = "orden-hac-200-2024:art-1"
_CASILLA_SOURCE: Final = "aeat-dr-999-2025"
_OWN_SOURCE: Final = "aeat-nota-999"
_REASON: Final = "no leading source_refs run is shared by two rows"


def _binding(identifier: str) -> str:
    return (
        f'[[revisions."{_REVISION}".bindings]]\n'
        f'id = "{identifier}"\n'
        'provider = { kind = "manual_input", record = "page_01", field = "f", '
        'offset = 1, length = 5, data_type = "text" }\n'
        'value = { data_type = "text", channel = "text" }\n'
        f'legal_refs = ["{_ARTICLE}"]\n'
        f'source_refs = ["{_OWN_SOURCE}-{identifier}"]\n'
    )


def _casilla(casilla_id: str) -> str:
    return (
        f'[[revisions."{_REVISION}".casillas]]\n'
        f'id = "{casilla_id}"\n'
        f'number = "{casilla_id}"\n'
        'section = ["liquidacion"]\n'
        f'continuidad_id = "linaje-{casilla_id}"\n'
    )


def _tree(root: Path, *, dispositions: str) -> Path:
    """Write a modelo whose two bindings each state their own, unshared refs."""
    modelo_dir = root / _MODELO_ID
    modelo_dir.mkdir(parents=True)
    _write_standard_manifest(modelo_dir, "Test")
    revision_dir = modelo_dir / "revisions" / _REVISION
    for family in ("casillas", "bindings"):
        (revision_dir / family).mkdir(parents=True)
    (revision_dir / "revision.toml").write_text(
        f'[revisions."{_REVISION}"]\n'
        "valid_from = 2025-01-01\n"
        "valid_to = 2025-12-31\n"
        'period_selector = { years = [2025], periods = ["0A"] }\n'
        f'legal_refs = ["{_ARTICLE}"]\n'
        'source_refs = ["aeat-manual"]\n'
        f'orden_aplicabilidad = ["{_ORDEN}"]\n'
        f'casilla_source_refs = ["{_CASILLA_SOURCE}"]\n'
        f"{dispositions}",
        encoding="utf-8",
        newline="\n",
    )
    (revision_dir / "casillas" / "0001-casillas.toml").write_text(
        _casilla("01") + _casilla("02"), encoding="utf-8", newline="\n"
    )
    (revision_dir / "bindings" / "0001-bindings.toml").write_text(
        _binding("b-uno") + _binding("b-dos"), encoding="utf-8", newline="\n"
    )
    return modelo_dir


def _disposition(family: str) -> str:
    return (
        f'\n[revisions."{_REVISION}".source_default_dispositions.{family}]\n'
        'kind = "underivable"\n'
        f'reason = "{_REASON}"\n'
    )


def test_an_authored_disposition_reaches_the_revision(tmp_path: Path) -> None:
    """A family with no derivable default carries its reason onto the loaded revision."""
    revision = load_modelo_directory(_tree(tmp_path, dispositions=_disposition("bindings"))).revisions[_REVISION]

    disposition = revision.source_default_dispositions["bindings"]
    assert disposition.kind == "underivable"
    assert disposition.reason == _REASON
    # The claim is per family: the casilla default the edition DOES declare is untouched.
    assert revision.casilla_source_refs == (_CASILLA_SOURCE,)
    assert "casillas" not in revision.source_default_dispositions


def test_a_disposition_for_a_family_carrying_no_default_is_refused(tmp_path: Path) -> None:
    """A key naming no source-default family explains nothing while reading as though it did."""
    with pytest.raises(RegistryLoadError, match="declares no edition source default"):
        load_modelo_directory(_tree(tmp_path, dispositions=_disposition("deadline_windows")))


def test_a_disposition_contradicting_a_declared_default_is_refused(tmp_path: Path) -> None:
    """An edition cannot call underivable the very default it declares."""
    with pytest.raises(RegistryLoadError, match="casilla_source_refs"):
        load_modelo_directory(_tree(tmp_path, dispositions=_disposition("casillas")))
