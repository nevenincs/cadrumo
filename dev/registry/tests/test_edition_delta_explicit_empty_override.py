"""An explicit empty value survives the family collapse, and a restated value still does not.

A keyed-family member may state a field empty where the member it is stored
against leaves that field out. The typed model reads both as the same empty
default, but the storage is not the same: the chain proof compares the edition
as its chain materialises it, byte for byte, so a collapse that turned the
explicit empty into an override and then pruned that override as "equal to the
baseline" left a tree that no longer materialised as its source did, and the
proof refused it. An override leaf is redundant only where the baseline itself
states the value it repeats.

Every test builds a small modelo on disk and drives the real collapse, the real
pruning of redundant override leaves, the real assessor and the real chain
proof; nothing is mocked and no production registry corpus is read.
"""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Final

import pytest
import tomlkit

from cadrumo.core.toml import parse_toml
from cadrumo.domain.calculations.registry.errors import RegistryError

from ..compiler.loader import load_modelo_directory
from ..conformance.loader_directory_mode_support import write_standard_manifest
from ..edition_delta_migration import (
    _prove_chain,
    _prune_redundant_override_leaves,
    assess_migration_state,
)
from ..edition_family_delta import collapse_keyed_families
from ..edition_round_trip import RoundTripReport

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO_ID: Final = "999"
_REF: Final = "ley-58-2003:art-29"
_SOURCE: Final = "aeat-manual"
_BASELINE: Final = "2024"
_EDITION: Final = "2025"
_CONSTRUCT: Final = "modelo-999-liquidacion"
_CLEAN_REPORT: Final = RoundTripReport(findings=(), byte_compared_revisions=())


def _casillas(revision_id: str) -> str:
    return "".join(
        f'[[revisions."{revision_id}".casillas]]\nid = "000{index}"\nnumber = "{index}"\n'
        f'section = ["liquidacion"]\ncontinuidad_id = "linaje-{index}"\n'
        f'legal_refs = ["{_REF}"]\nsource_refs = ["{_SOURCE}"]\n\n'
        for index in range(1, 3)
    )


def _construct(revision_id: str, *, extra: str = "") -> str:
    return (
        f'[[revisions."{revision_id}".constructs]]\nid = "{_CONSTRUCT}"\ncasilla_ids = ["0001", "0002"]\n'
        f'legal_refs = ["{_REF}"]\nsource_refs = ["{_SOURCE}"]\n{extra}\n'
    )


def _edition(modelo_dir: Path, revision_id: str, *, manifest_extra: str, sections: dict[str, str]) -> None:
    year = int(revision_id)
    revision_dir = modelo_dir / "revisions" / revision_id
    revision_dir.mkdir(parents=True)
    (revision_dir / "revision.toml").write_text(
        f'[revisions."{revision_id}"]\nvalid_from = {year}-01-01\nvalid_to = {year}-12-31\n'
        f'period_selector = {{ years = [{year}], periods = ["0A"] }}\n'
        f'legal_refs = ["{_REF}"]\nsource_refs = ["{_SOURCE}"]\n' + manifest_extra,
        encoding="utf-8",
        newline="\n",
    )
    for section, text in sections.items():
        (revision_dir / section).mkdir()
        (revision_dir / section / "0001-declarations.toml").write_text(text, encoding="utf-8", newline="\n")


def _modelo(root: Path, *, construct_extra: str = "", manifest_extra: str = "", state_construct: bool = True) -> Path:
    """A 2024 root whose construct omits ``deadline_windows``, and a 2025 edition stored against it."""
    modelo_dir = root / _MODELO_ID
    modelo_dir.mkdir(parents=True)
    write_standard_manifest(modelo_dir, "Explicit empty fixture")
    _edition(
        modelo_dir,
        _BASELINE,
        manifest_extra="",
        sections={"casillas": _casillas(_BASELINE), "constructs": _construct(_BASELINE)},
    )
    _edition(
        modelo_dir,
        _EDITION,
        manifest_extra=(
            f'casilla_storage_baseline = "{_BASELINE}"\nfamily_storage_baseline = "{_BASELINE}"\n' + manifest_extra
        ),
        sections={"constructs": _construct(_EDITION, extra=construct_extra)} if state_construct else {},
    )
    return modelo_dir


def _construct_overrides(modelo_dir: Path) -> list[dict[str, object]]:
    manifest = parse_toml((modelo_dir / "revisions" / _EDITION / "revision.toml").read_text(encoding="utf-8"))
    operations = manifest["revisions"][_EDITION].get("family_overrides", ())
    return [dict(item) for item in operations if isinstance(item, dict) and item.get("family") == "constructs"]


def _construct_findings(modelo_dir: Path) -> list[Mapping[str, object]]:
    return [
        item
        for item in assess_migration_state(modelo_dir).unresolved_duplication
        if item.get("revision") == _EDITION and item.get("family") == "constructs"
    ]


def _prove(reference_dir: Path, staged_dir: Path) -> RoundTripReport:
    return _prove_chain(
        reference_modelo_dir=reference_dir,
        staged_modelo_dir=staged_dir,
        revision_ids=(_BASELINE, _EDITION),
        report=_CLEAN_REPORT,
    )


def _hydrated_constructs(modelo_dir: Path) -> list[dict[str, object]]:
    revision = load_modelo_directory(modelo_dir).revisions[_EDITION]
    return [construct.model_dump(mode="json", exclude={"inherited_from"}) for construct in revision.constructs]


def test_an_explicit_empty_over_an_omitted_field_is_carried_as_an_override_and_proves(tmp_path: Path) -> None:
    """The stated ``deadline_windows = []`` becomes the edition's one override leaf and survives pruning."""
    source = _modelo(tmp_path / "source", construct_extra="deadline_windows = []\n")
    candidate = tmp_path / "candidate" / _MODELO_ID

    collapse_keyed_families(source, candidate)
    _prune_redundant_override_leaves(candidate)

    (override,) = _construct_overrides(candidate)
    assert override["selector"] == {"revision": _BASELINE, "id": _CONSTRUCT}
    assert override["fields"] == {"deadline_windows": []}
    assert not (candidate / "revisions" / _EDITION / "constructs").exists()
    assert _construct_findings(candidate) == []
    assert _hydrated_constructs(candidate) == _hydrated_constructs(source)
    assert _prove(source, candidate) == _CLEAN_REPORT


def test_the_chain_proof_refuses_the_collapse_that_drops_the_explicit_empty(tmp_path: Path) -> None:
    """Detector teeth: the same collapse with the empty leaf pruned no longer materialises as its source."""
    source = _modelo(tmp_path / "source", construct_extra="deadline_windows = []\n")
    candidate = tmp_path / "candidate" / _MODELO_ID
    collapse_keyed_families(source, candidate)
    dropped = shutil.copytree(candidate, tmp_path / "dropped" / _MODELO_ID)
    manifest_path = dropped / "revisions" / _EDITION / "revision.toml"
    document = tomlkit.parse(manifest_path.read_text(encoding="utf-8"))
    del document["revisions"][_EDITION]["family_overrides"]
    manifest_path.write_text(tomlkit.dumps(document), encoding="utf-8", newline="\n")

    assert _hydrated_constructs(dropped) == _hydrated_constructs(source)
    with pytest.raises(RegistryError, match=r"the lift is not an identity"):
        _prove(source, dropped)
    assert _prove(source, candidate) == _CLEAN_REPORT


def test_an_override_repeating_a_value_the_baseline_states_is_still_redundant_and_pruned(tmp_path: Path) -> None:
    """The normal path: a non-empty leaf equal to what the baseline states is reported and removed."""
    repeated = (
        f'[[revisions."{_EDITION}".family_overrides]]\nfamily = "constructs"\n'
        f'selector = {{ revision = "{_BASELINE}", id = "{_CONSTRUCT}" }}\n'
        'fields = { casilla_ids = ["0001", "0002"] }\n'
    )
    source = _modelo(tmp_path / "source", manifest_extra=repeated, state_construct=False)
    findings = _construct_findings(source)
    assert [(item["member"], item["fields"], item["reason"]) for item in findings] == [
        (_CONSTRUCT, ["casilla_ids"], "authored override equals hydrated baseline")
    ]
    staged = shutil.copytree(source, tmp_path / "staged" / _MODELO_ID)

    assert _prune_redundant_override_leaves(staged) == 1

    assert _construct_overrides(staged) == []
    assert _construct_findings(staged) == []
    assert _hydrated_constructs(staged) == _hydrated_constructs(source)
    assert _prove(source, staged) == _CLEAN_REPORT


def test_an_explicit_empty_override_already_authored_is_genuine_and_kept(tmp_path: Path) -> None:
    """An authored override setting the omitted field empty is not reported, so pruning leaves it alone."""
    explicit = (
        f'[[revisions."{_EDITION}".family_overrides]]\nfamily = "constructs"\n'
        f'selector = {{ revision = "{_BASELINE}", id = "{_CONSTRUCT}" }}\n'
        "fields = { deadline_windows = [] }\n"
    )
    source = _modelo(tmp_path / "source", manifest_extra=explicit, state_construct=False)
    staged = shutil.copytree(source, tmp_path / "staged" / _MODELO_ID)

    assert _construct_findings(source) == []
    assert _prune_redundant_override_leaves(staged) == 0

    assert _construct_overrides(staged) == _construct_overrides(source)
    assert _prove(source, staged) == _CLEAN_REPORT
