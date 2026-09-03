"""The shipped Renta WEB Open replay fold, over the bundled AEAT captures.

Every test here runs the real oracle against the real registry declaration and
the real bundled corpus. Nothing is mocked, and nothing reaches the network:
the replay driver's only planned operation is a local parse, which the
remote-state guard authorises before any comparison happens.

Four questions are asked, and they are deliberately different questions:

* the bundled captures agree with the figures AEAT's simulator produced;
* a perturbed capture is REPORTED as a mismatch rather than passed -- the
  detector-teeth proof, run against an isolated copy so the shipped corpus and
  the contributor's working tree are never touched;
* an expected casilla the capture never observed stays ``unverifiable``, which
  is neither the match nor the mismatch it would collapse into under a boolean;
* a non-finite numeric token is refused as a match even against an identical
  string, because declaring ``"NaN"`` equal to ``"NaN"`` would certify a
  corrupt magnitude as verified against AEAT.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from ..live_parity import ParityVerdictKind
from ..renta_web_open_replay_corpus import (
    build_renta_web_open_replay_parity,
    replay_corpus_payload_paths,
)

if TYPE_CHECKING:
    from ..schema import ModeloDefinition, RegistryCatalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Autonomous-community suffixes the bundled corpus captures, plus the state default.
_EXPECTED_CAPTURE_STEMS: frozenset[str] = frozenset(
    {
        "modelo-100-2025-employee-default-minimo",
        "modelo-100-2025-employee-default-minimo-canarias",
        "modelo-100-2025-employee-default-minimo-cataluna",
        "modelo-100-2025-employee-default-minimo-galicia",
        "modelo-100-2025-employee-default-minimo-madrid",
    },
)

#: The casilla whose value diverges by autonomous community: minimo personal, autonomic part.
_AUTONOMIC_MINIMO_CASILLA = "0520"


def _modelos(registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]) -> tuple[ModeloDefinition, ...]:
    modelos, _catalogues = registry_tree
    return modelos


def _copy_corpus(destination: Path) -> tuple[Path, ...]:
    """Copy the bundled captures into ``destination`` so a test may perturb them.

    The shipped corpus is read-only evidence. A detector-teeth proof that
    mutated it in place would corrupt the very figures every other test reads,
    so the perturbation always happens on a copy under the test's own tmp path.
    """
    destination.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for source in replay_corpus_payload_paths():
        target = destination / source.name
        target.write_bytes(source.read_bytes())
        copied.append(target)
    return tuple(copied)


def _rewrite_capture(path: Path, *, mutate: Mapping[str, object]) -> None:
    document = json.loads(path.read_text(encoding="utf-8"))
    document.update(mutate)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")


def test_bundled_captures_cover_every_autonomous_community_variant() -> None:
    """The corpus must still hold the five captures the regional fold depends on."""
    assert {path.stem for path in replay_corpus_payload_paths()} == _EXPECTED_CAPTURE_STEMS


def test_bundled_replay_corpus_agrees_with_the_aeat_captured_figures(
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    """Every bundled capture replays to ``match`` through the shipped fold."""
    report = build_renta_web_open_replay_parity(_modelos(registry_tree), registry_validated=False)

    assert report.guard_policy_id == "modelo-100-renta-web-open-read-only"
    assert len(report.payloads) == len(_EXPECTED_CAPTURE_STEMS)
    assert report.compared_field_count() == 4 * len(_EXPECTED_CAPTURE_STEMS)
    assert report.verdict == ParityVerdictKind.MATCH
    assert report.payload_count_of(ParityVerdictKind.MATCH) == len(_EXPECTED_CAPTURE_STEMS)
    assert report.payload_count_of(ParityVerdictKind.MISMATCH) == 0
    assert report.payload_count_of(ParityVerdictKind.UNVERIFIABLE) == 0
    assert report.payload_count_of(ParityVerdictKind.BLOCKED) == 0
    for payload in report.payloads:
        assert payload.verdict == ParityVerdictKind.MATCH, (
            f"{payload.payload_name}: {payload.narrative}; fields={payload.fields}"
        )
        assert payload.raw_evidence_locator, f"{payload.payload_name} replayed with no evidence provenance"


def test_every_autonomous_community_capture_checks_its_own_autonomic_minimo(
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    """The regional captures must differ where the law differs, not merely all pass.

    Five captures that agreed on every figure would prove nothing about the
    hardest variation in Modelo 100. This asserts the autonomic ``minimo``
    actually varies across the corpus, so the passing fold above is comparing
    distinct regional figures rather than one figure five times.
    """
    report = build_renta_web_open_replay_parity(_modelos(registry_tree), registry_validated=False)

    autonomic_values = {
        payload.payload_name: field.observed
        for payload in report.payloads
        for field in payload.fields
        if field.name == _AUTONOMIC_MINIMO_CASILLA
    }
    assert len(autonomic_values) == len(_EXPECTED_CAPTURE_STEMS)
    assert len(set(autonomic_values.values())) > 1, autonomic_values


def test_a_perturbed_expected_figure_is_reported_as_a_mismatch(
    tmp_path: Path,
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    """Detector teeth: the fold must FAIL a capture whose expectation was moved."""
    captures = _copy_corpus(tmp_path / "parity_replays")
    perturbed = next(path for path in captures if path.stem == "modelo-100-2025-employee-default-minimo-madrid")
    original = json.loads(perturbed.read_text(encoding="utf-8"))
    moved = dict(original["expected_by_casilla_id"])
    assert moved[_AUTONOMIC_MINIMO_CASILLA] == "5956.65"
    moved[_AUTONOMIC_MINIMO_CASILLA] = "5956.66"
    _rewrite_capture(perturbed, mutate={"expected_by_casilla_id": moved})

    report = build_renta_web_open_replay_parity(
        _modelos(registry_tree),
        payload_paths=captures,
        registry_validated=False,
    )

    assert report.verdict == ParityVerdictKind.MISMATCH
    assert report.payload_count_of(ParityVerdictKind.MISMATCH) == 1
    offending = next(payload for payload in report.payloads if payload.payload_name == perturbed.name)
    assert offending.verdict == ParityVerdictKind.MISMATCH
    moved_field = next(field for field in offending.fields if field.name == _AUTONOMIC_MINIMO_CASILLA)
    assert moved_field.verdict == ParityVerdictKind.MISMATCH
    assert moved_field.expected == "5956.66"
    assert moved_field.observed == "5.956,65"
    untouched = {payload.verdict for payload in report.payloads if payload.payload_name != perturbed.name}
    assert untouched == {ParityVerdictKind.MATCH}


def test_an_unobserved_expected_casilla_stays_unverifiable(
    tmp_path: Path,
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    """``unverifiable`` is a third outcome: not a match, and not a mismatch."""
    captures = _copy_corpus(tmp_path / "parity_replays")
    target = next(path for path in captures if path.stem == "modelo-100-2025-employee-default-minimo-galicia")
    document = json.loads(target.read_text(encoding="utf-8"))
    observed = {
        casilla_id: value
        for casilla_id, value in document["observed_by_casilla_id"].items()
        if casilla_id != _AUTONOMIC_MINIMO_CASILLA
    }
    _rewrite_capture(target, mutate={"observed_by_casilla_id": observed})

    report = build_renta_web_open_replay_parity(
        _modelos(registry_tree),
        payload_paths=captures,
        registry_validated=False,
    )

    affected = next(payload for payload in report.payloads if payload.payload_name == target.name)
    unobserved = next(field for field in affected.fields if field.name == _AUTONOMIC_MINIMO_CASILLA)
    assert unobserved.verdict == ParityVerdictKind.UNVERIFIABLE
    assert unobserved.verdict != ParityVerdictKind.MATCH
    assert unobserved.verdict != ParityVerdictKind.MISMATCH
    assert affected.verdict == ParityVerdictKind.UNVERIFIABLE
    assert report.verdict == ParityVerdictKind.UNVERIFIABLE
    assert report.payload_count_of(ParityVerdictKind.UNVERIFIABLE) == 1
    assert report.payload_count_of(ParityVerdictKind.MISMATCH) == 0
    assert report.payload_count_of(ParityVerdictKind.MATCH) == len(_EXPECTED_CAPTURE_STEMS) - 1


def test_a_non_finite_token_is_refused_as_a_parity_match(
    tmp_path: Path,
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    """Identical ``NaN`` strings must not certify a corrupt magnitude as verified."""
    captures = _copy_corpus(tmp_path / "parity_replays")
    target = next(path for path in captures if path.stem == "modelo-100-2025-employee-default-minimo-canarias")
    document = json.loads(target.read_text(encoding="utf-8"))
    expected = dict(document["expected_by_casilla_id"]) | {_AUTONOMIC_MINIMO_CASILLA: "NaN"}
    observed = dict(document["observed_by_casilla_id"]) | {_AUTONOMIC_MINIMO_CASILLA: "NaN"}
    _rewrite_capture(target, mutate={"expected_by_casilla_id": expected, "observed_by_casilla_id": observed})

    report = build_renta_web_open_replay_parity(
        _modelos(registry_tree),
        payload_paths=captures,
        registry_validated=False,
    )

    affected = next(payload for payload in report.payloads if payload.payload_name == target.name)
    corrupt = next(field for field in affected.fields if field.name == _AUTONOMIC_MINIMO_CASILLA)
    assert corrupt.expected == corrupt.observed == "NaN"
    assert corrupt.verdict == ParityVerdictKind.MISMATCH
    assert affected.verdict == ParityVerdictKind.MISMATCH
