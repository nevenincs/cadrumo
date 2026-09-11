"""Real-behaviour tests for the generated tree state report.

The classifier decides what a repair would be, and getting it wrong inverts the
advice: its first version called twenty-five safe trees record drift. Every state
is therefore reached from input written here, and the serialisation subtraction
has its own case.
"""

from __future__ import annotations

import pytest

from cadrumo.core.resources.bundled_data import bundled_path

from ..analysis import generated_tree_state as _generated_tree_state_module
from ..analysis.generated_tree_state import STATES, classify_comparison, tree_states
from ..compiler.authority import compiled_bundled_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MANIFEST = "_generation.provenance.json"


def test_a_tree_with_no_committed_bytes_needs_publication() -> None:
    """Publication is a different act from republication and is not blocked alike."""
    assert classify_comparison((), committed=False) == "never_committed"


def test_a_tree_reproducing_exactly_needs_nothing() -> None:
    assert classify_comparison((), committed=True) == "reproducible"


def test_manifest_only_staleness_is_safe_to_republish() -> None:
    assert classify_comparison((_MANIFEST,), committed=True) == "manifest_only_stale"


def test_a_differing_record_is_drift_and_must_not_be_republished() -> None:
    """The two modelo 347 revisions are in this state and the ledger says why."""
    differing = ("0002-record-m347-declarado.toml", _MANIFEST)
    assert classify_comparison(differing, committed=True) == "record_drift"


def test_a_reformatted_record_is_not_drift() -> None:
    """Serialisation-only differences are subtracted before the state is decided.

    Modelo 322's 2023 tree lists six differing files, five of them reformattings
    and one the manifest. Counted raw it reads as drift and "do not republish";
    counted after the subtraction it is manifest-only staleness and safe. The
    first version of the classifier did the former for every tree in the corpus.
    """
    records = tuple(f"000{n}-record-m322-page-0{n}.toml" for n in range(1, 6))
    assert (
        classify_comparison((*records, _MANIFEST), committed=True, serialization_only=records) == "manifest_only_stale"
    )
    # Without the subtraction the same input reads as drift, which is the bug.
    assert classify_comparison((*records, _MANIFEST), committed=True) == "record_drift"


def test_a_tree_differing_only_in_serialisation_reproduces() -> None:
    """No meaningful difference at all, so nothing needs doing."""
    records = ("0001-record.toml",)
    assert classify_comparison(records, committed=True, serialization_only=records) == "reproducible"


def test_every_declared_state_is_reachable() -> None:
    """A state with no proof stops being reported without anyone noticing."""
    reached = {
        classify_comparison((), committed=False),
        classify_comparison((), committed=True),
        classify_comparison((_MANIFEST,), committed=True),
        classify_comparison(("0001-record.toml",), committed=True),
    }
    assert reached == set(STATES)


def test_a_comparison_failure_is_excluded_not_reported_reproducible(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A raised comparison failure must never read as the strongest possible claim.

    Substituting an empty diff for a re-render that raised would report
    ``reproducible`` for a committed tree :func:`tree_states` never actually
    compared -- indistinguishable from a genuine byte-for-byte match. The
    revision is excluded from the census instead and named on stderr, the
    same discipline the sibling analysis screens already apply to their own
    inapplicable revisions.
    """
    authority = compiled_bundled_authority()
    modelo_id, revision_id = next(
        (str(modelo.id), str(revision_id))
        for modelo in authority.modelos
        for revision_id in modelo.revisions
        if (
            bundled_path("registry", "aeat", "modelos", str(modelo.id), "revisions", str(revision_id), "export")
            / _MANIFEST
        ).is_file()
    )

    def _broken_compare(authority: object, *, modelo: str, revision: str) -> object:
        raise ValueError(f"synthetic comparison failure for {modelo}/{revision}")

    monkeypatch.setattr(_generated_tree_state_module, "compare_revision_against_committed", _broken_compare)

    states = tree_states(authority, (modelo_id,))

    assert not any(state.revision == revision_id for state in states)
    assert states == ()
    warning = capsys.readouterr().err
    assert "generated_tree_state:" in warning
    assert "could not be re-rendered for comparison and were excluded" in warning
