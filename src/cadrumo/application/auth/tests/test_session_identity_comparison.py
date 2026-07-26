"""Real-behavior tests for the comparison at the far end of the identity guard.

The fail-closed promise is a chain of two halves. The near half resolves
what the profile expects and is covered by
``test_clave_credential_resolution``. The far half - comparing that
expectation against the identity the bound session actually carries -
had four production call sites and no test at all, so the expectation was
proven POPULATED while nothing proved the comparison REFUSES.

That is the same shape as the defect the near half was written for: a
populated-looking expectation that nothing compares makes the downstream
check pass silently rather than skip loudly.

It matters most for the certificate provider. A certificate carries no
operator-configured credential, so the up-front guard cannot compare it;
its identity exists only once the certificate is read at session bind.
The certificate is therefore checked HERE rather than exempted, which
makes this comparison its only identity check.

Every test drives the real profile store and derives its expectation from
the real resolver rather than passing a literal, so a pass here exercises
the two halves joined. Sessions are real :class:`AeatSession` records -
value objects the guard genuinely receives, not test doubles - because the
comparison reads an identity off a bound session and nothing more.
"""

from __future__ import annotations

import ast
import inspect
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from ....adapters.outbound.aeat.auth import (
    AeatSession,
    CertificateSessionDetail,
    ClaveMovilSessionDetail,
)
from ....core import AuthProviderKind
from ....core.config import override_settings
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from ...user_profile import profile_create_storage_span
from ...workflow import workflow_state_repository
from .. import _sessions
from .._sessions import (
    AuthProfileIdentityMismatchError,
    _assert_session_identity_matches_expected,
    _prepare_clave_auth,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "33333333-3333-4333-8333-333333333333"
_PROFILE_LABEL = "session-identity-operator"
_TAX_ID = "12345678Z"
_OTHER_TAX_ID = "00000001R"

_LIVE_SESSION_RETURN_TYPES = ("AeatSession", "AuthenticatedAeatSessionResult")
_GUARD = "_assert_session_identity_matches_expected"


def _register_profile(**overrides: str) -> None:
    facts = {"identity.tax_id": _TAX_ID}
    facts.update(overrides)
    workflow_state_repository().update(
        lambda state: register_minimal_profile(
            state,
            profile_id=_BUCKET_ID,
            display_name=_PROFILE_LABEL,
            overrides=facts,
        ),
    )


def _clave_session(identity_nif: str) -> AeatSession:
    authenticated_at = datetime.now(UTC)
    return AeatSession(
        authenticated_at=authenticated_at,
        idle_deadline=authenticated_at + timedelta(minutes=30),
        storage_state_path=None,
        identity_nif=identity_nif,
        provider_detail=ClaveMovilSessionDetail(dni_nie=identity_nif),
    )


def _certificate_session(identity_nif: str) -> AeatSession:
    authenticated_at = datetime.now(UTC)
    return AeatSession(
        authenticated_at=authenticated_at,
        idle_deadline=authenticated_at + timedelta(minutes=30),
        storage_state_path=None,
        identity_nif=identity_nif,
        provider_detail=CertificateSessionDetail(
            certificate_thumbprint="abc123",
            certificate_subject=f"CN=OTHER TAXPAYER - {identity_nif}",
        ),
    )


def _expectation_for(kind: AuthProviderKind) -> str | None:
    with override_settings(
        cadrumo_clave_movil_dni_nie=SecretStr(_TAX_ID),
        cadrumo_clave_permanente_dni_nie=SecretStr(_TAX_ID),
    ) as settings:
        _bound, expected_identity = _prepare_clave_auth(settings, kind)
    return expected_identity


def test_a_session_bound_to_another_taxpayer_is_refused() -> None:
    """The comparison must refuse, not merely hold an expectation.

    The expectation comes from the real resolver rather than a literal,
    so this exercises the whole chain: the profile's identity is resolved,
    handed down, and compared against what the session actually carries.
    """

    _register_profile(**{"auth.dni_nie": _TAX_ID})
    expected_identity = _expectation_for(AuthProviderKind.CLAVE_MOVIL)
    assert expected_identity == _TAX_ID

    with pytest.raises(AuthProfileIdentityMismatchError):
        _assert_session_identity_matches_expected(_clave_session(_OTHER_TAX_ID), expected_identity)


def test_a_certificate_session_bound_to_another_taxpayer_is_refused() -> None:
    """This comparison is the certificate provider's only identity check.

    A certificate has no operator-configured credential for the up-front
    guard to compare, so its identity is first knowable at session bind.
    If this comparison did not refuse, a certificate belonging to another
    taxpayer would authenticate against this profile unremarked.
    """

    _register_profile()
    expected_identity = _expectation_for(AuthProviderKind.CERTIFICATE)
    assert expected_identity == _TAX_ID

    with pytest.raises(AuthProfileIdentityMismatchError):
        _assert_session_identity_matches_expected(
            _certificate_session(_OTHER_TAX_ID),
            expected_identity,
        )


def test_the_taxpayers_own_session_is_accepted() -> None:
    """The control the refusals need to mean anything.

    A comparison that refused every session would satisfy both tests
    above while making the product unusable, so the matching case must
    pass through untouched.
    """

    _register_profile(**{"auth.dni_nie": _TAX_ID})
    expected_identity = _expectation_for(AuthProviderKind.CLAVE_MOVIL)

    _assert_session_identity_matches_expected(_clave_session(_TAX_ID), expected_identity)
    _assert_session_identity_matches_expected(_certificate_session(_TAX_ID), expected_identity)


def test_the_comparison_normalises_before_it_refuses() -> None:
    """Presentation differences are not identity differences.

    AEAT surfaces echo a NIF with varying case and padding. Comparing
    raw strings would refuse the taxpayer's own session over a lower-case
    letter, which reads to the operator as an accusation rather than as
    the formatting artefact it is.
    """

    _register_profile(**{"auth.dni_nie": _TAX_ID})
    expected_identity = _expectation_for(AuthProviderKind.CLAVE_MOVIL)

    _assert_session_identity_matches_expected(
        _clave_session(f"  {_TAX_ID.lower()}  "),
        expected_identity,
    )


def test_a_real_session_cannot_carry_a_blank_identity() -> None:
    """The comparison's blank-session branch is defence, not exposure.

    The guard skips when the session reports no identity, which would be
    a fail-open if a bound session could ever reach it that way. It
    cannot: the field is constrained at the type, so the skip is
    unreachable through the record the four call sites actually pass.
    """

    with pytest.raises(ValidationError):
        _clave_session("")


def test_a_profile_without_a_fiscal_id_has_nothing_to_compare() -> None:
    """Names the one fail-open honestly rather than implying there is none.

    The comparison cannot invent an identity the profile does not carry,
    so a profile with no fiscal ID admits any session. That is the
    boundary of what this guard can promise, and it closes by the profile
    carrying a fiscal ID - not by anything this function could do.
    """

    _assert_session_identity_matches_expected(_clave_session(_OTHER_TAX_ID), "")
    _assert_session_identity_matches_expected(_clave_session(_OTHER_TAX_ID), None)


def test_every_path_that_hands_back_a_session_compares_its_identity() -> None:
    """Behavioural cover alone would not notice a call site vanishing.

    The original defect was not a wrong comparison but an absent one, and
    every test above would stay green if the call sites were deleted. So
    this asserts the wiring, and it asserts it per RETURN rather than per
    function: a writer with four guarded returns that grows an unguarded
    fifth is the exact shape being defended against, and a
    does-this-function-mention-the-guard check would call that green.

    A return satisfies the rule by being preceded by the comparison in its
    own block or an enclosing one, or by delegating to a module-local
    function whose own returns all satisfy it.
    """

    # Module level only. The provider Protocols in this module declare
    # session-returning methods too, but those describe what an outbound
    # provider offers; the comparison belongs to the application writer
    # that hands a bound session on, not to the provider contract.
    tree = ast.parse(inspect.getsource(_sessions))
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)}
    writers = {
        name: node
        for name, node in functions.items()
        if node.returns is not None and ast.unparse(node.returns).strip() in _LIVE_SESSION_RETURN_TYPES
    }
    assert writers, (
        "no session-returning function was found in _sessions.py; the sweep matched "
        "nothing and so proves nothing about the guard's wiring"
    )

    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    def guard_precedes(node: ast.AST, within: ast.AST) -> bool:
        """Report whether the comparison runs before ``node`` on every route to it.

        Only an unconditional call counts - a bare expression statement in
        the prefix of a block on the route. A preceding SIBLING branch that
        calls the comparison guards its own return, not this one, so
        accepting a nested mention would pass a writer whose new return
        path skips the check entirely.
        """
        current = node
        while current in parents and current is not within:
            parent = parents[current]
            for field in ("body", "orelse", "finalbody"):
                block = getattr(parent, field, None)
                if not isinstance(block, list) or current not in block:
                    continue
                preceding = block[: block.index(current)]
                if any(isinstance(statement, ast.Expr) and _GUARD in ast.unparse(statement) for statement in preceding):
                    return True
            current = parent
        return False

    def delegates_to_checked_writer(value: ast.expr, seen: frozenset[str]) -> bool:
        for call in ast.walk(value):
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id in writers:
                return not unchecked_returns(call.func.id, seen)
        return False

    def unchecked_returns(name: str, seen: frozenset[str] = frozenset()) -> list[int]:
        if name in seen:
            return []
        writer = writers[name]
        return [
            statement.lineno
            for statement in ast.walk(writer)
            if isinstance(statement, ast.Return)
            and statement.value is not None
            and not guard_precedes(statement, writer)
            and not delegates_to_checked_writer(statement.value, seen | {name})
        ]

    unguarded = {name: lines for name in sorted(writers) if (lines := unchecked_returns(name))}
    assert not unguarded, (
        f"_sessions.py hands back a bound session without comparing its identity at "
        f"{unguarded} (name -> line numbers). A return that skips the comparison restores "
        "the silent pass this guard exists to prevent."
    )


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span(_BUCKET_ID),
    ):
        yield
