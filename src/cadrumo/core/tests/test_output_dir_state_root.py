"""Where each generated output lands, pinned against an independent oracle.

Durable state must not default under the checkout on an installed run: every
output directory derives its default from ``cadrumo_local_storage_root``, and
an explicit per-field override still wins.

This module owns the on-disk-name oracle, and owning it is the point. These
subpaths exist on operators' disks right now, so the names are the property
being defended rather than incidental detail. Deriving the expectation from the
taxonomy would turn every assertion below into the taxonomy compared with
itself: settings validation resolves each default by iterating that same
declaration, so a subpath edited there would move the directory and move the
expectation with it, in step and in silence, while the suite stayed green and
the operator's data sat at the old path.

So the oracle is written out by hand, once, here, and pinned against the
declaration in both directions -- neither side can drift toward the other
without someone deciding to. It replaces a literal table that lived in the
settings module, where a reader could mistake it for the authority. Nothing in
production reads these names; an oracle for a gate is a different thing from a
second authority, and the distinguishing test is exactly that.

The rule when the parity assertion reddens: if a location genuinely moved,
change both sides deliberately and know that data at the old path is stranded.
If it did not move, the taxonomy is what is wrong.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from ...tests import REPO_ROOT
from ...tests.env_scope import isolated_aeat_env, settings_without_env_file
from .._storage_taxonomy import STORAGE_TAXONOMY, StorageScope
from ..config import Settings

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


PINNED_TAXONOMY_LITERALS: Final[frozenset[str]] = frozenset(
    {
        "attachments",
        "blobs",
        "cache",
        "corpus-search",
        "corpus-text",
        "drafts",
        "filed-declarations",
        "filing-history",
        "financial",
        "invoices",
        "iva-compensation-history",
        "iva-read-evidence",
        "justificantes",
        "live",
        "live-state",
        "llm-cache",
        "llm-run-telemetry",
        "llm-usage",
        "logs",
        "registry-verdict",
        "runs",
        "secrets",
        "submissions",
        "telemetry",
        "tokens",
        "transactions",
        "usage-ratios.json",
        "workflow-runs",
    },
)
"""Taxonomy-vocabulary literals this module deliberately pins.

This module *is* the on-disk-name oracle -- see the module docstring. The
provenance gate names it in PERMITTED_PRODUCERS for the same reason: it must
build the expected location from its own oracle to measure the validator, and
routing it through the accessor would compare the taxonomy with itself.
"""


DERIVED_OUTPUT_SUBPATHS: Final[dict[str, str]] = {
    "cadrumo_token_dir": "tokens",
    "cadrumo_secret_store_dir": "secrets",
    "cadrumo_blob_store_dir": "blobs",
    "cadrumo_live_state_dir": "live-state",
    "cadrumo_log_dir": "logs",
    "cadrumo_llm_usage_dir": "llm-usage",
    "cadrumo_llm_run_telemetry_dir": "llm-run-telemetry",
    "cadrumo_mcp_telemetry_dir": "telemetry",
    "cadrumo_llm_cache_dir": "cache/llm-cache",
    "cadrumo_corpus_text_cache_dir": "cache/corpus-text",
    "cadrumo_corpus_search_cache_dir": "cache/corpus-search",
    "cadrumo_validation_verdict_cache_dir": "cache/registry-verdict",
    "cadrumo_submissions_dir": "submissions",
    "cadrumo_workflow_runs_dir": "workflow-runs",
    "cadrumo_drafts_dir": "drafts",
    "cadrumo_runs_dir": "runs",
    "cadrumo_justificantes_dir": "justificantes",
    "cadrumo_filing_history_dir": "filing-history",
    "cadrumo_filed_declarations_dir": "filed-declarations",
    "cadrumo_iva_compensation_history_dir": "live/iva-compensation-history",
    "cadrumo_iva_read_evidence_dir": "live/iva-read-evidence",
    "cadrumo_financial_txs_dir": "financial/transactions",
    "cadrumo_invoices_dir": "financial/invoices",
    "cadrumo_attachments_dir": "financial/attachments",
    "cadrumo_usage_ratios_path": "financial/usage-ratios.json",
}
"""The relative location of every root-derived output, stated independently.

Byte-identical strings, never normalised or resolved paths: normalisation is
exactly what would hide a moved directory behind an equal-looking comparison.
"""


def _declared_subpaths() -> dict[str, str]:
    """The same mapping as the taxonomy declares it."""
    return {
        location.settings_field: location.subpath
        for location in STORAGE_TAXONOMY.values()
        if location.scope is StorageScope.ROOT
        and location.settings_field is not None
        and location.derives_settings_default
    }


def test_the_oracle_and_the_declaration_name_the_same_locations() -> None:
    """Both directions: an added derived member is as much a drift as a dropped one."""
    declared = _declared_subpaths()
    assert DERIVED_OUTPUT_SUBPATHS, "the oracle is empty, so every assertion here is vacuous"

    assert set(declared) == set(DERIVED_OUTPUT_SUBPATHS), (
        f"only in the taxonomy: {sorted(set(declared) - set(DERIVED_OUTPUT_SUBPATHS))}; "
        f"only in the oracle: {sorted(set(DERIVED_OUTPUT_SUBPATHS) - set(declared))}"
    )

    moved = {
        field_name: (subpath, declared[field_name])
        for field_name, subpath in DERIVED_OUTPUT_SUBPATHS.items()
        if declared[field_name] != subpath
    }
    assert not moved, (
        f"declared subpaths differ from the pinned on-disk names (field: pinned -> declared): "
        f"{moved}. If the location genuinely moved, change both sides deliberately and account "
        "for the operator data still sitting at the old path; if it did not, the taxonomy is wrong"
    )


def _settings_from_env(**env: str) -> Settings:
    with isolated_aeat_env(**env):
        return settings_without_env_file()


def test_every_derived_output_dir_roots_under_storage_root(tmp_path: Path) -> None:
    """Each pinned location resolves to ``<root>/<subpath>``.

    The oracle is independent of the declaration settings validation reads, so
    this measures the validator rather than restating it.
    """
    storage_root = tmp_path / "state"

    settings = _settings_from_env(CADRUMO_LOCAL_STORAGE_ROOT=str(storage_root))

    root = settings.cadrumo_local_storage_root
    assert root == storage_root
    for field_name, subpath in DERIVED_OUTPUT_SUBPATHS.items():
        expected = root.joinpath(*subpath.split("/"))
        assert getattr(settings, field_name) == expected, field_name


def test_no_derived_output_dir_defaults_under_project_root_var(tmp_path: Path) -> None:
    """With the root pointed away from the checkout, no derived dir escapes to
    ``REPO_ROOT/var`` — proving the effective default is root-derived, not
    the ``REPO_ROOT/var/...`` placeholder each field still carries."""
    storage_root = tmp_path / "state"

    settings = _settings_from_env(CADRUMO_LOCAL_STORAGE_ROOT=str(storage_root))

    project_var = REPO_ROOT / "var"
    for field_name in DERIVED_OUTPUT_SUBPATHS:
        value = getattr(settings, field_name)
        assert value is not None, field_name
        assert storage_root in value.parents or value == storage_root, field_name
        assert project_var not in value.parents, field_name


def test_explicit_output_dir_override_wins_over_derivation(tmp_path: Path) -> None:
    """An explicit per-field env override defeats the state-root derivation."""
    storage_root = tmp_path / "state"
    explicit_runs = tmp_path / "operator-runs"

    settings = _settings_from_env(
        CADRUMO_LOCAL_STORAGE_ROOT=str(storage_root),
        CADRUMO_RUNS_DIR=str(explicit_runs),
    )

    assert settings.cadrumo_runs_dir == explicit_runs
    # A sibling derived dir still follows the root.
    assert settings.cadrumo_drafts_dir == storage_root / "drafts"


def test_cache_dirs_share_the_cache_namespace(tmp_path: Path) -> None:
    """The regenerable caches derive under the ``cache/`` on-disk namespace."""
    storage_root = tmp_path / "state"

    settings = _settings_from_env(CADRUMO_LOCAL_STORAGE_ROOT=str(storage_root))

    assert settings.cadrumo_llm_cache_dir == storage_root / "cache" / "llm-cache"
    assert settings.cadrumo_corpus_text_cache_dir == storage_root / "cache" / "corpus-text"
