"""Multi-year-renta modelo authorization manifest, types, and derivation.

This module owns the type spine of the multi-year-renta authorization
gate. The gate's governing principle is **default-deny-by-absence**: a
modelo's calculation backend
is treated as NON-FUNCTIONAL until its authorization is *derived* from the
declarative manifest and *verified* by an enrolling end-to-end persona
test that drove the real backend across at least two distinct renta
(annual) periods.

Four collaborating pieces live here:

- :class:`AuthorizationState` and :class:`EnrollmentEvidenceClass` — the
  closed value sets, declared as :class:`enum.StrEnum` (``core/`` owns
  closed enums).
- :class:`ModeloAuthorizationEntry` — the strict pydantic record modelling
  one manifest entry. The ``>=2 distinct renta years`` invariant is
  enforced at the type boundary so a malformed (single-year) enrollment
  claim cannot construct.
- :class:`AuthorizationManifest` — the parsed, validated view of the
  directory-mode manifest (``authorization.d/<modelo>.toml`` fragments,
  one per enrolled modelo, merged by the loader). Default-deny is literal:
  an absent directory or one with no fragments authorizes zero modelos.
- :class:`ModeloAuthorization` — the *derived* per-modelo capability the
  runtime consults. It is computed at the registry boundary (see
  :meth:`domain.calculations.registry.ValidatedRegistryAuthority.authorization`),
  never authored independently per revision, so the capability cannot
  drift from the manifest.

The manifest is the only writable authorization surface; everything else
is a derivation of it. A declaration in data is cross-checked against
evidence the declaration cannot fabricate (here, the year-set a recorder
observes a real test exercising).
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Final

from pydantic import BaseModel, Field, model_validator

from ...core.directory_scan import scan_directory
from ..modelo import NON_REGISTRY_MODELOS, Modelo
from ..models import STRICT_FROZEN_CONFIG
from ..toml import read_toml
from .errors import AuthorizationManifestError

#: Minimum number of distinct renta (annual) years an enrolling test must
#: exercise before a modelo may be authorized. The owner mandate is two
#: distinct years: a single-period test cannot prove cross-year stability.
MIN_DISTINCT_RENTA_YEARS: Final[int] = 2

#: Directory holding the per-modelo authorization manifest fragments,
#: resolved relative to the AEAT registry root (sibling of ``legal/`` and
#: ``modelos/``). The manifest is directory-mode: each enrolled modelo owns
#: one ``authorization.d/<modelo>.toml`` file, mirroring the registry's own
#: directory-mode layout. The loader merges every fragment. Per-modelo
#: files let concurrent enrollment target disjoint files — zero
#: contention on a single shared manifest.
AUTHORIZATION_MANIFEST_DIRNAME: Final[str] = "authorization.d"

#: The canonical fleet of modelo ids the gate enrolls. The owner mandate
#: is non-negotiable: every modelo enrolls, none is out-of-scope. This is
#: the honest denominator behind the meta-test's ``authorized N/30`` line.
#: It is the union of every modelo the registry authority can load today
#: plus the engine-build modelos whose registry directory carries no
#: ``manifest.toml`` yet (151 Beckham, 714 Patrimonio, 721 crypto), which
#: remain in scope. The meta-test pins
#: this tuple against the live registry so a registry change that adds or
#: drops a modelo surfaces loudly rather than silently moving the
#: denominator.  Retired identifiers carried by :class:`Modelo` but with no
#: registry definition (:data:`NON_REGISTRY_MODELOS`, e.g. the suppressed M037
#: censo simplificada) are NOT enrolled and are excluded here.
CANONICAL_MODELO_FLEET: Final[tuple[str, ...]] = tuple(m for m in Modelo if m not in NON_REGISTRY_MODELOS)

#: The enrolled-fleet size used as the meta-test denominator. Derived from
#: the canonical fleet rather than hard-coded so the two cannot disagree.
FLEET_SIZE: Final[int] = len(CANONICAL_MODELO_FLEET)


class AuthorizationState(StrEnum):
    """Closed two-state authorization verdict for a modelo's backend.

    ``UNAUTHORIZED`` is the default for every modelo not proven by an
    enrolling test; ``AUTHORIZED`` is granted only once a verified
    enrollment record exists in the manifest.
    """

    UNAUTHORIZED = "unauthorized"
    AUTHORIZED = "authorized"


class EnrollmentEvidenceClass(StrEnum):
    """Closed set of enrollment-evidence shapes across the modelo fleet.

    The owner mandate keeps every modelo in scope, but the *shape* of the
    cross-year evidence varies by modelo class:

    - ``CALCULATION`` — engine plus a cross-year carry (130, 100, 200,
      202, 303, 131, …); the recorder captures two ``filing_year`` values
      computed through ``calculate_modelo_revision``.
    - ``RECONCILIATION`` — periodic→annual summary reconciled across two
      years (390, 180, 190, 193).
    - ``DATA_FIDELITY`` — informativa year-over-year fidelity plus
      provenance, with no numeric oracle (347, 184, 721, 232, 349, …).
    - ``THRESHOLD_CONTINUITY`` — structural exemption / obligation logic
      across two years (720, 840, 036).
    """

    CALCULATION = "calculation"
    RECONCILIATION = "reconciliation"
    DATA_FIDELITY = "data_fidelity"
    THRESHOLD_CONTINUITY = "threshold_continuity"


class ModeloAuthorizationEntry(BaseModel):
    """One enrolling claim from the authorization manifest.

    An entry is a *claim* the enrolling end-to-end test must verify, not a
    trusted grant. The ``>=2 distinct renta years`` invariant is enforced
    here at the pydantic boundary so a single-year (un-cross-year) claim
    cannot even construct — the minimum-two-years contract is
    unconstructable to violate, not merely asserted in a test.

    Attributes:
        modelo: The modelo id the entry authorizes (e.g. ``"130"``).
        renta_years: The distinct renta (annual) years the enrolling
            evidence must exercise. At least :data:`MIN_DISTINCT_RENTA_YEARS`
            distinct years are required; duplicates are rejected.
        evidence_class: The enrollment-evidence shape for this modelo.
        enrolling_test: Dotted-or-path reference to the end-to-end persona
            test that enrolls this modelo. The meta-test confirms the
            referenced test exists and that the year-set its recorder
            observes equals ``renta_years``.
    """

    model_config = STRICT_FROZEN_CONFIG

    modelo: str = Field(min_length=1, max_length=8)
    renta_years: tuple[int, ...]
    evidence_class: EnrollmentEvidenceClass
    enrolling_test: str = Field(min_length=1, max_length=256)

    @model_validator(mode="after")
    def _validate_distinct_renta_years(self) -> ModeloAuthorizationEntry:
        """Reject any claim that does not span >=2 distinct renta years.

        Two failure modes are caught: fewer than the minimum number of
        years, and a claim padded with duplicate years to fake breadth.
        Both reduce to "the distinct-year count is below the floor".
        """
        distinct = set(self.renta_years)
        if len(distinct) < MIN_DISTINCT_RENTA_YEARS:
            raise ValueError(
                f"modelo {self.modelo!r} authorization claim must span at least "
                f"{MIN_DISTINCT_RENTA_YEARS} distinct renta years; got "
                f"{sorted(self.renta_years)!r} ({len(distinct)} distinct)",
            )
        return self

    @property
    def distinct_renta_years(self) -> tuple[int, ...]:
        """Return the claim's distinct renta years, sorted ascending."""
        return tuple(sorted(set(self.renta_years)))


class AuthorizationManifest(BaseModel):
    """Parsed, validated view of the directory-mode authorization manifest.

    The manifest is the merge of every ``authorization.d/<modelo>.toml``
    fragment. Default-deny is literal: an absent directory or one with no
    fragments yields an empty :attr:`entries` tuple and therefore authorizes
    zero modelos. A modelo id may appear at most once across fragments; a
    duplicate is an authoring error, not a silent last-wins overwrite.
    """

    model_config = STRICT_FROZEN_CONFIG

    entries: tuple[ModeloAuthorizationEntry, ...] = ()

    @model_validator(mode="after")
    def _reject_unenrollable_or_duplicate_modelos(self) -> AuthorizationManifest:
        unknown = sorted(entry.modelo for entry in self.entries if entry.modelo not in CANONICAL_MODELO_FLEET)
        if unknown:
            raise ValueError(
                f"authorization manifest declares non-enrollable modelo identifiers: {unknown!r}; "
                "enroll only canonical registry-backed modelos",
            )
        seen: set[str] = set()
        for entry in self.entries:
            if entry.modelo in seen:
                raise ValueError(
                    f"authorization manifest declares modelo {entry.modelo!r} more than once; "
                    f"each modelo enrolls through exactly one entry",
                )
            seen.add(entry.modelo)
        return self

    def entry_for(self, modelo: str) -> ModeloAuthorizationEntry | None:
        """Return the enrolling :class:`ModeloAuthorizationEntry` for ``modelo``, or ``None`` if absent."""
        for entry in self.entries:
            if entry.modelo == modelo:
                return entry
        return None

    @property
    def authorized_modelos(self) -> frozenset[str]:
        """Return the set of modelo ids the manifest authorizes."""
        return frozenset(entry.modelo for entry in self.entries)


class ModeloAuthorization(BaseModel):
    """Derived per-modelo authorization capability the runtime consults.

    This record is *computed* at the registry boundary from the manifest
    cross-checked against the loadable registry — it is never authored
    independently per revision, so it cannot drift from the manifest.
    See
    :meth:`domain.calculations.registry.ValidatedRegistryAuthority.authorization`.

    Attributes:
        modelo: The modelo id this capability describes.
        state: ``AUTHORIZED`` iff the manifest enrolls the modelo;
            ``UNAUTHORIZED`` otherwise (the default for every modelo).
        has_engine: Whether the modelo declares a ``calculation`` surface
            application-link in the loaded registry. Drives the CLI
            ADVISORY-vs-refusal split: an UNAUTHORIZED modelo that has an
            engine still computes (with an advisory banner); a modelo with
            no loadable engine is refused at ``work create`` by the
            established stub guard.
        entry: The manifest entry backing an ``AUTHORIZED`` state, or
            ``None`` when ``UNAUTHORIZED``.
    """

    model_config = STRICT_FROZEN_CONFIG

    modelo: str = Field(min_length=1, max_length=8)
    state: AuthorizationState
    has_engine: bool
    entry: ModeloAuthorizationEntry | None = None

    @model_validator(mode="after")
    def _validate_entry_matches_state(self) -> ModeloAuthorization:
        """An AUTHORIZED capability must carry its backing manifest entry."""
        if self.state is AuthorizationState.AUTHORIZED and self.entry is None:
            raise ValueError(
                f"modelo {self.modelo!r} is AUTHORIZED but carries no backing manifest entry; "
                f"the derived capability must reference the entry that authorizes it",
            )
        if self.state is AuthorizationState.UNAUTHORIZED and self.entry is not None:
            raise ValueError(
                f"modelo {self.modelo!r} is UNAUTHORIZED but carries a manifest entry; "
                f"an unauthorized capability must not reference an enrolling entry",
            )
        return self

    @property
    def is_authorized(self) -> bool:
        """Return whether the modelo's backend is authorized."""
        return self.state is AuthorizationState.AUTHORIZED


def manifest_dir(registry_root: Path) -> Path:
    """Return the ``authorization.d`` directory for an AEAT registry root.

    The directory is a sibling of ``legal/`` and ``modelos/`` under the
    registry root, so callers that hold the registry root (the authority,
    the fingerprint walker) resolve it the same way.
    """
    return registry_root / AUTHORIZATION_MANIFEST_DIRNAME


def _load_manifest_fragment(path: Path) -> ModeloAuthorizationEntry:
    """Parse and validate one ``authorization.d/<modelo>.toml`` fragment.

    A fragment declares exactly one enrolled modelo as a top-level
    ``[modelo]`` table. The fragment filename stem should match the
    declared ``modelo`` id (e.g. ``130.toml`` declares ``modelo = "130"``);
    the loader cross-checks the two so a mis-filed fragment fails loudly.

    Args:
        path: The fragment file path.

    Returns:
        The validated :class:`ModeloAuthorizationEntry`.

    Raises:
        AuthorizationManifestError: When the fragment cannot be parsed,
            omits or duplicates the ``[modelo]`` table, declares a stem that
            disagrees with the ``modelo`` id, or violates an entry invariant
            (single-year claim, unknown field).
    """
    raw = read_toml(path, error_factory=AuthorizationManifestError)
    raw_entry = raw.get("modelo")
    if not isinstance(raw_entry, dict):
        raise AuthorizationManifestError(
            f"{path}: an authorization.d fragment must declare exactly one [modelo] table; "
            f"got {type(raw_entry).__name__ if raw_entry is not None else 'no [modelo] table'}",
        )
    try:
        # TOML hydration is a boundary coercion: arrays decode to ``list``
        # and scalars to ``str``, but the entry model is ``strict=True`` for
        # programmatic construction. Validate non-strictly here so
        # ``renta_years`` (TOML array -> tuple) and ``evidence_class`` (TOML
        # string -> StrEnum) hydrate at the boundary; every value invariant
        # (>=2 distinct years, field bounds) still runs regardless of mode.
        entry = ModeloAuthorizationEntry.model_validate(raw_entry, strict=False)
    except ValueError as exc:
        raise AuthorizationManifestError(f"{path}: invalid authorization fragment: {exc}") from exc
    if entry.modelo != path.stem:
        raise AuthorizationManifestError(
            f"{path}: fragment filename stem {path.stem!r} does not match its declared "
            f"modelo id {entry.modelo!r}; name the fragment <modelo>.toml",
        )
    return entry


def load_authorization_manifest(registry_root: Path) -> AuthorizationManifest:
    """Load and validate the directory-mode authorization manifest.

    The manifest is directory-mode: every enrolled modelo owns one
    ``authorization.d/<modelo>.toml`` fragment under ``registry_root``. The
    loader merges every fragment in sorted order into one
    :class:`AuthorizationManifest`.

    Default-deny-by-absence: when the ``authorization.d`` directory is
    missing or holds no ``*.toml`` fragments, the result is an empty
    manifest (zero authorized modelos), never an error. A present-but-
    malformed fragment raises :class:`AuthorizationManifestError` so a broken
    authorization surface fails loudly rather than silently authorizing
    nothing or everything.

    Args:
        registry_root: The AEAT registry root directory.

    Returns:
        The validated :class:`AuthorizationManifest`.

    Raises:
        AuthorizationManifestError: When a fragment cannot be parsed or
            violates an entry/manifest invariant (single-year claim,
            duplicate modelo across fragments, stem/id mismatch, unknown
            field).
    """
    directory = manifest_dir(registry_root)
    if not directory.is_dir():
        return AuthorizationManifest()
    entries = tuple(_load_manifest_fragment(path) for path in scan_directory(directory, pattern="*.toml"))
    try:
        return AuthorizationManifest(entries=entries)
    except ValueError as exc:
        raise AuthorizationManifestError(f"{directory}: invalid authorization manifest: {exc}") from exc


def derive_modelo_authorization(
    modelo: str,
    *,
    manifest: AuthorizationManifest,
    has_engine: bool,
) -> ModeloAuthorization:
    """Derive the per-modelo capability from the manifest and engine presence.

    This is the canonical derivation the registry authority exposes. The
    capability is a pure function of (a) the manifest entry, if any, and
    (b) whether the modelo declares a calculation surface in the loaded
    registry — never an independently authored flag.

    Args:
        modelo: The modelo id to derive a capability for.
        manifest: The loaded authorization manifest (default-deny source).
        has_engine: Whether the modelo declares a ``calculation`` surface
            application-link in the registry.

    Returns:
        The derived :class:`ModeloAuthorization`.
    """
    entry = manifest.entry_for(modelo)
    if entry is None:
        return ModeloAuthorization(
            modelo=modelo,
            state=AuthorizationState.UNAUTHORIZED,
            has_engine=has_engine,
            entry=None,
        )
    return ModeloAuthorization(
        modelo=modelo,
        state=AuthorizationState.AUTHORIZED,
        has_engine=has_engine,
        entry=entry,
    )


__all__ = [
    "AUTHORIZATION_MANIFEST_DIRNAME",
    "CANONICAL_MODELO_FLEET",
    "FLEET_SIZE",
    "MIN_DISTINCT_RENTA_YEARS",
    "AuthorizationManifest",
    "AuthorizationState",
    "EnrollmentEvidenceClass",
    "ModeloAuthorization",
    "ModeloAuthorizationEntry",
    "derive_modelo_authorization",
    "load_authorization_manifest",
    "manifest_dir",
]
