"""Gate 8: the shipped annual-Orden census artefact, and every way it must refuse.

The artefact lets a runtime skip a BeautifulSoup parse of five pinned BOE
Ordenes. That is only safe if two things hold, and both are asserted here.

**It carries the same censuses an extraction would produce.** Otherwise the
authority compiles from something other than the corpus, silently, and every
downstream IVA módulos figure is wrong with no symptom.

**Every way it can be wrong refuses, and refusing costs speed rather than
correctness.** A tampered, stale, foreign, or mis-versioned artefact must fall
back to extracting in full — never be served, and never raise. The runtime
cannot re-derive the truth cheaply, which is exactly why the build-side staleness
refusal exists alongside these runtime gates.

No test here mutates the tracked artefact. Tampering is done on a copy under
``tmp_path`` whose root is handed to the loader, so a crashed run leaves the
shipped tree untouched.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from .....core.resources import bundled_path
from .....tests.registry_tree import bundled_registry_tree
from .._errors import RegistryLoadError
from .._m303_orden_census_artefact import (
    M303_ORDEN_CENSUS_ARTEFACT_FILENAME,
    load_m303_annual_orden_censuses,
    m303_orden_census_artefact_path,
)
from .._m303_orden_manifest import (
    _generate_manifest_with_censuses,
    check_m303_annual_orden_census_artefact,
    collect_m303_annual_orden_fingerprints,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def registry_sources() -> dict:
    """The real source catalogue, loaded once for the module."""
    _modelos, catalogues = bundled_registry_tree()
    return dict(catalogues.sources)


@pytest.fixture(scope="module")
def shipped_artefact_text() -> str:
    """The committed artefact's bytes, read once and never written back."""
    path = m303_orden_census_artefact_path(bundled_path("registry", "aeat"))
    assert path.is_file(), f"the census artefact must be committed at {path}"
    return path.read_text(encoding="utf-8")


def _root_carrying(tmp_path: Path, text: str) -> Path:
    """Materialise a registry root whose only content is the given artefact."""
    root = tmp_path / "aeat"
    (root / "m303_orden_anual").mkdir(parents=True)
    (root / "m303_orden_anual" / M303_ORDEN_CENSUS_ARTEFACT_FILENAME).write_text(
        text,
        encoding="utf-8",
        newline="\n",
    )
    return root


def test_the_shipped_censuses_equal_a_fresh_extraction(registry_sources: dict) -> None:
    """The artefact is the corpus, not merely a plausible file shaped like it.

    Compared as whole models, so a field that silently stopped being extracted
    fails here rather than surfacing as a wrong módulos figure years later.
    """
    root = bundled_path("registry", "aeat")
    shipped = load_m303_annual_orden_censuses(root, sources=registry_sources)
    assert shipped is not None, "the committed artefact must load against the pinned sources"

    _manifest, extracted = _generate_manifest_with_censuses(
        source_root=bundled_path(),
        sources=registry_sources,
    )

    assert shipped == extracted


def test_the_artefact_is_fingerprinted_so_an_edit_re_keys_the_cache(tmp_path: Path) -> None:
    """A JSON artefact must not fall outside a TOML-shaped glob.

    The collector previously matched ``*.toml`` only. Under that pattern an edit
    to the census artefact would leave the cache key unmoved, and a compiled
    registry built from the OLD censuses would keep being served under a key that
    still looked valid. This is the assertion that keeps the glob honest.
    """
    root = _root_carrying(tmp_path, '{"schema_version": "x", "extractor_version": "y", "censuses": []}\n')

    before = collect_m303_annual_orden_fingerprints(root)
    assert any(M303_ORDEN_CENSUS_ARTEFACT_FILENAME in entry[0] for entry in before), (
        "the census artefact must be inside the annual-Orden fingerprint set"
    )

    (root / "m303_orden_anual" / M303_ORDEN_CENSUS_ARTEFACT_FILENAME).write_text(
        '{"schema_version": "x", "extractor_version": "y", "censuses": [], "pad": 1}\n',
        encoding="utf-8",
        newline="\n",
    )

    assert collect_m303_annual_orden_fingerprints(root) != before


def _wrong_source_digest(payload: dict) -> None:
    payload["censuses"][0]["source_content_digest"] = "0" * 64


def _wrong_census_extractor(payload: dict) -> None:
    payload["censuses"][0]["extractor_version"] = "m303-bogus-v0"


def _wrong_envelope_extractor(payload: dict) -> None:
    payload["extractor_version"] = "m303-bogus-v0"


def _wrong_schema_version(payload: dict) -> None:
    payload["schema_version"] = "bogus-v0"


def _unknown_source_ref(payload: dict) -> None:
    payload["censuses"][0]["source_ref"] = "not-a-real-source"


def _duplicate_source_ref(payload: dict) -> None:
    payload["censuses"][1]["source_ref"] = payload["censuses"][0]["source_ref"]


def _foreign_field(payload: dict) -> None:
    payload["unexpected"] = True


@pytest.mark.parametrize(
    "tamper",
    [
        pytest.param(_wrong_source_digest, id="source-digest-disagrees-with-the-pinned-source"),
        pytest.param(_wrong_census_extractor, id="per-census-extractor-version"),
        pytest.param(_wrong_envelope_extractor, id="envelope-extractor-version"),
        pytest.param(_wrong_schema_version, id="schema-version"),
        pytest.param(_unknown_source_ref, id="source-ref-the-registry-does-not-pin"),
        pytest.param(_duplicate_source_ref, id="two-censuses-claiming-one-source"),
        pytest.param(_foreign_field, id="foreign-field-under-a-strict-model"),
    ],
)
def test_every_tampering_refuses_rather_than_serving(
    tmp_path: Path,
    registry_sources: dict,
    shipped_artefact_text: str,
    tamper: Callable[[dict], None],
) -> None:
    """Each way the artefact can be wrong yields ``None``, never a served census.

    ``None`` means "extract in full", so the cost of any of these is a slow load
    and never a wrong one. Parametrized rather than collapsed into one test so a
    failure names which guard stopped holding.
    """
    payload = json.loads(shipped_artefact_text)
    tamper(payload)
    root = _root_carrying(tmp_path, json.dumps(payload, indent=2) + "\n")

    assert load_m303_annual_orden_censuses(root, sources=registry_sources) is None


def test_the_untampered_copy_loads_so_the_refusals_are_not_vacuous(
    tmp_path: Path,
    registry_sources: dict,
    shipped_artefact_text: str,
) -> None:
    """The control for the parametrized refusals above.

    Without it, every refusal case would pass if the loader simply returned
    ``None`` for everything — including a perfectly good artefact — and the
    runtime would silently never take the fast path at all.
    """
    root = _root_carrying(tmp_path, shipped_artefact_text)

    assert load_m303_annual_orden_censuses(root, sources=registry_sources) is not None


def test_an_absent_artefact_falls_back_instead_of_raising(tmp_path: Path, registry_sources: dict) -> None:
    """A registry with no artefact at all must load, slowly, not refuse."""
    root = tmp_path / "aeat"
    (root / "m303_orden_anual").mkdir(parents=True)

    assert load_m303_annual_orden_censuses(root, sources=registry_sources) is None


def test_the_build_gate_refuses_a_stale_artefact(
    tmp_path: Path,
    registry_sources: dict,
    shipped_artefact_text: str,
) -> None:
    """The build-side half: a committed artefact that no longer matches the corpus.

    This is the only check that can catch a census which is internally consistent
    and version-correct but simply WRONG about the BOE text — the runtime cannot,
    because re-deriving the truth is the parse the artefact exists to avoid.
    """
    payload = json.loads(shipped_artefact_text)
    payload["censuses"][0]["difficult_justification"]["percentage"] = "99.99"
    artefact_path = tmp_path / M303_ORDEN_CENSUS_ARTEFACT_FILENAME
    artefact_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")

    with pytest.raises(RegistryLoadError, match="census artefact is stale"):
        check_m303_annual_orden_census_artefact(
            artefact_path=artefact_path,
            source_root=bundled_path(),
            sources=registry_sources,
        )


def test_the_build_gate_refuses_an_absent_artefact(tmp_path: Path, registry_sources: dict) -> None:
    """A deleted artefact is a build failure, not a silent regeneration."""
    with pytest.raises(RegistryLoadError, match="census artefact is missing"):
        check_m303_annual_orden_census_artefact(
            artefact_path=tmp_path / M303_ORDEN_CENSUS_ARTEFACT_FILENAME,
            source_root=bundled_path(),
            sources=registry_sources,
        )


def test_the_build_gate_passes_on_the_committed_artefact(registry_sources: dict) -> None:
    """The anti-vacuity control for both build-gate refusals above."""
    check_m303_annual_orden_census_artefact(
        artefact_path=m303_orden_census_artefact_path(bundled_path("registry", "aeat")),
        source_root=bundled_path(),
        sources=registry_sources,
    )
