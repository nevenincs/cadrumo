"""The supervised-KDF path still reads and writes the pre-change wire format.

The worker was cut down to a standard-library import closure: the AES-GCM
primitive, the KDF parameter and wrapped-DEK rules and the transport codecs
moved into leaves that import neither pydantic nor the error hierarchy. None
of that may change a byte on the wire. These cases replay values the previous
implementation produced -- AEAD blobs, control frames and wrapped DEKs from a
real worker -- through the current code, and check that the stdlib wire rules
accept and refuse exactly what the pydantic custody records do.
"""

from __future__ import annotations

import base64
import os
import time
from pathlib import Path

import pytest

from ......core.config import override_settings
from ...crypto.aead import EncryptedBlob, decrypt_record
from ...crypto.aes_gcm import open_sealed
from .._kdf_codec import (
    KDF_FAILED_FRAME,
    KDF_FRAME_CONTROL,
    calibration_frame_bytes,
    parse_calibration_frame,
    write_kdf_frame,
)
from .._kdf_records import (
    KDF_PARAMETER_FIELDS,
    WRAPPED_DEK_FIELDS,
    kdf_parameters_from_wire,
    wrapped_dek_from_wire,
)
from .._kdf_worker_supervision import _SupervisedKdfWorker
from .._profile_password_codec import encode_profile_password
from .._recovery_secret_codec import encode_recovery_secret
from ..records import ProfileCustodyKdfParameters, ProfileCustodyWrappedDek
from .kdf_wire_baseline import KDF_WIRE_BASELINE

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_BASELINE = KDF_WIRE_BASELINE


def _b64(value: str) -> bytes:
    return base64.b64decode(value)


@pytest.mark.parametrize("index", range(len(_BASELINE["aead"])))
def test_baseline_aead_blobs_decrypt_through_both_layers(index: int) -> None:
    sample = _BASELINE["aead"][index]
    key, associated_data = _b64(sample["key_b64"]), _b64(sample["associated_data_b64"])
    blob = EncryptedBlob.from_wire(_b64(sample["wire_b64"]))

    assert decrypt_record(blob, key=key, associated_data=associated_data) == _b64(sample["plaintext_b64"])
    assert open_sealed(blob.nonce, blob.ciphertext, key=key, associated_data=associated_data) == _b64(
        sample["plaintext_b64"]
    )


def test_the_failed_control_frame_is_byte_identical_to_the_baseline() -> None:
    reader, writer = os.pipe()
    try:
        write_kdf_frame(writer, KDF_FAILED_FRAME, kind=KDF_FRAME_CONTROL)
        os.close(writer)
        writer = -1
        framed = os.read(reader, 1024)
    finally:
        os.close(reader)
        if writer >= 0:
            os.close(writer)

    assert framed == _b64(_BASELINE["frames"]["KDF_FAILED_FRAME"])


@pytest.mark.parametrize("derivation_ns", [0, 1, 447_000_000, 2**53])
def test_a_calibration_frame_round_trips_its_worker_timing(derivation_ns: int) -> None:
    assert parse_calibration_frame(calibration_frame_bytes(derivation_ns=derivation_ns)) == derivation_ns


@pytest.mark.parametrize(
    "frame",
    [
        b'{"derivation_ns":-1,"protocol":"profile-kdf-calibrated/v2"}',
        b'{"derivation_ns":0.5,"protocol":"profile-kdf-calibrated/v2"}',
        b'{"derivation_ns":true,"protocol":"profile-kdf-calibrated/v2"}',
        b'{"derivation_ns":"5","protocol":"profile-kdf-calibrated/v2"}',
        b'{"derivation_ns":5,"protocol":"profile-kdf-calibrated/v1"}',
        b'{"derivation_ns":5}',
        b'{"derivation_ns":5,"extra":1,"protocol":"profile-kdf-calibrated/v2"}',
        b'{"protocol":"profile-kdf-calibrated/v2","derivation_ns":5}',
        b'{"derivation_ns": 5,"protocol":"profile-kdf-calibrated/v2"}',
        b"[5]",
        b"cadrumo-profile-kdf-calibrated-v1",
        b"\xff",
    ],
    ids=[
        "negative",
        "float",
        "bool",
        "string",
        "old-protocol",
        "missing-protocol",
        "extra-field",
        "non-canonical-order",
        "non-canonical-spacing",
        "not-an-object",
        "retired-constant-frame",
        "not-utf8",
    ],
)
def test_a_calibration_frame_of_any_other_shape_is_refused(frame: bytes) -> None:
    with pytest.raises(ValueError):
        parse_calibration_frame(frame)


def test_a_profile_wrapped_at_the_fallback_point_still_opens(tmp_path: Path) -> None:
    kdf = ProfileCustodyKdfParameters.model_validate(_BASELINE["fallback_kdf"])
    wrapped = ProfileCustodyWrappedDek.model_validate(_BASELINE["fallback_wrapped_dek"])
    dek, associated_data = _b64(_BASELINE["dek_b64"]), _b64(_BASELINE["associated_data_b64"])

    with (
        override_settings(cadrumo_local_storage_root=tmp_path),
        _SupervisedKdfWorker(deadline=time.monotonic() + 120) as worker,
    ):
        opened = worker.unwrap(
            password=encode_profile_password(_BASELINE["password"]),
            kdf=kdf,
            wrapped_dek=wrapped,
            associated_data=associated_data,
        )

    assert opened == dek


@pytest.mark.parametrize("label", ["password", "recovery"])
def test_the_current_worker_unwraps_baseline_wrapped_deks(tmp_path: Path, label: str) -> None:
    """A wrap the previous worker wrote opens under the current worker, and a fresh wrap round-trips."""
    kdf = ProfileCustodyKdfParameters.model_validate(_BASELINE["kdf"])
    wrapped = ProfileCustodyWrappedDek.model_validate(_BASELINE["wrapped_dek"][label])
    recovery = label == "recovery"
    secret = (
        encode_recovery_secret(_BASELINE["recovery_secret"])
        if recovery
        else encode_profile_password(_BASELINE["password"])
    )
    dek, associated_data = _b64(_BASELINE["dek_b64"]), _b64(_BASELINE["associated_data_b64"])

    with override_settings(cadrumo_local_storage_root=tmp_path):
        with _SupervisedKdfWorker(deadline=time.monotonic() + 120) as worker:
            opened = worker.unwrap(
                password=secret, kdf=kdf, wrapped_dek=wrapped, associated_data=associated_data, recovery=recovery
            )
        with _SupervisedKdfWorker(deadline=time.monotonic() + 120) as worker:
            rewrapped = worker.wrap(secret=secret, dek=dek, kdf=kdf, associated_data=associated_data, recovery=recovery)
        assert rewrapped is not None
        with _SupervisedKdfWorker(deadline=time.monotonic() + 120) as worker:
            reopened = worker.unwrap(
                password=secret, kdf=kdf, wrapped_dek=rewrapped, associated_data=associated_data, recovery=recovery
            )
        with _SupervisedKdfWorker(deadline=time.monotonic() + 120) as worker:
            refused = worker.unwrap(
                password=secret, kdf=kdf, wrapped_dek=wrapped, associated_data=b"another binding", recovery=recovery
            )

    assert opened == dek
    assert reopened == dek
    assert rewrapped != wrapped, "a fresh wrap must use a fresh nonce"
    assert refused is None, "a wrong associated-data binding must fail closed, not open"


def test_the_wire_rules_name_exactly_the_pydantic_record_fields() -> None:
    assert set(KDF_PARAMETER_FIELDS) == set(ProfileCustodyKdfParameters.model_fields)
    assert set(WRAPPED_DEK_FIELDS) == set(ProfileCustodyWrappedDek.model_fields)


def _kdf_variants() -> list[object]:
    base: dict[str, object] = dict(_BASELINE["kdf"])
    variants: list[object] = [base, [], "kdf", None]
    for field, replacements in {
        "algorithm": ["argon2i", "", 1, None],
        "version": [16, True, 19.0, "19", None],
        "memory_mib": [20, 0, True, 64.0, "64", -19],
        "iterations": [1, 5, False, 2.0],
        "parallelism": [3, True, 1.0, "1"],
        "salt_b64": [
            "",
            "AAAA",
            base64.b64encode(bytes(15)).decode(),
            base64.b64encode(bytes(16)).decode()[:-1] + "=",
            "!" * 24,
            16,
            None,
            base64.b64encode(bytes(16)).decode(),
        ],
        "output_bytes": [16, 64, True, 32.0],
    }.items():
        variants.extend({**base, field: replacement} for replacement in replacements)
        variants.append({key: value for key, value in base.items() if key != field})
    variants.append({**base, "extra": 1})
    return variants


def _wrapped_variants() -> list[object]:
    base: dict[str, object] = dict(_BASELINE["wrapped_dek"]["password"])
    variants: list[object] = [base, [], None]
    for field, size in (("nonce_b64", 12), ("ciphertext_b64", 32), ("tag_b64", 16)):
        variants.extend(
            {**base, field: replacement}
            for replacement in (
                base64.b64encode(bytes(size - 1)).decode(),
                base64.b64encode(bytes(size + 1)).decode(),
                base64.b64encode(bytes(size)).decode().rstrip("=") + "!",
                base64.b64encode(bytes(size)),
                size,
                "",
            )
        )
        variants.append({key: value for key, value in base.items() if key != field})
    variants.append({**base, "extra": "AAAA"})
    return variants


def _accepted(validate: object, value: object) -> bool:
    assert callable(validate)
    try:
        validate(value)
    except ValueError:
        return False
    return True


@pytest.mark.parametrize("value", _kdf_variants())
def test_kdf_wire_rules_agree_with_the_pydantic_record(value: object) -> None:
    assert _accepted(kdf_parameters_from_wire, value) is _accepted(ProfileCustodyKdfParameters.model_validate, value)


@pytest.mark.parametrize("value", _wrapped_variants())
def test_wrapped_dek_wire_rules_agree_with_the_pydantic_record(value: object) -> None:
    assert _accepted(wrapped_dek_from_wire, value) is _accepted(ProfileCustodyWrappedDek.model_validate, value)


def test_the_agreement_corpus_contains_both_verdicts() -> None:
    """Anchor the two agreement tests: a corpus of only refusals would agree vacuously."""
    kdf_verdicts = {_accepted(kdf_parameters_from_wire, value) for value in _kdf_variants()}
    wrapped_verdicts = {_accepted(wrapped_dek_from_wire, value) for value in _wrapped_variants()}

    assert kdf_verdicts == {True, False}
    assert wrapped_verdicts == {True, False}
