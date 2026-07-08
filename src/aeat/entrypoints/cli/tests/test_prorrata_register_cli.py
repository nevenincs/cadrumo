"""CLI surface tests for the cross-period IVA prorrata register verbs.

Exercises ``aeat app ledger prorrata elect-especial / elect-general / list``
through the real Typer surface against an isolated encrypted backend (state is
verified by reading it back through the ``list`` verb, the same session the
write ran under), and pins the ``upsert_entry`` sector-definition preservation
fix through the real encrypted repository under an in-process bucket session.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from ....core import ProrrataProvisionalProvenance, ProrrataRegisterRegime, SectorDiferenciadoLetra
from ....domain.prorrata_register import (
    ProrrataRegister,
    ProrrataRegisterEntry,
    SectorDefinition,
)
from ....tests.secure_sql import isolated_runtime_profile
from ._cli_surface_support import (
    _invoke,
    _json,
    create_cli_surface_profile,
    isolated_cli_surface_backend,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_cli_surface_backend(tmp_path):
        create_cli_surface_profile()
        yield


def _prorrata_list() -> dict[str, object]:
    result = _invoke(["--format", "json", "app", "ledger", "prorrata", "list"])
    assert result.exit_code == 0, result.output
    return _json(result)


def test_elect_especial_persists_especial_register_entry() -> None:
    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "prorrata",
            "elect-especial",
            "--ejercicio",
            "2025",
            "--percentage",
            "60",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = _json(result)
    assert payload["entry"]["regime"] == ProrrataRegisterRegime.ESPECIAL.value
    assert payload["entry"]["provisional_percentage"] == "60"
    assert payload["entry"]["provisional_provenance"] == (ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA.value)

    # The election reaches the persisted register read back through the list
    # verb: a subsequent live aggregation would read this ESPECIAL entry and
    # fire the art. 106 apportionment.
    listing = _prorrata_list()
    entries = listing["entries"]
    assert isinstance(entries, list) and len(entries) == 1
    assert entries[0]["ejercicio"] == 2025
    assert entries[0]["regime"] == ProrrataRegisterRegime.ESPECIAL.value
    assert entries[0]["provisional_percentage"] == "60"


def test_elect_general_persists_general_register_entry() -> None:
    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "prorrata",
            "elect-general",
            "--ejercicio",
            "2025",
            "--percentage",
            "75",
        ],
    )
    assert result.exit_code == 0, result.output
    entries = _prorrata_list()["entries"]
    assert isinstance(entries, list) and len(entries) == 1
    assert entries[0]["regime"] == ProrrataRegisterRegime.GENERAL.value
    assert entries[0]["provisional_percentage"] == "75"


def test_elect_especial_for_sector_scopes_the_entry() -> None:
    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "prorrata",
            "elect-especial",
            "--ejercicio",
            "2025",
            "--percentage",
            "40",
            "--sector",
            "alquiler",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = _json(result)
    assert payload["entry"]["sector_id"] == "alquiler"
    entries = _prorrata_list()["entries"]
    assert isinstance(entries, list) and len(entries) == 1
    assert entries[0]["sector_id"] == "alquiler"
    assert entries[0]["regime"] == ProrrataRegisterRegime.ESPECIAL.value


def test_referenced_provenance_without_reference_refuses() -> None:
    result = _invoke(
        [
            "app",
            "ledger",
            "prorrata",
            "elect-general",
            "--ejercicio",
            "2025",
            "--percentage",
            "50",
            "--provenance",
            ProrrataProvisionalProvenance.AEAT_AUTORIZADA.value,
        ],
    )
    assert result.exit_code != 0
    assert "reference" in result.output.lower()


def test_interrupted_provenance_is_not_operator_electable() -> None:
    result = _invoke(
        [
            "app",
            "ledger",
            "prorrata",
            "elect-general",
            "--ejercicio",
            "2025",
            "--percentage",
            "50",
            "--provenance",
            ProrrataProvisionalProvenance.INTERRUMPIDA_TRES_ULTIMOS.value,
        ],
    )
    assert result.exit_code != 0


def test_upsert_entry_preserves_sector_definitions(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="prorrata-preserve-sectors"):
        repository = ProrrataRegisterRepository()
        definition = SectorDefinition(
            sector_id="comercio",
            letra=SectorDiferenciadoLetra.A,
            member_activity_codes=("4711",),
        )
        repository.save(
            ProrrataRegister(
                entries=(ProrrataRegisterEntry(ejercicio=2024, regime=ProrrataRegisterRegime.GENERAL),),
                sector_definitions=(definition,),
            )
        )

        repository.upsert_entry(
            ProrrataRegisterEntry(
                ejercicio=2025,
                regime=ProrrataRegisterRegime.ESPECIAL,
                provisional_percentage=Decimal("60"),
                provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
            )
        )

        reloaded = repository.load()
        assert reloaded.sector_definitions == (definition,)
        assert {entry.ejercicio for entry in reloaded.entries} == {2024, 2025}


def test_declare_sector_persists_partition_and_sectorizes_register() -> None:
    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "prorrata",
            "declare-sector",
            "--sector-id",
            "arrendamiento",
            "--letra",
            SectorDiferenciadoLetra.A.value,
            "--activity-code",
            "6820",
            "--activity-code",
            "6810",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = _json(result)
    assert payload["sector"]["sector_id"] == "arrendamiento"
    assert payload["sector"]["letra"] == SectorDiferenciadoLetra.A.value
    assert payload["sector"]["member_activity_codes"] == ["6820", "6810"]

    listing = _invoke(["--format", "json", "app", "ledger", "prorrata", "list"])
    assert listing.exit_code == 0, listing.output
    sectors = _json(listing)["sectors"]
    assert isinstance(sectors, list) and len(sectors) == 1
    assert sectors[0]["sector_id"] == "arrendamiento"


def test_declare_sector_requires_at_least_one_activity_code() -> None:
    result = _invoke(
        [
            "app",
            "ledger",
            "prorrata",
            "declare-sector",
            "--sector-id",
            "arrendamiento",
            "--letra",
            SectorDiferenciadoLetra.A.value,
        ],
    )
    assert result.exit_code != 0


def test_upsert_sector_definition_preserves_entries(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="prorrata-preserve-entries"):
        repository = ProrrataRegisterRepository()
        entry = ProrrataRegisterEntry(
            ejercicio=2025,
            regime=ProrrataRegisterRegime.ESPECIAL,
            provisional_percentage=Decimal("60"),
            provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
        )
        repository.save(ProrrataRegister(entries=(entry,)))

        repository.upsert_sector_definition(
            SectorDefinition(
                sector_id="comercio",
                letra=SectorDiferenciadoLetra.A,
                member_activity_codes=("4711",),
            )
        )

        reloaded = repository.load()
        assert reloaded.entries == (entry,)
        assert reloaded.is_sectorized
        assert reloaded.sector_ids() == ("comercio",)


def _add_row(*, key: str, sector: str | None = None, input_classification: str | None = None):
    args = [
        "--format",
        "json",
        "app",
        "ledger",
        "add",
        "--date",
        "2026-05-03",
        "--amount",
        "121.00",
        "--direction",
        "OUTGOING",
        "--description",
        "supplier invoice",
        "--idempotency-key",
        key,
    ]
    if sector is not None:
        args += ["--sector", sector]
    if input_classification is not None:
        args += ["--input-classification", input_classification]
    return _invoke(args)


def _envelope_notice_codes(result) -> set[str]:
    payload = json.loads(result.output)
    return {notice["code"] for notice in payload.get("notices", [])}


def test_sector_tag_is_part_of_the_idempotency_identity() -> None:
    first = _add_row(key="tx-sector-id", sector="alquiler")
    assert first.exit_code == 0, first.output

    # Same key, same sector: guarded idempotent no-op (proves the tag persisted).
    replay = _add_row(key="tx-sector-id", sector="alquiler")
    assert replay.exit_code == 0, replay.output
    assert _json(replay)["bucket_event_ids"] == []

    # Same key, different sector: content differs, so the add is refused — proving
    # prorrata_sector_id participates in the persisted identity, not silently dropped.
    conflict = _add_row(key="tx-sector-id", sector="comercio")
    assert conflict.exit_code != 0


def test_input_classification_without_especial_election_warns() -> None:
    result = _add_row(key="tx-inert", input_classification="exclusively_deductible")
    assert result.exit_code == 0, result.output
    assert "ledger.add.input_classification_inert" in _envelope_notice_codes(result)


def test_input_classification_with_especial_election_is_not_inert() -> None:
    elected = _invoke(
        [
            "app",
            "ledger",
            "prorrata",
            "elect-especial",
            "--ejercicio",
            "2026",
            "--percentage",
            "60",
        ],
    )
    assert elected.exit_code == 0, elected.output

    result = _add_row(key="tx-especial", input_classification="exclusively_deductible")
    assert result.exit_code == 0, result.output
    assert "ledger.add.input_classification_inert" not in _envelope_notice_codes(result)


def test_sector_tag_naming_absent_sector_warns() -> None:
    # No sector declared: the tag matches nothing, so the input would silently
    # deduct at the common-use percentage. The advisory makes that visible.
    result = _add_row(key="tx-sector-typo", sector="comercio-typo")
    assert result.exit_code == 0, result.output
    assert "ledger.add.sector_unmatched" in _envelope_notice_codes(result)


def test_sector_tag_naming_declared_sector_is_silent() -> None:
    declared = _invoke(
        [
            "app",
            "ledger",
            "prorrata",
            "declare-sector",
            "--sector-id",
            "arrendamiento",
            "--letra",
            SectorDiferenciadoLetra.A.value,
            "--activity-code",
            "6820",
        ],
    )
    assert declared.exit_code == 0, declared.output

    result = _add_row(key="tx-sector-declared", sector="arrendamiento")
    assert result.exit_code == 0, result.output
    assert "ledger.add.sector_unmatched" not in _envelope_notice_codes(result)
