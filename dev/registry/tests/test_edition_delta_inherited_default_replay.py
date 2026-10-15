"""Focused checks for inherited rows whose effective values meet a new default."""

from __future__ import annotations

import pytest

from cadrumo.core.toml import parse_toml
from cadrumo.domain.calculations.registry.errors import RegistryError as MigrationRefusedError

from ..edition_delta_manifest_writer import _replace_authored_overrides
from ..edition_delta_row_delta_existing import normalize_authored_override_removals, preserve_inherited_rows
from ..edition_delta_row_delta_reconstruction import _simulate_storage_output
from ..edition_delta_source import _Defaults, _EditionSource, _EditionWork, _effective, _Placed
from ..edition_delta_types import EditionPlan, LiftCounts, PredecessorBasis

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_authored_override_composes_default_preservation_for_unstated_inherited_row() -> None:
    inherited = _Placed({"id": "170", "required": False}, "2024")
    existing_override = {
        "selector": {"revision": "2024", "id": "170"},
        "fields": {"required": True},
        "removed_fields": [],
    }
    source = _EditionSource(
        revision_id="2025",
        manifest_text="",
        manifest={"casilla_overrides": [existing_override]},
        table={},
        fragments=(),
        rows=(),
        origins=(),
        declarations={},
        retired=frozenset(),
        family_defaults={},
    )
    target: dict[str, object] = {"id": "170", "required": True, "source_refs": ["parent-source"]}
    current = _Placed({"id": "170", "required": True}, "2024")

    appended, replacements = preserve_inherited_rows(
        revision_id="2025",
        predecessor="2024",
        inherited=(inherited,),
        full_rows=(target,),
        source=source,
        defaults=_Defaults(source_refs=("child-source",), orden=()),
        current_output=(current,),
    )

    assert appended == ()
    assert len(replacements) == 1
    assert replacements[0]["selector"] == existing_override["selector"]
    assert replacements[0]["fields"] == {
        "required": True,
        "source_refs": ["parent-source"],
    }, replacements[0]
    text = (
        '[revisions."2025"]\n'
        'casilla_source_refs = ["child-source"]\n\n'
        '[[revisions."2025".casilla_overrides]]\n'
        'selector = { revision = "2024", id = "170" }\n'
        "fields = { required = true }\n"
        "removed_fields = []\n"
    )
    work = _EditionWork(
        plan=EditionPlan(
            revision_id="2025",
            basis=PredecessorBasis.LIFT_ONLY,
            predecessor="2024",
            blocked=(),
            source_default=None,
            source_default_withheld=None,
            rows_before=0,
            stated_ids=(),
            inherited_ids=(),
            lifted=LiftCounts(),
            kept={},
            not_exact=(),
            comments_dropped=0,
            reviewed_against=None,
        ),
        source=source,
        lifts={},
        root_declaration=None,
        casilla_override_replacements=replacements,
    )
    rewritten = _replace_authored_overrides(text, work)
    parsed = parse_toml(rewritten)["revisions"]["2025"]["casilla_overrides"]
    assert parsed == list(replacements)
    replayed = _simulate_storage_output(
        revision_id="2025",
        predecessor="2024",
        inherited=(inherited,),
        source=source,
        stated_rows=(),
        overrides=replacements,
        removals=(),
    )
    assert len(replayed) == 1
    effective = _effective(
        replayed[0].row,
        origin=replayed[0].origin,
        revision_id="2025",
        defaults=_Defaults(source_refs=("child-source",), orden=()),
        declarations={},
    )
    assert effective == target, effective


def test_authored_removal_cannot_claim_an_inherited_target_row() -> None:
    inherited = _Placed({"id": "170", "required": False}, "2024")
    source = _EditionSource(
        revision_id="2025",
        manifest_text="",
        manifest={"casilla_removals": [{"selector": {"revision": "2024", "id": "170"}}]},
        table={},
        fragments=(),
        rows=(),
        origins=(),
        declarations={},
        retired=frozenset(),
        family_defaults={},
    )
    target: dict[str, object] = {"id": "170", "required": False, "source_refs": ["parent-source"]}

    with pytest.raises(MigrationRefusedError, match="removes or relocates inherited casilla '170'"):
        preserve_inherited_rows(
            revision_id="2025",
            predecessor="2024",
            inherited=(inherited,),
            full_rows=(target,),
            source=source,
            defaults=_Defaults(source_refs=("child-source",), orden=()),
            current_output=(),
        )


def test_stale_authored_field_removal_is_recomposed_against_planned_raw_parent() -> None:
    inherited = _Placed({"id": "170-old", "required": False}, "2024")
    source = _EditionSource(
        revision_id="2025",
        manifest_text="",
        manifest={
            "casilla_overrides": [
                {
                    "selector": {"revision": "2024", "id": "170-old"},
                    "fields": {"id": "170", "required": True},
                    "removed_fields": ["source_refs"],
                    "restate_provenance": True,
                }
            ]
        },
        table={},
        fragments=(),
        rows=(),
        origins=(),
        declarations={},
        retired=frozenset(),
        family_defaults={},
    )
    target: dict[str, object] = {"id": "170", "required": True, "source_refs": ["parent-source"]}
    defaults = _Defaults(source_refs=("child-source",), orden=())

    replacements = normalize_authored_override_removals(
        revision_id="2025",
        predecessor="2024",
        inherited=(inherited,),
        full_rows=(target,),
        source=source,
        defaults=defaults,
    )

    assert len(replacements) == 1
    assert replacements[0]["fields"] == {
        "id": "170",
        "required": True,
        "source_refs": ["parent-source"],
    }
    assert replacements[0]["removed_fields"] == []
    assert replacements[0]["restate_provenance"] is True
    replayed = _simulate_storage_output(
        revision_id="2025",
        predecessor="2024",
        inherited=(inherited,),
        source=source,
        stated_rows=(),
        overrides=replacements,
        removals=(),
    )
    assert len(replayed) == 1
    assert (
        _effective(
            replayed[0].row,
            origin=replayed[0].origin,
            revision_id="2025",
            defaults=defaults,
            declarations={},
        )
        == target
    )
