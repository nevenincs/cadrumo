"""Real-path gates for developer audit and evidence tooling after the Cadrumo cut."""

from __future__ import annotations

import json

import pytest
from dev import _build_evidence_corpus
from dev.audit import report, semantic
from dev.audit.complexity import collect_cc, load_baseline

from ._inventory import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_code_health_scanners_target_the_live_cadrumo_tree_non_vacuously() -> None:
    """The composed report scans real Cadrumo modules rather than a retired empty root."""
    source_root = REPO_ROOT / report._PRODUCT_SOURCE_ROOT
    production_files = tuple(source_root.rglob("*.py"))
    cyclomatic = collect_cc(report._PRODUCTION_EXCLUDE)

    assert source_root == REPO_ROOT / "src" / "cadrumo"
    assert len(production_files) > 1_000
    assert len(cyclomatic) > 100
    assert all(finding.path.startswith("src/cadrumo/") for finding in cyclomatic)


def test_complexity_baseline_keys_use_only_current_product_paths() -> None:
    """The ratchet preserves its debt values while every source key follows the move."""
    baseline_path = REPO_ROOT / "dev" / "audit" / "complexity_baseline.json"
    document = json.loads(baseline_path.read_text(encoding="utf-8"))
    serialized = json.dumps(document)
    production = load_baseline(is_test_run=False, path=baseline_path)
    tests = load_baseline(is_test_run=True, path=baseline_path)
    keys = {
        *production.cyclomatic,
        *production.maintainability,
        *production.cognitive,
        *tests.cyclomatic,
        *tests.maintainability,
        *tests.cognitive,
    }

    assert len(keys) > 500
    assert "src/aeat" not in serialized
    assert all(key.startswith("src/cadrumo/") for key in keys)


def test_semantic_leak_classifier_uses_cadrumo_paths_and_keeps_aeat_as_authority() -> None:
    """Product roots move while the outbound AEAT adapter remains correctly named."""
    verified_authority_adapter = "src/cadrumo/adapters/outbound/aeat/export/_formats/_record_spec.py"

    assert semantic.is_violation(verified_authority_adapter) is False
    assert semantic.is_violation("src/cadrumo/adapters/outbound/google/_rounding_copy.py") is True
    assert semantic.is_violation("src/cadrumo/domain/money.py") is False
    assert all(path.startswith("src/cadrumo/adapters/outbound/aeat/") for path in semantic._VERIFIED_NON_LEAK_PATHS)


def test_evidence_builder_targets_the_live_cadrumo_fixture_corpus() -> None:
    """A corpus build writes only beneath the current product test tree."""
    corpus = REPO_ROOT / _build_evidence_corpus._CORPUS

    assert corpus == REPO_ROOT / "src" / "cadrumo" / "application" / "ledger" / "tests" / "_evidence_corpus"
    assert corpus.is_dir()
    assert _build_evidence_corpus._UA.startswith("cadrumo-fixtures/")


def test_vulture_whitelist_references_current_modules_only() -> None:
    """Whitelist rationale cannot keep retired product module paths alive."""
    whitelist = (REPO_ROOT / "dev" / "vulture_whitelist.py").read_text(encoding="utf-8")

    assert "aeat." not in whitelist
    assert "cadrumo.adapters.outbound.google._api" in whitelist
    assert "cadrumo.application.ledger._evidence_input" in whitelist
