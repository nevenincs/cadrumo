"""Fail-closed guard for live AEAT cross-reference surfaces.

This module uses :class:`LiveCrossReferenceDecision` and :class:`RemoteOperation`
to enforce fail-closed access control.
"""

from __future__ import annotations

from collections.abc import Iterable
from fnmatch import fnmatchcase
from typing import Literal
from urllib.parse import urlparse

from pydantic import AnyUrl, BaseModel, Field, field_validator, model_validator

from ....core import STRICT_FROZEN_CONFIG
from ._aeat_hosts import first_aeat_host, is_aeat_host
from ._errors import RegistryValidationError
from ._schema import LiveCrossReferenceDecision

CrossReferenceClassification = Literal[
    "open_simulator",
    "integration_test_service",
    "public_read_surface",
    "authenticated_read_surface",
    "static_official_only",
    "forbidden_stateful_surface",
]
RemoteOperationKind = Literal["http", "browser_action", "local_workbook"]
RemoteGuardDecision = Literal["allowed", "blocked"]
RemoteEvidenceTier = Literal["official_source_guidance", "executable_parity_evidence", "layout_authority"]

_READ_ONLY_HTTP_METHODS = {"GET", "HEAD", "OPTIONS"}
# Canonical AEAT write-class action labels that EVERY guard policy
# attached to a live cross-reference / oracle MUST include. This is the
# read-only mandate enforced as code: AEAT writes are PERMANENTLY
# FORBIDDEN under any classification, and any operation whose action
# text mentions one of these is rejected by the guard before any
# network or browser call leaves the process. Callers import this
# constant rather than redeclaring it so the canonical set stays
# centralised.
AEAT_WRITE_FORBIDDEN_ACTIONS: tuple[str, ...] = (
    "server-side-save",
    "signing",
    "presentation",
    "payment",
    "amendment",
    "cancellation",
    "document-submission",
    "declaration-submission",
)

# Canonical AEAT write-action verb tokens — the universal, surface-agnostic
# denylist of action labels (button text, URL action segments, English/Spanish
# write verbs) that signal a state-modifying call. EVERY guard surface
# (HTTP/method/url scanning here, Playwright click-time scanning in the
# renta-web-open safety adapter, future stateful surfaces) MUST include
# these tokens. The set is exported as ``AEAT_WRITE_FORBIDDEN_VERB_TOKENS``
# so all consumers derive from a single source of truth.
#
# Adapters that match additional surface-specific tokens (accented
# variants for diacritic-preserving regex, multi-word button labels,
# Validar pre-presentation verification surfaces) extend this set
# rather than redeclaring the core.
#
# AEAT verification surfaces that stage uploaded files in server-side
# state under the authenticated NIF even before legal presentation.
# TGVI online (Transmisión y Gestión de Volúmenes de Información) creates
# a FINALIZED state visible in declaration-history surfaces, configurable
# for substitutive replacement of prior filings, and logged as an upload
# attempt regardless of presentation. Per the live-parity-oracle ADR
# decision D13a, these surfaces are forbidden under the production-NIF
# classification; oracle adapters that target them must run only under
# AEAT pre-production with test NIFs and declare the test environment
# explicitly in their catalogue registration.
AEAT_WRITE_FORBIDDEN_VERB_TOKENS: frozenset[str] = frozenset(
    {
        # Spanish action verbs (write-class)
        "presentar",
        "presentacion",
        "enviar",
        "guardar",
        "firmar",
        "pagar",
        "domiciliar",
        "modificar",
        "anular",
        "cancelar",
        "subsanar",
        "transmision",
        "transmitir",
        "confirmar",
        "confirmacion",
        # AEAT-specific write surfaces
        "tgvi",
        # English equivalents matched against URL action labels and English text
        "submit",
        "sign",
        "save",
        "payment",
    },
)

# Tokens unique to URL/HTTP-method scanning (not exposed for click-time
# adapters because they are HTTP verbs or pre-state surface labels that
# do not appear as button text).
_URL_AND_METHOD_FORBIDDEN_TOKENS: tuple[str, ...] = (
    "post",
    "send",
    "commit",
    "debit",
    "amend",
    "cancel",
    "delete",
    "borrador",
    "predeclaracion",
)

_FORBIDDEN_TOKENS: tuple[str, ...] = (
    *sorted(AEAT_WRITE_FORBIDDEN_VERB_TOKENS),
    *_URL_AND_METHOD_FORBIDDEN_TOKENS,
)


class RemoteStateGuardModel(BaseModel):
    """Strict frozen base for remote-state guard records."""

    model_config = STRICT_FROZEN_CONFIG


class RemoteStateGuardPolicy(RemoteStateGuardModel):
    """Policy attached to a live/static AEAT cross-reference decision."""

    id: str
    evidence_tier: RemoteEvidenceTier
    classification: CrossReferenceClassification
    allowed_hosts: tuple[str, ...] = Field(default_factory=tuple)
    allowed_read_post_paths: tuple[str, ...] = Field(default_factory=tuple)
    allowed_browser_action_patterns: tuple[str, ...] = Field(default_factory=tuple)
    synthetic_data_allowed: bool
    requires_authentication: bool
    requires_aeat_authorization: bool
    forbidden_actions: tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _validate_policy(self) -> RemoteStateGuardPolicy:
        # Each predicate group raises in the same order as before; the phases are
        # evidence-tier consistency, allowed-hosts presence, authentication
        # consistency, then synthetic-data consistency.
        self._validate_evidence_tier()
        self._validate_allowed_hosts_presence()
        self._validate_authentication_consistency()
        self._validate_synthetic_data_consistency()
        return self

    def _validate_evidence_tier(self) -> None:
        if self.classification in {"open_simulator", "integration_test_service"} and (
            self.evidence_tier != "executable_parity_evidence"
        ):
            raise RegistryValidationError("live cross-reference policy requires executable parity evidence")
        if self.classification == "public_read_surface" and self.evidence_tier == "executable_parity_evidence":
            raise RegistryValidationError("public read surfaces are observations, not executable parity evidence")
        if self.classification == "authenticated_read_surface" and self.evidence_tier == "executable_parity_evidence":
            raise RegistryValidationError(
                "authenticated filed-data reads are observations, not executable parity evidence",
            )
        if self.classification == "static_official_only" and self.evidence_tier == "executable_parity_evidence":
            raise RegistryValidationError("static official documentation is not executable parity evidence")

    def _validate_allowed_hosts_presence(self) -> None:
        if (
            self.classification
            in {"open_simulator", "integration_test_service", "public_read_surface", "authenticated_read_surface"}
            and not self.allowed_hosts
        ):
            raise RegistryValidationError("AEAT remote policy must declare allowed hosts")

    def _validate_authentication_consistency(self) -> None:
        if self.classification == "open_simulator" and self.requires_authentication:
            raise RegistryValidationError("open simulator policy must not require authentication")
        if self.classification == "public_read_surface" and self.requires_authentication:
            raise RegistryValidationError("public read policy must not require authentication")
        if self.classification == "authenticated_read_surface" and not self.requires_authentication:
            raise RegistryValidationError("authenticated filed-data read policy must require authentication")

    def _validate_synthetic_data_consistency(self) -> None:
        if self.classification == "public_read_surface" and self.synthetic_data_allowed:
            raise RegistryValidationError("public reads must not use synthetic remote data")
        if self.classification == "authenticated_read_surface" and self.synthetic_data_allowed:
            raise RegistryValidationError("authenticated filed-data reads must not use synthetic remote data")
        if self.classification == "static_official_only" and self.synthetic_data_allowed:
            raise RegistryValidationError("static official documentation cannot accept synthetic remote data")
        if self.classification == "forbidden_stateful_surface" and self.synthetic_data_allowed:
            raise RegistryValidationError("forbidden stateful surface cannot accept synthetic remote data")
        if self.synthetic_data_allowed:
            aeat_host = first_aeat_host(self.allowed_hosts)
            if aeat_host is not None:
                raise RegistryValidationError(
                    f"AEAT-hosted policy {self.id!r} declares synthetic_data_allowed = true "
                    f"on AEAT host {aeat_host!r}; synthetic data is prohibited on AEAT-hosted surfaces",
                )

    @field_validator("allowed_hosts")
    @classmethod
    def _validate_hosts(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for host in value:
            parsed = urlparse(f"https://{host}")
            if not parsed.hostname or parsed.hostname != host.lower():
                raise RegistryValidationError(f"invalid allowed host {host!r}")
            if not _is_aeat_host(host):
                raise RegistryValidationError(f"allowed host is not an AEAT host: {host!r}")
        return value

    @field_validator("allowed_read_post_paths")
    @classmethod
    def _validate_read_post_paths(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for path in value:
            if not path.startswith("/"):
                raise RegistryValidationError(f"allowed read POST path must be absolute: {path!r}")
        return value

    @field_validator("allowed_browser_action_patterns")
    @classmethod
    def _validate_allowed_browser_action_patterns(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for pattern in value:
            if not pattern.strip():
                raise RegistryValidationError("allowed browser action pattern must not be blank")
        return value


class RemoteOperation(RemoteStateGuardModel):
    """One candidate browser/network/local operation before execution."""

    kind: RemoteOperationKind
    method: str | None = None
    url: AnyUrl | None = None
    action: str | None = None

    @model_validator(mode="after")
    def _validate_operation(self) -> RemoteOperation:
        if self.kind == "http" and (self.method is None or self.url is None):
            raise RegistryValidationError("http operation requires method and url")
        if self.kind == "browser_action" and self.action is None:
            raise RegistryValidationError("browser action requires action text")
        if self.kind == "local_workbook" and (self.method is not None or self.url is not None):
            raise RegistryValidationError("local workbook operation must not declare remote method or url")
        return self


class RemoteStateGuardResult(RemoteStateGuardModel):
    """Decision returned by the remote-state guard."""

    decision: RemoteGuardDecision
    reason: str
    policy_id: str


def remote_state_policy_from_cross_reference(decision: LiveCrossReferenceDecision) -> RemoteStateGuardPolicy:
    """Build the executable remote-state guard policy for a registry cross-reference.

    Returns:
        The :class:`RemoteStateGuardPolicy` derived from the cross-reference decision.
    """
    if decision.evidence_tier == "legal_authority":
        raise RegistryValidationError("remote-state policy cannot be built from legal-authority evidence")
    evidence_tier: RemoteEvidenceTier = decision.evidence_tier
    classification: CrossReferenceClassification
    if decision.surface == "static_official_documentation":
        classification = "static_official_only"
    elif decision.surface == "open_simulator":
        classification = "open_simulator"
    elif decision.surface == "public_read_surface":
        classification = "public_read_surface"
    elif decision.surface == "authenticated_read_surface":
        classification = "authenticated_read_surface"
    else:
        classification = "integration_test_service"
    return RemoteStateGuardPolicy(
        id=decision.guard_policy_id,
        evidence_tier=evidence_tier,
        classification=classification,
        allowed_hosts=decision.allowed_hosts,
        allowed_browser_action_patterns=_browser_action_patterns_for_decision(decision),
        synthetic_data_allowed=decision.synthetic_data_allowed,
        requires_authentication=decision.requires_authentication,
        requires_aeat_authorization=decision.requires_aeat_authorization,
        forbidden_actions=decision.forbidden_actions,
    )


def assert_remote_operation_allowed(
    policy: RemoteStateGuardPolicy,
    operation: RemoteOperation,
) -> RemoteStateGuardResult:
    """Return an allowed decision or raise for forbidden AEAT remote state.

    Returns:
        A :class:`RemoteStateGuardResult` with an allowed decision.
    """
    result = evaluate_remote_operation(policy, operation)
    if result.decision == "blocked":
        raise RegistryValidationError(result.reason)
    return result


def assert_remote_operations_allowed(
    policy: RemoteStateGuardPolicy,
    operations: Iterable[RemoteOperation],
    *,
    context: str = "remote operation",
) -> tuple[RemoteOperation, ...]:
    """Pre-flight an operation plan through the remote-state guard and return a tuple of :class:`RemoteOperation`.

    Returns:
        The validated operations as an immutable tuple.
    """
    operation_tuple = tuple(operations)
    for index, operation in enumerate(operation_tuple):
        try:
            assert_remote_operation_allowed(policy, operation)
        except RegistryValidationError as exc:
            raise RegistryValidationError(f"{context} {index} blocked by policy {policy.id!r}: {exc}") from exc
    return operation_tuple


def evaluate_remote_operation(policy: RemoteStateGuardPolicy, operation: RemoteOperation) -> RemoteStateGuardResult:
    """Evaluate one operation against the guard and return a :class:`RemoteStateGuardResult`."""
    if operation.kind == "local_workbook":
        return RemoteStateGuardResult(
            decision="allowed",
            reason="local workbook parity does not touch AEAT remote state",
            policy_id=policy.id,
        )
    if policy.classification in {"static_official_only", "forbidden_stateful_surface"}:
        return _blocked(policy, f"{policy.classification} does not allow live AEAT operations")
    if operation.kind == "http":
        return _evaluate_http(policy, operation)
    return _evaluate_browser_action(policy, operation)


def _evaluate_http(policy: RemoteStateGuardPolicy, operation: RemoteOperation) -> RemoteStateGuardResult:
    method = (operation.method or "").upper()
    assert operation.url is not None
    path = operation.url.path
    read_post_allowed = (
        method == "POST"
        and policy.classification == "authenticated_read_surface"
        and path in policy.allowed_read_post_paths
    )
    if method not in _READ_ONLY_HTTP_METHODS and not read_post_allowed:
        return _blocked(policy, f"AEAT remote write method {method!r} is forbidden")
    host = operation.url.host
    if host is None or host.lower() not in policy.allowed_hosts:
        return _blocked(policy, f"AEAT host {host!r} is not in allowed read-only hosts")
    text = f"{operation.url} {operation.action or ''}".lower()
    action = _first_declared_forbidden_action(policy, text)
    if action is not None:
        return _blocked(policy, f"AEAT forbidden action {action!r} is blocked")
    token = _first_forbidden_token(text)
    if token is not None:
        return _blocked(policy, f"AEAT remote state token {token!r} is forbidden")
    return RemoteStateGuardResult(decision="allowed", reason="read-only AEAT operation allowed", policy_id=policy.id)


def _evaluate_browser_action(policy: RemoteStateGuardPolicy, operation: RemoteOperation) -> RemoteStateGuardResult:
    text = operation.action or ""
    normalized = text.lower()
    action = _first_declared_forbidden_action(policy, normalized)
    if action is not None:
        return _blocked(policy, f"AEAT forbidden action {action!r} is blocked")
    token = _first_forbidden_token(normalized)
    if token is not None:
        return _blocked(policy, f"AEAT browser action token {token!r} is forbidden")
    if policy.allowed_browser_action_patterns and not _matches_allowed_browser_action(policy, text):
        return _blocked(policy, f"AEAT browser action {text!r} is not in the explicit read-only allow-list")
    return RemoteStateGuardResult(decision="allowed", reason="read-only browser action allowed", policy_id=policy.id)


def _blocked(policy: RemoteStateGuardPolicy, reason: str) -> RemoteStateGuardResult:
    return RemoteStateGuardResult(decision="blocked", reason=reason, policy_id=policy.id)


def _first_forbidden_token(value: str) -> str | None:
    for token in _FORBIDDEN_TOKENS:
        if token in value:
            return token
    return None


def _first_declared_forbidden_action(policy: RemoteStateGuardPolicy, value: str) -> str | None:
    for action in policy.forbidden_actions:
        if action.lower() in value:
            return action
    return None


def _matches_allowed_browser_action(policy: RemoteStateGuardPolicy, value: str) -> bool:
    normalized = value.casefold()
    return any(fnmatchcase(normalized, pattern.casefold()) for pattern in policy.allowed_browser_action_patterns)


def _browser_action_patterns_for_decision(decision: LiveCrossReferenceDecision) -> tuple[str, ...]:
    if decision.oracle_id in {"aeat-groi-spanish-roi-checker", "aeat-nif-iva-checker"}:
        from ....core.config import Settings

        return Settings.external_constants().aeat.live_safety.consult_oracle_browser_action_patterns
    if decision.oracle_id == "modelo-100-renta-web-open":
        from ....core.config import Settings

        return Settings.external_constants().aeat.live_safety.renta_web_open_browser_action_patterns
    return ()


def _is_aeat_host(host: str) -> bool:
    return is_aeat_host(host)
