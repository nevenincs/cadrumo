"""Typed live verification surfaces, authentication constraints and profile predicates."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Final

from pydantic import BeforeValidator, Field, field_validator, model_validator

from ....core.errors.hierarchy import pydantic_validation_boundary
from ....core.remote_authority import first_aeat_host
from .condition_mode import ConditionMode, ConditionModeField
from .errors import RegistryValidationError
from .ids import CrossReferenceId, OracleId
from .schema_base import EvidenceTierField, LegalRefs, RegistryModel, SourceRefs, coerce_enum_member

ProfileFactValue = bool | int | str


READ_ONLY_HTTP_METHODS: Final[frozenset[str]] = frozenset({"GET", "HEAD", "OPTIONS"})
"""The HTTP methods that cannot change state on an AEAT surface.

Not an enum: HTTP methods are an external vocabulary this codebase does not close, and
declaring one here would assert a completeness the registry has no authority over. What
is closed is THIS set -- the methods a read surface may use -- and it was written out
here and again as a private set in `remote_state_guard`, where the read-only mandate is
enforced. Two copies of a security allowlist is one copy too many.
"""

SIMULATOR_HTTP_METHODS: Final[frozenset[str]] = READ_ONLY_HTTP_METHODS | {"POST"}
"""Read-only methods plus POST, which a simulator may accept.

Derived from the read-only set rather than relisted, so a method admitted to the
read-only allowlist cannot be accidentally withheld from the simulator one -- and, more
importantly, so a method removed from read-only cannot silently survive here.
"""


class ProfilePredicateOp(StrEnum):
    """The comparison a profile predicate performs."""

    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    INCLUDES = "includes"
    """The observed value is a token set that contains the predicate token.

    An absent set contains nothing, so it never matches.
    """


ProfilePredicateOpField = Annotated[ProfilePredicateOp, BeforeValidator(coerce_enum_member(ProfilePredicateOp))]
"""Registry token hydrated into a ProfilePredicateOp member."""


class LiveVerificationSurface(StrEnum):
    """The kind of AEAT surface a live cross-reference verifies against.

    Declared because six tokens were compared as bare strings across this module and
    its two neighbours, and two of the groupings below were written out three times
    each. The `surface` annotations stay `str` deliberately: a member compares equal to
    its token, so nothing about validation changes here, and retyping a validated field
    is a separate decision from naming the vocabulary.
    """

    OPEN_SIMULATOR = "open_simulator"
    INTEGRATION_TEST_SERVICE = "integration_test_service"
    AUTHENTICATED_SIMULATOR = "authenticated_simulator"
    PUBLIC_READ_SURFACE = "public_read_surface"
    AUTHENTICATED_READ_SURFACE = "authenticated_read_surface"
    STATIC_OFFICIAL_DOCUMENTATION = "static_official_documentation"


READ_SURFACES: Final[frozenset[LiveVerificationSurface]] = frozenset(
    {
        LiveVerificationSurface.PUBLIC_READ_SURFACE,
        LiveVerificationSurface.AUTHENTICATED_READ_SURFACE,
    },
)
"""Surfaces that read live AEAT data rather than a simulator or a static document.

Written out at three sites in this module before this existed. These are the surfaces
that must refuse synthetic data and are restricted to safe HTTP methods, so a surface
added to this set inherits both rules at once instead of one of them.
"""

SIMULATOR_SURFACES: Final[frozenset[LiveVerificationSurface]] = frozenset(
    {
        LiveVerificationSurface.OPEN_SIMULATOR,
        LiveVerificationSurface.INTEGRATION_TEST_SERVICE,
        LiveVerificationSurface.AUTHENTICATED_SIMULATOR,
    },
)
"""Surfaces that are not AEAT production infrastructure."""

LiveVerificationSurfaceField = Annotated[
    LiveVerificationSurface,
    BeforeValidator(coerce_enum_member(LiveVerificationSurface)),
]
"""The surface as a REGISTRY SCHEMA field.

`LiveCrossReferenceDecision` validates strictly and is built from registry TOML, so the
declared token needs the coercion hop to arrive as a member. The bare enum stays the
form this module's own comparisons use, and the two subsets stay derived from it.
"""


def _validate_open_or_public_authentication(
    surface: str,
    requires_authentication: bool,
    cross_reference_id: CrossReferenceId,
) -> None:
    if surface == LiveVerificationSurface.OPEN_SIMULATOR and requires_authentication:
        raise RegistryValidationError(
            f"cross-reference {cross_reference_id!r} open simulator must not require authentication",
        )
    if surface == LiveVerificationSurface.PUBLIC_READ_SURFACE and requires_authentication:
        raise RegistryValidationError(
            f"cross-reference {cross_reference_id!r} public read surface must not require authentication",
        )


def _validate_authenticated_read_authentication(
    surface: str,
    requires_authentication: bool,
    requires_aeat_authorization: bool,
    cross_reference_id: CrossReferenceId,
) -> None:
    if surface != "authenticated_read_surface":
        return
    if not requires_authentication:
        raise RegistryValidationError(
            f"cross-reference {cross_reference_id!r} authenticated read surface must require authentication",
        )
    if not requires_aeat_authorization:
        raise RegistryValidationError(
            f"cross-reference {cross_reference_id!r} authenticated read surface must require authorization",
        )


def _validate_authenticated_simulator_authentication(
    surface: str,
    requires_authentication: bool,
    cross_reference_id: CrossReferenceId,
) -> None:
    if surface == LiveVerificationSurface.AUTHENTICATED_SIMULATOR and not requires_authentication:
        raise RegistryValidationError(
            f"cross-reference {cross_reference_id!r} authenticated simulator must require authentication",
        )


class ProfilePredicateDefinition(RegistryModel):
    """Declare one profile condition that controls verification applicability."""

    field: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z_][A-Za-z0-9_.-]*$")
    op: ProfilePredicateOpField
    value: ProfileFactValue
    explanation: str = Field(min_length=1)
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _includes_names_one_token(self) -> ProfilePredicateDefinition:
        if self.op is ProfilePredicateOp.INCLUDES and (not isinstance(self.value, str) or not self.value.strip()):
            raise RegistryValidationError(f"profile predicate on {self.field!r} uses 'includes' with a non-token value")
        return self


class LiveCrossReferenceDecision(RegistryModel):
    """Declare a resolved live cross-reference and its supporting evidence."""

    id: CrossReferenceId
    evidence_tier: EvidenceTierField
    surface: LiveVerificationSurfaceField
    guard_policy_id: str
    allowed_hosts: tuple[str, ...] = ()
    allowed_methods: tuple[str, ...] = ()
    forbidden_actions: tuple[str, ...] = Field(min_length=1)
    synthetic_data_allowed: bool
    requires_authentication: bool
    requires_aeat_authorization: bool
    legal_refs: LegalRefs
    source_refs: SourceRefs
    # Optional: id of an oracle adapter registered in LiveParityCatalogue.
    # When set, the calculation engine looks up the bound adapter to drive
    # synthetic-payload verification under the cross-reference's policy.
    # Resolution against the catalogue happens at calculation time, not at
    # registry-load time, so the registry remains loadable when adapters
    # are imported lazily.
    oracle_id: OracleId | None = None
    # Optional applicability gate: when non-empty the cross-reference is
    # only applicable to a taxpayer profile whose values satisfy these
    # predicates under the chosen mode. An empty tuple (the default) means
    # the cross-reference is unconditionally applicable. Used to gate
    # optional surfaces (GROI / IXVI for ROI-enrolled subjects, OSS
    # bindings for OSS-enrolled subjects, etc.).
    applicability_condition_mode: ConditionModeField = ConditionMode.ALL
    applicability_predicates: tuple[ProfilePredicateDefinition, ...] = ()

    @field_validator("oracle_id")
    @classmethod
    @pydantic_validation_boundary
    def _oracle_id_shape(cls, value: str | None) -> str | None:
        if value is None:
            return None
        # kebab-case ASCII identifier: lowercase alpha start, alphanumerics
        # plus hyphens, no trailing hyphen.
        if not value[0].isalpha() or not value[0].islower():
            raise RegistryValidationError("oracle_id must start with a lowercase ASCII letter")
        if value.endswith("-"):
            raise RegistryValidationError("oracle_id must not end with a hyphen")
        for char in value:
            if not (char.islower() and char.isascii()) and not char.isdigit() and char != "-":
                raise RegistryValidationError(
                    f"oracle_id contains unsupported character {char!r}; "
                    f"only lowercase ASCII letters, digits, and hyphens are permitted",
                )
        return value

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_cross_reference(self) -> LiveCrossReferenceDecision:
        self._validate_evidence_tier_alignment()
        self._validate_allowed_hosts_declared()
        self._validate_authentication_constraints()
        self._validate_synthetic_data_constraints()
        for method in self.allowed_methods:
            self._validate_allowed_method(method)
        if self.applicability_condition_mode is ConditionMode.ANY and not self.applicability_predicates:
            raise RegistryValidationError(f"cross-reference {self.id!r} any-mode requires applicability predicates")
        return self

    def _validate_evidence_tier_alignment(self) -> None:
        """The evidence_tier must match the surface's regulatory class.

        Live surfaces (simulators, integration test services) carry
        executable parity evidence; read surfaces and static
        documentation carry observation evidence only.
        """
        if self.surface in SIMULATOR_SURFACES and self.evidence_tier != "executable_parity_evidence":
            raise RegistryValidationError(
                f"cross-reference {self.id!r} live surface requires executable parity evidence",
            )
        if self.surface in READ_SURFACES and self.evidence_tier == "executable_parity_evidence":
            raise RegistryValidationError(
                f"cross-reference {self.id!r} read surface is observation evidence, not parity",
            )
        if (
            self.surface == LiveVerificationSurface.STATIC_OFFICIAL_DOCUMENTATION
            and self.evidence_tier == "executable_parity_evidence"
        ):
            raise RegistryValidationError(
                f"cross-reference {self.id!r} static documentation is not executable parity evidence",
            )

    def _validate_allowed_hosts_declared(self) -> None:
        """Every non-static surface must declare its allowed_hosts."""
        if (
            self.surface
            in {
                "open_simulator",
                "integration_test_service",
                "public_read_surface",
                "authenticated_read_surface",
                "authenticated_simulator",
            }
            and not self.allowed_hosts
        ):
            raise RegistryValidationError(f"cross-reference {self.id!r} must declare allowed_hosts")

    def _validate_authentication_constraints(self) -> None:
        """Per-surface auth + AEAT-authorization requirements.

        Open simulators and public reads must not require auth;
        authenticated reads must require both auth and AEAT
        authorization; authenticated simulators must require auth.
        """
        _validate_open_or_public_authentication(self.surface, self.requires_authentication, self.id)
        _validate_authenticated_read_authentication(
            self.surface,
            self.requires_authentication,
            self.requires_aeat_authorization,
            self.id,
        )
        _validate_authenticated_simulator_authentication(self.surface, self.requires_authentication, self.id)

    def _validate_synthetic_data_constraints(self) -> None:
        """Read surfaces and static docs must not accept synthetic data.

        Additionally, no cross-reference whose ``allowed_hosts`` include an
        AEAT-owned host (suffix match against ``agenciatributaria.gob.es``
        or ``aeat.es``) may declare ``synthetic_data_allowed = true``.
        Synthetic taxpayer, counterparty, declaration, profile, or form
        data is prohibited on AEAT-hosted live surfaces; the surface
        shape (``open_simulator`` / ``authenticated_simulator``) does not
        license synthetic input against AEAT infrastructure.
        """
        if self.surface in READ_SURFACES and self.synthetic_data_allowed:
            raise RegistryValidationError(f"cross-reference {self.id!r} read surface must not accept synthetic data")
        if self.surface == LiveVerificationSurface.STATIC_OFFICIAL_DOCUMENTATION and self.synthetic_data_allowed:
            raise RegistryValidationError(
                f"cross-reference {self.id!r} static documentation cannot accept synthetic data",
            )
        if self.synthetic_data_allowed:
            aeat_host = first_aeat_host(self.allowed_hosts)
            if aeat_host is not None:
                raise RegistryValidationError(
                    f"cross-reference {self.id!r} declares synthetic_data_allowed = true "
                    f"on AEAT-hosted allowed host {aeat_host!r}; synthetic data is prohibited "
                    f"on AEAT-hosted live surfaces",
                )

    def _validate_allowed_method(self, method: str) -> None:
        """Per-surface HTTP method allowlist + uppercase shape requirement."""
        if method.upper() != method:
            raise RegistryValidationError(f"cross-reference {self.id!r} allowed_methods must be uppercase")
        if self.surface in READ_SURFACES and method not in READ_ONLY_HTTP_METHODS:
            raise RegistryValidationError(
                f"cross-reference {self.id!r} read surface method {method!r} is not read-only",
            )
        # authenticated_simulator declares the AEAT-prescribed query
        # method (POST is the GROI / IXVI form-submit mechanism). The
        # remote-state guard's HTTP-method check stays strict for
        # ``kind="http"`` operations; only the cross-reference's
        # allowed_methods declaration is widened.
        if self.surface == LiveVerificationSurface.AUTHENTICATED_SIMULATOR and method not in SIMULATOR_HTTP_METHODS:
            raise RegistryValidationError(
                f"cross-reference {self.id!r} authenticated simulator method "
                f"{method!r} not in (GET, HEAD, OPTIONS, POST)",
            )
