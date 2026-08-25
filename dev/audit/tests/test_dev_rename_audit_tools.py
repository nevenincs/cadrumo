"""Real-path gates for developer audit and evidence tooling after the Cadrumo cut."""

from __future__ import annotations

import pytest

from cadrumo.core import scan_directory

from ..._paths import REPO_ROOT
from ...corpus import build_evidence_corpus
from .. import dead_code, report, semantic
from ..complexity import collect_cc, load_baseline

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_code_health_scanners_target_the_live_cadrumo_tree_non_vacuously() -> None:
    """The composed report scans real Cadrumo modules rather than a retired empty root."""
    source_root = REPO_ROOT / report._PRODUCT_SOURCE_ROOT
    production_files = tuple(scan_directory(source_root, pattern="*.py", recursive=True))
    cyclomatic = collect_cc(report._PRODUCTION_EXCLUDE)

    assert source_root == REPO_ROOT / "src" / "cadrumo"
    assert len(production_files) > 1_000
    assert len(cyclomatic) > 100
    assert all(finding.path.startswith("src/cadrumo/") for finding in cyclomatic)


def test_complexity_baseline_keys_reference_current_owner_namespaces() -> None:
    """The canonical ratchet retains only debt its production scanner can measure."""
    production = load_baseline(is_test_run=False)
    tests = load_baseline(is_test_run=True)
    keys = {
        *production.cyclomatic,
        *production.maintainability,
        *production.cognitive,
        *tests.cyclomatic,
        *tests.maintainability,
        *tests.cognitive,
    }

    assert keys
    assert all(key.startswith("src/cadrumo/") for key in keys)
    assert all((REPO_ROOT / key.partition("::")[0]).is_file() for key in keys)


def test_semantic_leak_classifier_uses_cadrumo_paths_and_keeps_aeat_as_authority() -> None:
    """Fixed-width coercion has no adapter-side semantic-leak exception."""
    canonical_codec = "src/cadrumo/domain/calculations/registry/_fixed_width_codec.py"

    assert semantic.is_violation(canonical_codec) is False
    assert semantic.is_violation("src/cadrumo/adapters/outbound/google/_rounding_copy.py") is True
    assert semantic.is_violation("src/cadrumo/domain/money.py") is False
    assert frozenset() == semantic._VERIFIED_NON_LEAK_PATHS


def _semantic_gate_violations(result: dict[str, object]) -> tuple[str, ...]:
    """Classify one deterministic tax-base result through the real gate projection."""
    return semantic.semantic_leak_violations(
        {
            "currency rounding": (),
            "calculate tax base": (result,),
        },
    )


def test_semantic_gate_fails_for_adapter_tax_base_calculation() -> None:
    """An adapter that divides gross by a rate is a real tax-base calculation leak."""
    result: dict[str, object] = {
        "path": "src/cadrumo/adapters/inbound/einvoice/_parsers.py",
        "score": 0.64,
        "function_name": "calculate_tax_base",
        "snippet": "def calculate_tax_base(gross, rate):\n    return gross / (1 + rate)\n",
    }

    assert _semantic_gate_violations(result) == (
        "Leak detected for query 'calculate tax base' "
        "(tax-base arithmetic in calculate_tax_base; score 0.64): "
        "src/cadrumo/adapters/inbound/einvoice/_parsers.py",
    )


def test_semantic_gate_keeps_structured_tax_base_read_transcriptive() -> None:
    """A parser reading Facturae's named base is not a second base calculation."""
    result: dict[str, object] = {
        "path": "src/cadrumo/adapters/inbound/einvoice/_parsers.py",
        "score": 0.59,
        "snippet": (
            'parsed.taxable_base = _decimal(_first_text(totals, "TotalGrossAmountBeforeTaxes"))\n'
            "parsed.grand_total = _facturae_invoice_total(base=parsed.taxable_base)\n"
        ),
    }

    assert _semantic_gate_violations(result) == ()


def test_evidence_builder_targets_the_live_cadrumo_fixture_corpus() -> None:
    """A corpus build writes only beneath the current product test tree."""
    corpus = REPO_ROOT / build_evidence_corpus._CORPUS

    assert corpus == REPO_ROOT / "src" / "cadrumo" / "application" / "ledger" / "tests" / "_evidence_corpus"
    assert corpus.is_dir()
    assert build_evidence_corpus._UA.startswith("cadrumo-fixtures/")


def test_dead_code_runner_owns_the_current_whitelist_path() -> None:
    """The sole runner targets its live whitelist, never the deleted root-level path."""
    command = dead_code.vulture_command()

    assert command[-2:] == ["src/cadrumo", "dev/audit/vulture_whitelist.py"]
    assert all((REPO_ROOT / target).exists() for target in command[-2:])
    assert not (REPO_ROOT / "dev" / "vulture_whitelist.py").exists()
