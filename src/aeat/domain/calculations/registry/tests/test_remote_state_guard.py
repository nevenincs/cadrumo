"""Tests for deny-by-default AEAT remote-state guard policy."""

from __future__ import annotations

import pytest
from pydantic import AnyUrl, ValidationError

from .....core.resources import bundled_path
from .....tests.aeat_literal_fixtures import (
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
from .. import ModeloDefinition, RegistryCatalogues, build_snapshot, load_registry_tree
from .._aeat_nif_iva_oracle import ORACLE_ID, AeatNifIvaCheckerOracle
from .._errors import RegistrySnapshotError, RegistryValidationError
from .._groi_oracle import GROI_ORACLE_ID, GroiOracle
from .._live_parity import LiveParityCatalogue, OracleEnvironment
from .._remote_state_guard import (
    _FORBIDDEN_TOKENS,
    AEAT_WRITE_FORBIDDEN_VERB_TOKENS,
    RemoteOperation,
    RemoteStateGuardPolicy,
    assert_remote_operation_allowed,
    assert_remote_operations_allowed,
    evaluate_remote_operation,
    remote_state_policy_from_cross_reference,
)
from .._renta_web_open_oracle import RentaWebOpenOracle
from .._schema import LiveCrossReferenceDecision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SEDE_HOST = aeat_host("sede")
_WWW2_HOST = aeat_host("www2")
_WWW6_HOST = aeat_host("www6")
_AEAT_APEX_HOST = aeat_host("aeat_gob")
_PLANNED_OPERATION_EXPECTED_FIXTURES = {
    GROI_ORACLE_ID: {"A28015865": "valid"},
    ORACLE_ID: {"DE111222333": "valid"},
    "modelo-100-renta-web-open": {"0180": object()},
}


def test_url_method_guard_includes_canonical_write_verb_tokens() -> None:
    """The URL/method denylist MUST cover every canonical write-verb token.

    Both this guard and the renta-web-open click-time safety adapter
    derive from ``AEAT_WRITE_FORBIDDEN_VERB_TOKENS``. If a future
    refactor accidentally drops the canonical core from the URL/method
    set, the safety net silently weakens — this regression test breaks
    the build first.
    """

    forbidden = set(_FORBIDDEN_TOKENS)
    missing = AEAT_WRITE_FORBIDDEN_VERB_TOKENS - forbidden
    assert not missing, f"_FORBIDDEN_TOKENS is missing canonical write verbs: {sorted(missing)}"


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


@pytest.mark.parametrize(
    ("action", "token"),
    (
        ("representation-gate-represented-taxpayer-continue", "explicit read-only allow-list"),
        ("Presentar declaracion", "presentar"),
        ("Firmar declaracion", "firmar"),
        ("Pagar liquidacion", "pagar"),
        ("Confirmar", "confirmar"),
    ),
)
def test_remote_state_guard_blocks_non_read_only_browser_action_matrix(action: str, token: str) -> None:
    policy = _open_policy().model_copy(
        update={"allowed_browser_action_patterns": ("representation-gate-own-name-continue",)},
    )

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


@pytest.mark.parametrize(
    "aeat_host",
    [
        _AEAT_APEX_HOST,
        _SEDE_HOST,
        _WWW2_HOST,
        AEAT_LEGACY_APEX_CANARY,
        AEAT_LEGACY_SEDE_CANARY,
    ],
)
def test_schema_rejects_each_aeat_suffix_form_with_synthetic_data(aeat_host: str) -> None:
    """Every AEAT-suffix form (apex and subdomain, both apex domains) is rejected."""
    with pytest.raises(ValidationError, match="synthetic data is prohibited on AEAT-hosted"):
        LiveCrossReferenceDecision(
            id="test-aeat-suffix-form-reject",
            evidence_tier="executable_parity_evidence",
            surface="open_simulator",
            guard_policy_id="test-aeat-suffix-form-policy",
            allowed_hosts=(aeat_host,),
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


@pytest.mark.parametrize(
    "aeat_host",
    [
        _AEAT_APEX_HOST,
        AEAT_LEGACY_APEX_CANARY,
        AEAT_LEGACY_SEDE_CANARY,
    ],
)
def test_guard_rejects_each_aeat_suffix_form_with_synthetic_data(aeat_host: str) -> None:
    """Guard layer mirrors the schema rejection for every AEAT-suffix form."""
    with pytest.raises(ValidationError, match="synthetic data is prohibited on AEAT-hosted"):
        RemoteStateGuardPolicy(
            id="test-guard-suffix-form-reject",
            evidence_tier="executable_parity_evidence",
            classification="open_simulator",
            allowed_hosts=(aeat_host,),
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
    policy = RemoteStateGuardPolicy(
        id="wallet-read",
        evidence_tier="official_source_guidance",
        classification="authenticated_read_surface",
        allowed_hosts=(_WWW6_HOST,),
        allowed_read_post_paths=(configured_path("sede_paths", "iva_compensation_wallet"),),
        synthetic_data_allowed=False,
        requires_authentication=True,
        requires_aeat_authorization=True,
    )

    result = assert_remote_operation_allowed(
        policy,
        RemoteOperation(
            kind="http",
            method="POST",
            url=AnyUrl(aeat_url("www6", configured_path("sede_paths", "iva_compensation_wallet"))),
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
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))

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
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
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
            )
        except RegistrySnapshotError:
            continue
    raise AssertionError(f"modelo {modelo.id} has no selectable committed snapshot")
