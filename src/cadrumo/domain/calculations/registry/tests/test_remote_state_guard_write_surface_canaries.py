"""The guard must refuse the real AEAT state-creating paths, by URL.

``LIVE_PARITY_STATE_CREATING_PATH_CANARIES`` declares four genuine AEAT write
surfaces -- TGVI online and the PRET upload/transmission family, documented in
``_remote_state_guard`` as staging server-side state under the authenticated
NIF even before legal presentation -- and had **zero consumers**. A declared
canary set that nothing fires is not coverage: it would not have caught a
regression in either direction, while reading as enforcement to anyone who
found it.

The gap is one level deeper than an unused constant.
``test_url_method_guard_includes_canonical_write_verb_tokens`` asserts
``AEAT_WRITE_FORBIDDEN_VERB_TOKENS - set(_FORBIDDEN_TOKENS) == set()``, but
``_FORBIDDEN_TOKENS`` is *built by unpacking* ``AEAT_WRITE_FORBIDDEN_VERB_TOKENS``.
The containment therefore holds by construction at every value of the constant:
dropping ``tgvi`` from the canonical set removes it from both sides and nothing
reds. That test pins the token list against itself, so before this module the
token list was the only thing standing between a production NIF and a real AEAT
upload surface, and nothing measured whether it worked.

These tests pin the tokens against the real-world fact they encode -- the
actual AEAT paths that must be refused -- so removing a token fails here with
the path it stopped refusing.

Every probe uses **GET**. The guard refuses any POST outright, so a POST probe
would pass with the URL scan deleted entirely and prove nothing about the path.
A positive control asserts a genuine read path is still allowed, so a
refuse-everything guard cannot satisfy this module.
"""

from __future__ import annotations

import pytest
from pydantic import AnyUrl

from .....tests.aeat_literal_fixtures import (
    AEAT_WRITE_VERB_TOKEN_WITNESS_PATH_CANARIES,
    LIVE_PARITY_STATE_CREATING_PATH_CANARIES,
    PUBLIC_OPEN_SIMULATOR_PATH_FIXTURE,
    WRITE_VERB_WITNESS_CANCELAR_PATH_CANARY,
    WRITE_VERB_WITNESS_PAGAR_PATH_CANARY,
    WRITE_VERB_WITNESS_PRESENTACION_PATH_CANARY,
    aeat_host,
    aeat_url,
)
from ..errors import RegistryValidationError
from ..remote_state_guard import (
    RemoteOperation,
    RemoteStateGuardPolicy,
    assert_remote_operation_allowed,
)
from ..schema_base import EvidenceTier

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SEDE_HOST = aeat_host("sede")


def _open_policy() -> RemoteStateGuardPolicy:
    """The most permissive real classification, so a refusal is the path's doing.

    ``open_simulator`` needs no authentication and no AEAT authorization, which
    strips away every refusal reason except the one under test.
    """
    return RemoteStateGuardPolicy(
        id="state-creating-canaries",
        evidence_tier=EvidenceTier.EXECUTABLE_PARITY_EVIDENCE,
        classification="open_simulator",
        allowed_hosts=(_SEDE_HOST,),
        synthetic_data_allowed=False,
        requires_authentication=False,
        requires_aeat_authorization=False,
    )


def _get(path: str) -> None:
    assert_remote_operation_allowed(
        _open_policy(),
        RemoteOperation(kind="http", method="GET", url=AnyUrl(aeat_url("sede", path))),
    )


def test_a_genuine_read_path_is_allowed_on_get() -> None:
    """Positive control: a refuse-everything guard cannot satisfy this module."""
    _get(PUBLIC_OPEN_SIMULATOR_PATH_FIXTURE)


@pytest.mark.parametrize("state_creating_path", LIVE_PARITY_STATE_CREATING_PATH_CANARIES)
def test_every_declared_state_creating_path_is_refused_on_get(state_creating_path: str) -> None:
    """Each declared AEAT write surface is refused before any call leaves the process."""
    with pytest.raises(RegistryValidationError, match=r"forbidden"):
        _get(state_creating_path)


def test_the_canary_set_is_not_empty() -> None:
    """A parametrized suite over an emptied tuple would collect zero cases and pass.

    Without this, deleting the canaries silently removes the enforcement above
    rather than failing -- the same shape of vacuity the module docstring
    describes, reintroduced through the fixture instead of the token list.
    """
    assert len(LIVE_PARITY_STATE_CREATING_PATH_CANARIES) == 4


def test_each_canary_is_refused_for_a_distinct_stated_reason() -> None:
    """The refusals name the token they fired on, so a lost token is attributable.

    A guard that refused all four for one blanket reason would satisfy the
    parametrized test above while hiding which token carries which surface.
    """
    reasons: dict[str, str] = {}
    for path in LIVE_PARITY_STATE_CREATING_PATH_CANARIES:
        with pytest.raises(RegistryValidationError) as excinfo:
            _get(path)
        reasons[path] = str(excinfo.value)

    tgvi_online, pret_upload, pret_transmision, pret_transmitir = LIVE_PARITY_STATE_CREATING_PATH_CANARIES
    assert "tgvi" in reasons[tgvi_online]
    assert "tgvi" in reasons[pret_upload]
    assert "transmision" in reasons[pret_transmision]
    assert "transmitir" in reasons[pret_transmitir]


@pytest.mark.parametrize("write_verb_witness_path", AEAT_WRITE_VERB_TOKEN_WITNESS_PATH_CANARIES)
def test_every_write_verb_witness_path_is_refused_on_get(write_verb_witness_path: str) -> None:
    """Each token independently witnessed against a real AEAT surface is refused.

    Unlike ``LIVE_PARITY_STATE_CREATING_PATH_CANARIES`` (the TGVI/PRET upload
    family), these three paths are not project-authored canary shapes: they are
    the batch-presentation endpoint, the deployed Clave Movil cancellation
    path, and a debt-payment procedure quoted verbatim from the bundled AEAT
    Manual Practico de Sociedades -- each a genuine AEAT-published surface, not
    a synthetic stand-in.
    """
    with pytest.raises(RegistryValidationError, match=r"forbidden"):
        _get(write_verb_witness_path)


def test_the_write_verb_witness_set_is_not_empty() -> None:
    """A parametrized suite over an emptied tuple would collect zero cases and pass."""
    assert len(AEAT_WRITE_VERB_TOKEN_WITNESS_PATH_CANARIES) == 3


def test_each_write_verb_witness_is_refused_for_its_own_token() -> None:
    """The refusals name the token they fired on, so a lost token is attributable."""
    with pytest.raises(RegistryValidationError) as presentacion_excinfo:
        _get(WRITE_VERB_WITNESS_PRESENTACION_PATH_CANARY)
    assert "presentacion" in str(presentacion_excinfo.value)

    with pytest.raises(RegistryValidationError) as cancelar_excinfo:
        _get(WRITE_VERB_WITNESS_CANCELAR_PATH_CANARY)
    assert "cancelar" in str(cancelar_excinfo.value)

    with pytest.raises(RegistryValidationError) as pagar_excinfo:
        _get(WRITE_VERB_WITNESS_PAGAR_PATH_CANARY)
    assert "pagar" in str(pagar_excinfo.value)
