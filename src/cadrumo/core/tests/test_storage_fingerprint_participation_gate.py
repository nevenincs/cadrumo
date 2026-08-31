"""What the drift digest covers is a decision, and it cannot be changed quietly.

The data-root digest is what a recorded run's replay refuses on. Getting its
coverage wrong is invisible in both directions and neither moves an existing
test. Exclude too much and the digest walks toward the empty-tree constant --
the documented historical defect, where every installed operator's ``db_sha256``
stayed constant forever and drift detection was defeated outright. Exclude too
little and it churns on every cache write until an operator learns the refusal
means nothing.

So this gate has two halves and both are required.

**Set equality, by field name, in both directions.** The exclusion set derived
from the taxonomy's participation axis must equal an oracle that states a reason
per entry. Both inclusions are asserted, and that two-directional shape is what
makes the discipline enforceable rather than advisory: a red here must never be
resolved by editing the oracle to match, because silently dropping a name from
the oracle reds the opposite inclusion. The oracle cannot be bent toward a
change unless the change is also made, deliberately, in the taxonomy.

**Names, never resolved-path cardinality.** Two settings may legitimately be
overridden onto one directory, which collapses a resolved-path frozenset while
exactly the same fields are consulted. A cardinality assertion would red on that
legitimate collision and pass on a real omission -- wrong in both directions at
once.

**Behavioural, with the control built in.** Writing beneath a non-participating
category must leave the digest unchanged, and writing beneath a participating
one must change it. The second assertion is the control, and it is not optional:
without it the gate passes against a digest function that has degraded to the
empty-tree constant, which is to say it would certify the exact failure it
exists to catch.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final, NamedTuple

import pytest

from ..config import override_settings
from ..observability.fingerprint import compute_data_root_sha256, data_root_cache_exclusions
from ..storage_taxonomy import (
    FINGERPRINT_EXCLUDED_STORAGE_FIELDS,
    STORAGE_TAXONOMY,
    FingerprintParticipation,
    StorageCategory,
    StorageScope,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class ExclusionExpectation(NamedTuple):
    """One field the digest must skip, and why it must."""

    settings_field: str
    reason: str


EXPECTED_EXCLUSIONS: Final[tuple[ExclusionExpectation, ...]] = (
    ExclusionExpectation(
        "cadrumo_runs_dir",
        "Self-reference. This is observability's own output, so hashing it makes every run's "
        "digest depend on the traces the immediately preceding run left, and a hermetic replay "
        "refuses on essentially every attempt.",
    ),
    ExclusionExpectation(
        "cadrumo_llm_cache_dir",
        "Regenerable prompt cache. It drifts on every model call and holds no taxpayer state.",
    ),
    ExclusionExpectation(
        "cadrumo_llm_usage_dir",
        "Usage meters. They move on every model call and carry no taxpayer state.",
    ),
    ExclusionExpectation(
        "cadrumo_llm_run_telemetry_dir",
        "Run-timing telemetry. It moves on every model call and carries no taxpayer state.",
    ),
    ExclusionExpectation(
        "cadrumo_corpus_text_cache_dir",
        "Regenerable cache keyed by content fingerprint over the finite bundled corpus.",
    ),
    ExclusionExpectation(
        "cadrumo_corpus_search_cache_dir",
        "A search index rebuilt from a static bundled corpus. It is derived from shipped bytes, "
        "so it carries no taxpayer state of its own.",
    ),
    ExclusionExpectation(
        "cadrumo_validation_verdict_cache_dir",
        "One small fingerprint-keyed verdict per registry root, deleted and rewritten on a "
        "mismatch. Regenerable and unrelated to taxpayer state.",
    ),
    ExclusionExpectation(
        "cadrumo_registry_disk_cache_dir",
        "The compiled registry pickle, rewritten on every recompile. Fingerprinting it churned "
        "the digest and produced spurious replay refusals; it was included only because the old "
        "hardcoded list could not resolve a field defaulting to None.",
    ),
)
"""The exclusion set, stated independently of the taxonomy, with a reason each.

Never edited to make a failure go away. A red means the taxonomy and this
statement of intent disagree, and the resolution is to decide which is wrong --
which is the whole point of keeping two statements.
"""


def _oracle_fields() -> frozenset[str]:
    return frozenset(expectation.settings_field for expectation in EXPECTED_EXCLUSIONS)


def test_the_oracle_and_the_taxonomy_agree_in_both_directions() -> None:
    """Neither side may drift toward the other without the other being changed."""
    declared = FINGERPRINT_EXCLUDED_STORAGE_FIELDS
    oracle = _oracle_fields()
    assert oracle, "the oracle is empty, so both inclusions below hold vacuously"

    # Both sides must be real. Two empty sets are equal, and an empty exclusion
    # set fails in the safer direction -- the digest becomes maximally
    # sensitive rather than blind -- but it would still be wrong, and silently:
    # every replay would refuse on an ordinary cache write.
    assert len(declared) >= 5, (
        f"the taxonomy declares only {len(declared)} excluded field(s): {sorted(declared)}. "
        "Several regenerable categories exist, so a set this small means the participation axis "
        "collapsed and the digest now churns on every cache write"
    )

    excluded_without_a_reason = sorted(declared - oracle)
    assert not excluded_without_a_reason, (
        f"the taxonomy excludes {excluded_without_a_reason} from the drift digest, which the "
        "oracle does not. Excluding a directory is a decision about what a replay refusal means, "
        "so state the reason here in the same change -- and if the exclusion is wrong, change the "
        "taxonomy rather than this list"
    )

    promised_but_not_excluded = sorted(oracle - declared)
    assert not promised_but_not_excluded, (
        f"the oracle expects {promised_but_not_excluded} to be excluded and the taxonomy "
        "fingerprints them. Either the participation axis regressed -- these churn the digest and "
        "produce spurious replay refusals -- or the member was retired, in which case strike its "
        "oracle entry deliberately"
    )


def test_every_oracle_entry_states_why() -> None:
    """A list of names without reasons is a copy, not an independent statement."""
    for expectation in EXPECTED_EXCLUSIONS:
        assert expectation.reason.strip(), f"{expectation.settings_field} is excluded for no stated reason"
    assert len({expectation.settings_field for expectation in EXPECTED_EXCLUSIONS}) == len(EXPECTED_EXCLUSIONS)


def test_participation_is_compared_by_name_not_by_resolved_path_count() -> None:
    """Two fields pointed at one directory is legitimate and must not red.

    The resolved-path set collapses while exactly the same fields are consulted.
    A gate asserting cardinality would fail on this and pass on a real omission.
    """
    shared = Path.cwd() / "shared-cache-target"
    with override_settings(
        cadrumo_llm_cache_dir=shared,
        cadrumo_llm_usage_dir=shared,
    ):
        from ..config import load_settings

        resolved = data_root_cache_exclusions(load_settings())

    assert len(resolved) < len(FINGERPRINT_EXCLUDED_STORAGE_FIELDS), (
        "the collision fixture did not actually collapse the resolved-path set, so this proves "
        "nothing about comparing by name"
    )
    assert shared.resolve() in resolved


def _participating_root_members() -> tuple[StorageCategory, ...]:
    return tuple(
        category
        for category, location in STORAGE_TAXONOMY.items()
        if location.scope is StorageScope.ROOT
        and location.settings_field is not None
        and location.fingerprint_participation is FingerprintParticipation.PARTICIPATING
    )


def _excluded_root_members() -> tuple[StorageCategory, ...]:
    return tuple(
        category
        for category, location in STORAGE_TAXONOMY.items()
        if location.scope is StorageScope.ROOT
        and location.settings_field is not None
        and location.fingerprint_participation is FingerprintParticipation.EXCLUDED
    )


def _digest_after_writing(root: Path, target: Path) -> str:
    from ..config import load_settings

    target.mkdir(parents=True, exist_ok=True)
    (target / "written.txt").write_text("content", encoding="utf-8")
    with override_settings(cadrumo_local_storage_root=root):
        return compute_data_root_sha256(load_settings())


def test_writing_beneath_a_participating_category_moves_the_digest(tmp_path: Path) -> None:
    """The control half. Without it the gate certifies the historical defect.

    A digest function degraded to the empty-tree constant satisfies every
    "unchanged" assertion in this module. This is the only assertion that
    notices.
    """
    root = tmp_path / "state"
    from ..config import load_settings
    from ..storage_materialization import ensure_storage_tree

    with override_settings(cadrumo_local_storage_root=root):
        ensure_storage_tree()
        settings = load_settings()
        before = compute_data_root_sha256(settings)

    participating = _participating_root_members()
    assert participating, "no participating root member resolved; the behavioural halves cover nothing"

    category = participating[0]
    field = STORAGE_TAXONOMY[category].settings_field
    assert field is not None
    after = _digest_after_writing(root, Path(getattr(settings, field)))

    assert after != before, (
        f"writing beneath {category.value}, which the taxonomy declares participating, left the "
        "data-root digest unchanged. Either the digest has degraded toward the empty-tree "
        "constant -- the defect that once defeated drift detection for every installed operator "
        "-- or this category is being excluded despite its declaration"
    )


def test_writing_beneath_an_excluded_category_leaves_the_digest_unchanged(tmp_path: Path) -> None:
    """The property half: a regenerable cache must not churn the refusal."""
    root = tmp_path / "state"
    from ..config import load_settings
    from ..storage_materialization import ensure_storage_tree

    with override_settings(cadrumo_local_storage_root=root):
        ensure_storage_tree()
        settings = load_settings()
        before = compute_data_root_sha256(settings)

    excluded = [
        category
        for category in _excluded_root_members()
        if getattr(settings, STORAGE_TAXONOMY[category].settings_field or "", None)
    ]
    assert excluded, "no excluded root member resolved; this half covers nothing"

    for category in excluded:
        field = STORAGE_TAXONOMY[category].settings_field
        assert field is not None
        after = _digest_after_writing(root, Path(getattr(settings, field)))
        assert after == before, (
            f"writing beneath {category.value}, which the taxonomy declares excluded, moved the "
            "data-root digest. A regenerable cache that churns the digest makes every replay "
            "refusal untrustworthy"
        )
