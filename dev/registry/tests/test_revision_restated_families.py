"""An edition's authored refusal to inherit a family, and the claims it cannot make.

A delta edition inherits every family the merge carries forward, which is the
wrong reading when the official structure the successor was drawn from states a
family end to end. ``restated_families`` is the edition saying so: this family is
stated in full here, and the merge does not inherit it on this edge.

The claim withdraws real members, so it is refused in the four directions where
it would read as load-bearing while withdrawing nothing -- a family the edition
declares empty, an edition with no predecessor to decline, a family declared
twice, and a family or cause outside the closed vocabularies.

Every test drives the real directory loader over an on-disk two-edition modelo
built in ``tmp_path``. A test double here would verify the double rather than
the declaration the loader admits.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.keyed_families import INHERITED_FAMILIES
from cadrumo.domain.calculations.registry.restated_families import (
    RestatedFamilyCause,
    RestatedFamilyDeclaration,
)
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from ..compiler.loader import load_modelo_directory
from ..conformance.loader_directory_mode_support import write_standard_manifest
from .synthetic_delta_edition_support import (
    MODELO_ID,
    PREDECESSOR_EDITION,
    PREDECESSOR_EDITION_YEAR,
    SUCCESSOR_EDITION,
    SUCCESSOR_EDITION_YEAR,
    delta_casilla,
    delta_formula,
    write_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REASON: Final = "the 2025 diseno de registros lays the formula set out end to end"
_RESTATED_FORMULAS: Final = (
    f'restated_families = [{{ family = "formulas", cause = "official_structure_differs", reason = "{_REASON}" }}]\n'
)


def _build_modelo(root: Path, *, successor_extra: str = "", predecessor_extra: str = "") -> Path:
    """A two-edition modelo: a root and a delta naming it.

    Both editions state casillas and formulas, so a restatement claim about
    ``formulas`` has members behind it and a claim about ``constructs`` -- a
    family neither edition declares -- has none.
    """
    modelo_dir = root / MODELO_ID
    modelo_dir.mkdir(parents=True)
    write_standard_manifest(modelo_dir, "Test")
    write_revision(
        modelo_dir,
        PREDECESSOR_EDITION,
        year=PREDECESSOR_EDITION_YEAR,
        casillas=delta_casilla(PREDECESSOR_EDITION, "0001", number="1", lineage="base")
        + delta_casilla(PREDECESSOR_EDITION, "0002", number="2", lineage="cuota"),
        formulas=delta_formula(PREDECESSOR_EDITION, f"modelo-999-{PREDECESSOR_EDITION}-cuota", target="0002"),
        extra_manifest=predecessor_extra,
    )
    write_revision(
        modelo_dir,
        SUCCESSOR_EDITION,
        year=SUCCESSOR_EDITION_YEAR,
        predecessor=PREDECESSOR_EDITION,
        casillas=delta_casilla(SUCCESSOR_EDITION, "0002", number="22", lineage="cuota"),
        formulas=delta_formula(SUCCESSOR_EDITION, f"modelo-999-{SUCCESSOR_EDITION}-cuota", target="0002"),
        extra_manifest=successor_extra,
    )
    return modelo_dir


def _successor(modelo_dir: Path) -> ModeloRevision:
    return load_modelo_directory(modelo_dir).revisions[SUCCESSOR_EDITION]


def test_an_authored_restatement_reaches_the_successor_revision(tmp_path: Path) -> None:
    """The declared family, cause and reason survive the load as typed members."""
    revision = _successor(_build_modelo(tmp_path, successor_extra=_RESTATED_FORMULAS))

    assert len(revision.restated_families) == 1
    entry = revision.restated_families[0]
    assert entry.family == "formulas"
    assert entry.cause is RestatedFamilyCause.OFFICIAL_STRUCTURE_DIFFERS
    assert entry.reason == _REASON


def test_a_restatement_round_trips_through_the_authority_serialisation(tmp_path: Path) -> None:
    """The claim survives the JSON the published authority artifact is built from.

    An authored withdrawal that serialised away would leave the artifact
    inheriting what the edition declined, so the round trip is the same claim on
    both sides, and an edition declaring nothing must still emit no key at all.
    """
    revision = _successor(_build_modelo(tmp_path, successor_extra=_RESTATED_FORMULAS))

    payload = revision.model_dump()
    assert [dict(entry) for entry in payload["restated_families"]] == [
        {
            "family": "formulas",
            "cause": RestatedFamilyCause.OFFICIAL_STRUCTURE_DIFFERS,
            "reason": _REASON,
        }
    ]
    restored = tuple(
        RestatedFamilyDeclaration.model_validate_json(entry.model_dump_json()) for entry in revision.restated_families
    )
    assert restored == revision.restated_families

    silent = _successor(_build_modelo(tmp_path / "silent"))
    assert silent.restated_families == ()
    assert "restated_families" not in silent.model_dump()


def test_restating_a_family_the_edition_declares_empty_is_refused(tmp_path: Path) -> None:
    """A family with no stated members restates nothing while reading as though it did."""
    empty_family = (
        'restated_families = [{ family = "constructs", cause = "official_structure_differs", '
        f'reason = "{_REASON}" }}]\n'
    )
    with pytest.raises(RegistryLoadError, match="restated in full but declares no"):
        load_modelo_directory(_build_modelo(tmp_path, successor_extra=empty_family))


def test_a_restatement_on_a_root_edition_is_refused(tmp_path: Path) -> None:
    """A root edition inherits nothing on any family, so it has no edge to decline."""
    with pytest.raises(RegistryLoadError, match="no declared predecessor"):
        load_modelo_directory(_build_modelo(tmp_path, predecessor_extra=_RESTATED_FORMULAS))


def test_one_family_restated_twice_is_refused(tmp_path: Path) -> None:
    """Two authored reasons for one merge decision leave no rule for picking between them."""
    duplicated = (
        'restated_families = [{ family = "formulas", cause = "official_structure_differs", '
        f'reason = "{_REASON}" }}, {{ family = "formulas", cause = "official_structure_differs", '
        'reason = "a second, differently worded claim about the same family" }]\n'
    )
    with pytest.raises(RegistryLoadError, match="restated twice"):
        load_modelo_directory(_build_modelo(tmp_path, successor_extra=duplicated))


def test_a_family_the_merge_never_inherits_is_refused(tmp_path: Path) -> None:
    """A name outside the merge vocabulary declines nothing, so the declaration is refused.

    The name is chosen against the live vocabulary rather than pinned. This test
    named ``bindings`` while bindings were full copy in every edition; they are
    inherited now, and the pin then proved the opposite of its own docstring by
    refusing for a different reason. Every canonical family being inherited is
    itself a legitimate state, and what stays true across it is that a family
    the merge never carries forward declines nothing.
    """
    never_inherited = "una-familia-que-el-registro-no-declara"
    assert never_inherited not in INHERITED_FAMILIES, "the chosen name must lie outside the merge vocabulary"
    not_inherited = (
        f'restated_families = [{{ family = "{never_inherited}", cause = "official_structure_differs", '
        f'reason = "{_REASON}" }}]\n'
    )
    with pytest.raises(RegistryLoadError, match="is not inherited along a predecessor chain"):
        load_modelo_directory(_build_modelo(tmp_path, successor_extra=not_inherited))


def test_restating_casillas_is_refused_until_the_casilla_pass_honours_it(tmp_path: Path) -> None:
    """Casillas inherit through their own loader pass, which never reads the declaration."""
    assert "casillas" in INHERITED_FAMILIES
    casillas = (
        f'restated_families = [{{ family = "casillas", cause = "official_structure_differs", reason = "{_REASON}" }}]\n'
    )
    with pytest.raises(RegistryLoadError, match="restated family 'casillas' is not honoured"):
        load_modelo_directory(_build_modelo(tmp_path, successor_extra=casillas))


def test_an_unknown_cause_is_refused(tmp_path: Path) -> None:
    """The cause vocabulary is closed, so a new one is an added member, not a free string."""
    unknown_cause = (
        f'restated_families = [{{ family = "formulas", cause = "the_editor_preferred_it", reason = "{_REASON}" }}]\n'
    )
    with pytest.raises(RegistryLoadError, match="the_editor_preferred_it"):
        load_modelo_directory(_build_modelo(tmp_path, successor_extra=unknown_cause))


def test_an_empty_reason_is_refused() -> None:
    """The reason is the whole content of the claim, so a blank one is not one."""
    with pytest.raises(ValueError, match="reason"):
        RestatedFamilyDeclaration(
            family="formulas",
            cause=RestatedFamilyCause.OFFICIAL_STRUCTURE_DIFFERS,
            reason="",
        )
