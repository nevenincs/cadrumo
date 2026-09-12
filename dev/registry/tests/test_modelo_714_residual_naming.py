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

from ..record_design_labels import (
    RecordDesignUnavailableError,
    edition_record_designs,
    record_design_source_ref,
)
from ..rename_formula_binding_identifiers import (
    REGISTRY_MODELOS_ROOT,
    binding_identifier_limit,
    plan_span_strip,
    render_retired_evolutions,
    repurposed_addresses,
    revision_binding_source_refs,
    revision_legal_refs,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

MODELO = "714"
FIXTURES = Path(__file__).parent / "fixtures"
EXPECTED_RENAMES = FIXTURES / "modelo-714-residual-binding-renames.json"


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


def test_no_address_repurpose_is_declared_while_both_names_survive() -> None:
    """An identifier evolution is about an IDENTIFIER, not about an address.

    Modelo 714's 2022 design inserts a 3-byte "Codigo pais" at 714-04 offset 927
    and pushes "Descripcion 1" to 930. The address carries a different field,
    but both names still exist, so nothing is withdrawn. Declaring one replaced
    would assert a retirement the successor edition contradicts by still
    declaring the id -- which is what the enrolment check refuses.
    """
    declared = {}
    for edition in ("2021", "2022"):
        revision_dir = REGISTRY_MODELOS_ROOT / MODELO / "revisions" / edition
        names = set()
        for path in revision_dir.rglob("*.toml"):
            if "export" in path.parts:
                continue
            table = tomllib.loads(path.read_text(encoding="utf-8")).get("revisions", {}).get(edition, {})
            names.update(
                member["id"] for member in table.get("bindings", []) or [] if isinstance(member.get("id"), str)
            )
        declared[edition] = names

    for _address, (old_id, new_id) in repurposed_addresses(MODELO, "2021", "2022").items():
        assert old_id not in declared["2022"], f"{old_id} is still declared in 2022, so it is not retired"
        assert new_id in declared["2022"]


def test_a_moved_field_is_not_reported_as_a_repurpose() -> None:
    """Detector teeth for the rule above, on the real pair that produced the refusal."""
    moved = (
        "modelo-714.714-04.bienes-y-derechos-f1-valores-cesion-terceros-deuda-publica-obligaciones-bonos-descripcion-1"
    )

    pairs = {old_id for old_id, _new_id in repurposed_addresses(MODELO, "2021", "2022").values()}

    assert moved not in pairs


def test_the_committed_131_retired_fragment_matches_what_the_generator_emits() -> None:
    """The CORPUS artefact is the thing gated, not a copy of it beside the test.

    Comparing the generator against a fixture leaves the committed fragment
    ungated: a hand-edit to the file the registry actually loads would pass. So
    the assertion is against the corpus path, which is what a hand-edit would
    have to survive.
    """
    committed = (
        REGISTRY_MODELOS_ROOT
        / "131"
        / "revisions"
        / "2025"
        / "identifier_evolutions"
        / "0001-retired-record-design-withdrawn-fields.toml"
    )
    assert committed.is_file(), "the retired fragment is missing from the corpus"

    rendered = render_retired_evolutions(
        "131",
        "2024",
        "2025",
        revision_legal_refs("131", "2025"),
        revision_binding_source_refs("131", "2025"),
    )

    assert rendered == committed.read_text(encoding="utf-8")


def test_an_evolution_cites_the_design_source_the_edition_declares() -> None:
    """Provenance is read off the registry, never spelled from a naming pattern.

    The corpus does not name design sources to one shape -- ``aeat-dr-714-2021``
    sits beside ``aeat-dr-111-2019-v18`` -- so a constructed citation is right by
    luck. This asserts the id comes from the edition's own ``source_refs``.
    """
    assert record_design_source_ref("714", "2021") == "aeat-dr-714-2021"
    assert record_design_source_ref("131", "2025") == "aeat-dr-131-2025"

    declared = set()
    for edition in ("2021", "2022"):
        manifest = REGISTRY_MODELOS_ROOT / "714" / "revisions" / edition / "revision.toml"
        table = tomllib.loads(manifest.read_text(encoding="utf-8"))["revisions"][edition]
        declared.update(table.get("source_refs", ()))
        assert record_design_source_ref("714", edition) in declared


def test_an_edition_citing_no_record_design_refuses_rather_than_naming_one(tmp_path: Path) -> None:
    """Detector teeth: a statement that cites nothing is not written at all."""
    revision_dir = tmp_path / "999" / "revisions" / "2025"
    revision_dir.mkdir(parents=True)
    (revision_dir / "revision.toml").write_text(
        '[revisions."2025"]\nvalid_from = 2025-01-01\nsource_refs = ["aeat-modelo-999-instructions"]\n',
        encoding="utf-8",
    )

    with pytest.raises(RecordDesignUnavailableError) as refusal:
        record_design_source_ref("999", "2025", modelos_root=tmp_path)

    assert "cites no record_design source" in str(refusal.value)
