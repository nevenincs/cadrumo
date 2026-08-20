"""Child-only Argon2id and password-wrap AEAD execution."""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
from collections.abc import Mapping
from typing import cast

from argon2.exceptions import Argon2Error
from argon2.low_level import Type, hash_secret_raw

from .....core.external_constants import UTF_8_ENCODING
from ..crypto import EncryptedBlob, decrypt_record, encrypt_record
from ..errors import DecryptionError, EncryptionError
from ._kdf_attestation import kdf_worker_ready_attestation
from ._kdf_codec import (
    KDF_FRAME_CONTROL,
    KDF_FRAME_DEK,
    canonical_frame_bytes,
    read_kdf_frame,
    write_kdf_frame,
)
from ._kdf_worker_supervision import (
    KDF_CALIBRATED_FRAME,
    KDF_FAILED_FRAME,
)
from ._records import (
    ProfileCustodyKdfParameters,
    ProfileCustodyWrappedDek,
    decode_profile_password,
)

_CALIBRATION_PASSWORD = b"cadrumo-profile-kdf-calibration-v1"


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--request-fd", type=int)
    parser.add_argument("--result-fd", type=int)
    parser.add_argument("--request-handle", type=int)
    parser.add_argument("--result-handle", type=int)
    args = parser.parse_args()
    request_fd, result_fd = _worker_fds(args)
    try:
        write_kdf_frame(result_fd, kdf_worker_ready_attestation(), kind=KDF_FRAME_CONTROL)
        request_kind, request = read_kdf_frame(request_fd)
        if request_kind != KDF_FRAME_CONTROL:
            raise ValueError("profile KDF request frame kind is invalid")
        payload = _parse_request(request)
        operation = payload["operation"]
        if operation == "calibrate-v1":
            _derive_calibration(payload)
            write_kdf_frame(result_fd, KDF_CALIBRATED_FRAME, kind=KDF_FRAME_CONTROL)
        elif operation == "unwrap-v1":
            write_kdf_frame(result_fd, _unwrap(payload), kind=KDF_FRAME_DEK)
        elif operation == "wrap-v1":
            write_kdf_frame(result_fd, _wrap(payload), kind=KDF_FRAME_CONTROL)
        else:
            write_kdf_frame(result_fd, KDF_FAILED_FRAME, kind=KDF_FRAME_CONTROL)
    except (Argon2Error, DecryptionError, EncryptionError, ValueError, TypeError, UnicodeError, binascii.Error):
        write_kdf_frame(result_fd, KDF_FAILED_FRAME, kind=KDF_FRAME_CONTROL)
    finally:
        os.close(request_fd)
        os.close(result_fd)
    return 0


def _worker_fds(args: argparse.Namespace) -> tuple[int, int]:
    if args.request_fd is not None and args.result_fd is not None:
        return cast(int, args.request_fd), cast(int, args.result_fd)
    if args.request_handle is not None and args.result_handle is not None:
        import msvcrt

        return (
            msvcrt.open_osfhandle(args.request_handle, os.O_RDONLY),
            msvcrt.open_osfhandle(args.result_handle, os.O_WRONLY),
        )
    raise ValueError("profile KDF worker pipe handles are incomplete")


def _parse_request(value: bytes) -> dict[str, object]:
    payload = json.loads(value.decode(UTF_8_ENCODING))
    if not isinstance(payload, dict):
        raise ValueError("profile KDF request is invalid")
    record = cast(dict[str, object], payload)
    if record.get("version") != 1:
        raise ValueError("profile KDF request is invalid")
    operation = record.get("operation")
    if operation == "calibrate-v1":
        required = {"version", "operation", "kdf"}
    elif operation == "unwrap-v1":
        required = {"version", "operation", "kdf", "wrapped_dek", "password_b64", "associated_data_b64"}
    elif operation == "wrap-v1":
        required = {"version", "operation", "kdf", "dek_b64", "secret_b64", "associated_data_b64"}
    else:
        raise ValueError("profile KDF operation is invalid")
    if set(record) != required:
        raise ValueError("profile KDF request fields are invalid")
    return record


def _derive_calibration(payload: Mapping[str, object]) -> None:
    kdf = _validated_kdf(payload["kdf"])
    _derive_key(secret=_CALIBRATION_PASSWORD, kdf=kdf)


def _unwrap(payload: Mapping[str, object]) -> bytes:
    kdf = _validated_kdf(payload["kdf"])
    wrapped_dek = _validated_wrapped_dek(payload["wrapped_dek"])
    password = decode_profile_password(_decode_b64(payload["password_b64"]))
    key = _derive_key(secret=password.encode("utf-8", errors="strict"), kdf=kdf)
    associated_data = _decode_b64(payload["associated_data_b64"])
    ciphertext = _decode_b64(wrapped_dek.ciphertext_b64) + _decode_b64(wrapped_dek.tag_b64)
    dek = decrypt_record(
        EncryptedBlob(nonce=_decode_b64(wrapped_dek.nonce_b64), ciphertext=ciphertext),
        key=key,
        associated_data=associated_data,
    )
    if len(dek) != 32:
        raise ValueError("profile custody wrapped DEK has invalid length")
    return dek


def _wrap(payload: Mapping[str, object]) -> bytes:
    kdf = _validated_kdf(payload["kdf"])
    secret = decode_profile_password(_decode_b64(payload["secret_b64"]))
    dek = _decode_b64(payload["dek_b64"])
    if len(dek) != 32:
        raise ValueError("profile custody DEK has invalid length")
    key = _derive_key(secret=secret.encode("utf-8", errors="strict"), kdf=kdf)
    encrypted = encrypt_record(
        dek,
        key=key,
        associated_data=_decode_b64(payload["associated_data_b64"]),
    )
    wrapped_dek = ProfileCustodyWrappedDek(
        nonce_b64=base64.b64encode(encrypted.nonce).decode("ascii"),
        ciphertext_b64=base64.b64encode(encrypted.ciphertext[:-16]).decode("ascii"),
        tag_b64=base64.b64encode(encrypted.ciphertext[-16:]).decode("ascii"),
    )
    return canonical_frame_bytes({"wrapped_dek": wrapped_dek.model_dump(mode="json")})


def _derive_key(*, secret: bytes, kdf: ProfileCustodyKdfParameters) -> bytes:
    return hash_secret_raw(
        secret=secret,
        salt=_decode_b64(kdf.salt_b64),
        time_cost=kdf.iterations,
        memory_cost=kdf.memory_mib * 1024,
        parallelism=kdf.parallelism,
        hash_len=kdf.output_bytes,
        type=Type.ID,
        version=kdf.version,
    )


def _validated_kdf(value: object) -> ProfileCustodyKdfParameters:
    if not isinstance(value, dict):
        raise ValueError("profile KDF record is invalid")
    return ProfileCustodyKdfParameters.model_validate(value)


def _validated_wrapped_dek(value: object) -> ProfileCustodyWrappedDek:
    if not isinstance(value, dict):
        raise ValueError("profile wrapped DEK record is invalid")
    return ProfileCustodyWrappedDek.model_validate(value)


def _decode_b64(value: object) -> bytes:
    if not isinstance(value, str):
        raise ValueError("profile KDF binary field is invalid")
    return base64.b64decode(value.encode("ascii"), validate=True)


if __name__ == "__main__":
    raise SystemExit(main())
