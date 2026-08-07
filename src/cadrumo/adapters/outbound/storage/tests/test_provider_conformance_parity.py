"""Both storage backends are held to the :class:`StorageProvider` contract.

Before this module only ONE of the two backends was ever checked against the
Protocol it implements. ``test_foundation.py`` asserts
``isinstance(LocalFileSystemProvider(...), StorageProvider)`` and names
``GoogleDriveProvider`` only as a string in the public-surface allowlist -- it
never instantiates it. A backend that structurally cannot be checked against
its own contract is worse than one that fails the check, because the failure is
at least visible.

``runtime_checkable`` alone is a weak instrument: ``isinstance`` against a
Protocol verifies that the METHOD NAMES exist and nothing else. A backend whose
``put`` dropped ``label``, renamed ``content_hash``, or turned a keyword-only
parameter positional would still pass it, while every Protocol-typed caller
broke. So the checks below compare signatures, not just membership.

The rule is deliberately a PREFIX rule rather than equality, because one real
divergence is legitimate: ``LocalFileSystemProvider.put`` takes an extra
``batch`` parameter that opts the write into a ``DurableWriteBatch``, deferring
fsyncs to the batch commit. Drive has no fsync to defer, so the parameter
cannot exist there -- a genuine capability difference, not drift. Measured at
the time of writing: no Protocol-typed caller passes ``batch``; the only
producer reaching a provider through the Protocol is the mirror-manifest writer,
which does not. An extra parameter is therefore admissible **only** when it
carries a default, so a caller holding the Protocol can never trip over it.

Every check runs against both backends by parametrisation rather than being
written once per backend, so a third provider is covered the moment it is added
to ``_PROVIDERS`` -- and a provider added without being listed there is the one
gap this module cannot close by itself.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from .._google_drive import GoogleDriveProvider
from .._local import LocalFileSystemProvider
from .._protocol import StorageProvider

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

#: The Protocol's own method set, named once so a method added to the contract
#: without being added here cannot pass unnoticed -- the count assertion below
#: is checked against the Protocol rather than hardcoded.
_PROTOCOL_METHODS = ("put", "get", "delete", "iter_namespaces", "iter_objects", "probe")


def _local_provider(tmp_path: Path) -> LocalFileSystemProvider:
    return LocalFileSystemProvider(tmp_path / "vault")


def _drive_provider(_tmp_path: Path) -> GoogleDriveProvider:
    # The Protocol requires construction to be safe without network IO, so this
    # is a real instance rather than a double: no credentials are exercised and
    # no request is issued until a read/write method is called.
    return GoogleDriveProvider(
        credentials=object(),
        root_folder_id="root-folder-id",
        vault_folder_name="vault",
    )


_PROVIDERS: tuple[tuple[str, Callable[[Path], object]], ...] = (
    ("local", _local_provider),
    ("google_drive", _drive_provider),
)
_PROVIDER_IDS = tuple(name for name, _ in _PROVIDERS)


def _conformance_failures(provider_type: type) -> list[str]:
    """Return every way ``provider_type`` diverges from the Protocol contract.

    Accumulates rather than raising on the first divergence so a failure names
    the whole gap, and returns a list so the mutation proof can drive this
    predicate directly on a deliberately broken stub.
    """
    failures: list[str] = []
    for name in _PROTOCOL_METHODS:
        implementation = getattr(provider_type, name, None)
        if implementation is None:
            failures.append(f"{name}: not implemented")
            continue
        expected = inspect.signature(getattr(StorageProvider, name))
        actual = inspect.signature(implementation)
        expected_params = list(expected.parameters.values())
        actual_params = list(actual.parameters.values())
        if len(actual_params) < len(expected_params):
            failures.append(f"{name}: drops parameters {[p.name for p in expected_params[len(actual_params) :]]}")
            continue
        for position, contract_param in enumerate(expected_params):
            provider_param = actual_params[position]
            if provider_param.name != contract_param.name:
                failures.append(
                    f"{name}: parameter {position} is {provider_param.name!r}, contract declares {contract_param.name!r}",
                )
            elif provider_param.kind is not contract_param.kind:
                failures.append(
                    f"{name}: parameter {provider_param.name!r} is {provider_param.kind.name}, "
                    f"contract declares {contract_param.kind.name}",
                )
        for extra in actual_params[len(expected_params) :]:
            if extra.default is inspect.Parameter.empty:
                failures.append(
                    f"{name}: adds required parameter {extra.name!r}; a Protocol-typed caller cannot supply it",
                )
        if actual.return_annotation != expected.return_annotation:
            failures.append(
                f"{name}: returns {actual.return_annotation!r}, contract declares {expected.return_annotation!r}",
            )
    return failures


@pytest.mark.parametrize(("_name", "build"), _PROVIDERS, ids=_PROVIDER_IDS)
def test_every_backend_instance_satisfies_the_runtime_protocol(
    _name: str,
    build: Callable[[Path], object],
    tmp_path: Path,
) -> None:
    """Each shipped backend is a real ``StorageProvider`` instance.

    Weak on its own -- ``runtime_checkable`` only checks method names -- but it
    is the check Drive never had, and it also proves the Protocol's
    "constructible without network IO" clause holds for both.
    """
    assert isinstance(build(tmp_path), StorageProvider)


@pytest.mark.parametrize(("_name", "build"), _PROVIDERS, ids=_PROVIDER_IDS)
def test_every_backend_matches_the_contract_signatures(
    _name: str,
    build: Callable[[Path], object],
    tmp_path: Path,
) -> None:
    """Each backend accepts what the contract declares, under the same names and kinds."""
    failures = _conformance_failures(type(build(tmp_path)))

    assert not failures, "storage provider diverges from StorageProvider:\n" + "\n".join(failures)


def test_the_protocol_method_set_is_covered() -> None:
    """The checked method set is the Protocol's own, not a stale hand-copy.

    Without this, a method added to ``StorageProvider`` would simply go
    unchecked on both backends and every assertion above would still pass.
    """
    declared = {name for name, value in vars(StorageProvider).items() if not name.startswith("_") and callable(value)}

    assert declared == set(_PROTOCOL_METHODS)


def test_the_conformance_check_rejects_a_backend_that_drops_a_parameter() -> None:
    """Anti-tautology: the predicate bites on the exact drift it exists to catch.

    A green sweep over two conforming backends cannot distinguish a working
    check from one that inspects nothing, so the check is driven against
    deliberately broken stubs. ``put`` here omits ``label``, which
    ``runtime_checkable`` accepts and every Protocol-typed caller would break on.
    """

    class DropsLabel:
        def put(self, namespace: str, object_key_hmac: str, payload: bytes, *, content_hash: str) -> None: ...
        def get(self, namespace: str, object_key_hmac: str) -> None: ...
        def delete(self, namespace: str, object_key_hmac: str) -> None: ...
        def iter_namespaces(self) -> None: ...
        def iter_objects(self, namespace: str) -> None: ...
        def probe(self, *, read_only: bool = False) -> None: ...

    assert isinstance(DropsLabel(), StorageProvider), "runtime_checkable alone accepts this, which is the point"

    failures = _conformance_failures(DropsLabel)

    assert any("drops parameters" in failure and "label" in failure for failure in failures)


def test_the_conformance_check_rejects_a_renamed_parameter() -> None:
    """A renamed contract parameter breaks keyword callers and must be caught."""

    class RenamesContentHash:
        def put(
            self,
            namespace: str,
            object_key_hmac: str,
            payload: bytes,
            *,
            digest: str,
            label: str,
        ) -> None: ...
        def get(self, namespace: str, object_key_hmac: str) -> None: ...
        def delete(self, namespace: str, object_key_hmac: str) -> None: ...
        def iter_namespaces(self) -> None: ...
        def iter_objects(self, namespace: str) -> None: ...
        def probe(self, *, read_only: bool = False) -> None: ...

    failures = _conformance_failures(RenamesContentHash)

    assert any("content_hash" in failure for failure in failures)


def test_the_conformance_check_rejects_a_required_extra_parameter() -> None:
    """An extra parameter is admissible only with a default.

    This is the boundary the prefix rule draws: ``LocalFileSystemProvider.put``
    legitimately adds ``batch`` because it defaults, while a REQUIRED addition
    is unreachable for any caller holding only the Protocol.
    """

    class RequiresBatch:
        def put(
            self,
            namespace: str,
            object_key_hmac: str,
            payload: bytes,
            *,
            content_hash: str,
            label: str,
            batch: object,
        ) -> None: ...
        def get(self, namespace: str, object_key_hmac: str) -> None: ...
        def delete(self, namespace: str, object_key_hmac: str) -> None: ...
        def iter_namespaces(self) -> None: ...
        def iter_objects(self, namespace: str) -> None: ...
        def probe(self, *, read_only: bool = False) -> None: ...

    failures = _conformance_failures(RequiresBatch)

    assert any("adds required parameter" in failure and "batch" in failure for failure in failures)


def test_the_local_optional_batch_extension_stays_admissible(tmp_path: Path) -> None:
    """The one real divergence is admitted deliberately, not by a blind rule.

    Pins the fact this module reasons from: ``put`` is the only method whose
    signatures differ across the two backends, the difference is exactly
    ``batch``, and it defaults. If ``batch`` ever loses its default, or Drive
    grows a divergence of its own, this fails rather than the prefix rule
    quietly absorbing it.
    """
    local_put = inspect.signature(LocalFileSystemProvider.put)
    drive_put = inspect.signature(GoogleDriveProvider.put)

    extra = set(local_put.parameters) - set(drive_put.parameters)

    assert extra == {"batch"}
    assert local_put.parameters["batch"].default is None
    assert not _conformance_failures(type(_local_provider(tmp_path)))
    for name in _PROTOCOL_METHODS:
        if name == "put":
            continue
        assert list(inspect.signature(getattr(LocalFileSystemProvider, name)).parameters) == list(
            inspect.signature(getattr(GoogleDriveProvider, name)).parameters,
        ), name
