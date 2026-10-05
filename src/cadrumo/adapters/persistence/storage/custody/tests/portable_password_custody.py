"""Joined observable password custody for portable tests, owned by custody."""

from __future__ import annotations

import time
from collections.abc import Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager
from typing import override

import pytest
from argon2.exceptions import Argon2Error
from cryptography.exceptions import InvalidTag

from .. import kdf_supervision
from .._kdf_codec import KDF_FAILED_FRAME, KDF_FRAME_CONTROL, KDF_FRAME_DEK, canonical_frame_bytes
from .._kdf_operations import UNWRAP_OPERATIONS, WRAP_OPERATIONS, KdfOperation
from .._kdf_worker import _derive_calibration, _parse_request, _unwrap, _wrap
from .._kdf_worker_supervision import _SupervisedKdfWorker


class _JoinedKdfWorker(_SupervisedKdfWorker):
    """Synthetic process custody, exact password codec/Argon2id/AEAD and wire checks."""

    pool: ThreadPoolExecutor
    response: Future[tuple[int, bytes]] | None = None

    @override
    def __enter__(self) -> _JoinedKdfWorker:
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="portable-password-custody")
        return self

    @override
    def __exit__(self, exc_type: object, _exc_value: object, _traceback: object) -> None:
        try:
            self.settle()
        except BaseException as error:
            if self.response is not None and not self.response.done():
                error.__dict__["portable_kdf_cleanup_owner"] = self
                error.add_note("Joined test KDF cleanup remains owned; retry through portable_kdf_cleanup_owner.settle")
            raise

    def settle(self) -> None:
        """Retain the exact computation until a finite join succeeds, including failures."""
        try:
            if self.response is not None:
                self.response.result(timeout=20)
        finally:
            if self.response is None or self.response.done():
                self.pool.shutdown(wait=True)

    @override
    def _write_request(self, payload: dict[str, object]) -> None:
        if self.response is not None:
            raise AssertionError("one joined KDF owner performs only one computation")
        encoded = canonical_frame_bytes(payload)

        def compute() -> tuple[int, bytes]:
            request = _parse_request(encoded)
            operation = request["operation"]
            try:
                if operation in WRAP_OPERATIONS:
                    return KDF_FRAME_CONTROL, _wrap(request, recovery=str(operation).startswith("recovery-"))
                if operation in UNWRAP_OPERATIONS:
                    return KDF_FRAME_DEK, _unwrap(request, recovery=str(operation).startswith("recovery-"))
                if operation == KdfOperation.CALIBRATE:
                    return KDF_FRAME_CONTROL, _derive_calibration(request)
                raise AssertionError("the owning KDF parser accepted an unknown operation")
            except (Argon2Error, InvalidTag, ValueError, TypeError, UnicodeError):
                return KDF_FRAME_CONTROL, KDF_FAILED_FRAME

        self.response = self.pool.submit(compute)

    @override
    def _read_response_frame(self) -> tuple[int, bytes]:
        if self.response is None:
            raise AssertionError("the joined KDF owner requires its request first")
        return self.response.result(timeout=max(0, self._deadline - time.monotonic()))

    @override
    def _require_clean_worker_exit(self) -> None:
        if self.response is None or not self.response.done():
            raise AssertionError("the joined KDF computation has not settled")


@contextmanager
def portable_password_custody() -> Iterator[None]:
    """Keep real password cryptography observable without starting an OS child."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(kdf_supervision, "_SupervisedKdfWorker", _JoinedKdfWorker)
        yield


__all__ = ["portable_password_custody"]
