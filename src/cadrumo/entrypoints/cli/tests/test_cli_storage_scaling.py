"""Listing cost must scale linearly with the number of stored profiles.

The defect this fix removed was per-profile custody entry on a pure read:
the old listing took a transaction lock, loaded password material, read the
transaction journal and verified-or-published a label head FOR EVERY PROFILE,
to answer a question that needs a UUID and a label. That is invisible on an
empty store and on a single profile; it only shows up as the store grows,
which is exactly when an operator notices.

Three lanes -- empty, one profile, many -- against real persisted capsules and
real child interpreters, because the cost is a property of a cold process
reading a real filesystem.

Scaling is asserted on the STORAGE-CALL count, never on wall time. A latency
comparison on a shared runner measures the runner, and this repository's
backing share is slow and contended enough that a timing assertion would flap
without ever describing the code. The call count is deterministic and is what
actually regressed.

The assertion is a shape, not a threshold: the marginal cost of the eighth
profile must not exceed the marginal cost of the first by more than a small
factor. A pinned number would encode today's implementation and would have to
be edited by whoever next changed it, which trains everyone to update the
constant instead of reading the result.
"""

from __future__ import annotations

import base64
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from ....adapters.persistence.storage.custody.capsule import publish_profile_custody_capsule
from ....adapters.persistence.storage.custody.capsule_records import ProfileCustodyCapsuleLabel
from ....adapters.persistence.storage.custody.records import (
    ProfileCustodyEnvelope,
    ProfileCustodyKdfParameters,
    ProfileCustodyWrappedDek,
)
from ....adapters.persistence.storage.custody.sentinel import create_profile_custody_sentinel
from ....core.config import Settings
from ....tests.cli_performance import profile_cli_path

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_LIST_PATH = ("config", "profile", "list")
_DEK = bytes(range(32))
_EPOCH = base64.b64encode(b"e" * 16).decode("ascii")

#: How much the per-profile cost may grow between the first profile and the
#: eighth. Linear work gives a ratio near 1.0; the old per-profile custody
#: entry gave several times that. The allowance covers only fixed per-run
#: overhead landing in the marginal figure, not a change of complexity class.
_MARGINAL_COST_ALLOWANCE = 2.0

_MANY = 8


def _publish(root: Path, profile_id: UUID, label: str) -> None:
    envelope = ProfileCustodyEnvelope.create(
        profile_id=profile_id,
        password_generation=1,
        dek_epoch=_EPOCH,
        kdf=ProfileCustodyKdfParameters(
            algorithm="argon2id",
            version=19,
            memory_mib=19,
            iterations=2,
            parallelism=1,
            salt_b64=base64.b64encode(b"k" * 16).decode("ascii"),
            output_bytes=32,
        ),
        wrapped_dek=ProfileCustodyWrappedDek(
            nonce_b64=base64.b64encode(b"n" * 12).decode("ascii"),
            ciphertext_b64=base64.b64encode(b"c" * 32).decode("ascii"),
            tag_b64=base64.b64encode(b"t" * 16).decode("ascii"),
        ),
    )
    publish_profile_custody_capsule(
        profile_id=profile_id,
        transaction_id=uuid4(),
        publication_kind="enroll",
        password_envelope=envelope,
        sentinel=create_profile_custody_sentinel(envelope=envelope, dek=_DEK),
        data_files={
            "profile-label.v1.json": ProfileCustodyCapsuleLabel.create(
                profile_id=profile_id,
                label=label,
            ).canonical_json_bytes()
        },
        settings=Settings(cadrumo_local_storage_root=root),
    )


def _root_with(tmp_path: Path, name: str, count: int) -> Path:
    root = tmp_path / name
    root.mkdir()
    for index in range(count):
        _publish(root, UUID(f"{index + 1:08d}-1111-4111-8111-111111111111"), f"Profile {index}")
    return root


def _storage_calls(root: Path) -> int:
    profile = profile_cli_path(_LIST_PATH, storage_root=root)
    assert profile.invocation.failure_kind == "none", profile.invocation.stderr
    assert profile.invocation.exit_code == 0, profile.invocation.stderr
    return sum(profile.invocation.storage_operation_calls.values())


@pytest.fixture(scope="module")
def lanes(tmp_path_factory: pytest.TempPathFactory) -> dict[str, int]:
    """Measure the three lanes once; each is a real child process."""
    tmp_path = tmp_path_factory.mktemp("scaling")
    return {
        "empty": _storage_calls(_root_with(tmp_path, "empty", 0)),
        "one": _storage_calls(_root_with(tmp_path, "one", 1)),
        "many": _storage_calls(_root_with(tmp_path, "many", _MANY)),
    }


def test_an_empty_store_costs_something_measurable(lanes: dict[str, int]) -> None:
    """FIXTURE ANCHOR: the probe must be observing real storage work.

    If the profiler stopped recording storage calls, every ratio below would be
    zero over zero and the lanes would agree perfectly while measuring nothing.
    """
    assert lanes["empty"] > 0, f"the probe recorded no storage calls at all: {lanes}"


def test_each_stored_profile_adds_work(lanes: dict[str, int]) -> None:
    """DISCRIMINATING: a populated store must cost more than an empty one.

    Without this the linearity assertion could be satisfied by a listing that
    reads nothing per profile -- which would also mean it lists nothing.
    """
    assert lanes["one"] > lanes["empty"], lanes
    assert lanes["many"] > lanes["one"], lanes


def test_per_profile_cost_stays_linear_as_the_store_grows(lanes: dict[str, int]) -> None:
    """DISCRIMINATING: the marginal profile must not cost more than the first.

    This is the shape the old aggregate path violated: per-profile custody
    entry made each additional profile cost a lock, a password-material read, a
    journal read and a label-head verification.
    """
    first = lanes["one"] - lanes["empty"]
    marginal = (lanes["many"] - lanes["empty"]) / _MANY

    assert first > 0, lanes
    assert marginal <= first * _MARGINAL_COST_ALLOWANCE, (
        f"listing cost grows faster than linearly: the first profile costs {first} storage calls, "
        f"the average of {_MANY} costs {marginal:.1f} (lanes={lanes}). "
        "Something on the listing path is doing per-profile work that does not scale."
    )
