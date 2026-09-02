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

from ....core.models import STRICT_FROZEN_CONFIG
from ....core.remote_authority import (
    REMOTE_READ_SCHEME,
    canonical_remote_hostname,
    first_aeat_host,
    is_aeat_host,
    is_sanctioned_gov_idp_host,
)
from .errors import RegistryValidationError
from .schema_base import EvidenceTier
from .schema_verification import READ_ONLY_HTTP_METHODS, LiveCrossReferenceDecision

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
RemoteEvidenceTier = Literal[
    EvidenceTier.OFFICIAL_SOURCE_GUIDANCE,
    EvidenceTier.EXECUTABLE_PARITY_EVIDENCE,
    EvidenceTier.LAYOUT_AUTHORITY,
]

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
# attempt regardless of presentation. These surfaces are forbidden under
# the production-NIF classification; oracle adapters that target them
# must run only under AEAT pre-production with test NIFs and declare the
# test environment explicitly in their catalogue registration.
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
    allowed_host_suffixes: tuple[str, ...] = Field(default_factory=tuple)
    allowed_read_paths: tuple[str, ...] = Field(default_factory=tuple)
    allowed_read_post_paths: tuple[str, ...] = Field(default_factory=tuple)
    allowed_browser_action_patterns: tuple[str, ...] = Field(default_factory=tuple)
    synthetic_data_allowed: bool
    requires_authentication: bool
    requires_aeat_authorization: bool
    forbidden_actions: tuple[str, ...] = Field(default_factory=tuple)
    allows_gov_idp_hosts: bool = False

    @model_validator(mode="after")
    def _validate_policy(self) -> RemoteStateGuardPolicy:
        # Each predicate group raises in the same order as before; the phases are
        # evidence-tier consistency, allowed-hosts presence, authentication
        # consistency, synthetic-data consistency, then the government-IdP opt-in
        # gate (a sanctioned non-AEAT identity-provider host is admitted only for
        # an explicit opt-in authenticated-read policy).
        self._validate_evidence_tier()
        self._validate_allowed_hosts_presence()
        self._validate_authentication_consistency()
        self._validate_synthetic_data_consistency()
        self._validate_gov_idp_hosts()
        self._validate_read_post_paths_are_declared_reads()
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

    def _validate_gov_idp_hosts(self) -> None:
        # The field validators admit sanctioned government-IdP hosts syntactically
        # but DEFER the policy-level decision here: an IdP host/suffix is legal only
        # on an explicit opt-in (``allows_gov_idp_hosts``) authenticated-read policy.
        # Default false + no IdP entry = every existing policy is unchanged; a
        # non-AEAT, non-IdP host is already refused at the field-validator stage.
        idp_entries = tuple(
            entry
            for entry in (*self.allowed_hosts, *self.allowed_host_suffixes)
            if is_sanctioned_gov_idp_host(entry) and not is_aeat_host(entry)
        )
        if self.allows_gov_idp_hosts:
            if self.classification != "authenticated_read_surface":
                raise RegistryValidationError(
                    "government-IdP host opt-in requires an authenticated_read_surface policy, "
                    f"got classification {self.classification!r}",
                )
            if not self.requires_authentication:
                raise RegistryValidationError(
                    "government-IdP host opt-in requires requires_authentication = true",
                )
        elif idp_entries:
            raise RegistryValidationError(
                f"policy {self.id!r} lists sanctioned government-IdP host(s) {idp_entries!r} "
                "without the allows_gov_idp_hosts opt-in",
            )

    @field_validator("allowed_hosts")
    @classmethod
    def _validate_hosts(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for host in value:
            parsed = urlparse(f"https://{host}")
            if not parsed.hostname or parsed.hostname != host.lower():
                raise RegistryValidationError(f"invalid allowed host {host!r}")
            if is_aeat_host(host):
                continue
            # A sanctioned government-IdP host is syntactically admitted here and
            # gated on the opt-in flag in the model phase (_validate_gov_idp_hosts);
            # every other non-AEAT host is refused exactly as before.
            if is_sanctioned_gov_idp_host(host):
                continue
            raise RegistryValidationError(f"allowed host is not an AEAT host: {host!r}")
        return value

    @field_validator("allowed_host_suffixes")
    @classmethod
    def _validate_host_suffixes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        # A host suffix widens the exact-host allow-list to any subdomain
        # under an AEAT-owned apex, so AEAT's ``www{n}`` load-balancer
        # dispatch (www1/www2/www6/www12/sede) is not refused. The suffix
        # itself MUST still be an AEAT-owned host — or a sanctioned
        # government-IdP apex, deferred to the model-phase opt-in gate — so the
        # widening cannot admit an arbitrary non-AEAT surface.
        for suffix in value:
            parsed = urlparse(f"https://{suffix}")
            if not parsed.hostname or parsed.hostname != suffix.lower():
                raise RegistryValidationError(f"invalid allowed host suffix {suffix!r}")
            if is_aeat_host(suffix):
                continue
            if is_sanctioned_gov_idp_host(suffix):
                continue
            raise RegistryValidationError(f"allowed host suffix is not an AEAT host: {suffix!r}")
        return value

    @field_validator("allowed_read_paths", "allowed_read_post_paths")
    @classmethod
    def _validate_read_paths(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for path in value:
            if not path.startswith("/"):
                raise RegistryValidationError(f"allowed read path must be absolute: {path!r}")
        return value

    def _validate_read_post_paths_are_declared_reads(self) -> None:
        """Require a bounded read surface to name every sanctioned read POST."""
        if self.allowed_read_paths and not set(self.allowed_read_post_paths).issubset(self.allowed_read_paths):
            raise RegistryValidationError(
                "allowed read POST paths must be a subset of the policy's allowed read paths",
            )

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

    A policy built here admits exactly the hosts its own surface declares and
    no sibling subdomains; see the note at the construction site for why the
    host-suffix widening is deliberately not applied to every policy.

    Returns:
        The :class:`RemoteStateGuardPolicy` derived from the cross-reference decision.
    """
    if decision.evidence_tier is EvidenceTier.LEGAL_AUTHORITY:
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
    # ``allowed_host_suffixes`` is deliberately NOT set here. Its absence is a
    # decision, not an omission -- an omission invites the next reader to
    # complete it, and the completion is one line whose diff reads like a bug
    # fix. Setting it would widen EVERY policy this builder produces to any
    # subdomain under an AEAT apex, authenticated read surfaces included. A
    # policy built here therefore admits exactly the hosts its own surface
    # declares, and no siblings.
    #
    # This is not a prohibition: a surface whose reads genuinely span AEAT's
    # numbered pool is entitled to that pool. Declare it on that surface's own
    # ``allowed_hosts``, so the widening stays scoped to the surface measured
    # to need it and every other policy stays as narrow as it was written.
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


def _http_method_is_allowed(policy: RemoteStateGuardPolicy, method: str, path: str | None) -> bool:
    return method in READ_ONLY_HTTP_METHODS or (
        method == "POST"
        and policy.classification == "authenticated_read_surface"
        and path in policy.allowed_read_post_paths
    )


def _http_policy_block_reason(policy: RemoteStateGuardPolicy, url: AnyUrl, action: str | None, host: str) -> str | None:
    if not _host_within_policy(policy, host):
        return f"AEAT host {host!r} is not in allowed read-only hosts"
    if policy.allowed_read_paths and url.path not in policy.allowed_read_paths:
        return f"AEAT path {url.path!r} is not in allowed read-only paths"
    text = f"{url} {action or ''}".lower()
    forbidden_action = _first_declared_forbidden_action(policy, text)
    if forbidden_action is not None:
        return f"AEAT forbidden action {forbidden_action!r} is blocked"
    token = _first_forbidden_token(text)
    if token is not None:
        return f"AEAT remote state token {token!r} is forbidden"
    return None


def _evaluate_http(policy: RemoteStateGuardPolicy, operation: RemoteOperation) -> RemoteStateGuardResult:
    method = (operation.method or "").upper()
    url = operation.url
    if url is None:
        raise RegistryValidationError("AEAT remote HTTP operation carries no URL to evaluate")
    path = url.path
    if not _http_method_is_allowed(policy, method, path):
        return _blocked(policy, f"AEAT remote write method {method!r} is forbidden")
    # Scheme, user-info and port are decided by the one canonical authority
    # helper, not by ``operation.url.host`` — that attribute reports a host
    # with user-info and any port already stripped, so a credentialed or
    # off-port authority reads as a plain AEAT host and slips the allow-list.
    #
    # The URL is re-canonicalised from its serialised form because pydantic
    # normalises the authority at model construction.
    #
    # ACCEPTED EQUIVALENCE — an explicit DEFAULT port. ``AnyUrl`` erases
    # ``:443`` from an https URL before the guard runs, so ``https://host:443/``
    # is admitted as ``https://host/``. This is deliberate, not an unclosed
    # hole: the two denote the same origin, so admitting them alike is what a
    # URL type should do. The alternative — widening ``RemoteOperation.url`` to
    # ``str`` to preserve the raw text — would trade a typed boundary for a
    # distinction that carries no security difference.
    #
    # Everything that DOES carry a difference is refused: every non-default
    # port survives serialisation and is rejected, as is every user-info
    # authority and every non-``https`` scheme. Note the string-level callers
    # of the same helper (the Cl@ve landing predicates) never see pydantic
    # normalisation and so refuse an explicit ``:443`` outright; the two
    # populations agree on every authority that differs in origin.
    url = operation.url
    raw_url = str(url)
    host = canonical_remote_hostname(raw_url)
    if url is None or host is None:
        return _blocked(
            policy,
            f"AEAT remote authority {raw_url!r} is not a bare {REMOTE_READ_SCHEME} host "
            "(scheme, user-info or port refused)",
        )
    if reason := _http_policy_block_reason(policy, url, operation.action, host):
        return _blocked(policy, reason)
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
    # An EMPTY allow-list refuses every action; it does not wave them through.
    #
    # This guard previously read ``if policy.allowed_browser_action_patterns
    # and not _matches(...)``, so a policy declaring no actions imposed no
    # restriction at all. Dropping a pattern set therefore did not NARROW the
    # allow-list, it REMOVED the gate -- fail-open in the configuration most
    # likely to arise by accident, since the field defaults to an empty tuple
    # and a registry key that is simply absent lands there silently.
    #
    # Refusing on absence is what the surrounding code already assumed: the
    # expedientes walker documents its deliberately-empty tuple as meaning
    # "any future browser action added here fails the guard until it is
    # declared", a guarantee the old branch did not actually provide.
    if not policy.allowed_browser_action_patterns:
        return _blocked(policy, f"AEAT policy {policy.id!r} declares no allowed browser actions")
    if not _matches_allowed_browser_action(policy, text):
        return _blocked(policy, f"AEAT browser action {text!r} is not in the explicit read-only allow-list")
    return RemoteStateGuardResult(decision="allowed", reason="read-only browser action allowed", policy_id=policy.id)


def _host_within_policy(policy: RemoteStateGuardPolicy, host: str) -> bool:
    """Return whether ``host`` is admitted by the policy's exact hosts or host suffixes.

    Exact ``allowed_hosts`` membership is checked first; a policy may
    additionally widen the allow-list with ``allowed_host_suffixes`` so
    AEAT's ``www{n}`` load-balancer dispatch (a request pinned to one host
    but served from a sibling subdomain under the same AEAT apex) is not
    refused. The suffix set is validated to AEAT-owned apexes at build
    time, so widening never admits a non-AEAT host.
    """
    normalized = host.lower()
    if normalized in policy.allowed_hosts:
        return True
    return any(normalized == suffix or normalized.endswith(f".{suffix}") for suffix in policy.allowed_host_suffixes)


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
