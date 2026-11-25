"""Focused checks for inherited rows whose effective values meet a new default."""

from __future__ import annotations

import pytest

from cadrumo.core.toml import parse_toml
from cadrumo.domain.calculations.registry.errors import RegistryError as MigrationRefusedError
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ..edition_delta_manifest_writer import replace_authored_overrides
from ..edition_delta_row_delta_preserving import normalize_authored_override_removals, preserve_inherited_rows
from ..edition_delta_row_delta_reconstruction import simulate_storage_output
from ..edition_delta_source import Defaults, EditionSource, EditionWork, Placed, edition_delta_source_effective
from ..edition_delta_types import EditionPlan, LiftCounts, PredecessorBasis

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PREDECESSOR = str(filing_year_envelope().horizon - 1)
_SUCCESSOR = str(filing_year_envelope().horizon)


def test_an_exact_authored_claim_does_not_generate_a_second_lineage_selector() -> None:
    """A grounded override already selects the row even if its lineage moved."""
    lineage = "grounded-lineage"
    target: dict[str, object] = {
        "id": "170",
        "continuidad_id": lineage,
        "continuidad_origin": "grounded",
        "continuidad_evidence": "existing validated evidence",
    }
    source = EditionSource(
        revision_id=_SUCCESSOR,
        manifest_text="",
        manifest={
            "casilla_overrides": [{"selector": {"revision": _PREDECESSOR, "id": "170"}, "fields": target}],
        },
        table={},
        fragments=(),
        rows=(),
        origins=(),
        declarations={},
        retired=frozenset(),
        family_defaults={},
    )

    appended, replacements = preserve_inherited_rows(
        revision_id=_SUCCESSOR,
        predecessor=_PREDECESSOR,
        inherited=(
            Placed({"id": "170", "continuidad_id": "previous-lineage"}, _PREDECESSOR),
            Placed({"id": "175", "continuidad_id": lineage}, _PREDECESSOR),
        ),
        full_rows=(target,),
        source=source,
        defaults=Defaults(source_refs=None, orden=()),
        current_output=(Placed(dict(target), _SUCCESSOR),),
    )

    assert appended == ()
    assert replacements == ()


def test_authored_override_composes_default_preservation_for_unstated_inherited_row() -> None:
    inherited = Placed({"id": "170", "required": False}, _PREDECESSOR)
    existing_override = {
        "selector": {"revision": _PREDECESSOR, "id": "170"},
        "fields": {"required": True},
        "removed_fields": [],
    }
    source = EditionSource(
        revision_id=_SUCCESSOR,
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
    current = Placed({"id": "170", "required": True}, _PREDECESSOR)

    appended, replacements = preserve_inherited_rows(
        revision_id=_SUCCESSOR,
        predecessor=_PREDECESSOR,
        inherited=(inherited,),
        full_rows=(target,),
        source=source,
        defaults=Defaults(source_refs=("child-source",), orden=()),
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
        f'[revisions."{_SUCCESSOR}"]\n'
        'casilla_source_refs = ["child-source"]\n\n'
        f'[[revisions."{_SUCCESSOR}".casilla_overrides]]\n'
        f'selector = {{ revision = "{_PREDECESSOR}", id = "170" }}\n'
        "fields = { required = true }\n"
        "removed_fields = []\n"
    )
    work = EditionWork(
        plan=EditionPlan(
            revision_id=_SUCCESSOR,
            basis=PredecessorBasis.LIFT_ONLY,
            predecessor=_PREDECESSOR,
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
    rewritten = replace_authored_overrides(text, work)
    parsed = parse_toml(rewritten)["revisions"][_SUCCESSOR]["casilla_overrides"]
    assert parsed == list(replacements)
    replayed = simulate_storage_output(
        revision_id=_SUCCESSOR,
        predecessor=_PREDECESSOR,
        inherited=(inherited,),
        source=source,
        stated_rows=(),
        overrides=replacements,
        removals=(),
    )
    assert len(replayed) == 1
    effective = edition_delta_source_effective(
        replayed[0].row,
        origin=replayed[0].origin,
        revision_id=_SUCCESSOR,
        defaults=Defaults(source_refs=("child-source",), orden=()),
        declarations={},
    )
    assert effective == target, effective


def test_authored_removal_cannot_claim_an_inherited_target_row() -> None:
    inherited = Placed({"id": "170", "required": False}, _PREDECESSOR)
    source = EditionSource(
        revision_id=_SUCCESSOR,
        manifest_text="",
        manifest={"casilla_removals": [{"selector": {"revision": _PREDECESSOR, "id": "170"}}]},
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
            revision_id=_SUCCESSOR,
            predecessor=_PREDECESSOR,
            inherited=(inherited,),
            full_rows=(target,),
            source=source,
            defaults=Defaults(source_refs=("child-source",), orden=()),
            current_output=(),
        )


def test_stale_authored_field_removal_is_recomposed_against_planned_raw_parent() -> None:
    inherited = Placed({"id": "170-old", "required": False}, _PREDECESSOR)
    source = EditionSource(
        revision_id=_SUCCESSOR,
        manifest_text="",
        manifest={
            "casilla_overrides": [
                {
                    "selector": {"revision": _PREDECESSOR, "id": "170-old"},
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
    defaults = Defaults(source_refs=("child-source",), orden=())

    replacements = normalize_authored_override_removals(
        revision_id=_SUCCESSOR,
        predecessor=_PREDECESSOR,
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
    replayed = simulate_storage_output(
        revision_id=_SUCCESSOR,
        predecessor=_PREDECESSOR,
        inherited=(inherited,),
        source=source,
        stated_rows=(),
        overrides=replacements,
        removals=(),
    )
    assert len(replayed) == 1
    assert (
        edition_delta_source_effective(
            replayed[0].row,
            origin=replayed[0].origin,
            revision_id=_SUCCESSOR,
            defaults=defaults,
            declarations={},
        )
        == target
    )
