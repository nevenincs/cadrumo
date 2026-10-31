"""Where each generated output lands, pinned against an independent oracle.

Every output resolves at a fixed subpath beneath the configured storage root,
which defaults to the per-user application-data directory. Nothing relocates an
output independently of the root.

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

from ...tests.env_scope import isolated_aeat_env, settings_without_env_file
from ..config import Settings
from ..config_state_root import default_storage_root
from ..storage_taxonomy import StorageCategory
from ..storage_taxonomy_locations import (
    MATERIALISED_STORAGE_LOCATIONS,
    storage_location,
    storage_path,
    uses_external_transport,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


DERIVED_OUTPUT_SUBPATHS: Final[dict[StorageCategory, str]] = {
    StorageCategory.TEMPORARY_FILES: "tmp",
    StorageCategory.CONNECTION_SOCKETS: "runtime",
    StorageCategory.PLAYWRIGHT_BROWSERS: "components/playwright",
    StorageCategory.GNOME_EXTENSIONS: "integrations/gnome/extensions",
    StorageCategory.CHROMIUM_DATA: "chromium-data",
    StorageCategory.TOKENS: "tokens",
    StorageCategory.SECRETS: "secrets",
    StorageCategory.BLOBS: "blobs",
    StorageCategory.LIVE_STATE: "live-state",
    StorageCategory.LOGS: "logs",
    StorageCategory.LLM_USAGE: "llm-usage",
    StorageCategory.LLM_RUN_RECORD: "llm-run-telemetry",
    StorageCategory.LLM_CACHE: "cache/llm-cache",
    StorageCategory.CORPUS_SEARCH_CACHE: "cache/corpus-search",
    StorageCategory.SUBMISSIONS: "submissions",
    StorageCategory.WORKFLOW_RUNS: "workflow-runs",
    StorageCategory.DRAFTS: "drafts",
    StorageCategory.RUNS: "runs",
    StorageCategory.JUSTIFICANTES: "justificantes",
    StorageCategory.FILING_HISTORY: "filing-history",
    StorageCategory.FILED_DECLARATIONS: "filed-declarations",
    StorageCategory.IVA_COMPENSATION_HISTORY: "live/iva-compensation-history",
    StorageCategory.IVA_READ_EVIDENCE: "live/iva-read-evidence",
    StorageCategory.FINANCIAL_TRANSACTIONS: "financial/transactions",
    StorageCategory.INVOICES: "financial/invoices",
    StorageCategory.ATTACHMENTS: "financial/attachments",
    StorageCategory.USAGE_RATIOS: "financial/usage-ratios.json",
}
"""The relative location of every root-materialised output, stated independently.

Byte-identical strings, never normalised or resolved paths: normalisation is
exactly what would hide a moved directory behind an equal-looking comparison.
"""


def _declared_subpaths() -> dict[StorageCategory, str]:
    """The same mapping as the taxonomy declares it."""
    return {location.category: location.subpath for location in MATERIALISED_STORAGE_LOCATIONS}


def test_the_oracle_and_the_declaration_name_the_same_locations() -> None:
    """Both directions: an added derived member is as much a drift as a dropped one."""
    declared = _declared_subpaths()
    assert DERIVED_OUTPUT_SUBPATHS, "the oracle is empty, so every assertion here is vacuous"

    assert set(declared) == set(DERIVED_OUTPUT_SUBPATHS), (
        f"only in the taxonomy: {sorted(c.value for c in set(declared) - set(DERIVED_OUTPUT_SUBPATHS))}; "
        f"only in the oracle: {sorted(c.value for c in set(DERIVED_OUTPUT_SUBPATHS) - set(declared))}"
    )

    moved = {
        category.value: (subpath, declared[category])
        for category, subpath in DERIVED_OUTPUT_SUBPATHS.items()
        if declared[category] != subpath
    }
    assert not moved, (
        f"declared subpaths differ from the pinned on-disk names (category: pinned -> declared): "
        f"{moved}. If the location genuinely moved, change both sides deliberately and account "
        "for the operator data still sitting at the old path; if it did not, the taxonomy is wrong"
    )


def _root_relative_categories() -> dict[StorageCategory, str]:
    """The pinned locations the root owns; an OS-derived connection namespace sits outside it by design."""
    return {
        category: subpath
        for category, subpath in DERIVED_OUTPUT_SUBPATHS.items()
        if not uses_external_transport(storage_location(category))
    }


def _settings_from_env(**env: str) -> Settings:
    with isolated_aeat_env(**env):
        return settings_without_env_file()


def test_every_output_resolves_beneath_the_storage_root(tmp_path: Path) -> None:
    """Each pinned location resolves to ``<root>/<subpath>``.

    The oracle is independent of the declaration the resolver reads, so this
    measures the resolver rather than restating it.
    """
    storage_root = tmp_path / "state"

    settings = _settings_from_env(CADRUMO_STORAGE_ROOT=str(storage_root))

    assert settings.cadrumo_storage_root == storage_root
    for category, subpath in _root_relative_categories().items():
        resolved = storage_path(category, settings=settings)
        assert resolved.relative_to(storage_root).as_posix() == subpath, category.value


def test_default_outputs_follow_the_per_user_storage_root() -> None:
    """Undefined root keeps every default inside the per-user application-data directory."""
    with isolated_aeat_env():
        settings = Settings()
        root = default_storage_root()
    assert settings.cadrumo_storage_root == root
    for category, subpath in _root_relative_categories().items():
        assert storage_path(category, settings=settings).relative_to(root).as_posix() == subpath, category.value


def test_cache_outputs_share_the_cache_namespace(tmp_path: Path) -> None:
    """The regenerable caches resolve under the ``cache/`` on-disk namespace."""
    storage_root = tmp_path / "state"

    settings = _settings_from_env(CADRUMO_STORAGE_ROOT=str(storage_root))

    assert storage_path(StorageCategory.LLM_CACHE, settings=settings) == storage_root / "cache" / "llm-cache"
    assert (
        storage_path(StorageCategory.CORPUS_SEARCH_CACHE, settings=settings) == storage_root / "cache" / "corpus-search"
    )
