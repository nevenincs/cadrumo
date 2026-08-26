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
from .._key_validation import assert_admissible_object_key_hmac
from .._local import LocalFileSystemProvider
from .._protocol import StorageProvider
from ..errors import OutboundStorageValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

if TYPE_CHECKING:
    from collections.abc import Callable

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


_PROVIDERS: tuple[tuple[str, Callable[[Path], StorageProvider]], ...] = (
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
    build: Callable[[Path], StorageProvider],
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
    build: Callable[[Path], StorageProvider],
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


# --- object-key admissibility -------------------------------------------------
#
# Signature conformance says the backends accept the same ARGUMENTS. These say
# they accept the same VALUES, which is the half that had actually diverged:
# local enforced an `[alnum-_]` charset on `object_key_hmac` while Drive
# enforced only non-blank, so a key one backend refused the other stored.

#: Keys no digest can produce. The quote is the one that mattered: Drive
#: interpolates the key's 8-character prefix into a query string, so a quote
#: inside that prefix is the shape the charset rule exists to exclude.
_INADMISSIBLE_KEYS = ("abc'defg", "../../etc/passwd", "has space", "sla/sh", r"back\slash", "semi;colon")

#: Keys every production producer actually emits: two sha256 hex digests and
#: the sentinel both providers' `probe` writes.
_ADMISSIBLE_KEYS = ("0" * 64, "7f343fa82f8a281192c3e4b4a1d0f5e6", "00000000probe", "with-dash_and_underscore")


@pytest.mark.parametrize(("_name", "build"), _PROVIDERS, ids=_PROVIDER_IDS)
@pytest.mark.parametrize("hostile", _INADMISSIBLE_KEYS)
def test_both_backends_refuse_the_same_inadmissible_object_key(
    _name: str,
    build: Callable[[Path], StorageProvider],
    hostile: str,
    tmp_path: Path,
) -> None:
    """Neither backend stores a key the other would reject.

    Drive is the backend this changes: it previously accepted every one of
    these. The parametrisation is over BOTH so the property is "they agree",
    not "Drive was fixed once".
    """
    provider = build(tmp_path)

    with pytest.raises(OutboundStorageValidationError):
        provider.get("namespace", hostile)


@pytest.mark.parametrize(("_name", "build"), _PROVIDERS, ids=_PROVIDER_IDS)
@pytest.mark.parametrize("admissible", _ADMISSIBLE_KEYS)
def test_neither_backend_refuses_a_key_production_actually_emits(
    _name: str,
    build: Callable[[Path], StorageProvider],
    admissible: str,
    tmp_path: Path,
) -> None:
    """The tightened rule refuses nothing any writer in this repository produces.

    The narrowing's precondition, kept as a standing assertion rather than a
    one-off measurement: if a future producer emits something outside the
    admissible set, this fails rather than that key being silently refused at
    runtime on one backend only.
    """
    provider = build(tmp_path)

    # A validation refusal is the failure under test; anything else (missing
    # object, absent root, no credentials, a backend-specific transport
    # failure) means the key itself was admitted. The failure surface differs
    # per backend (a typed OutboundStorageError locally, a raw googleapiclient
    # exception for a mocked Drive credential), so this deliberately catches
    # anything and discriminates inside the handler rather than
    # pytest.raises(Exception), which the broad-exception-assertion gate would
    # otherwise flag as an untargeted expectation.
    try:
        provider.get("namespace", admissible)
    except Exception as exc:
        if isinstance(exc, OutboundStorageValidationError):
            raise AssertionError(f"admissible key {admissible!r} was refused as invalid: {exc}") from exc
    else:
        raise AssertionError(
            f"expected {provider!r}.get to fail for admissible key {admissible!r} on this unwired test fixture "
            "(missing object, absent root, or no credentials) -- a silent success means the fixture changed "
            "and this test's assumptions need revisiting",
        )


def test_each_backend_keeps_its_own_refusal_identity() -> None:
    """One rule, two error identities -- an operator learns WHICH backend refused.

    The shared validator is parameterised by backend rather than raising one
    flattened message, for the reason the AEAT representation gate is: merging
    two refusals into one loses the only information the operator can act on.
    """
    messages = {}
    for backend in ("local", "google_drive"):
        with pytest.raises(OutboundStorageValidationError) as caught:
            assert_admissible_object_key_hmac("abc'defg", backend=backend)
        messages[backend] = caught.value.translated_message

    assert messages["local"] != messages["google_drive"]
    for backend, message in messages.items():
        assert message == f"adapters.outbound.storage.{backend}.errors.object_key_hmac_forbidden_characters"


def test_the_namespace_divergence_stays_permitted_and_stated() -> None:
    """A leading-dot namespace is refused locally and admitted by Drive, on purpose.

    Recorded as an EXPLICITLY permitted divergence so the next author does not
    "fix" it into a shared rule. A leading dot makes a hidden file on a
    filesystem and means nothing in a Drive folder name, so the two backends
    are answering different questions -- unlike the object key, which is one
    contract-level value both were answering differently.
    """
    from .._google_drive import _validate_namespace as drive_namespace
    from .._local import _validate_namespace as local_namespace

    with pytest.raises(OutboundStorageValidationError):
        local_namespace(".hidden")

    assert drive_namespace(".hidden") == ".hidden"
