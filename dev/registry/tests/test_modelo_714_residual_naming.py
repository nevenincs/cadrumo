"""The modelo 714 residual naming, checked against an independently derived oracle.

The rule under test is not a transformation of a string: it is a claim about what
the official record design says. So the expected map is not recomputed here from
the same code that produces it -- that would assert only that the tool is
self-consistent. It is a fixture derived from the designs before the tool could
produce it, and these cases compare the tool's live plan against it.

The corpus is read, never written. The 714 tree is the real one, so a rename that
lands in the corpus changes what these cases see: after the apply, the ids the
fixture names as ``old_id`` no longer exist and the plan is legitimately empty.
Each case states which side of that it asserts.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest

from ..record_design_labels import edition_record_designs
from ..rename_formula_binding_identifiers import (
    REGISTRY_MODELOS_ROOT,
    binding_identifier_limit,
    plan_span_strip,
    render_repurposed_evolutions,
    repurposed_addresses,
    revision_legal_refs,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

MODELO = "714"
FIXTURES = Path(__file__).parent / "fixtures"
EXPECTED_RENAMES = FIXTURES / "modelo-714-residual-binding-renames.json"
EXPECTED_EVOLUTIONS = FIXTURES / "modelo-714-expected-identifier-evolutions.toml"


def _expected() -> dict[tuple[str, str], str]:
    document = json.loads(EXPECTED_RENAMES.read_text(encoding="utf-8"))
    return {(row["edition"], row["old_id"]): row["new_id"] for row in document["renames"]}


def _planned() -> dict[tuple[str, str], str]:
    plan = plan_span_strip(MODELO)
    return {(strip.edition, strip.old_id): strip.new_id for strip in plan.strips}


def test_every_planned_rename_matches_the_design_derived_oracle() -> None:
    """The tool names each slot exactly as the record designs do, or it names none left to name.

    Once the pass has been applied the plan is empty, because no id ends in its
    own provider address any more; that is success, not a vacuous assertion, and
    the emptiness is checked against the corpus rather than assumed.
    """
    expected = _expected()
    planned = _planned()

    if not planned:
        declared = {
            member["id"]
            for revision_dir in sorted((REGISTRY_MODELOS_ROOT / MODELO / "revisions").iterdir())
            for path in revision_dir.rglob("*.toml")
            if "export" not in path.parts
            for member in (tomllib.loads(path.read_text(encoding="utf-8")).get("revisions", {}))
            .get(revision_dir.name, {})
            .get("bindings", [])
            or []
            if isinstance(member.get("id"), str)
        }
        # The pass has run: every old id is gone and every new id is present.
        assert not {old_id for _edition, old_id in expected} & declared
        assert set(expected.values()) <= declared
        return

    assert planned == expected


def test_every_expected_name_is_readable_off_the_record_design() -> None:
    """Independence check: each expected name comes from the design, not from the tool.

    Without this the fixture could drift into a record of whatever the tool once
    emitted. The check keys on the EXPECTED NEW id, which exists in the corpus
    after the pass and is what the fixture asserts, so it holds on both sides of
    the apply: each name must end either in the design's own field component for
    that row or in that row's own ordinal, and nothing else may account for it.
    """
    from ..record_design_labels import design_field_component

    designs = edition_record_designs(MODELO)
    addresses: dict[tuple[str, str], tuple[object, int]] = {}
    for revision_dir in sorted((REGISTRY_MODELOS_ROOT / MODELO / "revisions").iterdir()):
        edition = revision_dir.name
        for path in revision_dir.rglob("*.toml"):
            if "export" in path.parts:
                continue
            table = tomllib.loads(path.read_text(encoding="utf-8")).get("revisions", {}).get(edition, {})
            for member in table.get("bindings", []) or []:
                provider = member.get("provider") or {}
                if isinstance(member.get("id"), str) and isinstance(provider.get("offset"), int):
                    addresses[(edition, member["id"])] = (provider.get("record"), provider["offset"])

    checked = 0
    for (edition, old_id), new_id in _expected().items():
        address = addresses.get((edition, new_id)) or addresses.get((edition, old_id))
        assert address is not None, f"{edition}: neither {old_id} nor {new_id} is declared"
        row = designs[edition].get(address)
        assert row is not None, f"{edition} {new_id} has no design row at {address}"
        by_label = new_id.endswith(f"-{design_field_component(row.label)}")
        by_ordinal = new_id.endswith(f"-fila-{row.ordinal}")
        assert by_label or by_ordinal, f"{new_id} matches neither the design label nor its row ordinal"
        checked += 1
    assert checked == len(_expected()), "the oracle was not fully compared"


def test_no_expected_name_carries_its_own_provider_offset() -> None:
    """The whole point of the rule, asserted against the oracle rather than the implementation."""
    expected = _expected()
    corpus_offsets = {
        (edition, old_id): int(old_id.rsplit("-", 1)[-1])
        for edition, old_id in expected
        if old_id.rsplit("-", 1)[-1].isdigit()
    }

    for (edition, old_id), new_id in expected.items():
        offset = corpus_offsets.get((edition, old_id))
        if offset is None:
            continue
        assert not new_id.endswith(f"-{offset}"), f"{new_id} still ends in the offset {offset}"


def test_every_expected_name_fits_the_identifier_the_loader_accepts() -> None:
    """A name the schema would refuse is not a name; the limit is read off the shipped type."""
    limit = binding_identifier_limit()

    over = sorted({new_id for new_id in _expected().values() if len(new_id) > limit})

    assert not over, f"{len(over)} expected names exceed the {limit}-character BindingId limit"


def test_the_rendered_evolutions_match_the_committed_fragment() -> None:
    """The emitted fragment is compared byte-for-byte with the one the corpus carries.

    The generator reads the corpus and the designs as they stand, so this holds
    before and after the rename: a repurposed address is a fact about the two
    designs, and the two ids naming it are whatever the corpus currently spells.
    A drift in either the designs, the corpus, or the renderer shows up here.
    """
    rendered = render_repurposed_evolutions(MODELO, "2021", "2022", revision_legal_refs(MODELO, "2022"))

    assert rendered == EXPECTED_EVOLUTIONS.read_text(encoding="utf-8")


def test_every_declared_evolution_names_an_address_both_designs_disagree_about() -> None:
    """Detector teeth: a row here must be a real repurpose, not a moved or renamed field.

    An address whose two designs declare the same width and the same field is
    the same slot, and declaring it replaced would assert a discontinuity the
    designs deny.
    """
    from ..record_design_labels import design_field_component

    designs = edition_record_designs(MODELO)
    addresses = repurposed_addresses(MODELO, "2021", "2022")

    assert addresses, "no repurposed address found, so this case proves nothing"
    for address in addresses:
        was, now = designs["2021"][address], designs["2022"][address]
        assert was.length != now.length or design_field_component(was.label) != design_field_component(now.label)
