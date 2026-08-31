"""Real-behavior tests: carried custody rows restore all-or-nothing.

``restore_carried_objects`` saved one row at a time, so a failure partway
through left every earlier row durable while the call raised. That is the
worst pair of outcomes a custody boundary can produce at once: the caller is
told the restore did not happen, and the target bucket nonetheless holds
part of another bucket's key material. Nothing recorded where it stopped,
so a retry had to reason about which rows already existed rather than about
whether the restore ran at all.

The failure injected here is a genuine production refusal -- a registered
namespace carrying the wrong sensitivity class, which the secure-object
write policy rejects -- rather than a patched save. No test double is
involved: the repository, the encryption, and the SQLite backend are real.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....adapters.persistence.storage.errors import ClassificationError
from ....adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ....adapters.persistence.storage.secure_object_namespaces import WORKFLOW_RUN_NAMESPACE
from ....adapters.persistence.tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ....core.classification.policies import SensitivityClass
from ....domain.user_profile.portable_export import CarriedSecureObject
from ..custody_carry import restore_carried_objects

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"

# A registered namespace, with the sensitivity its definition declares. The
# rejected row below reuses the namespace and changes only the class, so the
# refusal is the write policy's and nothing else differs between the rows.
_NAMESPACE = "cadrumo.application.workflow.runs"
_NAMESPACE_SCHEMA_VERSION = WORKFLOW_RUN_NAMESPACE.schema_version
_DECLARED_CLASS = SensitivityClass.FINANCIAL
_WRONG_CLASS = SensitivityClass.IDENTITY
_WRITTEN_AT = datetime(2026, 4, 1, 10, 0, 0, tzinfo=UTC)


def _carried(object_key: str, classification: SensitivityClass) -> CarriedSecureObject:
    return CarriedSecureObject(
        namespace=_NAMESPACE,
        object_key=object_key,
        classification=classification,
        schema_version=_NAMESPACE_SCHEMA_VERSION,
        written_at=_WRITTEN_AT,
        payload_b64="eyJhIjogMX0=",  # {"a": 1}
    )


def _stored(object_key: str):
    return secure_object_repository_for_bucket(_BUCKET_ID).load(
        _NAMESPACE,
        object_key,
        expected_class=_DECLARED_CLASS,
        max_supported_version=_NAMESPACE_SCHEMA_VERSION,
    )


def test_a_failing_row_leaves_no_earlier_row_durable() -> None:
    good = _carried("run-first", _DECLARED_CLASS)
    rejected = _carried("run-second", _WRONG_CLASS)

    with pytest.raises(ClassificationError):
        restore_carried_objects((good, rejected), target_bucket_id=_BUCKET_ID)

    assert _stored("run-first") is None
    assert _stored("run-second") is None


def test_a_valid_restore_commits_every_row() -> None:
    rows = tuple(_carried(f"run-{index}", _DECLARED_CLASS) for index in range(3))

    restore_carried_objects(rows, target_bucket_id=_BUCKET_ID)

    for index in range(3):
        stored = _stored(f"run-{index}")
        assert stored is not None
        assert stored.payload == b'{"a": 1}'


def test_restoring_nothing_is_a_no_op() -> None:
    restore_carried_objects((), target_bucket_id=_BUCKET_ID)

    assert _stored("run-first") is None


def test_a_restore_is_replayable_after_a_refusal() -> None:
    """The point of all-or-nothing: a retry reasons about the whole set."""
    good = _carried("run-retry", _DECLARED_CLASS)
    rejected = _carried("run-bad", _WRONG_CLASS)

    with pytest.raises(ClassificationError):
        restore_carried_objects((good, rejected), target_bucket_id=_BUCKET_ID)
    restore_carried_objects((good,), target_bucket_id=_BUCKET_ID)

    assert _stored("run-retry") is not None


_isolated_backend = bucket_scoped_runtime_profile_fixture(_BUCKET_ID, autouse=True, name="_isolated_backend")
