"""What ``reclaim`` can reach when no profile is active.

``config storage`` is bootstrap-exempt, so ``reclaim`` runs outside the
profile-bound write guard. That is correct — it must work on a machine with no
profile, and the write guard would refuse it there — but it means the lifecycle
guard is now the only thing standing between the verb and the encrypted
substrate. A guarantee resting on one guard should be asserted as a property
rather than inferred from that guard's own tests.

The sibling suite proves the guard refuses the right members **today**. This one
proves the containment holds as the taxonomy **grows**: the accepted set is
derived by invoking the real verb over every declared member, never from a
predicate that could drift away from the guard it claims to mirror, and the
assertions are over axes rather than a list of names. A member declared
``RETENTION`` at bucket scope tomorrow cannot quietly join the accepted set
without reddening this file.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....core import (
    STORAGE_TAXONOMY,
    StorageCategory,
    StorageGrouping,
    StorageScope,
    storage_path,
)
from ....core.config import override_settings
from .._errors import StorageManagementError
from .._service import RECLAIMABLE_LIFECYCLES, reclaim_storage_category

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _accepted_categories(root: Path) -> list[StorageCategory]:
    """Return every member the real verb accepts, with no profile active.

    Derived by invoking ``reclaim`` rather than by re-stating its predicate. A
    predicate copied into the test would keep agreeing with itself after the
    guard changed underneath it, which is the one failure this file exists to
    rule out.
    """
    accepted: list[StorageCategory] = []
    for category in STORAGE_TAXONOMY:
        with override_settings(cadrumo_local_storage_root=root):
            try:
                reclaim_storage_category(category, confirmed=True)
            except StorageManagementError:
                continue
        accepted.append(category)
    return accepted


class TestReclaimCannotReachTaxpayerData:
    def test_the_accepted_set_is_not_empty(self, tmp_path) -> None:
        """Non-vacuity floor.

        Every assertion below quantifies over the accepted set, so a guard that
        refused everything would satisfy all of them while proving nothing.
        """
        assert _accepted_categories(tmp_path), "reclaim accepted nothing, so the containment claims are vacuous"

    def test_no_accepted_member_lives_inside_a_profile_bucket(self, tmp_path) -> None:
        """The containment property, stated over resolved paths.

        Scope is the guard's own reasoning, so asserting only scope would test
        the guard against itself. This asserts where the accepted paths actually
        land: outside the bucket container, which is the tree holding every
        profile's encrypted database, its blobs, and the keystore that opens
        them.
        """
        with override_settings(cadrumo_local_storage_root=tmp_path):
            buckets_root = storage_path(StorageCategory.BUCKETS)

        for category in _accepted_categories(tmp_path):
            with override_settings(cadrumo_local_storage_root=tmp_path):
                resolved = storage_path(category)
            assert not resolved.is_relative_to(buckets_root), (
                f"reclaim accepts {category.value}, which resolves inside the bucket container at {resolved}"
            )

    def test_no_accepted_member_is_bucket_or_keystore_scoped(self, tmp_path) -> None:
        for category in _accepted_categories(tmp_path):
            assert STORAGE_TAXONOMY[category].scope is StorageScope.ROOT

    def test_no_accepted_member_belongs_to_the_state_substrate(self, tmp_path) -> None:
        """The encrypted substrate, its key material, and the audit over both.

        Grouping is declared independently of lifecycle, so this is a second
        axis agreeing rather than a restatement of the guard's own test.
        """
        for category in STORAGE_TAXONOMY:
            if category not in _accepted_categories(tmp_path):
                continue
            assert STORAGE_TAXONOMY[category].grouping is not StorageGrouping.STATE

    def test_every_accepted_member_declares_a_bounded_lifecycle(self, tmp_path) -> None:
        for category in _accepted_categories(tmp_path):
            assert STORAGE_TAXONOMY[category].lifecycle in RECLAIMABLE_LIFECYCLES

    def test_no_accepted_member_contains_a_refused_one(self, tmp_path) -> None:
        """Reclaiming a permitted category must not delete a protected one.

        Reclaim removes a category's whole subtree, including nesting the
        taxonomy does not declare, so containment is not settled by the accepted
        member's own classification: if a protected member sat beneath an
        accepted one, reclaiming the parent would take the child with it. The
        registry parity store, declared at ``audit/registry/parity`` beneath the
        ``audit`` category, is the shape that makes this reachable rather than
        theoretical.

        Compared with :meth:`~pathlib.PurePath.is_relative_to` rather than a
        string prefix, because ``cache/registry`` is accepted while
        ``cache/registry-verdict`` is protected: a prefix test reads the second
        as living inside the first and would fail against a correct tree.
        """
        accepted = _accepted_categories(tmp_path)
        with override_settings(cadrumo_local_storage_root=tmp_path):
            resolved = {category: storage_path(category) for category in STORAGE_TAXONOMY if _is_root_scoped(category)}

        for category in accepted:
            parent = resolved[category]
            for other, path in resolved.items():
                if other == category or other in accepted:
                    continue
                assert not path.is_relative_to(parent), (
                    f"reclaiming {category.value} would delete {other.value} at {path}, which it refuses directly"
                )

    def test_the_containment_check_would_notice_a_protected_member_nested_below_an_accepted_one(
        self,
        tmp_path,
    ) -> None:
        """Positive control for the assertion above.

        The nesting check passes trivially if ``is_relative_to`` never returns
        true for any pair, which is also what a broken comparison looks like.
        Constructing the containment it is meant to catch proves the comparison
        can fire.
        """
        with override_settings(cadrumo_local_storage_root=tmp_path):
            accepted_parent = storage_path(StorageCategory.LOGS)
            planted = accepted_parent / "would-be-protected"

        assert planted.is_relative_to(accepted_parent)


def _is_root_scoped(category: StorageCategory) -> bool:
    """Return whether ``category`` resolves without a bucket identifier."""
    return STORAGE_TAXONOMY[category].scope is StorageScope.ROOT
