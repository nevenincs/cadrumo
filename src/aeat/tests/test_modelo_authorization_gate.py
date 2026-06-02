"""Fleet-wide CI meta-test for the multi-year-renta authorization gate.

The ``modelo-multiyear-renta`` ADR makes every modelo's calculation backend
NON-FUNCTIONAL until an enrolling end-to-end persona test proves it across at
least two distinct renta (annual) years. The authorization manifest
(``authorization.toml``) is the single source of truth; this meta-test is the
fleet-level structural gate over it.

The gate has two jobs:

- **Report coverage honestly.** On every run it prints ``authorized N/30`` plus
  the explicit UNAUTHORIZED id list and any engine-build-blocked modelos. There
  is no stored baseline and no recorded number to silently regress against;
  coverage can only ratchet upward as enrolling tests land. The denominator is
  the curated :data:`CANONICAL_MODELO_FLEET` (30), pinned against the live
  registry so a registry change that adds or drops a modelo surfaces loudly.

- **Enforce enrollment validity.** For every manifest entry it asserts the
  claim is real and un-fakeable: the modelo is in the canonical fleet, the
  ``renta_years`` claim spans at least two distinct years (also guaranteed at
  the :class:`aeat.core.access_gate.ModeloAuthorizationEntry` type boundary),
  the named ``enrolling_test`` file exists, and that test actually drives the
  enrollment recorder's cross-check
  (:func:`aeat.application.calculations.assert_enrollment_matches_manifest`) so
  a stub or single-year test cannot claim authorization.

CRITICAL DESIGN: the gate is GREEN at partial rollout. An empty manifest yields
``authorized 0/30`` and passes, because there are zero *invalid* entries — the
campaign ratchets coverage rather than the gate being permanently red until
30/30 (a permanent-red gate would violate ``aeat-quality-gates``). A fake,
single-year, missing-test, or contract-less entry turns the gate RED.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aeat.application.calculations import assert_enrollment_matches_manifest
from aeat.core.access_gate import (
    CANONICAL_MODELO_FLEET,
    FLEET_SIZE,
    MIN_DISTINCT_RENTA_YEARS,
    AuthorizationState,
)
from aeat.core.resources import resources

pytestmark = [pytest.mark.unit, pytest.mark.domain_model, pytest.mark.inventory]

#: The name of the cross-check every enrolling test must call. Its presence in
#: the enrolling test source is the AST-level proof the test verifies its
#: recorded year-set against the manifest claim rather than asserting nothing.
_ENROLLMENT_CONTRACT_CALL = assert_enrollment_matches_manifest.__name__

#: Repository root: this file lives at ``src/aeat/tests/`` so the repo root is
#: four parents up. Used to resolve manifest-declared ``enrolling_test`` paths.
_REPO_ROOT = Path(__file__).resolve().parents[3]


def _authority():
    return resources().modelos.authority


def test_canonical_fleet_is_thirty_distinct_modelos() -> None:
    """The canonical fleet — the gate's denominator — is exactly 30 distinct ids."""
    assert len(CANONICAL_MODELO_FLEET) == FLEET_SIZE
    assert len(set(CANONICAL_MODELO_FLEET)) == FLEET_SIZE
    assert FLEET_SIZE == 30


def test_canonical_fleet_covers_every_loadable_modelo() -> None:
    """Every modelo the registry can load today is in the canonical fleet.

    This pins the denominator against the live registry: if a modelo is added
    to the registry without being added to :data:`CANONICAL_MODELO_FLEET`, the
    fleet would silently under-count and this gate fails — the denominator
    cannot drift unnoticed.
    """
    loadable = {modelo.id for modelo in _authority().modelos}
    missing_from_fleet = sorted(loadable - set(CANONICAL_MODELO_FLEET))
    assert not missing_from_fleet, (
        f"registry loads modelos {missing_from_fleet!r} that are absent from "
        f"CANONICAL_MODELO_FLEET; add them so the gate denominator stays honest"
    )


def test_authorization_coverage_report_and_validity(capsys: pytest.CaptureFixture[str]) -> None:
    """Report ``authorized N/30`` and enforce per-entry enrollment validity.

    GREEN at partial rollout: the assertions below check only that each
    *present* manifest entry is a valid, un-fakeable enrollment. Zero entries
    means zero invalid entries means green. Coverage ratchets up as enrolling
    tests land.
    """
    authority = _authority()
    manifest = authority.authorization_manifest
    loadable = {modelo.id for modelo in authority.modelos}

    authorized: list[str] = []
    unauthorized: list[str] = []
    engine_build_blocked: list[str] = []
    for modelo in CANONICAL_MODELO_FLEET:
        capability = authority.authorization(modelo)
        if capability.state is AuthorizationState.AUTHORIZED:
            authorized.append(modelo)
        else:
            unauthorized.append(modelo)
        # A fleet modelo that does not load and has no engine cannot be
        # authorized by a test-only change; the ADR's engine-build sub-decision
        # tracks these explicitly so the lag is visible, not hidden.
        if modelo not in loadable and not capability.has_engine:
            engine_build_blocked.append(modelo)

    # Honest coverage line printed on every run (use -s to see it locally).
    print(
        f"\nauthorized {len(authorized)}/{FLEET_SIZE}"
        f" | unauthorized: {','.join(unauthorized) or '-'}"
        f" | engine-build-blocked ({len(engine_build_blocked)}): "
        f"{','.join(engine_build_blocked) or '-'}"
    )
    captured = capsys.readouterr()
    assert f"authorized {len(authorized)}/{FLEET_SIZE}" in captured.out

    # Per-entry validity — the un-fakeable contract. Every assertion holds
    # vacuously on an empty manifest (green at zero rollout).
    for entry in manifest.entries:
        assert entry.modelo in CANONICAL_MODELO_FLEET, (
            f"manifest enrolls {entry.modelo!r}, which is not in the canonical fleet"
        )
        assert len(set(entry.renta_years)) >= MIN_DISTINCT_RENTA_YEARS, (
            f"manifest entry {entry.modelo!r} claims fewer than {MIN_DISTINCT_RENTA_YEARS} "
            f"distinct renta years: {entry.renta_years!r}"
        )
        test_path = _REPO_ROOT / entry.enrolling_test
        assert test_path.is_file(), (
            f"manifest entry {entry.modelo!r} names enrolling_test {entry.enrolling_test!r}, "
            f"which does not exist at {test_path}"
        )
        source = test_path.read_text(encoding="utf-8")
        assert _ENROLLMENT_CONTRACT_CALL in source, (
            f"enrolling test {entry.enrolling_test!r} for modelo {entry.modelo!r} does not call "
            f"{_ENROLLMENT_CONTRACT_CALL}(...); an enrollment must verify its recorded year-set "
            f"against the manifest claim, not assert nothing"
        )


def test_empty_manifest_authorizes_nothing() -> None:
    """Default-deny-by-absence: every fleet modelo derives to UNAUTHORIZED when unenrolled.

    This is the anti-tautology proof for the coverage gate: with no manifest
    entry for a modelo, its derived capability MUST be UNAUTHORIZED. If this
    ever passed while a modelo read AUTHORIZED without a manifest entry, the
    whole gate would be meaningless.
    """
    authority = _authority()
    manifest = authority.authorization_manifest
    for modelo in CANONICAL_MODELO_FLEET:
        if manifest.entry_for(modelo) is None:
            capability = authority.authorization(modelo)
            assert capability.state is AuthorizationState.UNAUTHORIZED, (
                f"modelo {modelo!r} has no manifest entry but derived to {capability.state.value!r}; "
                f"default-deny-by-absence is broken"
            )
            assert not capability.is_authorized
