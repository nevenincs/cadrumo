"""The file-fallback ``master.kdf`` salt obeys the shared storage KDF contract.

``_KdfParameters.salt_b64`` accepted anything that base64-decoded while the
canonical :mod:`..._kdf_salt` contract requires exactly
:data:`~..._kdf_salt.KDF_SALT_BYTES`. The reader decoded the field and handed
it straight to Argon2, so the two authorities disagreed with operator-visible
consequences:

* an 8-byte salt derived a different KEK and surfaced as
  ``MasterKeyPassphraseMismatchError`` -- sending the operator to recover a
  passphrase that was never wrong, for a store whose *parameters* were corrupt;
* a 1-byte or empty salt reached the library and leaked
  ``argon2.exceptions.HashingError: Salt is too short`` out of the storage
  boundary entirely.

Real behaviour throughout: a real provisioned file store, real Argon2id, real
on-disk rewriting of the persisted parameters. Nothing is mocked.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ......core.external_constants import UTF_8_ENCODING
from ..._kdf_salt import KDF_SALT_BYTES
from ...errors import MasterKeyUnavailableError, StorageValidationError
from .. import FileFallbackMasterKeyProvider
from .._master_key import _KdfParameters
from .._master_key_derivation import SALT_SIZE, derive_kek_with_params

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_PASSPHRASE = "test-passphrase"  # noqa: S105 - synthetic test fixture


def _provision(tmp_path: Path) -> Path:
    """Provision a real file-backed store and return its directory."""
    store_dir = tmp_path / "secrets"
    FileFallbackMasterKeyProvider(
        store_dir=store_dir,
        passphrase_callback=lambda: _PASSPHRASE,
    ).provision_master_key()
    return store_dir


def _rewrite_salt(store_dir: Path, salt: bytes) -> None:
    """Replace only ``salt_b64`` in the persisted parameters."""
    kdf_path = store_dir / "master.kdf"
    document = json.loads(kdf_path.read_text(encoding=UTF_8_ENCODING))
    document["salt_b64"] = base64.b64encode(salt).decode("ascii")
    kdf_path.write_text(json.dumps(document), encoding=UTF_8_ENCODING)


def _reopen(store_dir: Path) -> bytes:
    return FileFallbackMasterKeyProvider(
        store_dir=store_dir,
        passphrase_callback=lambda: _PASSPHRASE,
    ).get_master_key()


def test_minted_salt_length_is_read_from_the_shared_contract() -> None:
    """The mint length and the validation length are one value, not two.

    This is what the refusals below rest on: if the store were minted at a
    length the record refused, provisioning would produce an unreadable store,
    and if the record accepted a length the mint never produces, the refusals
    would be untested in practice.
    """
    assert SALT_SIZE == KDF_SALT_BYTES


def test_provisioned_store_reopens(tmp_path: Path) -> None:
    """POSITIVE CONTROL: an untouched store opens and yields a 32-byte key.

    Without this, every refusal below is equally satisfied by a provider that
    refuses everything, and the rewrite helper could be corrupting the file in
    some way that has nothing to do with the salt.
    """
    store_dir = _provision(tmp_path)
    assert len(_reopen(store_dir)) == 32


def test_canonical_length_salt_is_accepted_and_reports_a_key_mismatch(tmp_path: Path) -> None:
    """A DIFFERENT 16-byte salt stays a passphrase mismatch, not a parse refusal.

    DISCRIMINATING against a fix that simply refuses every rewritten salt: a
    canonical-length salt is well-formed material, and the KEK it derives is
    genuinely indistinguishable from one derived under a wrong passphrase. The
    refusals below must be attributable to the LENGTH and to nothing else.
    """
    from ...errors import MasterKeyPassphraseMismatchError

    store_dir = _provision(tmp_path)
    _rewrite_salt(store_dir, b"\xab" * KDF_SALT_BYTES)

    with pytest.raises(MasterKeyPassphraseMismatchError):
        _reopen(store_dir)


@pytest.mark.parametrize("salt_length", [0, 1, 8, 15, 17, 64])
def test_noncanonical_salt_length_is_a_typed_material_refusal(tmp_path: Path, salt_length: int) -> None:
    """Every off-contract length refuses as unavailable material.

    ``0`` and ``1`` are the lengths that used to escape the storage boundary as
    a raw ``argon2.exceptions.HashingError``; ``8``, ``15``, ``17`` and ``64``
    are the lengths that used to be misreported as a wrong passphrase. Asserting
    ``MasterKeyUnavailableError`` excludes both: it is not an
    ``argon2.exceptions`` type, and ``MasterKeyPassphraseMismatchError`` is a
    distinct error the previous behaviour raised here.
    """
    store_dir = _provision(tmp_path)
    _rewrite_salt(store_dir, b"\xab" * salt_length)

    with pytest.raises(MasterKeyUnavailableError):
        _reopen(store_dir)


def test_record_refuses_a_short_salt_directly() -> None:
    """The record is the authority, asserted without going through a store."""
    with pytest.raises(ValidationError):
        _KdfParameters(
            memory_cost=19 * 1024,
            time_cost=2,
            parallelism=1,
            salt_b64=base64.b64encode(b"\xab" * 8).decode("ascii"),
        )


def test_record_exposes_the_decoded_salt_at_contract_length() -> None:
    """A valid record hands the derivation its bytes; nothing re-decodes them."""
    salt = b"\xab" * KDF_SALT_BYTES
    params = _KdfParameters(
        memory_cost=19 * 1024,
        time_cost=2,
        parallelism=1,
        salt_b64=base64.b64encode(salt).decode("ascii"),
    )
    assert params.salt == salt


def test_record_refuses_malformed_base64_salt() -> None:
    """A salt that does not decode at all is refused by the same validator."""
    with pytest.raises(ValidationError):
        _KdfParameters(
            memory_cost=19 * 1024,
            time_cost=2,
            parallelism=1,
            salt_b64="!!!not-base64!!!",
        )


def test_derivation_translates_a_library_refusal_to_a_storage_error() -> None:
    """Argon2's own refusal does not escape the storage boundary.

    Defence in depth behind the record validation above, reached here by
    calling the derivation helper directly with material no validated record
    could carry. A caller that assembles parameters without a record still gets
    a storage error rather than an ``argon2.exceptions`` type the CLI has no
    handler for.
    """
    with pytest.raises(StorageValidationError):
        derive_kek_with_params(
            b"passphrase",
            b"\x00",
            memory_cost=19 * 1024,
            time_cost=2,
            parallelism=1,
        )


def test_derivation_still_produces_a_key_for_valid_material() -> None:
    """POSITIVE CONTROL for the translation: valid material still derives."""
    kek = derive_kek_with_params(
        b"passphrase",
        b"\xab" * KDF_SALT_BYTES,
        memory_cost=19 * 1024,
        time_cost=2,
        parallelism=1,
    )
    assert len(kek) == 32
