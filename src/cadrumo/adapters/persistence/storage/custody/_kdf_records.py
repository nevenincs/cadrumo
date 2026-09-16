"""The Argon2id parameter grid and wrapped-DEK shape, as plain wire rules.

One declaration of the custody v1 KDF grid and of the canonical base64 rule.
The pydantic records in :mod:`.records` annotate with these aliases and call
:func:`canonical_b64`; the supervised key-derivation worker, which is started
for every wrap and unwrap and must not import pydantic, validates its request
with :func:`kdf_parameters_from_wire` and :func:`wrapped_dek_from_wire`.
Standard library and :mod:`cryptography` constants only.

Every refusal is a :class:`ValueError`, which the worker already turns into
its failure frame, exactly as it did for the pydantic ``ValidationError``.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from typing import Final, Literal, cast, get_args

from .._kdf_salt import KDF_SALT_BYTES
from ..crypto.aes_gcm import GCM_TAG_SIZE, KEY_SIZE, NONCE_SIZE

type KdfAlgorithm = Literal["argon2id"]
type KdfVersion = Literal[19]
type KdfMemoryMib = Literal[19, 32, 64, 128, 256]
type KdfIterations = Literal[2, 3, 4, 6, 8, 10]
type KdfParallelism = Literal[1, 2, 4]
type KdfOutputBytes = Literal[32]


def _integer_choices(alias: object) -> frozenset[int]:
    choices = get_args(getattr(alias, "__value__", None))
    integers = frozenset(choice for choice in choices if type(choice) is int)
    if not choices or len(integers) != len(choices):
        raise TypeError("a KDF grid alias must list integer literals only")
    return integers


PROFILE_CUSTODY_KDF_MEMORY_MIB: Final = _integer_choices(KdfMemoryMib)
PROFILE_CUSTODY_KDF_ITERATIONS: Final = _integer_choices(KdfIterations)
PROFILE_CUSTODY_KDF_PARALLELISM: Final = _integer_choices(KdfParallelism)

KDF_PARAMETER_FIELDS: Final = (
    "algorithm",
    "version",
    "memory_mib",
    "iterations",
    "parallelism",
    "salt_b64",
    "output_bytes",
)
WRAPPED_DEK_FIELDS: Final = ("nonce_b64", "ciphertext_b64", "tag_b64")


def canonical_b64(value: str, *, field_name: str, expected_bytes: int) -> str:
    """Return ``value`` if it is the canonical base64 of exactly ``expected_bytes`` bytes."""
    expected_length = 4 * ((expected_bytes + 2) // 3)
    if len(value) != expected_length:
        raise ValueError(f"{field_name} must contain exactly {expected_length} base64 characters")
    try:
        decoded = base64.b64decode(value.encode("ascii"), validate=True)
    except (UnicodeEncodeError, binascii.Error) as exc:
        raise ValueError(f"{field_name} must be canonical base64") from exc
    if len(decoded) != expected_bytes:
        raise ValueError(f"{field_name} must encode exactly {expected_bytes} bytes")
    if base64.b64encode(decoded).decode("ascii") != value:
        raise ValueError(f"{field_name} must use canonical base64")
    return value


@dataclass(frozen=True, slots=True)
class KdfParameterValues:
    """A validated KDF parameter set, as the worker consumes it."""

    algorithm: str
    version: int
    memory_mib: int
    iterations: int
    parallelism: int
    salt_b64: str
    output_bytes: int


@dataclass(frozen=True, slots=True)
class WrappedDekValues:
    """A validated wrapped-DEK record, as the worker consumes it."""

    nonce_b64: str
    ciphertext_b64: str
    tag_b64: str


def _record(value: object, fields: tuple[str, ...], subject: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != set(fields) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{subject} is invalid")
    return {str(key): item for key, item in value.items()}


def _member(record: dict[str, object], field: str, allowed: tuple[object, ...]) -> object:
    item = record[field]
    # Equality, as pydantic's literal check does even in strict mode: ``True``
    # and ``64.0`` match the literals ``1`` and ``64``, ``"64"`` matches nothing.
    # The accepted literal itself is returned, never the input spelling.
    for choice in allowed:
        if type(item) in {bool, int, float, str} and item == choice:
            return choice
    raise ValueError(f"{field} is not an accepted value")


def _text(record: dict[str, object], field: str, expected_bytes: int) -> str:
    item = record[field]
    if type(item) is not str:
        raise ValueError(f"{field} must be a string")
    return canonical_b64(item, field_name=field, expected_bytes=expected_bytes)


def kdf_parameters_from_wire(value: object) -> KdfParameterValues:
    """Validate a KDF parameter record received as JSON-shaped data."""
    record = _record(value, KDF_PARAMETER_FIELDS, "profile KDF record")
    return KdfParameterValues(
        algorithm=cast("str", _member(record, "algorithm", get_args(KdfAlgorithm.__value__))),
        version=cast("int", _member(record, "version", get_args(KdfVersion.__value__))),
        memory_mib=cast("int", _member(record, "memory_mib", get_args(KdfMemoryMib.__value__))),
        iterations=cast("int", _member(record, "iterations", get_args(KdfIterations.__value__))),
        parallelism=cast("int", _member(record, "parallelism", get_args(KdfParallelism.__value__))),
        salt_b64=_text(record, "salt_b64", KDF_SALT_BYTES),
        output_bytes=cast("int", _member(record, "output_bytes", get_args(KdfOutputBytes.__value__))),
    )


def wrapped_dek_from_wire(value: object) -> WrappedDekValues:
    """Validate a wrapped-DEK record received as JSON-shaped data."""
    record = _record(value, WRAPPED_DEK_FIELDS, "profile wrapped DEK record")
    return WrappedDekValues(
        nonce_b64=_text(record, "nonce_b64", NONCE_SIZE),
        ciphertext_b64=_text(record, "ciphertext_b64", KEY_SIZE),
        tag_b64=_text(record, "tag_b64", GCM_TAG_SIZE),
    )


__all__ = [
    "KDF_PARAMETER_FIELDS",
    "PROFILE_CUSTODY_KDF_ITERATIONS",
    "PROFILE_CUSTODY_KDF_MEMORY_MIB",
    "PROFILE_CUSTODY_KDF_PARALLELISM",
    "WRAPPED_DEK_FIELDS",
    "KdfAlgorithm",
    "KdfIterations",
    "KdfMemoryMib",
    "KdfOutputBytes",
    "KdfParallelism",
    "KdfParameterValues",
    "KdfVersion",
    "WrappedDekValues",
    "canonical_b64",
    "kdf_parameters_from_wire",
    "wrapped_dek_from_wire",
]
