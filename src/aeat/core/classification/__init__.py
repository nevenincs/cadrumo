"""Sensitivity classification primitives for persisted state.

Every persisted record (SQL row, file-backed envelope, blob, secret-store
entry, audit-log entry) declares a :class:`SensitivityClass`. Each class maps to
a default :class:`ClassificationPolicy` resolved by :func:`default_policy_for`;
the policy pins the at-rest treatment (plaintext or ciphertext-required),
retention behaviour, and the redaction rule references that the audit sink and
run-trace path honour. Operator-facing output uses
:class:`OutputSensitivityClass` and :func:`default_output_policy_for` so CLI
public output can be classified without pretending it is a persisted record.

The default policy table is the single point of truth. Per-domain
repositories MAY override the default for an individual record (e.g.
when an operator tags a corpus blob as identity-bearing), but the
default is always available via :func:`default_policy_for`. Redaction
rule references stored as names are resolved to live
:class:`RedactionRule` instances by :mod:`aeat.core.redaction`.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from enum import StrEnum
from types import MappingProxyType

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN


class SensitivityClass(StrEnum):
    """Closed catalogue of sensitivity classes for persisted state.

    Attributes:
        SECRET: Long-lived authentication material — OAuth client
            secrets, service-account private keys, certificate
            passphrases, refresh tokens. Treatment: ciphertext at rest;
            never logged; deletion verifiable; finite TTL required.
        SESSION: Short-lived bearer state — Playwright ``storage_state``,
            OAuth access-token caches, AEAT session sidecars. Treatment:
            ciphertext at rest; integrity-bound to the providing factor.
        IDENTITY: Operator and taxpayer identity records — NIF, full
            name, contact email, business profile. Treatment: ciphertext
            at rest where the field is not needed for query; never
            logged at INFO or above.
        FINANCIAL: Bank transaction rows, invoice records, attachment
            blobs, usage ratios, draft and submission payloads,
            amendment records. Treatment: ciphertext at rest by
            default; redaction rules govern log echo; retention aligns
            to the fiscal year plus statute of limitations.
        AUDIT: Submission audit log, run-trace records, divergence
            records, workflow-run records. Treatment: redaction at
            write time (NIF hashed, URL host-only, token fingerprinted)
            on top of ciphertext at rest for the underlying record.
        CACHE: LLM response cache, schema cache, status cache,
            corpora-derived caches. Treatment: defaults to plaintext for
            public reference data; identity-bearing caches escalate to
            IDENTITY.
        CORPUS: Public reference material — manuals, normatives, BOE
            PDFs, registry definitions. Treatment: plaintext at rest is
            acceptable; integrity (SHA-256) MUST still be tracked.
        OPERATIONAL: Settings, build manifests, low-sensitivity
            configuration that legitimately remains in plaintext.
        DIAGNOSTIC: ``scratch/`` outputs, browser traces, screenshots,
            network captures. Treatment: governed retention default
            (e.g. seven days); explicit redaction; opt-in capture.
    """

    SECRET = "secret"
    SESSION = "session"
    IDENTITY = "identity"
    FINANCIAL = "financial"
    AUDIT = "audit"
    CACHE = "cache"
    CORPUS = "corpus"
    OPERATIONAL = "operational"
    DIAGNOSTIC = "diagnostic"


class OutputSensitivityClass(StrEnum):
    """Closed catalogue of output redaction surfaces.

    Attributes:
        CLI_PUBLIC: Operator-facing CLI success output. It is not a
            persisted sensitivity class; the renderer redacts before
            emitting text or JSON.
        LOG: Log-line and log-context output.
        ERROR: Error-envelope and exception-message output.
        DIAGNOSTIC: Diagnostic output that may also be persisted under
            :attr:`SensitivityClass.DIAGNOSTIC`.
    """

    CLI_PUBLIC = "cli_public"
    LOG = "log"
    ERROR = "error"
    DIAGNOSTIC = "diagnostic"


class AtRestTreatment(StrEnum):
    """Closed catalogue of at-rest data-protection treatments.

    Attributes:
        PLAINTEXT: The record is stored as-is, with integrity tracking
            but without confidentiality protection. Acceptable for
            CORPUS and OPERATIONAL classes.
        CIPHERTEXT_REQUIRED: The record MUST be stored as ciphertext.
            Repositories enforce this at write time and refuse
            mismatches with :class:`ClassificationError`.
    """

    PLAINTEXT = "plaintext"
    CIPHERTEXT_REQUIRED = "ciphertext_required"


class RetentionPolicy(BaseModel):
    """Retention envelope for a :class:`SensitivityClass`.

    A policy declares how long a record SHOULD live and when it SHOULD
    be archived. Repositories enforce ``max_age`` at read time when the
    record carries a ``written_at`` field; archival itself is implemented
    by per-domain repositories.

    Attributes:
        max_age: Maximum live-record age. ``None`` means unbounded
            (e.g. for CORPUS material whose lifetime is the project
            lifetime).
        archive_after: Age at which a record should be archived from
            the live store. ``None`` means archival is not policy-
            mandated.
        require_explicit_expiry: When ``True``, a record of this class
            MUST carry an explicit ``expires_at`` field at write time.
            Defaults to ``True`` for SECRET and SESSION.
    """

    model_config = _STRICT_FROZEN

    max_age: timedelta | None = Field(default=None)
    archive_after: timedelta | None = Field(default=None)
    require_explicit_expiry: bool = Field(default=False)


class RedactionStrategy(StrEnum):
    """Closed catalogue of redaction strategies applied at write time.

    Attributes:
        SHA256_PREFIX: Replace the matched value with the first eight
            hex characters of its SHA-256 digest.
        HOST_ONLY: For URL-shaped values, retain only the host
            component; drop path, query, and fragment.
        FINGERPRINT: Replace bearer / OAuth token-shaped values with
            their SHA-256 fingerprint formatted as
            ``token:sha256:<8hex>``.
        ELLIPSIS: Replace the matched value with three ASCII-safe
            full stops (``...``).
    """

    SHA256_PREFIX = "sha256_prefix"
    HOST_ONLY = "host_only"
    FINGERPRINT = "fingerprint"
    ELLIPSIS = "ellipsis"


class RedactionRule(BaseModel):
    """One rule applied at write time by the audit sink and run-trace path.

    The rule shape is stable; :func:`aeat.core.redaction.redact` and
    :func:`aeat.core.redaction.redact_structured` consume tuples of
    rules and apply them in order.

    Attributes:
        name: Stable identifier for log diagnostics. Lowercase
            kebab-case.
        pattern: Regex (Python ``re`` flavour) matched against
            string values to detect the field shape that should be
            redacted. The regex is compiled at use time, not at
            declaration; rules can be loaded from configuration without
            requiring a working regex compiler at import.
        strategy: How the matched value is rewritten.
        applies_to: Sensitivity classes this rule applies to. Empty
            tuple means the rule applies regardless of class.
    """

    model_config = _STRICT_FROZEN

    name: str = Field(min_length=1)
    pattern: str = Field(min_length=1)
    strategy: RedactionStrategy
    applies_to: tuple[SensitivityClass, ...] = Field(default=())


class ClassificationPolicy(BaseModel):
    """Default policy attached to one :class:`SensitivityClass`.

    Per-domain repositories consult this record at write time to
    decide on encryption, retention, and redaction. Per-record
    overrides are supported by the consumer; the default is always
    available via :func:`default_policy_for`.

    Attributes:
        sensitivity: The class this policy governs.
        at_rest: At-rest treatment.
        retention: Retention behaviour.
        redaction_rules: Tuple of redaction-rule names (matched by
            :attr:`RedactionRule.name`) that apply when this class
            participates in audit-sink writes. Resolution to live
            :class:`RedactionRule` instances is performed by
            :func:`aeat.core.redaction.default_rules_for`; the policy
            carries names only so the table can be loaded eagerly
            without depending on the rule registry.
    """

    model_config = _STRICT_FROZEN

    sensitivity: SensitivityClass
    at_rest: AtRestTreatment
    retention: RetentionPolicy
    redaction_rules: tuple[str, ...] = Field(default=())


class OutputClassificationPolicy(BaseModel):
    """Default redaction policy attached to an output surface.

    Output classification is intentionally separate from
    :class:`SensitivityClass`: CLI success output is a rendering-time
    boundary, while diagnostics may also be persisted and therefore keep
    their existing at-rest sensitivity.

    Attributes:
        output: Output surface this policy governs.
        redaction_rules: Tuple of redaction-rule names to apply before
            output leaves the process.
        persisted_as: Persisted sensitivity class when this output is
            also stored. ``None`` means the surface is emit-only.
    """

    model_config = _STRICT_FROZEN

    output: OutputSensitivityClass
    redaction_rules: tuple[str, ...] = Field(default=())
    persisted_as: SensitivityClass | None = Field(default=None)


_FISCAL_YEAR_RETENTION = timedelta(days=365 * 5)
"""Five fiscal years — Spanish autónomo statute-of-limitations envelope."""

_SHORT_SESSION_RETENTION = timedelta(hours=24)
"""Default upper bound on raw bearer-state retention before invalidation."""

_DIAGNOSTIC_RETENTION = timedelta(days=7)
"""Default retention for opt-in diagnostic capture."""

_AUDIT_REDACTION_RULES = (
    "nif-hash",
    "url-host-only",
    "token-fingerprint",
    "bearer-token-fingerprint",
)
"""Default rule set for audit-shaped output strings and payloads."""

_DEFAULT_POLICY_TABLE: Mapping[SensitivityClass, ClassificationPolicy] = MappingProxyType(
    {
        SensitivityClass.SECRET: ClassificationPolicy(
            sensitivity=SensitivityClass.SECRET,
            at_rest=AtRestTreatment.CIPHERTEXT_REQUIRED,
            retention=RetentionPolicy(require_explicit_expiry=True),
            redaction_rules=("token-fingerprint", "bearer-token-fingerprint"),
        ),
        SensitivityClass.SESSION: ClassificationPolicy(
            sensitivity=SensitivityClass.SESSION,
            at_rest=AtRestTreatment.CIPHERTEXT_REQUIRED,
            retention=RetentionPolicy(
                max_age=_SHORT_SESSION_RETENTION,
                require_explicit_expiry=True,
            ),
            redaction_rules=("token-fingerprint", "bearer-token-fingerprint", "url-host-only"),
        ),
        SensitivityClass.IDENTITY: ClassificationPolicy(
            sensitivity=SensitivityClass.IDENTITY,
            at_rest=AtRestTreatment.CIPHERTEXT_REQUIRED,
            retention=RetentionPolicy(max_age=_FISCAL_YEAR_RETENTION),
            redaction_rules=("nif-hash",),
        ),
        SensitivityClass.FINANCIAL: ClassificationPolicy(
            sensitivity=SensitivityClass.FINANCIAL,
            at_rest=AtRestTreatment.CIPHERTEXT_REQUIRED,
            retention=RetentionPolicy(max_age=_FISCAL_YEAR_RETENTION),
            redaction_rules=("nif-hash",),
        ),
        SensitivityClass.AUDIT: ClassificationPolicy(
            sensitivity=SensitivityClass.AUDIT,
            at_rest=AtRestTreatment.CIPHERTEXT_REQUIRED,
            retention=RetentionPolicy(max_age=_FISCAL_YEAR_RETENTION),
            redaction_rules=_AUDIT_REDACTION_RULES,
        ),
        SensitivityClass.CACHE: ClassificationPolicy(
            sensitivity=SensitivityClass.CACHE,
            at_rest=AtRestTreatment.PLAINTEXT,
            retention=RetentionPolicy(),
            redaction_rules=(),
        ),
        SensitivityClass.CORPUS: ClassificationPolicy(
            sensitivity=SensitivityClass.CORPUS,
            at_rest=AtRestTreatment.PLAINTEXT,
            retention=RetentionPolicy(),
            redaction_rules=(),
        ),
        SensitivityClass.OPERATIONAL: ClassificationPolicy(
            sensitivity=SensitivityClass.OPERATIONAL,
            at_rest=AtRestTreatment.PLAINTEXT,
            retention=RetentionPolicy(),
            redaction_rules=(),
        ),
        SensitivityClass.DIAGNOSTIC: ClassificationPolicy(
            sensitivity=SensitivityClass.DIAGNOSTIC,
            at_rest=AtRestTreatment.PLAINTEXT,
            retention=RetentionPolicy(max_age=_DIAGNOSTIC_RETENTION),
            redaction_rules=_AUDIT_REDACTION_RULES,
        ),
    },
)

_DEFAULT_OUTPUT_POLICY_TABLE: Mapping[OutputSensitivityClass, OutputClassificationPolicy] = MappingProxyType(
    {
        OutputSensitivityClass.CLI_PUBLIC: OutputClassificationPolicy(
            output=OutputSensitivityClass.CLI_PUBLIC,
            redaction_rules=_AUDIT_REDACTION_RULES,
            persisted_as=None,
        ),
        OutputSensitivityClass.LOG: OutputClassificationPolicy(
            output=OutputSensitivityClass.LOG,
            redaction_rules=_AUDIT_REDACTION_RULES,
            persisted_as=SensitivityClass.AUDIT,
        ),
        OutputSensitivityClass.ERROR: OutputClassificationPolicy(
            output=OutputSensitivityClass.ERROR,
            redaction_rules=_AUDIT_REDACTION_RULES,
            persisted_as=SensitivityClass.AUDIT,
        ),
        OutputSensitivityClass.DIAGNOSTIC: OutputClassificationPolicy(
            output=OutputSensitivityClass.DIAGNOSTIC,
            redaction_rules=_AUDIT_REDACTION_RULES,
            persisted_as=SensitivityClass.DIAGNOSTIC,
        ),
    },
)


def default_policy_for(sensitivity: SensitivityClass) -> ClassificationPolicy:
    """Return the default :class:`ClassificationPolicy` for ``sensitivity``.

    Args:
        sensitivity: The :class:`SensitivityClass` to look up.

    Returns:
        The default policy. The returned record is frozen and shared;
        callers must not mutate it. Per-record overrides are made by
        constructing a fresh :class:`ClassificationPolicy`.
    """
    return _DEFAULT_POLICY_TABLE[sensitivity]


def default_output_policy_for(output: OutputSensitivityClass) -> OutputClassificationPolicy:
    """Return the default output redaction policy for ``output``.

    Args:
        output: The output surface to look up.

    Returns:
        The default :class:`OutputClassificationPolicy`. The returned
        record is frozen and shared.
    """
    return _DEFAULT_OUTPUT_POLICY_TABLE[output]


def default_policy_table() -> Mapping[SensitivityClass, ClassificationPolicy]:
    """Return the immutable default-policy mapping for every class.

    Returns:
        The shared :class:`MappingProxyType` view mapping each
        :class:`SensitivityClass` to its :class:`ClassificationPolicy`.
        The mapping itself and every value are frozen; callers cannot
        mutate either.
    """
    return _DEFAULT_POLICY_TABLE
