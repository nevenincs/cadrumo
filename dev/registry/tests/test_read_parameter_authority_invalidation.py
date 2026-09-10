"""Development-only regression coverage for parameter reads after authoring edits.

This suite materialises and rewrites a synthetic *authoring* tree. It therefore
belongs to the development registry boundary rather than the shipped package's
test tree. Production parameter reads consume only the immutable bundled
authority and expose no root override.

These tests exercise the default branch by redirecting only the bundled registry
root, so the code path under test is the real one. The verdict for each tree
state is certified in advance through the real verdict store: that is what makes
the regime WARM, which is the regime the defect lived in, and it keeps the
subject of the test cache invalidation rather than registry validation. The
source root stays genuine throughout.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.core import resources as core_resources
from cadrumo.core.config import override_settings
from cadrumo.domain.calculations.registry import formula_runtime_ops
from cadrumo.domain.calculations.registry._loader_internals import _collect_registry_tree_fingerprints_uncached
from dev.registry.compiler.source_evidence_fingerprint import collect_source_evidence_fingerprints
from dev.registry.compiler.verdict_cache import certify_registry_validation, compute_verdict_key
from dev.registry.compiler.convenio import collect_convenio_fingerprints
from cadrumo.domain.calculations.registry.formula_runtime_ops import read_parameter
from cadrumo.domain.calculations.registry.identity import compute_walked_tree_digest
from cadrumo.domain.calculations.registry.loader_cache import _bundled_registry_root
from cadrumo.domain.calculations.registry.loader_fingerprints import clear_fingerprint_cache
from dev.registry.compiler.m303_orden_manifest import collect_m303_annual_orden_fingerprints
from cadrumo.tests.attribute_scope import scoped_attribute

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO_ID = "999"
_REVISION_ID = "2025"
_PARAMETER_ID = "synthetic-rate"
_VALUE_SENTINEL = "@@VALUE@@"

_MODELO_TEXT = """
[modelo]
id = "999"
tax_domain = "iva"
cadence = "annual"
jurisdiction = "ES-AEAT"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[revisions."2025"]
valid_from = 2025-01-01
period_selector = { years = [2025], periods = ["0A"] }
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[[revisions."2025".parameters]]
id = "synthetic-rate"
data_type = "ratio"
unit = "ratio"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[[revisions."2025".parameters.values]]
value = "@@VALUE@@"
date_axis = "filing_period"
valid_from = 2025-01-01
valid_to = 2025-12-31
""".lstrip()


#: The one registry-wide declaration the loader requires of any tree.
_SUPPORTED_FILING_YEARS_TEXT = (
    "[supported_filing_years]\nyears = [2025]\n\n"
    "[sociedades_annual_manual_coverage]\n"
    "dispositions = [{ year = 2025, status = \"unpublished\", "
    "official_locator = \"https://example.com/manuals\", observed_at = 2026-09-10, "
    "acquisition_condition_key = \"application.registry.manuals.coverage.recheck_aeat_publication\" }]\n"
)


def _write_registry_tree(tmp_path: Path, *, value: str) -> Path:
    """Materialise (or rewrite) the synthetic authoring tree and return its root."""
    registry_root = tmp_path / "registry" / "aeat"
    legal_dir = registry_root / "legal"
    legal_dir.mkdir(parents=True, exist_ok=True)
    # The loader requires every authoring tree to declare its supported
    # filing years, so a synthetic tree omitting it fails to load before
    # this test can observe the parameter edit it exists to prove.
    (legal_dir / "supported-filing-years.toml").write_text(
        _SUPPORTED_FILING_YEARS_TEXT,
        encoding="utf-8",
        newline="\n",
    )
    modelos_dir = registry_root / "modelos"
    modelos_dir.mkdir(parents=True, exist_ok=True)
    (modelos_dir / "999.toml").write_text(_MODELO_TEXT.replace(_VALUE_SENTINEL, value), encoding="utf-8", newline="\n")
    return registry_root


def _certify_current_tree(registry_root: Path, source_root: Path) -> None:
    """Persist a green verdict for the tree exactly as it stands on disk.

    Certifies the same key :func:`_load_authority` derives -- the complete
    registry, treaty and supplementary-orden fingerprints plus the source
    evidence -- so the load reaches the warm, verdict-certified regime the
    defect lived in.
    """
    resolved = registry_root.expanduser().resolve()
    registry_fingerprints = (
        _collect_registry_tree_fingerprints_uncached(resolved)
        + collect_convenio_fingerprints(resolved)
        + collect_m303_annual_orden_fingerprints(resolved)
    )
    source_evidence = collect_source_evidence_fingerprints(source_root.expanduser().resolve())
    certify_registry_validation(
        resolved,
        verdict_key=compute_verdict_key(
            identity_digest=compute_walked_tree_digest(registry_fingerprints),
            source_evidence_fingerprints=source_evidence,
        ),
    )


@pytest.fixture
def redirected_bundled_registry_root() -> Iterator[Callable[[Path], Path]]:
    """Redirect only ``bundled_path("registry", "aeat")`` to a caller-chosen tree.

    The default-root branch is the one that carried the defect, and the only way
    to reach it without editing the shipped registry tree is to move where that
    root points. Everything else -- the source root, the loader, the authority,
    the verdict store -- stays real.
    """
    real_bundled_path = core_resources.bundled_path
    target: dict[str, Path] = {}

    def _redirected(*parts: str) -> Path:
        if tuple(parts) == ("registry", "aeat") and "root" in target:
            return target["root"]
        return real_bundled_path(*parts)

    def _point_at(root: Path) -> Path:
        target["root"] = root
        _bundled_registry_root.cache_clear()
        clear_fingerprint_cache()
        return real_bundled_path()

    with scoped_attribute(core_resources, "bundled_path", _redirected):
        yield _point_at
    _bundled_registry_root.cache_clear()
    clear_fingerprint_cache()


def test_read_parameter_sees_a_registry_edit_under_the_default_root(
    tmp_path: Path,
    redirected_bundled_registry_root: Callable[[Path], Path],
) -> None:
    """An edit to the default root's tree must reach the very next read.

    Settles with one read before the measured sequence, so the caches are in a
    steady warm state rather than a partially cold first load, and both tree
    states are verdict-certified in advance so neither read can be answered by
    a validation refusal instead of a value.
    """
    registry_root = _write_registry_tree(tmp_path, value="0.05")
    source_root = redirected_bundled_registry_root(registry_root)

    with override_settings(cadrumo_validation_verdict_cache_dir=tmp_path / "verdict"):
        _certify_current_tree(registry_root, source_root)

        settling = read_parameter(
            _MODELO_ID,
            _REVISION_ID,
            _PARAMETER_ID,
            date_context={"filing_period": date(2025, 6, 30)},
        )
        assert settling == Decimal("0.05")

        before = read_parameter(
            _MODELO_ID,
            _REVISION_ID,
            _PARAMETER_ID,
            date_context={"filing_period": date(2025, 6, 30)},
        )
        assert before == Decimal("0.05")

        _write_registry_tree(tmp_path, value="0.06")
        _certify_current_tree(registry_root, source_root)

        after = read_parameter(
            _MODELO_ID,
            _REVISION_ID,
            _PARAMETER_ID,
            date_context={"filing_period": date(2025, 6, 30)},
        )

    assert after == Decimal("0.06"), (
        "read_parameter served a registry parameter from an authority that predates the edit on disk"
    )


def test_no_memo_in_the_parameter_read_module_can_outlive_a_registry_edit() -> None:
    """No callable in this module carries a functools memo.

    Derived rather than enumerated, so it also catches a memo added to a
    function this test has never heard of. Any memo here is keyed on the
    arguments of a registry READ, and none of those arguments -- a modelo id, a
    revision id, a parameter id, a root path -- changes when the registry
    changes, so any such memo can outlive the tree it was computed from. The
    bounded caches this module must rely on live behind the authority, keyed on
    the complete tree fingerprint.
    """
    memoised = sorted(name for name, value in vars(formula_runtime_ops).items() if hasattr(value, "cache_info"))
    assert memoised == [], (
        f"functools-memoised callables in the registry parameter-read module cannot observe a registry edit: {memoised}"
    )
