"""Shared synthetic-locale lifecycle for registry tests."""

import hashlib
import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from .....tests.locales_root_fixture import locales_root_scope


class SyntheticLocaleState:
    root: Path | None = None


synthetic_locale_state = SyntheticLocaleState()

#: EXACT node ids of tests that exercise the real bundled/committed registry
#: corpus rather than a synthetic one, and so must keep the packaged locale
#: catalogue untouched. Membership is by exact node id, never a name
#: substring: a substring match is a silent opt-out — any future test whose
#: name happens to contain one of these words would stop getting the
#: synthetic wipe and nothing would fail, it would just quietly assert
#: against different data than its author intended. Extend this set (never
#: hand-roll a parallel scope, and never widen the match back to a
#: substring) when a new bundled-data test needs the same escape; a renamed
#: member here fails LOUDLY — the renamed test then runs against an
#: unexpectedly empty synthetic catalogue — rather than drifting silently.
BUNDLED_DATA_TEST_IDS: frozenset[str] = frozenset(
    {
        "src/cadrumo/domain/calculations/registry/tests/test_semantic_role.py"
        "::TestTypoTwinWarning::test_reviewed_singleton_roles_are_marked_in_committed_registry",
        "src/cadrumo/domain/calculations/registry/tests/test_semantic_role.py"
        "::TestTypoTwinWarning::test_m100_2024_2025_family_profile_roles_are_shared",
        "src/cadrumo/domain/calculations/registry/tests/test_semantic_role.py"
        "::TestTypoTwinWarning::test_reviewed_singleton_markers_do_not_warn",
        "src/cadrumo/domain/calculations/registry/tests/test_semantic_role.py"
        "::TestSignedCuotaResultadoRoles::test_irpf_and_is_signed_result_roles_are_bound_to_committed_casillas",
        "src/cadrumo/domain/calculations/registry/tests/test_semantic_role.py"
        "::TestModelo347QuarterlyContraparteRolesAreIntentionalSingletons"
        "::test_quarterly_contraparte_importe_roles_marked_intentional_singleton",
        "src/cadrumo/domain/calculations/registry/tests/test_cross_revision_drift.py"
        "::test_cross_revision_validator_accepts_committed_corpus",
        "src/cadrumo/domain/calculations/registry/tests/test_cross_revision_drift.py"
        "::test_committed_corpus_non_overlapping_inventory_keeps_annual_m100_drift_visible",
        "src/cadrumo/domain/calculations/registry/tests/test_cross_revision_drift.py"
        "::test_committed_m100_continuity_surface_for_0582_is_loaded",
        "src/cadrumo/domain/calculations/registry/tests/test_cross_revision_drift.py"
        "::test_committed_m100_continuity_surface_for_1038_retirement_is_loaded",
        "src/cadrumo/domain/calculations/registry/tests/test_cross_revision_drift.py"
        "::test_committed_m100_continuity_surface_for_0063_legal_refs_is_loaded",
        "src/cadrumo/domain/calculations/registry/tests/test_cross_revision_drift.py"
        "::test_committed_m100_continuity_surface_for_0070_label_and_legal_refs_is_loaded",
        "src/cadrumo/domain/calculations/registry/tests/test_cross_revision_drift.py"
        "::test_committed_m100_strict_continuity_surface_rejects_covered_label_drift",
        "src/cadrumo/domain/calculations/registry/tests/test_cross_revision_drift.py"
        "::test_backend_registry_validation_accepts_committed_corpus_drift_gate",
        "src/cadrumo/domain/calculations/registry/tests/test_label_artifacts.py"
        "::test_committed_corpus_has_no_unresolved_label_placeholders",
    },
)


@pytest.fixture(autouse=True)
def _synthetic_locale_scope(tmp_path: Path, request: pytest.FixtureRequest) -> Iterator[None]:
    if request.node.nodeid in BUNDLED_DATA_TEST_IDS:
        yield
        return
    (tmp_path / "es.yml").write_text("", encoding="utf-8", newline="\n")
    with locales_root_scope(tmp_path):
        synthetic_locale_state.root = tmp_path
        try:
            yield
        finally:
            synthetic_locale_state.root = None


def _write_test_label(label: str) -> str:
    """Enroll one synthetic Spanish value in the test-only catalogue.

    Lives beside :data:`synthetic_locale_state` because it writes into the
    catalogue that state owns: a copy in a test module can only append while
    the scope happens to be open, and cannot know when it is not.
    """
    key = f"test.schema.casilla.{hashlib.sha256(label.encode('utf-8')).hexdigest()}.label"
    if synthetic_locale_state.root is not None:
        with (synthetic_locale_state.root / "es.yml").open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(f"{json.dumps(key)}: {json.dumps(label, ensure_ascii=False)}\n")
    return key


__all__ = ["_synthetic_locale_scope", "_write_test_label", "synthetic_locale_state"]
