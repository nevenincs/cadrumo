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

What this file quantifies over, and what it therefore cannot reach
------------------------------------------------------------------

Containment has two directions, and only one of them is provable from the
declaration. Stating which is which matters because a proof built on
:data:`~cadrumo.core.STORAGE_TAXONOMY` is blind exactly where enrollment is
incomplete, and it reports clean *from* that blindness.

**Outward — can reclaim reach outside the directory it was handed?** Provable in
full generality, because it quantifies over the filesystem rather than over the
declaration: plant a tree, run the real verb, and check where the deletions
landed. No enumeration of members is involved, so an undeclared location cannot
hide from it. :class:`TestReclaimCannotReachOutsideItsOwnDirectory` asserts it
behaviourally, including the one real escape vector — a link inside a
reclaimable directory pointing out of it.

**Inward — is everything inside a reclaimable directory safe to delete?** *Not*
provable from the declaration, because the declaration is the incomplete thing.
The strongest available statement is the one
:meth:`~TestReclaimCannotReachTaxpayerData.test_no_accepted_member_contains_a_refused_one`
makes: no *declared* protected member nests beneath an accepted one. An
**undeclared** nested location is invisible to it, and reclaim removes the whole
subtree, so such a location is deleted. That is deliberate — production nests
paths beneath enrolled categories that the declaration does not enumerate, and a
reclaim that spared them would leave the bulk of a cache behind — but the
deliberateness is what makes it worth pinning rather than leaving to inference,
so
:meth:`~TestReclaimCannotReachOutsideItsOwnDirectory.test_undeclared_nesting_beneath_an_accepted_member_is_deleted_by_design`
asserts it directly. Narrowing reclaim to declared children then reds here and
forces the decision to be re-taken rather than drifted into.

The residual risk is therefore named rather than covered: an undeclared location
holding something that must survive, sitting beneath a member declared
``RETENTION``, ``ROTATION``, or ``TTL``. Nothing in this file can detect that,
and no proof quantified over the declaration can. It is closed by enrolling the
location, not by testing harder.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....core import (
    STORAGE_TAXONOMY,
    StorageCategory,
    StorageGrouping,
    StorageNodeKind,
    StorageScope,
    storage_path,
)
from ....core.config import ensure_storage_tree, load_settings, override_settings
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


def _materialise(root: Path) -> dict[StorageCategory, Path]:
    """Build the declared tree under ``root`` and return its root-scoped paths.

    Refuses to return a path outside ``root``. Every caller below hands these
    paths to a verb that deletes, so a settings override that silently failed to
    take effect must fail the test rather than reach the real storage tree.
    """
    with override_settings(cadrumo_local_storage_root=root):
        ensure_storage_tree(load_settings())
        resolved = {category: storage_path(category) for category in STORAGE_TAXONOMY if _is_root_scoped(category)}
    for category, path in resolved.items():
        assert path.resolve().is_relative_to(root.resolve()), (
            f"{category.value} resolved to {path}, outside the test root {root} -- refusing to "
            "run a deleting verb against it"
        )
    return resolved


def _plant(directory: Path, name: str) -> Path:
    """Create ``name`` inside ``directory`` and return it."""
    directory.mkdir(parents=True, exist_ok=True)
    planted = directory / name
    planted.write_text("sentinel", encoding="utf-8")
    return planted


class TestReclaimCannotReachOutsideItsOwnDirectory:
    """The outward direction, quantified over the filesystem rather than the declaration.

    Every assertion here observes where real deletions landed after running the
    real verb, so an undeclared location cannot hide from it the way it hides
    from a proof that iterates declared members.
    """

    def test_reclaim_deletes_nothing_outside_the_directory_it_was_given(self, tmp_path) -> None:
        """The containment property itself, measured rather than inferred.

        The sibling class establishes containment by comparing declared members'
        resolved paths. That reasoning is only as complete as the declaration.
        This plants a sentinel in every declared directory, at the storage root,
        and outside the root entirely, reclaims every accepted member, and
        requires each casualty to lie beneath a directory reclaim was handed.
        """
        root = tmp_path / "storage"
        resolved = _materialise(root)
        accepted = _accepted_categories(root)

        sentinels: dict[Path, str] = {}
        for category, path in resolved.items():
            location = STORAGE_TAXONOMY[category]
            directory = path.parent if location.node_kind is StorageNodeKind.FILE else path
            sentinels[_plant(directory, "sentinel.txt")] = category.value
        sentinels[_plant(root, "root-level-sentinel.txt")] = "the storage root itself"
        sentinels[_plant(tmp_path / "beyond", "beyond-sentinel.txt")] = "outside the storage root"

        for category in accepted:
            with override_settings(cadrumo_local_storage_root=root):
                reclaim_storage_category(category, confirmed=True)

        deleted = [path for path in sentinels if not path.exists()]
        assert deleted, "reclaim deleted nothing, so this proves no containment -- the fixture has stopped biting"

        accepted_directories = [resolved[category] for category in accepted]
        escaped = [
            path for path in deleted if not any(path.is_relative_to(directory) for directory in accepted_directories)
        ]
        assert not escaped, "reclaim deleted paths outside every directory it was given: " + ", ".join(
            f"{sentinels[path]} at {path}" for path in escaped
        )

    def test_the_escape_detector_fires_when_a_deletion_lands_outside_the_permitted_set(self, tmp_path) -> None:
        """Positive control for the assertion above.

        "No deletion escaped" is also what a broken comparison reports, and a
        containment claim that cannot fail is the failure mode this campaign
        keeps finding. Mutating production to prove otherwise is not available
        here -- the service carries another agent's uncommitted work -- so this
        mutates the *permitted set* instead, exactly as the sibling class's
        nesting control does: withhold one genuinely accepted directory, and the
        deletions that really happened beneath it must be reported as escapes.
        """
        root = tmp_path / "storage"
        resolved = _materialise(root)
        accepted = _accepted_categories(root)
        reclaimable = next(
            category for category in accepted if STORAGE_TAXONOMY[category].node_kind is StorageNodeKind.DIRECTORY
        )
        sentinel = _plant(resolved[reclaimable], "sentinel.txt")

        with override_settings(cadrumo_local_storage_root=root):
            reclaim_storage_category(reclaimable, confirmed=True)
        assert not sentinel.exists(), "fixture assumption: reclaim removes a file it was pointed at"

        withheld = [resolved[category] for category in accepted if category is not reclaimable]
        assert not any(sentinel.is_relative_to(directory) for directory in withheld), (
            "with the reclaimed directory withheld from the permitted set, the real deletion "
            "beneath it must read as an escape -- if it does not, the comparison in the test "
            "above cannot fail and proves nothing"
        )

    def test_a_link_inside_a_reclaimable_directory_does_not_let_reclaim_escape(self, tmp_path) -> None:
        """The one real escape vector, exercised against a live link.

        Two shapes, because two different mechanisms defend them: a link that is
        an immediate child is caught by the verb's own ``is_symlink`` branch,
        while one nested deeper is reached by :func:`shutil.rmtree`, which
        unlinks rather than follows. Both are asserted against one target that
        must survive.

        Where the platform refuses to create a link at all -- Windows without
        Developer Mode or an elevated process -- the link shapes are absent and
        this degrades to asserting that reclaim of a populated directory leaves
        an outside directory alone. That is weaker, so the shapes actually
        exercised are named in the failure message rather than left implicit.
        """
        root = tmp_path / "storage"
        resolved = _materialise(root)
        target = tmp_path / "must-survive"
        _plant(target, "taxpayer-evidence.txt")

        reclaimable = resolved[StorageCategory.LLM_CACHE]
        reclaimable.mkdir(parents=True, exist_ok=True)
        linked: list[str] = []
        for label, parent in (("immediate-child", reclaimable), ("nested", reclaimable / "subdirectory")):
            parent.mkdir(parents=True, exist_ok=True)
            try:
                (parent / f"{label}-link").symlink_to(target, target_is_directory=True)
            except OSError:
                continue
            linked.append(label)
        _plant(reclaimable / "subdirectory", "ordinary-file.txt")

        with override_settings(cadrumo_local_storage_root=root):
            report = reclaim_storage_category(StorageCategory.LLM_CACHE, confirmed=True)

        assert report.removed_entries, "reclaim removed nothing, so nothing about escaping was exercised"
        assert (target / "taxpayer-evidence.txt").exists(), (
            f"reclaim followed a link out of its own directory and destroyed {target} "
            f"(link shapes exercised: {linked or 'none -- platform refused to create links'})"
        )

    def test_undeclared_nesting_beneath_an_accepted_member_is_deleted_by_design(self, tmp_path) -> None:
        """Pin the decision the outward proof is otherwise silent about.

        Reclaim removes an accepted member's whole subtree, including nesting the
        taxonomy never declared. That is deliberate: production writes beneath
        enrolled categories without enumerating every segment, and sparing the
        undeclared parts would leave most of a cache on disk. Because no
        declaration-quantified assertion can see those paths, the behaviour is
        asserted here directly -- narrowing reclaim to declared children reds
        this test and forces the decision to be re-taken rather than drifted
        into.
        """
        root = tmp_path / "storage"
        resolved = _materialise(root)
        accepted = _accepted_categories(root)
        assert accepted, "no member was accepted, so there is no subtree to reason about"

        undeclared = {
            category: _plant(resolved[category] / "undeclared-segment" / "deeper", "undeclared.txt")
            for category in accepted
            if STORAGE_TAXONOMY[category].node_kind is StorageNodeKind.DIRECTORY
        }
        assert undeclared, "every accepted member is file-kind, so this pins nothing"

        for category in undeclared:
            with override_settings(cadrumo_local_storage_root=root):
                reclaim_storage_category(category, confirmed=True)

        survived = {category.value: path for category, path in undeclared.items() if path.exists()}
        assert not survived, (
            "reclaim spared undeclared nesting beneath an accepted member, which changes what a "
            f"reclaim leaves on disk: {survived}. If that narrowing is intended, this test is the "
            "decision record to update."
        )
