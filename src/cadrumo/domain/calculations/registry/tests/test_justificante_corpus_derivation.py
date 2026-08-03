"""Tests for the checkout-gated declaracion_pdf specimen corpus derivation.

:func:`~cadrumo.domain.calculations.registry._source_evidence_fingerprint.derive_justificante_corpus_candidate`
resolves the dev-only ``tests/fixtures/justificantes`` specimen corpus ONLY when
the process is classified as a source checkout, and returns a typed
:class:`~cadrumo.domain.calculations.registry.JustificanteCorpusUnavailableAdvisory`
instead of a bare ``None`` when it cannot. These tests prove:

- an installed-distribution context never probes the repo-shaped dev-fixture
  path and reports why through the advisory,
- a checkout context whose fixture directory is genuinely absent also reports
  why (naming the probed path), and
- :class:`~cadrumo.domain.calculations.registry.RegistryValidator` surfaces
  that same advisory through
  :attr:`~cadrumo.domain.calculations.registry._validate.RegistryValidator.justificante_corpus_unavailable_advisory`
  — the observability contract this module exists to prove. Before this
  change, an unavailable corpus silently collapsed to ``justificante_corpus_root
  is None`` with no distinguishable signal that derivation was even attempted.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core.paths import RunMode, StateRootInputs
from .....core.resources import bundled_path
from .. import JustificanteCorpusUnavailableAdvisory, RegistryCatalogues, RegistryValidator
from .._source_evidence_fingerprint import derive_justificante_corpus_candidate

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _installed_state_root_inputs(base: Path) -> StateRootInputs:
    """Build an ``installed`` :class:`StateRootInputs` context.

    Mirrors ``_installed_state_root_inputs`` in
    ``cadrumo.core.tests.test_paths``: the project-root candidate is a
    marker-free directory (no ``pyproject.toml`` / ``.git``), so
    :func:`~cadrumo.core.paths.detect_run_mode` classifies it installed.
    """
    candidate = base / "site-packages" / "cadrumo" / "core"
    return StateRootInputs(
        project_root_candidate=candidate,
        platform="win32",
        environ={"LOCALAPPDATA": str(base)},
        home=base / "home",
    )


def _checkout_state_root_inputs(project_root: Path) -> StateRootInputs:
    """Build a ``checkout`` :class:`StateRootInputs` context rooted at ``project_root``.

    ``project_root`` must carry both repository markers (a ``pyproject.toml``
    file and a ``.git`` entry) for
    :func:`~cadrumo.core.paths.detect_run_mode` to classify it a checkout.
    """
    return StateRootInputs(
        project_root_candidate=project_root,
        platform="win32",
        environ={"LOCALAPPDATA": str(project_root)},
        home=project_root / "home",
    )


def _empty_catalogues() -> RegistryCatalogues:
    return RegistryCatalogues(legal={}, sources={})


# --- derive_justificante_corpus_candidate: installed context -----------------


def test_installed_context_never_probes_and_reports_why(tmp_path: Path) -> None:
    """An installed distribution must not probe the repo-shaped dev-fixture path."""
    installed_inputs = _installed_state_root_inputs(tmp_path)
    source_root = tmp_path / "site-packages" / "cadrumo" / "_data"
    source_root.mkdir(parents=True)

    candidate, advisory = derive_justificante_corpus_candidate(source_root, state_root_inputs=installed_inputs)

    assert candidate is None
    assert advisory is not None
    assert advisory.run_mode is RunMode.INSTALLED
    assert advisory.probed_path is None, "installed mode must never construct a probe path"
    assert advisory.reason, "the advisory must carry a non-empty, operator-readable reason"


# --- derive_justificante_corpus_candidate: checkout context, fixture absent --


def test_checkout_context_with_absent_fixture_names_the_probed_path(tmp_path: Path) -> None:
    """A checkout whose dev-fixture directory is genuinely absent must name the probed path."""
    project_root = tmp_path / "repo"
    (project_root / "src" / "cadrumo").mkdir(parents=True)
    (project_root / "pyproject.toml").write_text("", encoding="utf-8")
    (project_root / ".git").write_text("gitdir: elsewhere", encoding="utf-8")
    source_root = project_root / "src" / "cadrumo" / "_data"
    source_root.mkdir()

    checkout_inputs = _checkout_state_root_inputs(project_root)
    candidate, advisory = derive_justificante_corpus_candidate(source_root, state_root_inputs=checkout_inputs)

    assert candidate is None
    assert advisory is not None
    assert advisory.run_mode is RunMode.CHECKOUT
    expected_probed_path = project_root / "src" / "cadrumo" / "tests" / "fixtures" / "justificantes"
    assert advisory.probed_path == expected_probed_path
    assert str(expected_probed_path) in advisory.reason


# --- derive_justificante_corpus_candidate: checkout context, fixture present -


def test_checkout_context_with_present_fixture_resolves_no_advisory(tmp_path: Path) -> None:
    """A checkout whose dev-fixture directory exists must resolve it with no advisory."""
    project_root = tmp_path / "repo"
    fixture_dir = project_root / "src" / "cadrumo" / "tests" / "fixtures" / "justificantes"
    fixture_dir.mkdir(parents=True)
    (project_root / "pyproject.toml").write_text("", encoding="utf-8")
    (project_root / ".git").write_text("gitdir: elsewhere", encoding="utf-8")
    source_root = project_root / "src" / "cadrumo" / "_data"
    source_root.mkdir()

    checkout_inputs = _checkout_state_root_inputs(project_root)
    candidate, advisory = derive_justificante_corpus_candidate(source_root, state_root_inputs=checkout_inputs)

    assert candidate == fixture_dir
    assert advisory is None


# --- RegistryValidator: observability contract --------------------------------


def test_validator_surfaces_the_advisory_when_derivation_fails(tmp_path: Path) -> None:
    """RegistryValidator must surface the advisory, not just an unexplained None.

    THIS is the falsifiability anchor: before the fix, an unavailable corpus
    silently collapsed ``justificante_corpus_root`` to ``None`` with no
    distinguishable signal that derivation was even attempted (an installed
    user and a misconfigured checkout looked identical). Reverting the
    advisory wiring in ``RegistryValidator.__init__`` while keeping
    ``justificante_corpus_root`` behaviour unchanged makes this test fail on
    the ``is not None`` assertion below, naming the real regression.
    """
    installed_inputs = _installed_state_root_inputs(tmp_path)
    source_root = tmp_path / "site-packages" / "cadrumo" / "_data"
    source_root.mkdir(parents=True)

    validator = RegistryValidator(
        _empty_catalogues(),
        source_root=source_root,
        state_root_inputs=installed_inputs,
    )

    assert validator.justificante_corpus_root is None
    advisory = validator.justificante_corpus_unavailable_advisory
    assert advisory is not None, "installed-mode derivation failure must be observable, not silent"
    assert isinstance(advisory, JustificanteCorpusUnavailableAdvisory)
    assert advisory.run_mode is RunMode.INSTALLED
    assert advisory.reason


def test_validator_reports_no_advisory_when_corpus_root_is_explicitly_injected(tmp_path: Path) -> None:
    """An explicit justificante_corpus_root injection is an opt-out, not a silent gap."""
    installed_inputs = _installed_state_root_inputs(tmp_path)
    source_root = tmp_path / "site-packages" / "cadrumo" / "_data"
    source_root.mkdir(parents=True)
    explicit_root = tmp_path / "explicit-corpus"
    explicit_root.mkdir()

    validator = RegistryValidator(
        _empty_catalogues(),
        source_root=source_root,
        justificante_corpus_root=explicit_root,
        state_root_inputs=installed_inputs,
    )

    assert validator.justificante_corpus_root == explicit_root
    assert validator.justificante_corpus_unavailable_advisory is None


def test_validator_reports_no_advisory_via_live_production_path() -> None:
    """The real bundled_path() checkout derivation must resolve cleanly with no advisory.

    Pure-production wiring (no state_root_inputs, no justificante_corpus_root
    injection): this repository is itself a source checkout with the real
    fixture inventory committed, so the derivation must succeed and the
    advisory must be absent. A regression that made the CHECKOUT branch
    itself always fail would turn this green suite red here.
    """
    validator = RegistryValidator(_empty_catalogues(), source_root=bundled_path())

    assert validator.justificante_corpus_root is not None
    assert validator.justificante_corpus_root.is_dir()
    assert validator.justificante_corpus_unavailable_advisory is None
