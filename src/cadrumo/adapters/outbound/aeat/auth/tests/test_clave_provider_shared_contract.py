"""Characterisation of the behaviour the two Cl@ve providers already share.

``ClaveMovilAuthProvider`` and ``ClavePermanenteAuthProvider`` are two
independently-authored classes with no common base: 37 and 34 methods, 30
of which share a name. Most of that overlap is one behaviour written twice,
differing only in a provider label, a settings key, a metadata class and a
storage stem — the shape a template method exists to carry.

Extracting a shared base is therefore attractive and, on an authentication
surface, dangerous: these methods drive browsers and persist sessions, so
the differential probe over pure functions that made other consolidations
safe is unavailable here. Without a suite pinning what each provider does
*today*, "behaviour-preserving" would be an assertion rather than a
measurement.

This module is that measurement. It pins the surface an extraction would
move — session persistence, context drop, invalidation, target-URL
defaulting, the landing predicate, and the public ``authenticate`` /
``verify`` guard rails — for both providers, so the same file can be re-run
unchanged afterwards. A test here that has to be *edited* to keep passing
is the signal that the extraction changed behaviour.

It also pins the places the two providers legitimately *diverge*. A base
class that unified those would pass a suite testing only the common parts,
so the divergence is asserted as deliberately as the overlap: each provider
keeps its own storage stem, its own selector-URL template, its own metadata
record and its own Cl@ve surface.

Everything below drives the real providers, the real external-constants
surface and the real encrypted session store. Nothing is stubbed; no test
here reaches a browser, and none reaches an AEAT write or submission path.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pytest

import cadrumo.adapters.outbound.aeat.auth.session_store as session_store

from ......core import AuthProviderKind
from ......core.config import Settings
from ......core.errors import AeatLoginAssertionError
from ......tests.aeat_literal_fixtures import (
    INWINVOC_LANDING_PATH_CANARY,
    INWINVOC_SIBLING_PATH_CANARY,
    INWINVOC_TARGET_PATH_CANARY,
    OTHERAPP_LANDING_PATH_CANARY,
    WLPL_INWINVOC_TWO_SEGMENT_PATH_CANARY,
)
from .....persistence.tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ..clave_movil import ClaveMovilAuthProvider
from ..clave_movil_metadata import ClaveMovilSessionMetadata
from ..clave_permanente import ClavePermanenteAuthProvider
from ..clave_permanente_metadata import ClavePermanenteSessionMetadata
from ._clave_movil_support import _settings_for as _movil_settings_for
from ._clave_permanente_support import _settings_for as _permanente_settings_for

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_EXTERNAL = Settings.external_constants()
_SEDE_PATHS = _EXTERNAL.aeat.sede_paths
_DOMAINS = _EXTERNAL.aeat.domains
_TARGET_PATH = _SEDE_PATHS.expedientes_resumen
_IDENTITY = "12345678Z"
_BUCKET_ID = "1f6b0000-0000-4000-8000-00000000d0d0"
_AUTHENTICATED_AT = datetime(2026, 7, 26, 9, 0, 0, tzinfo=UTC)


def _storage_state() -> dict[str, object]:
    """Build a storage state shaped like the one a real context yields."""
    return {
        "cookies": [
            {
                "name": "JSESSIONID",
                "value": "synthetic-session-value",
                "domain": f".{_DOMAINS.host_suffix}",
                "path": "/",
                "expires": -1,
                "httpOnly": True,
                "secure": True,
                "sameSite": "Lax",
            },
        ],
        "origins": [{"origin": _DOMAINS.www2, "localStorage": []}],
    }


@dataclass(frozen=True)
class _ProviderProfile:
    """One provider plus the facts an extraction must NOT unify away."""

    name: str
    build: Callable[[Path], Any]
    kind: AuthProviderKind
    #: Logical stem under which this provider's session is persisted. Two
    #: providers sharing a stem would collide in the encrypted store, so a
    #: base class hoisting this constant is a real defect.
    storage_stem: str
    #: Settings attribute holding this provider's selector-URL template.
    url_template_attribute: str
    metadata_model: type[ClaveMovilSessionMetadata | ClavePermanenteSessionMetadata]
    #: Attribute on ``external_constants().aeat`` carrying the Cl@ve surface.
    surface_attribute: str


def _movil(tmp_path: Path) -> ClaveMovilAuthProvider:
    return ClaveMovilAuthProvider(_movil_settings_for(tmp_path, CADRUMO_CLAVE_MOVIL_DNI_NIE=_IDENTITY))


def _permanente(tmp_path: Path) -> ClavePermanenteAuthProvider:
    return ClavePermanenteAuthProvider(
        _permanente_settings_for(
            tmp_path,
            CADRUMO_CLAVE_PERMANENTE_DNI_NIE=_IDENTITY,
            CADRUMO_CLAVE_PERMANENTE_PASSWORD="unused-by-these-contracts",
        ),
    )


_MOVIL_PROFILE = _ProviderProfile(
    name="clave_movil",
    build=_movil,
    kind=AuthProviderKind.CLAVE_MOVIL,
    storage_stem="clave-movil-storage",
    url_template_attribute="aeat_clave_sede_access_url_template",
    metadata_model=ClaveMovilSessionMetadata,
    surface_attribute="clave_movil",
)

_PERMANENTE_PROFILE = _ProviderProfile(
    name="clave_permanente",
    build=_permanente,
    kind=AuthProviderKind.CLAVE_PERMANENTE,
    storage_stem="clave-permanente-storage",
    url_template_attribute="aeat_clave_permanente_sede_access_url_template",
    metadata_model=ClavePermanenteSessionMetadata,
    surface_attribute="clave_permanente",
)

_PROFILES = (_MOVIL_PROFILE, _PERMANENTE_PROFILE)


def _profiles() -> pytest.MarkDecorator:
    return pytest.mark.parametrize("profile", _PROFILES, ids=[p.name for p in _PROFILES])


# Provisions the real active-profile bucket the storage paths resolve against.
bucket = bucket_scoped_runtime_profile_fixture(_BUCKET_ID, autouse=False, name="bucket")


def _metadata_for(profile: _ProviderProfile, storage_state: Mapping[str, object]) -> Any:
    return profile.metadata_model(
        identity_nif=_IDENTITY,
        authenticated_at=_AUTHENTICATED_AT,
        idle_deadline=_AUTHENTICATED_AT + timedelta(minutes=18),
        storage_state_sha256=session_store.storage_state_sha256(storage_state),
        landing_url=f"{_DOMAINS.www6}{_TARGET_PATH}",
    )


# ── Target and selector URL construction ────────────────────────────────────


@_profiles()
def test_the_default_target_is_the_shared_sede_expedientes_resumen(
    profile: _ProviderProfile,
    tmp_path: Path,
) -> None:
    """Both providers default to the same authenticated Sede landing.

    This one IS shared, and is the strongest candidate for the base: the
    two implementations are already byte-identical delegations to
    ``default_sede_target_url``.
    """

    provider = profile.build(tmp_path)

    assert provider._default_target_url() == f"{_DOMAINS.www6}{_SEDE_PATHS.expedientes_resumen}"


def test_both_providers_agree_on_the_default_target(tmp_path: Path) -> None:
    """Stated as an equality so an extraction cannot drift one provider."""
    assert _movil(tmp_path)._default_target_url() == _permanente(tmp_path)._default_target_url()


@_profiles()
def test_the_selector_url_percent_encodes_the_target_into_the_provider_template(
    profile: _ProviderProfile,
    tmp_path: Path,
) -> None:
    """The target is quoted with ``safe=""``, so every slash is encoded.

    A base class that hoisted the template would silently route one
    provider through the other's Cl@ve entry point.
    """

    provider = profile.build(tmp_path)
    template = getattr(provider._settings, profile.url_template_attribute)

    assert provider._selector_url(_TARGET_PATH) == template.format(target=quote(_TARGET_PATH, safe=""))
    assert "/" not in provider._selector_url(_TARGET_PATH).removeprefix(template.split("{target}")[0])


def test_both_providers_dispatch_through_the_one_shared_clave_selector(tmp_path: Path) -> None:
    """The shared ``aut=CP`` selector is correct for both methods, not a Móvil defect.

    ``aeat_clave_sede_access_url_template`` and
    ``aeat_clave_permanente_sede_access_url_template`` hold one
    byte-identical value ending ``aut=CP``, which reads at first glance
    like Móvil dispatching through Permanente's parameter.

    It is not. ``aut=CP`` selects Cl@ve as the identity *system* at AEAT's
    ``SelectorAccesos`` page; the Cl@ve gateway then branches to the
    method-specific screen — QR/push for Móvil, the DNI/NIE + password
    form for Permanente. The Móvil template carrying this value is
    recorded as live-tested against AEAT, and the same template is
    consumed by the censal and IVA-wallet sede readers, neither of which
    is a Móvil feature.

    Pinned as an equality so the shared selector stays deliberate: if AEAT
    ever makes ``aut`` method-specific, this reds and names the reason
    rather than one provider silently drifting.
    """

    movil = _movil(tmp_path)
    permanente = _permanente(tmp_path)

    assert movil._selector_url(_TARGET_PATH) == permanente._selector_url(_TARGET_PATH)
    assert movil._settings.aeat_clave_sede_access_url_template.endswith("aut=CP")


@_profiles()
def test_each_provider_reads_its_own_clave_surface(profile: _ProviderProfile, tmp_path: Path) -> None:
    """``_clave_surface`` is a genuine variation point, not shared behaviour."""
    provider = profile.build(tmp_path)
    expected = getattr(_EXTERNAL.aeat, profile.surface_attribute)

    assert provider._clave_surface() == expected


# ── Verification probe URL selection ────────────────────────────────────────


@_profiles()
def test_an_explicit_target_always_probes_through_the_clave_selector(
    profile: _ProviderProfile,
    tmp_path: Path,
) -> None:
    """An explicit target wins over any resolved landing URL.

    Some Cl@ve-backed apps only establish target-local state when
    dispatched from the selector, so the explicit branch must not be
    short-circuited by a cached landing.
    """

    provider = profile.build(tmp_path)

    probe = provider._probe_url_for_verification(
        explicit_target_url=f"{_DOMAINS.www6}{_TARGET_PATH}",
        resolved_target_url=f"{_DOMAINS.www2}/some/other/landing",
        target_path=_TARGET_PATH,
    )

    assert probe == provider._selector_url(_TARGET_PATH)


@_profiles()
def test_a_resolved_landing_containing_the_target_is_probed_directly(
    profile: _ProviderProfile,
    tmp_path: Path,
) -> None:
    """With no explicit target, a landing that already covers it is reused."""
    provider = profile.build(tmp_path)
    resolved = f"{_DOMAINS.www6}{_TARGET_PATH}"

    probe = provider._probe_url_for_verification(
        explicit_target_url=None,
        resolved_target_url=resolved,
        target_path=_TARGET_PATH,
    )

    assert probe == resolved


@_profiles()
def test_a_resolved_landing_missing_the_target_is_still_probed_directly(
    profile: _ProviderProfile,
    tmp_path: Path,
) -> None:
    """Pins the fall-through: a non-covering landing is preferred over the selector.

    This is the branch most likely to be "tidied" during an extraction,
    because it looks redundant beside the previous case and is not.
    """

    provider = profile.build(tmp_path)
    resolved = f"{_DOMAINS.www2}/unrelated/landing"

    probe = provider._probe_url_for_verification(
        explicit_target_url=None,
        resolved_target_url=resolved,
        target_path=_TARGET_PATH,
    )

    assert probe == resolved


@_profiles()
def test_no_target_at_all_falls_back_to_the_selector_url(
    profile: _ProviderProfile,
    tmp_path: Path,
) -> None:
    """With neither an explicit nor a resolved target the selector carries the probe."""
    provider = profile.build(tmp_path)

    probe = provider._probe_url_for_verification(
        explicit_target_url=None,
        resolved_target_url=None,
        target_path=_TARGET_PATH,
    )

    assert probe == provider._selector_url(_TARGET_PATH)


# ── Landing predicate wiring ────────────────────────────────────────────────


@_profiles()
def test_the_landing_predicate_delegates_to_the_authenticated_landing_decision(
    profile: _ProviderProfile,
    tmp_path: Path,
) -> None:
    """The positional-argument adapter must keep routing to the real guard.

    ``_authenticated_landing_predicate`` exists only to hand the guard to
    the page-flow helper as a positional callable. An extraction that
    rewired it to anything else would silently relax the authenticated
    landing check, which is what refuses a hostile authority.
    """

    provider = profile.build(tmp_path)
    honest = f"{_DOMAINS.www6}{_TARGET_PATH}"
    hostile = f"https://evil@www6.{_DOMAINS.host_suffix}{_TARGET_PATH}"

    assert provider._authenticated_landing_predicate(honest, _TARGET_PATH) is True
    assert provider._authenticated_landing_predicate(hostile, _TARGET_PATH) is False
    assert provider._authenticated_landing_predicate(honest, _TARGET_PATH) is provider._is_authenticated_aeat_landing(
        landing_url=honest,
        target_path=_TARGET_PATH,
    )


@_profiles()
def test_the_application_path_comparison_matches_on_the_first_two_segments(
    profile: _ProviderProfile,
    tmp_path: Path,
) -> None:
    """A sibling page inside the same AEAT application counts as the target."""
    provider = profile.build(tmp_path)

    assert (
        provider._same_aeat_application_path(
            landing_path=INWINVOC_LANDING_PATH_CANARY,
            target_path=INWINVOC_SIBLING_PATH_CANARY,
        )
        is True
    )
    assert (
        provider._same_aeat_application_path(
            landing_path=OTHERAPP_LANDING_PATH_CANARY,
            target_path=INWINVOC_TARGET_PATH_CANARY,
        )
        is False
    )


@_profiles()
def test_a_landing_outside_the_known_application_roots_is_refused(
    profile: _ProviderProfile,
    tmp_path: Path,
) -> None:
    """Only ``wlpl`` and ``sede`` roots participate; anything else fails closed."""
    provider = profile.build(tmp_path)

    assert (
        provider._same_aeat_application_path(
            landing_path="/unknown/root/page",
            target_path="/unknown/root/page",
        )
        is False
    )


@_profiles()
def test_a_single_segment_path_cannot_satisfy_the_comparison(
    profile: _ProviderProfile,
    tmp_path: Path,
) -> None:
    """Fewer than two segments on either side refuses, rather than index-erroring."""
    provider = profile.build(tmp_path)

    assert (
        provider._same_aeat_application_path(landing_path="/wlpl", target_path=WLPL_INWINVOC_TWO_SEGMENT_PATH_CANARY)
        is False
    )
    assert (
        provider._same_aeat_application_path(landing_path=WLPL_INWINVOC_TWO_SEGMENT_PATH_CANARY, target_path="/wlpl")
        is False
    )


# ── Encrypted session persistence ───────────────────────────────────────────


@_profiles()
@pytest.mark.usefixtures("bucket")
def test_the_storage_path_is_provider_scoped_within_the_active_bucket(
    profile: _ProviderProfile,
    tmp_path: Path,
) -> None:
    """Each provider owns its own stem, so the two never collide in the store."""
    provider = profile.build(tmp_path)

    assert provider._storage_state_path().name == f"{_BUCKET_ID}-{profile.storage_stem}.json"


@pytest.mark.usefixtures("bucket")
def test_the_two_providers_never_share_a_storage_path(tmp_path: Path) -> None:
    """Anti-collision guard: a hoisted stem would make one session overwrite the other."""
    assert _movil(tmp_path)._storage_state_path() != _permanente(tmp_path)._storage_state_path()


@_profiles()
@pytest.mark.usefixtures("bucket")
def test_a_persisted_session_round_trips_through_the_real_encrypted_store(
    profile: _ProviderProfile,
    tmp_path: Path,
) -> None:
    """Persist, reload and re-validate metadata through the provider's own methods.

    The cookie is asserted specifically: a persistence path that stored
    metadata and dropped the storage state would leave a record that loads
    cleanly and authenticates nothing.
    """

    provider = profile.build(tmp_path)
    path = provider._storage_state_path()
    storage_state = _storage_state()
    metadata = _metadata_for(profile, storage_state)

    assert session_store.exists(path) is False

    provider._persist_session(path, storage_state=storage_state, metadata=metadata)

    assert session_store.exists(path) is True
    persisted = provider._load_persisted(path)
    assert persisted.storage_state["cookies"] == storage_state["cookies"]

    reloaded = provider._load_metadata(path, persisted)
    assert reloaded == metadata
    assert reloaded.provider_kind is profile.kind


@_profiles()
@pytest.mark.usefixtures("bucket")
def test_loading_an_absent_session_refuses_rather_than_returning_none(
    profile: _ProviderProfile,
    tmp_path: Path,
) -> None:
    """The provider converts the store's ``None`` into an instructive refusal."""
    provider = profile.build(tmp_path)

    with pytest.raises(AeatLoginAssertionError, match="no persisted"):
        provider._load_persisted(provider._storage_state_path())


@_profiles()
@pytest.mark.usefixtures("bucket")
def test_metadata_that_does_not_validate_refuses_the_resume(
    profile: _ProviderProfile,
    tmp_path: Path,
) -> None:
    """A record whose metadata cannot be revalidated must not resume silently.

    Written as a corruption probe rather than a happy-path assertion: if
    this ever passes with the boundary broken, the round-trip above is
    tautological.
    """

    provider = profile.build(tmp_path)
    path = provider._storage_state_path()
    session_store.save(path, storage_state=_storage_state(), metadata={"provider_kind": "certificate"})

    persisted = provider._load_persisted(path)
    with pytest.raises(AeatLoginAssertionError, match="metadata invalid"):
        provider._load_metadata(path, persisted)


@_profiles()
@pytest.mark.usefixtures("bucket")
def test_invalidating_a_persisted_session_removes_it_from_the_store(
    profile: _ProviderProfile,
    tmp_path: Path,
) -> None:
    """Invalidation is what makes the fresh-login fallback reachable."""
    provider = profile.build(tmp_path)
    path = provider._storage_state_path()
    storage_state = _storage_state()
    provider._persist_session(path, storage_state=storage_state, metadata=_metadata_for(profile, storage_state))

    assert session_store.exists(path) is True

    provider._invalidate_persisted(path)

    assert session_store.exists(path) is False


@_profiles()
@pytest.mark.usefixtures("bucket")
def test_invalidating_an_absent_session_is_a_tolerated_no_op(
    profile: _ProviderProfile,
    tmp_path: Path,
) -> None:
    """The fallback path invalidates unconditionally, so absence must not raise."""
    provider = profile.build(tmp_path)

    provider._invalidate_persisted(provider._storage_state_path())

    assert session_store.exists(provider._storage_state_path()) is False


# ── Lifecycle ───────────────────────────────────────────────────────────────


@_profiles()
def test_dropping_an_absent_context_succeeds_and_clears_the_slot(
    profile: _ProviderProfile,
    tmp_path: Path,
) -> None:
    """``_drop_context`` reports success for a provider holding nothing.

    The salvage and failure paths call this unconditionally, so a version
    that reported failure on ``None`` would turn a clean teardown into a
    retained-resources error.
    """

    provider = profile.build(tmp_path)

    assert asyncio.run(provider._drop_context()) is True
    assert provider._context is None


@_profiles()
def test_closing_a_provider_that_never_authenticated_is_clean(
    profile: _ProviderProfile,
    tmp_path: Path,
) -> None:
    """Close is safe before authenticate, and leaves every resource slot empty."""
    provider = profile.build(tmp_path)

    asyncio.run(provider.close())

    assert provider._context is None
    assert provider._browser_session is None
    assert provider._active_session is None


@_profiles()
def test_a_fresh_provider_holds_no_session_or_browser_resources(
    profile: _ProviderProfile,
    tmp_path: Path,
) -> None:
    """Anti-tautology guard for the lifecycle assertions above."""
    provider = profile.build(tmp_path)

    assert provider._context is None
    assert provider._browser_session is None
    assert provider._active_session is None


@_profiles()
def test_resolving_a_browser_session_without_a_factory_refuses(
    profile: _ProviderProfile,
    tmp_path: Path,
) -> None:
    """Both providers refuse rather than constructing a browser implicitly."""
    provider = profile.build(tmp_path)

    with pytest.raises(AeatLoginAssertionError, match="browser"):
        asyncio.run(provider._resolve_browser_session())


# ── Public protocol guard rails ─────────────────────────────────────────────


@_profiles()
def test_verify_without_an_active_context_refuses(profile: _ProviderProfile, tmp_path: Path) -> None:
    """``verify`` requires ``authenticate`` first, on both providers."""
    provider = profile.build(tmp_path)
    session = object()

    with pytest.raises(AeatLoginAssertionError, match="active browser context"):
        asyncio.run(provider.verify(session))  # type: ignore[arg-type]


@_profiles()
def test_verify_delegates_to_the_untargeted_target_form(
    profile: _ProviderProfile,
    tmp_path: Path,
) -> None:
    """``verify`` is exactly ``verify_for_target(target_url=None)``.

    Both implementations are already byte-identical; pinning the
    delegation keeps an extraction from quietly giving ``verify`` a
    default target of its own.
    """

    provider = profile.build(tmp_path)
    session = object()

    with pytest.raises(AeatLoginAssertionError) as bare:
        asyncio.run(provider.verify(session))  # type: ignore[arg-type]
    with pytest.raises(AeatLoginAssertionError) as targeted:
        asyncio.run(provider.verify_for_target(session, target_url=None))  # type: ignore[arg-type]

    assert str(bare.value) == str(targeted.value)
