"""Child-only Argon2id and password-wrap AEAD execution.

Started as a fresh interpreter for every wrap, unwrap and calibration, so its
import closure is the standard library, :mod:`argon2` and :mod:`cryptography`
plus stdlib-only custody leaves. Records arrive as JSON and are checked
against the same rules the pydantic custody records use.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
import sys
import time
from collections.abc import Mapping
from typing import cast

from argon2.exceptions import Argon2Error
from argon2.low_level import Type, hash_secret_raw
from cryptography.exceptions import InvalidTag

from ..crypto.aes_gcm import GCM_TAG_SIZE, KEY_SIZE, open_sealed, seal
from ._kdf_attestation import kdf_worker_ready_attestation
from ._kdf_codec import (
    KDF_FAILED_FRAME,
    KDF_FRAME_CONTROL,
    KDF_FRAME_DEK,
    KDF_TRANSPORT_ENCODING,
    calibration_frame_bytes,
    canonical_frame_bytes,
    read_kdf_frame,
    write_kdf_frame,
)
from ._kdf_operations import UNWRAP_OPERATIONS, WRAP_OPERATIONS, KdfOperation
from ._kdf_records import KdfParameterValues, kdf_parameters_from_wire, wrapped_dek_from_wire
from ._profile_password_codec import decode_profile_password
from ._recovery_secret_codec import decode_recovery_secret

_CALIBRATION_PASSWORD = b"cadrumo-profile-kdf-calibration-v1"


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--request-fd", type=int)
    parser.add_argument("--result-fd", type=int)
    parser.add_argument("--request-handle", type=int)
    parser.add_argument("--result-handle", type=int)
    parser.add_argument("--descriptor-bound", type=int)
    args = parser.parse_args()
    request_fd, result_fd = _worker_fds(args)
    _close_unallowlisted_posix_file_descriptors(
        request_fd=request_fd,
        result_fd=result_fd,
        descriptor_bound=args.descriptor_bound,
    )
    try:
        write_kdf_frame(
            result_fd,
            kdf_worker_ready_attestation(request_fd=request_fd, result_fd=result_fd),
            kind=KDF_FRAME_CONTROL,
        )
        request_kind, request = read_kdf_frame(request_fd)
        if request_kind != KDF_FRAME_CONTROL:
            raise ValueError("profile KDF request frame kind is invalid")
        payload = _parse_request(request)
        operation = cast(str, payload["operation"])
        if operation == KdfOperation.CALIBRATE:
            write_kdf_frame(result_fd, _derive_calibration(payload), kind=KDF_FRAME_CONTROL)
        elif operation in UNWRAP_OPERATIONS:
            write_kdf_frame(result_fd, _unwrap(payload, recovery=operation.startswith("recovery-")), kind=KDF_FRAME_DEK)
        elif operation in WRAP_OPERATIONS:
            write_kdf_frame(
                result_fd,
                _wrap(payload, recovery=operation.startswith("recovery-")),
                kind=KDF_FRAME_CONTROL,
            )
        else:
            write_kdf_frame(result_fd, KDF_FAILED_FRAME, kind=KDF_FRAME_CONTROL)
    except (Argon2Error, InvalidTag, ValueError, TypeError, UnicodeError, binascii.Error):
        write_kdf_frame(result_fd, KDF_FAILED_FRAME, kind=KDF_FRAME_CONTROL)
    finally:
        os.close(request_fd)
        os.close(result_fd)
    return 0


def _close_unallowlisted_posix_file_descriptors(
    *,
    request_fd: int,
    result_fd: int,
    descriptor_bound: int | None,
) -> None:
    if sys.platform == "win32":
        return

    if descriptor_bound is None:
        raise ValueError("profile KDF worker descriptor bound is unavailable")
    allowed = {0, 1, 2, request_fd, result_fd}
    if any(descriptor < 0 or descriptor >= descriptor_bound for descriptor in allowed):
        raise ValueError("profile KDF worker descriptor is outside the OS bound")
    range_start = 3
    for descriptor in sorted(allowed - {0, 1, 2}):
        os.closerange(range_start, descriptor)
        range_start = descriptor + 1
    os.closerange(range_start, descriptor_bound)


def _worker_fds(args: argparse.Namespace) -> tuple[int, int]:
    """Resolve the worker's request/result descriptors from either transport.

    The ``sys.platform == "win32"`` block, rather than a guard at the call
    site or an early return, is what establishes the platform for the Windows
    API below: it is the only guard shape every checker this project runs
    narrows on, so those references resolve when the tree is analysed for a
    platform that does not ship them.
    """
    if args.request_fd is not None and args.result_fd is not None:
        return cast(int, args.request_fd), cast(int, args.result_fd)
    if sys.platform == "win32" and args.request_handle is not None and args.result_handle is not None:
        import msvcrt

        return (
            msvcrt.open_osfhandle(args.request_handle, os.O_RDONLY),
            msvcrt.open_osfhandle(args.result_handle, os.O_WRONLY),
        )
    raise ValueError("profile KDF worker pipe handles are incomplete")


def _parse_request(value: bytes) -> dict[str, object]:
    payload = json.loads(value.decode(KDF_TRANSPORT_ENCODING))
    if not isinstance(payload, dict):
        raise ValueError("profile KDF request is invalid")
    record = cast(dict[str, object], payload)
    if record.get("version") != 1:
        raise ValueError("profile KDF request is invalid")
    operation = record.get("operation")
    if operation == KdfOperation.CALIBRATE:
        required = {"version", "operation", "kdf"}
    elif operation in UNWRAP_OPERATIONS:
        required = {"version", "operation", "kdf", "wrapped_dek", "password_b64", "associated_data_b64"}
    elif operation in WRAP_OPERATIONS:
        required = {"version", "operation", "kdf", "dek_b64", "secret_b64", "associated_data_b64"}
    else:
        raise ValueError("profile KDF operation is invalid")
    if set(record) != required:
        raise ValueError("profile KDF request fields are invalid")
    return record


def _derive_calibration(payload: Mapping[str, object]) -> bytes:
    """Derive once and report the derivation's own duration, excluding this process's start-up."""
    kdf = kdf_parameters_from_wire(payload["kdf"])
    started = time.perf_counter_ns()
    _derive_key(secret=_CALIBRATION_PASSWORD, kdf=kdf)
    return calibration_frame_bytes(derivation_ns=time.perf_counter_ns() - started)


def _unwrap(payload: Mapping[str, object], *, recovery: bool = False) -> bytes:
    kdf = kdf_parameters_from_wire(payload["kdf"])
    wrapped_dek = wrapped_dek_from_wire(payload["wrapped_dek"])
    encoded = _decode_b64(payload["password_b64"])
    secret = decode_recovery_secret(encoded) if recovery else decode_profile_password(encoded)
    key = _derive_key(secret=secret.encode("utf-8", errors="strict"), kdf=kdf)
    associated_data = _decode_b64(payload["associated_data_b64"])
    ciphertext = _decode_b64(wrapped_dek.ciphertext_b64) + _decode_b64(wrapped_dek.tag_b64)
    dek = open_sealed(_decode_b64(wrapped_dek.nonce_b64), ciphertext, key=key, associated_data=associated_data)
    if len(dek) != KEY_SIZE:
        raise ValueError("profile custody wrapped DEK has invalid length")
    return dek


def _wrap(payload: Mapping[str, object], *, recovery: bool = False) -> bytes:
    kdf = kdf_parameters_from_wire(payload["kdf"])
    encoded = _decode_b64(payload["secret_b64"])
    secret = decode_recovery_secret(encoded) if recovery else decode_profile_password(encoded)
    dek = _decode_b64(payload["dek_b64"])
    if len(dek) != KEY_SIZE:
        raise ValueError("profile custody DEK has invalid length")
    key = _derive_key(secret=secret.encode("utf-8", errors="strict"), kdf=kdf)
    nonce, sealed = seal(dek, key=key, associated_data=_decode_b64(payload["associated_data_b64"]))
    # Validated on the way out as well, so the frame carries only a record the
    # supervisor's own parse would accept.
    wrapped_dek = wrapped_dek_from_wire(
        {
            "nonce_b64": base64.b64encode(nonce).decode("ascii"),
            "ciphertext_b64": base64.b64encode(sealed[:-GCM_TAG_SIZE]).decode("ascii"),
            "tag_b64": base64.b64encode(sealed[-GCM_TAG_SIZE:]).decode("ascii"),
        }
    )
    return canonical_frame_bytes(
        {
            "wrapped_dek": {
                "nonce_b64": wrapped_dek.nonce_b64,
                "ciphertext_b64": wrapped_dek.ciphertext_b64,
                "tag_b64": wrapped_dek.tag_b64,
            }
        }
    )


def _derive_key(*, secret: bytes, kdf: KdfParameterValues) -> bytes:
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


def _decode_b64(value: object) -> bytes:
    if not isinstance(value, str):
        raise ValueError("profile KDF binary field is invalid")
    return base64.b64decode(value.encode("ascii"), validate=True)


if __name__ == "__main__":
    raise SystemExit(main())
