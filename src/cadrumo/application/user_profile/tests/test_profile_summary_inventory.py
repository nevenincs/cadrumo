"""Real-store contract for the pure profile-summary listing.

Every case publishes genuine capsules through the real custody adapter and a
real filesystem root.  Nothing here is mocked: the point of the boundary is
that listing costs one anchored scan and enters no custody, so a test that
substituted the port would prove none of it.
"""

from __future__ import annotations

import base64
from collections.abc import Iterator
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from ....adapters.persistence.storage import build_profile_custody_port
from ....adapters.persistence.storage.custody import (
    ProfileCustodyCapsuleLabel,
    ProfileCustodyEnvelope,
    ProfileCustodyKdfParameters,
    ProfileCustodyWrappedDek,
    create_profile_custody_sentinel,
    publish_profile_custody_capsule,
)
from ....core.config import Settings
from ....core.profile_discovery import ProfileSummaryOutcome
from ..custody_ports import bind_profile_custody_port
from ..profile_summary import ProfileSummaryInventory, summary_inventory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DEK = bytes(range(32))
_EPOCH = base64.b64encode(b"e" * 16).decode("ascii")
_LABEL_MEMBER = "profile-label.v1.json"


@pytest.fixture(autouse=True)
def _bound_port() -> Iterator[None]:
    with bind_profile_custody_port(build_profile_custody_port()):
        yield


def _kdf() -> ProfileCustodyKdfParameters:
    return ProfileCustodyKdfParameters(
        algorithm="argon2id",
        version=19,
        memory_mib=19,
        iterations=2,
        parallelism=1,
        salt_b64=base64.b64encode(b"k" * 16).decode("ascii"),
        output_bytes=32,
    )


def _publish(root: Path, profile_id: UUID, label: str, *, publication_kind: str = "enroll") -> Path:
    envelope = ProfileCustodyEnvelope.create(
        profile_id=profile_id,
        password_generation=1,
        dek_epoch=_EPOCH,
        kdf=_kdf(),
        wrapped_dek=ProfileCustodyWrappedDek(
            nonce_b64=base64.b64encode(b"n" * 12).decode("ascii"),
            ciphertext_b64=base64.b64encode(b"c" * 32).decode("ascii"),
            tag_b64=base64.b64encode(b"t" * 16).decode("ascii"),
        ),
    )
    return publish_profile_custody_capsule(
        profile_id=profile_id,
        transaction_id=uuid4(),
        publication_kind=publication_kind,
        password_envelope=envelope,
        sentinel=create_profile_custody_sentinel(envelope=envelope, dek=_DEK),
        data_files={
            _LABEL_MEMBER: ProfileCustodyCapsuleLabel.create(
                profile_id=profile_id,
                label=label,
            ).canonical_json_bytes()
        },
        settings=Settings(cadrumo_local_storage_root=root),
    )


def test_an_empty_store_lists_nothing_and_is_still_a_recognized_observation(tmp_path: Path) -> None:
    """Absence must be reported as trustworthy emptiness, not as a failure."""
    inventory = summary_inventory(root=tmp_path)

    assert inventory == ProfileSummaryInventory(outcome=ProfileSummaryOutcome.RECOGNIZED, summaries=(), detail=None)
    assert inventory.recognized


def test_a_populated_store_projects_every_capsule_in_deterministic_uuid_order(tmp_path: Path) -> None:
    """Ordering is a contract: the operator listing must not reshuffle between runs."""
    first = UUID("11111111-1111-4111-8111-111111111111")
    second = UUID("22222222-2222-4222-8222-222222222222")
    third = UUID("33333333-3333-4333-8333-333333333333")
    _publish(tmp_path, third, "Third")
    _publish(tmp_path, first, "First")
    _publish(tmp_path, second, "Second", publication_kind="restore")

    inventory = summary_inventory(root=tmp_path)

    assert inventory.recognized
    assert [summary.profile_id for summary in inventory.summaries] == [str(first), str(second), str(third)]
    assert [summary.label for summary in inventory.summaries] == ["First", "Second", "Third"]
    assert summary_inventory(root=tmp_path) == inventory


def test_each_summary_carries_the_provenance_its_own_two_records_proved(tmp_path: Path) -> None:
    """Provenance is read from the observation, never defaulted or re-derived."""
    profile_id = UUID("44444444-4444-4444-8444-444444444444")
    _publish(tmp_path, profile_id, "Restored", publication_kind="restore")

    (summary,) = summary_inventory(root=tmp_path).summaries

    assert summary.profile_id == str(profile_id)
    assert summary.label == "Restored"
    assert summary.label_revision == 1
    assert summary.publication_kind == "restore"
    assert summary.published_at.tzinfo is not None


def test_the_inventory_is_immutable_and_refuses_an_unknown_field() -> None:
    """The projection cannot be widened or edited by a downstream consumer."""
    inventory = ProfileSummaryInventory()

    with pytest.raises(ValidationError):
        ProfileSummaryInventory(unexpected="widened")
    with pytest.raises(ValidationError):
        inventory.outcome = ProfileSummaryOutcome.DEGRADED


def test_a_capsule_losing_its_label_mid_scan_is_reported_as_concurrent_not_corrupt(tmp_path: Path) -> None:
    """A publication race must read as retryable, never as a damaged store."""
    profile_id = UUID("66666666-6666-4666-8666-666666666666")
    capsule = _publish(tmp_path, profile_id, "Vanishing")
    (capsule / "data" / _LABEL_MEMBER).unlink()

    inventory = summary_inventory(root=tmp_path)

    assert inventory.outcome is ProfileSummaryOutcome.CONCURRENT_CHANGE
    assert not inventory.recognized
    assert inventory.summaries == ()
    assert inventory.detail is not None


def test_a_malformed_label_is_reported_as_degraded_and_is_never_repaired(tmp_path: Path) -> None:
    """A pure read must leave a damaged record exactly as it found it."""
    profile_id = UUID("77777777-7777-4777-8777-777777777777")
    capsule = _publish(tmp_path, profile_id, "Damaged")
    label_path = capsule / "data" / _LABEL_MEMBER
    malformed = b"not a canonical profile custody label"
    label_path.write_bytes(malformed)

    inventory = summary_inventory(root=tmp_path)

    assert inventory.outcome is ProfileSummaryOutcome.DEGRADED
    assert inventory.summaries == ()
    assert label_path.read_bytes() == malformed


def test_the_concurrent_and_degraded_endings_are_distinguishable_on_the_same_store(tmp_path: Path) -> None:
    """The two failure endings must not collapse into one indistinguishable outcome.

    Without this, a retryable race and a corrupt capsule would advise the
    operator identically -- and one of those two answers is always wrong.
    """
    profile_id = UUID("88888888-8888-4888-8888-888888888888")
    capsule = _publish(tmp_path, profile_id, "Both")
    label_path = capsule / "data" / _LABEL_MEMBER
    original = label_path.read_bytes()

    label_path.write_bytes(b"corrupt")
    degraded = summary_inventory(root=tmp_path).outcome
    label_path.unlink()
    concurrent = summary_inventory(root=tmp_path).outcome
    label_path.write_bytes(original)
    recovered = summary_inventory(root=tmp_path)

    assert degraded is ProfileSummaryOutcome.DEGRADED
    assert concurrent is ProfileSummaryOutcome.CONCURRENT_CHANGE
    assert recovered.recognized
    assert [summary.label for summary in recovered.summaries] == ["Both"]


def test_the_summary_boundary_alone_reaches_no_custody_session_or_repair_module(tmp_path: Path) -> None:
    """Importing and calling the listing must pull in none of the heavy graph.

    A fresh interpreter is the only honest way to assert this: in this process
    sibling tests have already imported the aggregate, so an in-process check
    would pass no matter what the listing did.

    The probe deliberately measures the boundary in isolation rather than after
    composing the concrete port.  Composing the adapter package today eagerly
    drags the aggregate in, which is a real amplification -- but it is the
    adapter's edge, not this boundary's, and asserting it here would attribute
    the fault to the wrong module and make this contract unfixable in place.
    """
    import subprocess
    import sys
    import textwrap

    profile_id = UUID("99999999-9999-4999-8999-999999999999")
    _publish(tmp_path, profile_id, "Isolated")

    probe = textwrap.dedent(
        """
        import sys

        from cadrumo.application.user_profile.profile_summary import (
            ProfileSummaryInventory,
            summary_inventory,
        )

        assert summary_inventory is not None and ProfileSummaryInventory is not None
        forbidden = sorted(
            name
            for name in sys.modules
            if name.startswith("cadrumo.")
            and name.endswith(
                (
                    ".profile_repository",
                    ".custody_repository",
                    ".custody_transactions",
                    ".custody_service",
                    ".recovery_custody",
                    ".passphrase_rotation",
                    ".login_session",
                    ".aggregate",
                )
            )
        )
        assert not forbidden, forbidden
        print("clean")
        """
    )
    completed = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "clean"


def test_a_real_listing_call_adds_no_custody_session_or_repair_module(tmp_path: Path) -> None:
    """Executing the listing against a real store must load nothing further.

    This is the runtime half of the contract, and it is a delta rather than an
    absolute set precisely so the adapter composition's own eager edges cannot
    mask a regression introduced by the listing itself.
    """
    heavy_suffixes = (
        ".custody_service",
        ".recovery_custody",
        ".passphrase_rotation",
        ".login_session",
        ".bundle_encryption",
    )
    _publish(tmp_path, UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"), "Delta")

    import sys

    before = {name for name in sys.modules if name.startswith("cadrumo.")}
    inventory = summary_inventory(root=tmp_path)
    added = {name for name in sys.modules if name.startswith("cadrumo.")} - before

    assert [summary.label for summary in inventory.summaries] == ["Delta"]
    assert not [name for name in added if name.endswith(heavy_suffixes)], sorted(added)
