"""W16.P48 closure aggregate tests.

Verifies every closure contract for Steps S620-S630.  Each assertion is
real-behavior: no mocks, no skips, no tautologies.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]

_REPO_ROOT = Path(__file__).parent.parent.parent  # .../chore-476-restructure-execution
_SRC_ROOT = _REPO_ROOT / "src" / "aeat"


# ---------------------------------------------------------------------------
# S620 — IdentityError is an AeatError subclass and is raised on bad input
# ---------------------------------------------------------------------------


def test_s620_identity_error_is_aeat_error_subclass() -> None:
    from .core.errors import AeatError
    from .core.identity._documents import IdentityError

    assert issubclass(IdentityError, AeatError), "IdentityError must be a subclass of AeatError"


def test_s620_identity_error_raised_not_valueerror() -> None:
    """validate_identity raises IdentityError, not a bare ValueError."""
    from .core.identity._documents import IdentityError, validate_identity

    with pytest.raises(IdentityError):
        validate_identity("INVALID-DOC-XYZ-999")


# ---------------------------------------------------------------------------
# S621 — example_limit=0 raises RegistryValidationError, not ValueError
# ---------------------------------------------------------------------------


def test_s621_example_limit_zero_raises_registry_validation_error() -> None:
    from .domain.calculations.registry._errors import RegistryValidationError
    from .domain.calculations.registry._validate_cross_revision import (
        summarize_non_overlapping_cross_revision_casilla_drift,
    )

    with pytest.raises(RegistryValidationError, match="example_limit"):
        summarize_non_overlapping_cross_revision_casilla_drift([], example_limit=0)


# ---------------------------------------------------------------------------
# S622 — RevisionValidationContext has no Any in its type annotations
# ---------------------------------------------------------------------------


def test_s622_revision_validation_context_no_any_annotation() -> None:
    import typing

    from .domain.calculations.registry._validate_revision_context import (
        RevisionValidationContext,
    )

    hints = typing.get_type_hints(RevisionValidationContext)
    any_fields = [name for name, annotation in hints.items() if "Any" in str(annotation)]
    assert not any_fields, f"RevisionValidationContext has fields with Any annotation: {any_fields}"


# ---------------------------------------------------------------------------
# S623 — ANY-RETURN-RATIONALE-PRE303-RAW-STAGING marker present in
#         external_constants.py within 3 lines of pre303_raw field
# ---------------------------------------------------------------------------


def test_s623_pre303_raw_rationale_marker_present() -> None:
    source_path = _SRC_ROOT / "core" / "external_constants.py"
    lines = source_path.read_text(encoding="utf-8").splitlines()

    marker = "ANY-RETURN-RATIONALE-PRE303-RAW-STAGING"
    for i, line in enumerate(lines):
        if "pre303_raw" in line:
            window = lines[max(0, i - 3) : i + 4]
            if any(marker in w for w in window):
                return
    pytest.fail(f"Marker {marker!r} not found within 3 lines of 'pre303_raw' in external_constants.py")


# ---------------------------------------------------------------------------
# S624 — _synthesise_single_line_if_needed has no dict[str, Any] in its
#         return annotation (marker comment present instead)
# ---------------------------------------------------------------------------


def test_s624_synthesise_single_line_no_bare_dict_any_return() -> None:
    source_path = _SRC_ROOT / "application" / "invoices" / "_importing.py"
    source = source_path.read_text(encoding="utf-8")

    pattern = re.compile(r"def _synthesise_single_line_if_needed\([^)]*\)\s*->\s*([^\n:]+)")
    match = pattern.search(source)
    assert match is not None, "_synthesise_single_line_if_needed not found in _importing.py"

    return_annotation = match.group(1).strip()
    assert "dict[str, Any]" not in return_annotation, (
        f"_synthesise_single_line_if_needed must not return dict[str, Any]; "
        f"got return annotation: {return_annotation!r}"
    )


# ---------------------------------------------------------------------------
# S625 — CLASSIFIED_BY_MANUAL constant equals "manual"; no bare "manual"
#         literal in transactions/_models.py outside docstrings
# ---------------------------------------------------------------------------


def test_s625_classified_by_manual_constant_value() -> None:
    from .core.external_constants import CLASSIFIED_BY_MANUAL

    assert CLASSIFIED_BY_MANUAL == "manual"


def test_s625_no_bare_manual_literal_in_transactions_models() -> None:
    source_path = _SRC_ROOT / "domain" / "transactions" / "_models.py"
    source = source_path.read_text(encoding="utf-8")

    stripped = re.sub(r'""".*?"""', "", source, flags=re.DOTALL)
    stripped = re.sub(r"'''.*?'''", "", stripped, flags=re.DOTALL)

    bare_hits = [i + 1 for i, line in enumerate(stripped.splitlines()) if re.search(r'"manual"', line)]
    assert not bare_hits, (
        f'Bare "manual" literal found in _models.py at lines {bare_hits}; use CLASSIFIED_BY_MANUAL constant instead'
    )


# ---------------------------------------------------------------------------
# S626 — no prose-only "# deferred" comment adjacent to type: ignore in
#         errors/_registry.py
# ---------------------------------------------------------------------------


def test_s626_no_prose_deferred_comment_in_errors_registry() -> None:
    source_path = _SRC_ROOT / "core" / "errors" / "_registry.py"
    lines = source_path.read_text(encoding="utf-8").splitlines()

    violations = []
    for i, line in enumerate(lines):
        if "type: ignore" in line and re.search(r"#\s*deferred\b", line, re.IGNORECASE):
            violations.append((i + 1, line.strip()))
        if i > 0 and "type: ignore" in line:
            prev = lines[i - 1]
            if re.search(r"#\s*deferred\b", prev, re.IGNORECASE) and "CAST-RATIONALE" not in prev:
                violations.append((i, prev.strip()))

    assert not violations, "Prose-only '# deferred' comment adjacent to type: ignore found:\n" + "\n".join(
        f"  line {ln}: {txt}" for ln, txt in violations
    )


# ---------------------------------------------------------------------------
# S627 — CAST-RATIONALE-DYNAMIC-CLASSVAR-PROBE marker present in _base.py
# ---------------------------------------------------------------------------


def test_s627_dynamic_classvar_probe_rationale_marker_present() -> None:
    source_path = _SRC_ROOT / "adapters" / "inbound" / "financial" / "providers" / "_base.py"
    source = source_path.read_text(encoding="utf-8")
    marker = "CAST-RATIONALE-DYNAMIC-CLASSVAR-PROBE"
    assert source.count(marker) >= 2, (
        f"Expected at least 2 occurrences of {marker!r} in providers/_base.py; found {source.count(marker)}"
    )


# ---------------------------------------------------------------------------
# S628 — no pytest.skip( in core/test_profile.py
# ---------------------------------------------------------------------------


def test_s628_no_pytest_skip_in_test_profile() -> None:
    source_path = _SRC_ROOT / "core" / "test_profile.py"
    source = source_path.read_text(encoding="utf-8")
    hits = [i + 1 for i, line in enumerate(source.splitlines()) if "pytest.skip(" in line]
    assert not hits, f"pytest.skip( found in core/test_profile.py at lines {hits}"


# ---------------------------------------------------------------------------
# S629 — no pytest.skip( in modelo/test_taxation_comparison.py
# ---------------------------------------------------------------------------


def test_s629_no_pytest_skip_in_test_taxation_comparison() -> None:
    source_path = _SRC_ROOT / "application" / "modelo" / "test_taxation_comparison.py"
    source = source_path.read_text(encoding="utf-8")
    hits = [i + 1 for i, line in enumerate(source.splitlines()) if "pytest.skip(" in line]
    assert not hits, f"pytest.skip( found in test_taxation_comparison.py at lines {hits}"


# ---------------------------------------------------------------------------
# S630 — final assertions in singleton tests are not bare "is not None"
# ---------------------------------------------------------------------------


def test_s630_topics_singleton_test_has_typed_assertion() -> None:
    source_path = _SRC_ROOT / "core" / "resources" / "_repos" / "test_singletons.py"
    source = source_path.read_text(encoding="utf-8")

    topics_block_start = source.find("def test_topics_singleton_loads_real_catalogue")
    assert topics_block_start >= 0, "test_topics_singleton_loads_real_catalogue not found"
    next_def = source.find("\ndef test_", topics_block_start + 10)
    block = source[topics_block_start : next_def if next_def > 0 else len(source)]

    assert "isinstance(" in block or "len(" in block, (
        "test_topics_singleton_loads_real_catalogue must contain a typed or length assertion"
    )


def test_s630_legal_params_singleton_test_has_typed_assertion() -> None:
    source_path = _SRC_ROOT / "core" / "resources" / "_repos" / "test_singletons.py"
    source = source_path.read_text(encoding="utf-8")

    legal_block_start = source.find("def test_legal_parameters_singleton_loads_real_mapping")
    assert legal_block_start >= 0, "test_legal_parameters_singleton_loads_real_mapping not found"
    next_def = source.find("\ndef test_", legal_block_start + 10)
    block = source[legal_block_start : next_def if next_def > 0 else len(source)]

    assert "isinstance(" in block, (
        "test_legal_parameters_singleton_loads_real_mapping must contain an isinstance assertion"
    )


# ---------------------------------------------------------------------------
# Prior-wave inventory ratchets — invoked via subprocess for clean isolation
# ---------------------------------------------------------------------------


def _run_inventory_ratchet(test_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(test_path), "-q", "--tb=short"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"Inventory ratchet {test_path.name} FAILED:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def test_prior_wave_utf8_enrollment_inventory_passes() -> None:
    _run_inventory_ratchet(_SRC_ROOT / "test_utf8_enrollment_inventory.py")


def test_prior_wave_cast_rationale_inventory_passes() -> None:
    _run_inventory_ratchet(_SRC_ROOT / "test_cast_rationale_inventory.py")


def test_prior_wave_latin1_encoding_constant_enrollment_passes() -> None:
    _run_inventory_ratchet(_SRC_ROOT / "test_latin1_encoding_constant_enrollment.py")


def test_prior_wave_enum_constant_extraction_inventory_passes() -> None:
    _run_inventory_ratchet(_SRC_ROOT / "test_enum_constant_extraction_inventory.py")
