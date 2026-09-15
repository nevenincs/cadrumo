"""Exact named lineage debt over materialized editions, not repeated numbers.

A resolved origin is not necessarily grounded: SEEDED remains inference, and
accepted ledger refusals remain debt. This gate neither rereads official
evidence nor authorizes publication with an unresolved backlog. It rejects new
unrecorded debt, stale exceptions, counterfeit continuation and unjudged models.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.casilla_lineage import CasillaLineageOrigin
from cadrumo.domain.calculations.registry.casilla_lineage_totality import CasillaRowKey, lineage_totality
from cadrumo.domain.calculations.registry.schema import ModeloDefinition

from ..analysis.casilla_lineage_ledger import load_ledger_refusals
from ..analysis.casilla_lineage_partition import load_partitioned_corpus, partitioned_lineage_totality
from ..compiler.loader import load_modelo_directory
from ..compiler.loader_cache import discover_modelo_sources
from ..compiler.validate_cross_revision_lineage_origin import lineage_origin_continuity_failures
from ..conformance.loader_directory_mode_support import write_standard_manifest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_KEY = CasillaRowKey("999", "2025", "0001")
_REFS = 'legal_refs = ["ley-58-2003:art-29"]\nsource_refs = ["aeat-manual"]\n'


@pytest.fixture(scope="module")
def partition() -> tuple[dict[str, ModeloDefinition], dict[str, str]]:
    return load_partitioned_corpus()


def _origin_failures(loaded: Mapping[str, ModeloDefinition]) -> tuple[str, ...]:
    return tuple(failure for modelo in loaded.values() for failure in lineage_origin_continuity_failures(modelo))


def test_lineage_debt_matches_the_exact_named_ledger(
    partition: tuple[dict[str, ModeloDefinition], dict[str, str]],
) -> None:
    loaded, unjudged = partition
    expected = {source.modelo_id for source in discover_modelo_sources(bundled_path("registry", "aeat", "modelos"))}
    assert expected, "an empty source discovery is not a whole-corpus judgement"
    assert set(loaded) | set(unjudged) == expected
    assert not (set(loaded) & set(unjudged))
    ledger = load_ledger_refusals()
    report = partitioned_lineage_totality(loaded, unjudged, ledger.keys())
    accepted = len(ledger) - len(report.stale) - len(report.withheld)
    print(f"{accepted} covered unresolved rows remain debt, not grounded continuity.\n{report.describe()}")
    assert report.is_green, report.describe()


def test_every_declared_continuation_resolves_its_predecessor(
    partition: tuple[dict[str, ModeloDefinition], dict[str, str]],
) -> None:
    loaded, unjudged = partition
    assert loaded and not unjudged, f"continuation validation is incomplete: {unjudged}"
    failures = _origin_failures(loaded)
    assert not failures, "\n".join(failures)


def _row(year: int, *, chain: str | None, origin: str | None = None, role: str = "iva_base_general") -> str:
    text = (
        f'[[revisions."{year}".casillas]]\nid = "0001"\nnumber = "1"\n'
        f'section = ["liquidacion"]\nsemantic_role = "{role}"\n' + _REFS
    )
    if chain is not None:
        text += f'continuidad_id = "{chain}"\n'
    if origin is not None:
        text += f'continuidad_origin = "{origin}"\n'
        if origin != "seeded":
            text += 'continuidad_evidence = "Official paired fixture: independently adjudicated relationship."\n'
    return text


def _modelo(
    root: Path,
    *,
    successor: str,
    predecessor_chain: str | None = "base-general",
    delta: bool = False,
    attestation: bool = False,
) -> ModeloDefinition:
    directory = root / "999"
    directory.mkdir()
    write_standard_manifest(directory, "Canonical lineage detector fixture")
    for year in (2024, 2025):
        edition = directory / "revisions" / str(year)
        edition.mkdir(parents=True)
        manifest = (
            f'[revisions."{year}"]\nvalid_from = {year}-01-01\nvalid_to = {year}-12-31\n'
            f'period_selector = {{ years = [{year}], periods = ["0A"] }}\n' + _REFS
        )
        if year == 2025 and delta:
            manifest += 'predecessor = "2024"\n'
        if year == 2025 and attestation:
            manifest += (
                '[[revisions."2025".lineage_attestations]]\nfamily = "casillas"\n'
                'continuidad_id = "base-general"\nfrom_revision = "2024"\nto_revision = "2025"\n'
                'origin = "grounded"\nevidence = "Official fixture continuation at the exact edge."\n' + _REFS
            )
        (edition / "revision.toml").write_text(manifest, encoding="utf-8")
        rows = _row(2024, chain=predecessor_chain) if year == 2024 else successor
        if rows:
            section = edition / "casillas"
            section.mkdir()
            (section / "0001-declarations.toml").write_text(rows, encoding="utf-8")
    return load_modelo_directory(directory)


def test_unclassified_reused_number_requires_a_named_exception(tmp_path: Path) -> None:
    modelo = _modelo(tmp_path, successor=_row(2025, chain=None))
    assert lineage_totality((modelo,), ()).uncovered == (_KEY,)
    assert lineage_totality((modelo,), {_KEY}).is_total
    assert not _origin_failures({"999": modelo})


@pytest.mark.parametrize("origin", ["new_on_form", "predecessor_edition_silent", "not_on_form"])
def test_adjudicated_absence_is_not_a_partially_stamped_numeric_chain(tmp_path: Path, origin: str) -> None:
    modelo = _modelo(tmp_path, successor=_row(2025, chain=None, origin=origin))
    assert lineage_totality((modelo,), ()).is_total
    assert not _origin_failures({"999": modelo})
    assert lineage_totality((modelo,), {_KEY}).stale == (_KEY,)


def test_grounded_claim_cannot_cover_a_nonexistent_predecessor(tmp_path: Path) -> None:
    modelo = _modelo(tmp_path, successor=_row(2025, chain="different-concept", origin="grounded"))
    # Totality sees the claim; the independently required origin validator refuses it.
    assert lineage_totality((modelo,), ()).is_total
    assert any("does not carry continuidad_id" in failure for failure in _origin_failures({"999": modelo}))


@pytest.mark.parametrize("attestation", [False, True])
def test_inherited_rows_and_target_attestations_are_materialized_before_judgement(
    tmp_path: Path,
    attestation: bool,
) -> None:
    modelo = _modelo(tmp_path, successor="", delta=True, attestation=attestation)
    successor = modelo.revisions["2025"].casillas
    assert len(successor) == 1
    expected = CasillaLineageOrigin.GROUNDED if attestation else None
    assert successor[0].continuidad_origin is expected
    assert lineage_totality((modelo,), ()).is_total
    assert not _origin_failures({"999": modelo})


def test_seeded_is_admissible_inference_not_grounding(tmp_path: Path) -> None:
    modelo = _modelo(tmp_path, successor=_row(2025, chain="base-general", origin="seeded"))
    assert modelo.revisions["2025"].casillas[0].continuidad_origin is CasillaLineageOrigin.SEEDED
    assert lineage_totality((modelo,), ()).is_total
    assert not _origin_failures({"999": modelo})


def test_seeded_role_drift_is_refused(tmp_path: Path) -> None:
    modelo = _modelo(tmp_path, successor=_row(2025, chain="base-general", origin="seeded", role="iva_cuota_general"))
    assert any("semantic_role moved" in failure for failure in _origin_failures({"999": modelo}))


def test_missing_or_stale_exception_moves_the_exact_row(tmp_path: Path) -> None:
    modelo = _modelo(tmp_path, successor=_row(2025, chain=None))
    stale = CasillaRowKey("999", "2024", "0001")
    uncovered = partitioned_lineage_totality({"999": modelo}, {}, ())
    assert uncovered.uncovered == (_KEY,)
    assert not uncovered.is_green
    covered = partitioned_lineage_totality({"999": modelo}, {}, {_KEY})
    assert covered.is_green
    extra = partitioned_lineage_totality({"999": modelo}, {}, {_KEY, stale})
    assert extra.stale == (stale,)
    assert not extra.is_green


def test_unjudged_model_cannot_turn_withheld_debt_green() -> None:
    report = partitioned_lineage_totality({}, {"999": "planted compilation refusal"}, {_KEY})
    assert report.withheld == (_KEY,)
    assert report.unjudged == ("999",)
    assert not report.uncovered and not report.stale
    assert not report.is_green
