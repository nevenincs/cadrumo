"""Tests for deny-by-default AEAT remote-state guard policy."""

from __future__ import annotations

import pytest
from pydantic import AnyUrl, ValidationError

from .....core.resources import bundled_path
from .....tests.aeat_literal_fixtures import (
    AEAT_HOST_SUFFIX_EXPECTED,
    AEAT_LEGACY_APEX_CANARY,
    AEAT_LEGACY_SEDE_CANARY,
    PUBLIC_OPEN_SIMULATOR_PATH_FIXTURE,
    STATIC_DESIGN_REGISTER_PATH_FIXTURE,
    UNCLASSIFIED_MUTATING_READ_POST_PATH_CANARY,
    UNCLASSIFIED_WWW2_READ_PATH_CANARY,
    UNKNOWN_AEAT_STATE_SURFACE_URL_CANARY,
    aeat_host,
    aeat_url,
    configured_path,
)
from .. import ModeloDefinition, RegistryCatalogues, build_snapshot
from .._aeat_nif_iva_oracle import ORACLE_ID, AeatNifIvaCheckerOracle
from ..errors import RegistrySnapshotError, RegistryValidationError
from .._groi_oracle import GROI_ORACLE_ID, GroiOracle
from .._live_parity import LiveParityCatalogue, OracleEnvironment
from .._remote_state_guard import (
    _FORBIDDEN_TOKENS,
    RemoteOperation,
    RemoteStateGuardPolicy,
    assert_remote_operation_allowed,
    assert_remote_operations_allowed,
    evaluate_remote_operation,
    remote_state_policy_from_cross_reference,
)
from .._renta_web_open_oracle import RentaWebOpenOracle
from .._schema import LiveCrossReferenceDecision
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SEDE_HOST = aeat_host("sede")
_WWW2_HOST = aeat_host("www2")
_WWW6_HOST = aeat_host("www6")
_AEAT_APEX_HOST = aeat_host("aeat_gob")
_CLAVE_HOST = aeat_host("clave")
_PLANNED_OPERATION_EXPECTED_FIXTURES = {
    GROI_ORACLE_ID: {"A28015865": "valid"},
    ORACLE_ID: {"DE111222333": "valid"},
    "modelo-100-renta-web-open": {"0180": object()},
}


#: Tokens independently corroborated against a real AEAT write surface --
#: NOT derived from ``AEAT_WRITE_FORBIDDEN_VERB_TOKENS`` itself, which is what
#: makes this set usable as a pin. The other 14 members of that frozenset
#: (``anular``, ``confirmar``, ``confirmacion``, ``domiciliar``, ``enviar``,
#: ``firmar``, ``guardar``, ``modificar``, ``save``, ``sign``, ``subsanar``,
#: ``submit``) have no comparable real-surface witness in the bundled AEAT
#: corpus, the portal catalogue, or this project's deployment configuration
#: today; that gap is recorded against this task, not silently assumed closed.
_WITNESSED_AGAINST_A_REAL_AEAT_SURFACE = frozenset(
    {"presentacion", "cancelar", "tgvi", "transmision", "transmitir", "pagar"},
)


def test_url_method_guard_covers_every_witnessed_write_verb_token() -> None:
    """The URL/method denylist MUST cover every token proven against a real AEAT surface.

    The prior form of this test asserted
    ``AEAT_WRITE_FORBIDDEN_VERB_TOKENS - set(_FORBIDDEN_TOKENS) == set()``,
    which is VACUOUS: ``_FORBIDDEN_TOKENS`` is *built by unpacking*
    ``AEAT_WRITE_FORBIDDEN_VERB_TOKENS``, so the containment holds by
    construction at every value of the constant -- dropping ``tgvi`` from the
    source removes it from both sides and nothing reds (mutation-proven: see
    ``test_remote_state_guard_write_surface_canaries.py``, which failed three
    real-path cases on that exact deletion while this assertion stayed green).

    Pinning against ``_WITNESSED_AGAINST_A_REAL_AEAT_SURFACE`` -- a literal set
    independent of the constant under test -- breaks the circularity: a token
    dropped from ``AEAT_WRITE_FORBIDDEN_VERB_TOKENS`` is dropped from
    ``_FORBIDDEN_TOKENS`` too, and this assertion reds.
    """

    forbidden = set(_FORBIDDEN_TOKENS)
    missing = _WITNESSED_AGAINST_A_REAL_AEAT_SURFACE - forbidden
    assert not missing, f"_FORBIDDEN_TOKENS dropped a token witnessed against a real AEAT surface: {sorted(missing)}"


def _open_policy() -> RemoteStateGuardPolicy:
    # AEAT-hosted policies must not advertise synthetic input per the
    # no-synthetic-sede-live-surfaces contract.
    return RemoteStateGuardPolicy(
        id="m303-open",
        evidence_tier="executable_parity_evidence",
        classification="open_simulator",
        allowed_hosts=(_SEDE_HOST,),
        synthetic_data_allowed=False,
        requires_authentication=False,
        requires_aeat_authorization=False,
    )


def test_remote_state_guard_allows_read_only_open_simulator_get() -> None:
    result = assert_remote_operation_allowed(
        _open_policy(),
        RemoteOperation(
            kind="http",
            method="GET",
            url=AnyUrl(aeat_url("sede", PUBLIC_OPEN_SIMULATOR_PATH_FIXTURE)),
        ),
    )

    assert result.decision == "allowed"


def test_remote_state_guard_blocks_post_even_on_allowed_host() -> None:
    with pytest.raises(RegistryValidationError, match="remote write method"):
        assert_remote_operation_allowed(
            _open_policy(),
            RemoteOperation(
                kind="http",
                method="POST",
                url=AnyUrl(aeat_url("sede", PUBLIC_OPEN_SIMULATOR_PATH_FIXTURE)),
            ),
        )


def test_remote_state_guard_blocks_stateful_tokens_in_browser_actions() -> None:
    result = evaluate_remote_operation(
        _open_policy(),
        RemoteOperation(kind="browser_action", action="Presentar declaracion"),
    )

    assert result.decision == "blocked"
    assert "presentar" in result.reason


def test_remote_state_guard_blocks_non_read_only_browser_action_matrix() -> None:
    policy = _open_policy().model_copy(
        update={"allowed_browser_action_patterns": ("representation-gate-own-name-continue",)},
    )

    for action, token in (
        ("representation-gate-represented-taxpayer-continue", "explicit read-only allow-list"),
        ("Presentar declaracion", "presentar"),
        ("Firmar declaracion", "firmar"),
        ("Pagar liquidacion", "pagar"),
        ("Confirmar", "confirmar"),
    ):
        with pytest.raises(RegistryValidationError, match=token):
            assert_remote_operation_allowed(policy, RemoteOperation(kind="browser_action", action=action))


def test_remote_state_guard_blocks_unclassified_browser_action_when_allow_list_declared() -> None:
    policy = _open_policy().model_copy(update={"allowed_browser_action_patterns": ("open-safe-dialog",)})

    assert_remote_operation_allowed(
        policy,
        RemoteOperation(kind="browser_action", action="open-safe-dialog"),
    )
    with pytest.raises(RegistryValidationError, match="explicit read-only allow-list"):
        assert_remote_operation_allowed(
            policy,
            RemoteOperation(kind="browser_action", action="new-unreviewed-click"),
        )


def test_remote_state_guard_supports_allowed_browser_action_wildcards() -> None:
    policy = _open_policy().model_copy(update={"allowed_browser_action_patterns": ("check-nif-*",)})

    result = assert_remote_operation_allowed(
        policy,
        RemoteOperation(kind="browser_action", action="check-nif-ESB12345678"),
    )

    assert result.decision == "allowed"


def test_oracle_bound_cross_reference_policy_gets_consult_action_allow_list() -> None:
    # GROI is an authenticated_simulator on an AEAT host; per the
    # no-synthetic-sede-live-surfaces contract synthetic_data_allowed must
    # be false.
    decision = LiveCrossReferenceDecision(
        id="modelo-349-groi-spanish-counterparty-check",
        evidence_tier="executable_parity_evidence",
        surface="authenticated_simulator",
        guard_policy_id="modelo-349-groi-spanish-roi-check",
        allowed_hosts=(_WWW2_HOST,),
        allowed_methods=("GET", "POST"),
        forbidden_actions=(
            "server-side-save",
            "signing",
            "presentation",
            "payment",
            "amendment",
            "cancellation",
            "document-submission",
            "declaration-submission",
        ),
        synthetic_data_allowed=False,
        requires_authentication=True,
        requires_aeat_authorization=False,
        oracle_id="aeat-groi-spanish-roi-checker",
        legal_refs=("ley-58-2003:art-93",),
        source_refs=("aeat-vies-gestiones-procedure",),
    )
    policy = remote_state_policy_from_cross_reference(decision)

    assert "check-nif-*" in policy.allowed_browser_action_patterns
    assert_remote_operation_allowed(policy, RemoteOperation(kind="browser_action", action="check-nif-A28015865"))
    with pytest.raises(RegistryValidationError, match="explicit read-only allow-list"):
        assert_remote_operation_allowed(policy, RemoteOperation(kind="browser_action", action="unreviewed-click"))


# --- AEAT-host synthetic-data invariant tests (no-synthetic-sede-live-surfaces contract) ---


def test_schema_rejects_aeat_hosted_live_cross_reference_with_synthetic_data_allowed() -> None:
    """AEAT-hosted live cross-references must not declare synthetic_data_allowed = true."""
    with pytest.raises(ValidationError, match="synthetic data is prohibited on AEAT-hosted"):
        LiveCrossReferenceDecision(
            id="test-aeat-hosted-synthetic-reject",
            evidence_tier="executable_parity_evidence",
            surface="open_simulator",
            guard_policy_id="test-aeat-hosted-synthetic-reject-policy",
            allowed_hosts=(_SEDE_HOST,),
            allowed_methods=("GET",),
            forbidden_actions=(
                "server-side-save",
                "signing",
                "presentation",
                "payment",
                "amendment",
                "cancellation",
                "document-submission",
                "declaration-submission",
            ),
            synthetic_data_allowed=True,
            requires_authentication=False,
            requires_aeat_authorization=False,
            legal_refs=("ley-58-2003:art-93",),
            source_refs=("test-source",),
        )


def test_schema_accepts_non_aeat_host_with_synthetic_data_allowed() -> None:
    """A non-AEAT host may still declare synthetic_data_allowed = true (local simulator)."""
    decision = LiveCrossReferenceDecision(
        id="test-local-simulator-synthetic-ok",
        evidence_tier="executable_parity_evidence",
        surface="open_simulator",
        guard_policy_id="test-local-simulator-policy",
        allowed_hosts=("localhost",),
        allowed_methods=("GET",),
        forbidden_actions=(
            "server-side-save",
            "signing",
            "presentation",
            "payment",
            "amendment",
            "cancellation",
            "document-submission",
            "declaration-submission",
        ),
        synthetic_data_allowed=True,
        requires_authentication=False,
        requires_aeat_authorization=False,
        legal_refs=("ley-58-2003:art-93",),
        source_refs=("test-source",),
    )
    assert decision.synthetic_data_allowed is True


def test_schema_accepts_aeat_host_with_synthetic_data_not_allowed() -> None:
    """An AEAT-hosted cross-reference is valid when synthetic_data_allowed = false."""
    decision = LiveCrossReferenceDecision(
        id="test-aeat-hosted-no-synthetic",
        evidence_tier="executable_parity_evidence",
        surface="open_simulator",
        guard_policy_id="test-aeat-hosted-no-synthetic-policy",
        allowed_hosts=(_SEDE_HOST,),
        allowed_methods=("GET",),
        forbidden_actions=(
            "server-side-save",
            "signing",
            "presentation",
            "payment",
            "amendment",
            "cancellation",
            "document-submission",
            "declaration-submission",
        ),
        synthetic_data_allowed=False,
        requires_authentication=False,
        requires_aeat_authorization=False,
        legal_refs=("ley-58-2003:art-93",),
        source_refs=("test-source",),
    )
    assert decision.synthetic_data_allowed is False


def test_guard_rejects_aeat_hosted_policy_with_synthetic_data_allowed() -> None:
    """RemoteStateGuardPolicy must reject AEAT-hosted policies with synthetic_data_allowed = true."""
    with pytest.raises(ValidationError, match="synthetic data is prohibited on AEAT-hosted"):
        RemoteStateGuardPolicy(
            id="test-aeat-guard-synthetic-reject",
            evidence_tier="executable_parity_evidence",
            classification="open_simulator",
            allowed_hosts=(_SEDE_HOST,),
            synthetic_data_allowed=True,
            requires_authentication=False,
            requires_aeat_authorization=False,
        )


def test_schema_rejects_each_aeat_suffix_form_with_synthetic_data() -> None:
    """Every AEAT-suffix form (apex and subdomain, both apex domains) is rejected."""

    for host in (
        _AEAT_APEX_HOST,
        _SEDE_HOST,
        _WWW2_HOST,
        AEAT_LEGACY_APEX_CANARY,
        AEAT_LEGACY_SEDE_CANARY,
    ):
        with pytest.raises(ValidationError, match="synthetic data is prohibited on AEAT-hosted"):
            LiveCrossReferenceDecision(
                id="test-aeat-suffix-form-reject",
                evidence_tier="executable_parity_evidence",
                surface="open_simulator",
                guard_policy_id="test-aeat-suffix-form-policy",
                allowed_hosts=(host,),
                allowed_methods=("GET",),
                forbidden_actions=(
                    "server-side-save",
                    "signing",
                    "presentation",
                    "payment",
                    "amendment",
                    "cancellation",
                    "document-submission",
                    "declaration-submission",
                ),
                synthetic_data_allowed=True,
                requires_authentication=False,
                requires_aeat_authorization=False,
                legal_refs=("ley-58-2003:art-93",),
                source_refs=("test-source",),
            )


def test_guard_rejects_each_aeat_suffix_form_with_synthetic_data() -> None:
    """Guard layer mirrors the schema rejection for every AEAT-suffix form."""

    for host in (_AEAT_APEX_HOST, AEAT_LEGACY_APEX_CANARY, AEAT_LEGACY_SEDE_CANARY):
        with pytest.raises(ValidationError, match="synthetic data is prohibited on AEAT-hosted"):
            RemoteStateGuardPolicy(
                id="test-guard-suffix-form-reject",
                evidence_tier="executable_parity_evidence",
                classification="open_simulator",
                allowed_hosts=(host,),
                synthetic_data_allowed=True,
                requires_authentication=False,
                requires_aeat_authorization=False,
            )


def test_public_read_surface_synthetic_data_message_is_classification_specific() -> None:
    """public_read_surface synthetic data raises its own message, not the authenticated one.

    Locks the validator branch split: the synthetic-data consistency predicates are
    keyed on mutually-exclusive classifications, so a public_read_surface policy can
    only ever surface the public-reads message — never the authenticated-read one.
    """
    with pytest.raises(ValueError, match="public reads must not use synthetic remote data"):
        RemoteStateGuardPolicy(
            id="public-read-synthetic",
            evidence_tier="official_source_guidance",
            classification="public_read_surface",
            allowed_hosts=(_SEDE_HOST,),
            synthetic_data_allowed=True,
            requires_authentication=False,
            requires_aeat_authorization=False,
        )


def test_authenticated_read_surface_requires_authentication_message() -> None:
    """authenticated_read_surface without requires_authentication raises its own message."""
    with pytest.raises(ValueError, match="authenticated filed-data read policy must require authentication"):
        RemoteStateGuardPolicy(
            id="auth-read-no-auth",
            evidence_tier="official_source_guidance",
            classification="authenticated_read_surface",
            allowed_hosts=(_WWW6_HOST,),
            synthetic_data_allowed=False,
            requires_authentication=False,
            requires_aeat_authorization=False,
        )


def test_forbidden_stateful_surface_rejects_synthetic_data() -> None:
    """forbidden_stateful_surface with synthetic data raises in the synthetic-data phase."""
    with pytest.raises(ValueError, match="forbidden stateful surface cannot accept synthetic remote data"):
        RemoteStateGuardPolicy(
            id="forbidden-synthetic",
            evidence_tier="official_source_guidance",
            classification="forbidden_stateful_surface",
            allowed_hosts=(),
            synthetic_data_allowed=True,
            requires_authentication=False,
            requires_aeat_authorization=False,
        )


def test_open_simulator_must_not_require_authentication() -> None:
    """open_simulator with requires_authentication raises in the authentication phase."""
    with pytest.raises(ValueError, match="open simulator policy must not require authentication"):
        RemoteStateGuardPolicy(
            id="open-sim-auth",
            evidence_tier="executable_parity_evidence",
            classification="open_simulator",
            allowed_hosts=(_SEDE_HOST,),
            synthetic_data_allowed=False,
            requires_authentication=True,
            requires_aeat_authorization=False,
        )


def test_live_policy_must_declare_allowed_hosts() -> None:
    """A live read surface with no allowed hosts raises in the allowed-hosts phase."""
    with pytest.raises(ValueError, match="AEAT remote policy must declare allowed hosts"):
        RemoteStateGuardPolicy(
            id="open-sim-no-hosts",
            evidence_tier="executable_parity_evidence",
            classification="open_simulator",
            allowed_hosts=(),
            synthetic_data_allowed=False,
            requires_authentication=False,
            requires_aeat_authorization=False,
        )


def test_remote_state_guard_blocks_unknown_aeat_host() -> None:
    with pytest.raises(RegistryValidationError, match="not in allowed read-only hosts"):
        assert_remote_operation_allowed(
            _open_policy(),
            RemoteOperation(
                kind="http",
                method="GET",
                url=AnyUrl(aeat_url("www2", UNCLASSIFIED_WWW2_READ_PATH_CANARY)),
            ),
        )


def _host_suffix_policy() -> RemoteStateGuardPolicy:
    # An authenticated read surface pinned to www6 but widened to accept any
    # subdomain under the AEAT apex, mirroring the declarations/censo live-pull
    # guards that must tolerate ``www{n}`` load-balancer dispatch.
    return RemoteStateGuardPolicy(
        id="host-suffix-read",
        evidence_tier="official_source_guidance",
        classification="authenticated_read_surface",
        allowed_hosts=(_WWW6_HOST,),
        allowed_host_suffixes=(AEAT_HOST_SUFFIX_EXPECTED,),
        synthetic_data_allowed=False,
        requires_authentication=True,
        requires_aeat_authorization=True,
    )


def test_host_suffix_admits_sibling_load_balancer_host() -> None:
    # A GET dispatched to www12 (not the pinned www6) is accepted because the
    # policy widened to the AEAT apex suffix — the host-mapping-drift fix.
    result = assert_remote_operation_allowed(
        _host_suffix_policy(),
        RemoteOperation(
            kind="http",
            method="GET",
            url=AnyUrl(aeat_url("www12", configured_path("sede_paths", "declarations_listing"))),
        ),
    )

    assert result.decision == "allowed"


def test_host_suffix_still_refuses_non_aeat_host() -> None:
    # Widening to the AEAT apex suffix must NOT admit an off-AEAT host: the
    # suffix is AEAT-owned, so a foreign host still fails closed.
    with pytest.raises(RegistryValidationError, match="not in allowed read-only hosts"):
        assert_remote_operation_allowed(
            _host_suffix_policy(),
            RemoteOperation(
                kind="http",
                method="GET",
                url=AnyUrl("https://attacker.example/read/path"),
            ),
        )


def test_host_suffix_field_rejects_non_aeat_suffix() -> None:
    # A declared host suffix MUST itself be an AEAT-owned apex; a foreign
    # suffix would silently widen the allow-list to a non-AEAT surface.
    with pytest.raises(ValidationError, match="allowed host suffix is not an AEAT host"):
        RemoteStateGuardPolicy(
            id="host-suffix-foreign",
            evidence_tier="official_source_guidance",
            classification="authenticated_read_surface",
            allowed_hosts=(_WWW6_HOST,),
            allowed_host_suffixes=("example.com",),
            synthetic_data_allowed=False,
            requires_authentication=True,
            requires_aeat_authorization=True,
        )


def test_gov_idp_host_refused_without_opt_in() -> None:
    """A sanctioned Cl@ve IdP host is refused at build unless the policy opts in."""
    with pytest.raises(ValidationError, match="sanctioned government-IdP"):
        RemoteStateGuardPolicy(
            id="idp-no-optin",
            evidence_tier="official_source_guidance",
            classification="authenticated_read_surface",
            allowed_hosts=(_WWW6_HOST, _CLAVE_HOST),
            synthetic_data_allowed=False,
            requires_authentication=True,
            requires_aeat_authorization=True,
        )


def test_gov_idp_opt_in_refused_on_open_simulator() -> None:
    """The IdP opt-in is only for authenticated-read policies, never a simulator."""
    with pytest.raises(ValidationError, match="authenticated_read_surface"):
        RemoteStateGuardPolicy(
            id="idp-open-sim",
            evidence_tier="executable_parity_evidence",
            classification="open_simulator",
            allowed_hosts=(_SEDE_HOST,),
            allows_gov_idp_hosts=True,
            synthetic_data_allowed=False,
            requires_authentication=False,
            requires_aeat_authorization=False,
        )


def test_gov_idp_opt_in_refused_on_public_read_surface() -> None:
    """A public read policy has no business naming an identity provider."""
    with pytest.raises(ValidationError, match="authenticated_read_surface"):
        RemoteStateGuardPolicy(
            id="idp-public",
            evidence_tier="official_source_guidance",
            classification="public_read_surface",
            allowed_hosts=(_SEDE_HOST,),
            allows_gov_idp_hosts=True,
            synthetic_data_allowed=False,
            requires_authentication=False,
            requires_aeat_authorization=False,
        )


def test_arbitrary_gob_es_host_refused_even_with_opt_in() -> None:
    """The IdP allowance is the single Cl@ve apex only, not any *.gob.es host."""
    with pytest.raises(ValidationError, match="not an AEAT host"):
        RemoteStateGuardPolicy(
            id="idp-arbitrary-gob",
            evidence_tier="official_source_guidance",
            classification="authenticated_read_surface",
            allowed_hosts=(_SEDE_HOST, "foo.gob.es"),
            allows_gov_idp_hosts=True,
            synthetic_data_allowed=False,
            requires_authentication=True,
            requires_aeat_authorization=True,
        )


def test_gov_idp_opt_in_auth_read_admits_the_clave_idp_host() -> None:
    """A valid opt-in authenticated-read policy builds and admits the Cl@ve IdP host."""
    policy = RemoteStateGuardPolicy(
        id="idp-optin-valid",
        evidence_tier="official_source_guidance",
        classification="authenticated_read_surface",
        allowed_hosts=(_WWW6_HOST,),
        allowed_host_suffixes=(_CLAVE_HOST,),
        allows_gov_idp_hosts=True,
        synthetic_data_allowed=False,
        requires_authentication=True,
        requires_aeat_authorization=True,
    )

    result = assert_remote_operation_allowed(
        policy,
        RemoteOperation(
            kind="http",
            method="GET",
            url=AnyUrl(f"https://se-pasarela.{_CLAVE_HOST}/idp/gateway"),
        ),
    )

    assert result.decision == "allowed"


def test_remote_state_guard_allows_local_workbook_for_static_policy() -> None:
    policy = RemoteStateGuardPolicy(
        id="static-docs",
        evidence_tier="layout_authority",
        classification="static_official_only",
        allowed_hosts=(),
        synthetic_data_allowed=False,
        requires_authentication=False,
        requires_aeat_authorization=False,
    )

    result = assert_remote_operation_allowed(policy, RemoteOperation(kind="local_workbook"))

    assert result.decision == "allowed"


def test_remote_state_guard_rejects_static_policy_live_http() -> None:
    policy = RemoteStateGuardPolicy(
        id="static-docs",
        evidence_tier="layout_authority",
        classification="static_official_only",
        allowed_hosts=(),
        synthetic_data_allowed=False,
        requires_authentication=False,
        requires_aeat_authorization=False,
    )

    result = evaluate_remote_operation(
        policy,
        RemoteOperation(
            kind="http",
            method="GET",
            url=AnyUrl(aeat_url("sede", STATIC_DESIGN_REGISTER_PATH_FIXTURE)),
        ),
    )

    assert result.decision == "blocked"
    assert "static_official_only" in result.reason


def test_remote_state_guard_rejects_live_policy_without_executable_parity_tier() -> None:
    with pytest.raises(ValueError, match="requires executable parity evidence"):
        RemoteStateGuardPolicy(
            id="open-without-parity",
            evidence_tier="official_source_guidance",
            classification="open_simulator",
            allowed_hosts=(_SEDE_HOST,),
            synthetic_data_allowed=True,
            requires_authentication=False,
            requires_aeat_authorization=False,
        )


def test_remote_state_guard_rejects_static_policy_as_executable_parity() -> None:
    with pytest.raises(ValueError, match="static official documentation is not executable parity evidence"):
        RemoteStateGuardPolicy(
            id="static-as-parity",
            evidence_tier="executable_parity_evidence",
            classification="static_official_only",
            allowed_hosts=(),
            synthetic_data_allowed=False,
            requires_authentication=False,
            requires_aeat_authorization=False,
        )


def test_remote_state_guard_allows_authenticated_read_surface_get() -> None:
    policy = RemoteStateGuardPolicy(
        id="filed-data-read",
        evidence_tier="official_source_guidance",
        classification="authenticated_read_surface",
        allowed_hosts=(_WWW6_HOST,),
        synthetic_data_allowed=False,
        requires_authentication=True,
        requires_aeat_authorization=True,
    )

    result = assert_remote_operation_allowed(
        policy,
        RemoteOperation(
            kind="http",
            method="GET",
            url=AnyUrl(aeat_url("www6", configured_path("sede_paths", "declarations_listing"))),
        ),
    )

    assert result.decision == "allowed"


def test_remote_state_guard_allows_declared_authenticated_read_post_path_only() -> None:
    wallet_path = configured_path("sede_paths", "iva_compensation_wallet")
    policy = RemoteStateGuardPolicy(
        id="wallet-read",
        evidence_tier="official_source_guidance",
        classification="authenticated_read_surface",
        allowed_hosts=(_WWW6_HOST,),
        allowed_read_paths=(wallet_path,),
        allowed_read_post_paths=(wallet_path,),
        synthetic_data_allowed=False,
        requires_authentication=True,
        requires_aeat_authorization=True,
    )

    result = assert_remote_operation_allowed(
        policy,
        RemoteOperation(
            kind="http",
            method="POST",
            url=AnyUrl(aeat_url("www6", wallet_path)),
        ),
    )

    assert result.decision == "allowed"
    with pytest.raises(RegistryValidationError, match="remote write method"):
        assert_remote_operation_allowed(
            policy,
            RemoteOperation(
                kind="http",
                method="POST",
                url=AnyUrl(aeat_url("www6", UNCLASSIFIED_MUTATING_READ_POST_PATH_CANARY)),
            ),
        )


def test_bounded_read_policy_rejects_a_post_path_outside_its_read_routes() -> None:
    wallet_path = configured_path("sede_paths", "iva_compensation_wallet")

    with pytest.raises(ValidationError, match="subset of the policy's allowed read paths"):
        RemoteStateGuardPolicy(
            id="wallet-read-invalid-post-path",
            evidence_tier="official_source_guidance",
            classification="authenticated_read_surface",
            allowed_hosts=(_WWW6_HOST,),
            allowed_read_paths=(wallet_path,),
            allowed_read_post_paths=(UNCLASSIFIED_MUTATING_READ_POST_PATH_CANARY,),
            synthetic_data_allowed=False,
            requires_authentication=True,
            requires_aeat_authorization=True,
        )


def test_remote_state_guard_rejects_authenticated_read_as_parity() -> None:
    with pytest.raises(ValueError, match="not executable parity evidence"):
        RemoteStateGuardPolicy(
            id="filed-data-read",
            evidence_tier="executable_parity_evidence",
            classification="authenticated_read_surface",
            allowed_hosts=(_WWW6_HOST,),
            synthetic_data_allowed=False,
            requires_authentication=True,
            requires_aeat_authorization=True,
        )


def test_remote_state_guard_allows_public_read_surface_get() -> None:
    policy = RemoteStateGuardPolicy(
        id="public-read",
        evidence_tier="official_source_guidance",
        classification="public_read_surface",
        allowed_hosts=(_SEDE_HOST,),
        synthetic_data_allowed=False,
        requires_authentication=False,
        requires_aeat_authorization=False,
    )

    result = assert_remote_operation_allowed(
        policy,
        RemoteOperation(
            kind="http",
            method="GET",
            url=AnyUrl(aeat_url("sede", configured_path("help_pages", "csv_verification"))),
        ),
    )

    assert result.decision == "allowed"


def test_committed_static_cross_references_reject_remote_state_operations() -> None:
    modelos, catalogues = _committed_registry_tree()

    policies = [
        remote_state_policy_from_cross_reference(cross_reference)
        for modelo in modelos
        for cross_reference in _first_snapshot(modelo, catalogues).live_cross_references.values()
    ]

    assert policies
    for policy in policies:
        assert_remote_operation_allowed(policy, RemoteOperation(kind="local_workbook"))
        assert (
            evaluate_remote_operation(
                policy,
                RemoteOperation(
                    kind="http",
                    method="GET",
                    url=AnyUrl(UNKNOWN_AEAT_STATE_SURFACE_URL_CANARY),
                ),
            ).decision
            == "blocked"
        )
        assert (
            evaluate_remote_operation(
                policy,
                RemoteOperation(kind="browser_action", action="Presentar declaracion"),
            ).decision
            == "blocked"
        )


def test_committed_oracle_planned_operations_conform_to_bound_guard_policies() -> None:
    modelos, catalogues = _committed_registry_tree()
    oracle_catalogue = _production_oracle_catalogue()
    covered_oracle_ids: set[str] = set()

    for modelo in modelos:
        snapshot = _first_snapshot(modelo, catalogues)
        for cross_reference in snapshot.live_cross_references.values():
            oracle_id = cross_reference.oracle_id
            if oracle_id is None:
                continue
            oracle = oracle_catalogue.lookup(oracle_id, environment=OracleEnvironment.PRODUCTION)
            expected = _PLANNED_OPERATION_EXPECTED_FIXTURES.get(oracle.oracle_id)
            if expected is None:
                raise AssertionError(f"oracle {oracle.oracle_id!r} needs a planned-operation fixture")
            policy = remote_state_policy_from_cross_reference(cross_reference)
            operations = oracle.planned_operations(b"", expected=expected)

            assert operations, f"oracle {oracle.oracle_id!r} must declare at least one planned operation"
            assert_remote_operations_allowed(
                policy,
                operations,
                context=(
                    f"modelo {modelo.id} revision {snapshot.revision.id} "
                    f"cross-reference {cross_reference.id} oracle {oracle.oracle_id!r} planned operation"
                ),
            )
            covered_oracle_ids.add(oracle.oracle_id)

    assert {GROI_ORACLE_ID, ORACLE_ID}.issubset(covered_oracle_ids)


def _production_oracle_catalogue() -> LiveParityCatalogue:
    catalogue = LiveParityCatalogue()
    catalogue.register(GroiOracle(), environment=OracleEnvironment.PRODUCTION)
    catalogue.register(AeatNifIvaCheckerOracle(), environment=OracleEnvironment.PRODUCTION)
    catalogue.register(RentaWebOpenOracle(), environment=OracleEnvironment.PRODUCTION)
    return catalogue


def _first_snapshot(modelo: ModeloDefinition, catalogues: RegistryCatalogues):
    for revision in modelo.revisions.values():
        year = (
            revision.period_selector.years[0] if revision.period_selector.years else revision.period_selector.year_from
        )
        if year is None:
            continue
        try:
            return build_snapshot(
                modelo,
                catalogues,
                source_root=bundled_path(),
                filing_year=year,
                period=revision.period_selector.periods[0],
                # The rung this revision declares, not the FILING default. These
                # guards read live cross-references and planned operations, which
                # every rung carries; demanding FILING refuses an
                # applicability-grade modelo -- 036 declares no export layout --
                # with a RegistryValidationError the loop below does not catch,
                # so one such modelo aborted the whole walk.
                grade=revision.effective_authority_grade,
            )
        except RegistrySnapshotError:
            continue
    raise AssertionError(f"modelo {modelo.id} has no selectable committed snapshot")
