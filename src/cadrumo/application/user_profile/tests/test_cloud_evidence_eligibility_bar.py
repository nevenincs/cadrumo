"""The per-profile off-host eligibility bar: default off, gestor-locked off, unoffered while off.

Three claims, and the third is the one that needs care.

**Default off.** ``cloud_evidence_upload`` is the only
:class:`~core.ServiceCapability` whose ``default_enabled`` is ``False``: an
unanswered question there would decide by silence that a taxpayer's document may
leave the machine.

**Gestor-locked off.** The bar is applied BEFORE the profile fact is read, so an
explicit opt-in is unreachable rather than overridden -- the difference between
a bar and a strong default.

**No consent gate offered on any surface while off.** That is a completeness
claim, so the surface set is DERIVED from the production mechanism rather than
listed here: a surface can only offer a working acknowledgement by obtaining a
token, and :func:`~llm.mint_evidence_consent_token` is the sole constructor, so
"every consent-offering surface" is exactly "every call site of that function".
The sweep walks the production AST for those call sites and requires each to
source ``profile_eligible`` from
:func:`~application.user_profile.cloud_evidence_upload_eligible_for_active_profile`.

**One production surface mints today**, and the sweep finds it: the off-host
evidence extract verb in ``entrypoints/cli/_ledger_evidence_cli.py``. It passes
because it sources ``profile_eligible`` from the canonical resolver rather than
asserting its own eligibility, so what follows is a statement about a live
surface and not about an empty set.

The sweep would still be non-vacuous at zero call sites, because it also pins
the MECHANISM that makes the zero-site case safe: ``profile_eligible`` is
keyword-only with no default, so a minting surface cannot omit it (that is a
``TypeError``, not an open door), and the gate returns ``False`` whenever it is
``False``.
"""

from __future__ import annotations

import ast
import inspect
from datetime import UTC, datetime
from pathlib import Path

import pytest

from cadrumo.application.user_profile.capabilities import CapabilitySource, resolve_capability

from ....core import ServiceCapability, scan_directory
from ....core.config import Settings, load_settings
from ....domain.user_profile import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....llm import EvidenceConsentToken, LLMConsentError, cloud_evidence_read_permitted, mint_evidence_consent_token

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 6, 15, 10, 0, tzinfo=UTC)
_MINTER = "mint_evidence_consent_token"
_RESOLVER = "cloud_evidence_upload_eligible_for_active_profile"
_PRODUCTION_ROOT = Path(__file__).resolve().parents[3]


def _record(*facts: UserProfileFact) -> UserProfileRecord:
    return UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id="19191919-1919-4191-8191-191919191919",
        facts=facts,
        created_at=_NOW,
        updated_at=_NOW,
    )


def _permitting_settings(*, gestor: bool = False) -> Settings:
    return Settings(cadrumo_evidence_gestor_mode=gestor, cadrumo_evidence_cloud_upload_permitted=True)


# ------------------------------------------------------------------ #
# Default off, and gestor-locked off                                  #
# ------------------------------------------------------------------ #


def test_cloud_evidence_upload_is_the_one_capability_defaulting_off() -> None:
    off = {capability for capability in ServiceCapability if not capability.default_enabled}
    assert off == {ServiceCapability.CLOUD_EVIDENCE_UPLOAD}


def test_an_untouched_profile_is_not_eligible() -> None:
    resolved = resolve_capability(
        ServiceCapability.CLOUD_EVIDENCE_UPLOAD,
        profile_record=None,
        settings=load_settings(),
    )

    assert resolved.enabled is False
    assert resolved.source is CapabilitySource.DEFAULT


def test_gestor_mode_bars_the_capability_over_an_explicit_profile_opt_in() -> None:
    """The bar wins over consent, not the other way round."""
    record = _record(UserProfileFact(path="capabilities.cloud_evidence_upload", value=True))

    resolved = resolve_capability(
        ServiceCapability.CLOUD_EVIDENCE_UPLOAD,
        profile_record=record,
        settings=_permitting_settings(gestor=True),
    )

    assert resolved.enabled is False
    assert resolved.source is CapabilitySource.SAFETY_FLOOR

    # The positive control: the same opt-in DOES take effect without the bar, so
    # the refusal above is the bar's and not a fact that failed to parse.
    without_bar = resolve_capability(
        ServiceCapability.CLOUD_EVIDENCE_UPLOAD,
        profile_record=record,
        settings=_permitting_settings(),
    )
    assert without_bar.enabled is True
    assert without_bar.source is CapabilitySource.PROFILE


# ------------------------------------------------------------------ #
# While off, the gate cannot succeed                                  #
# ------------------------------------------------------------------ #


def test_an_ineligible_profile_is_refused_even_when_everything_else_permits() -> None:
    settings = _permitting_settings()

    assert cloud_evidence_read_permitted(settings, profile_eligible=False, acknowledged=True) is False
    # Positive control: the only difference is the bar.
    assert cloud_evidence_read_permitted(settings, profile_eligible=True, acknowledged=True) is True


def test_no_token_can_be_minted_for_an_ineligible_profile() -> None:
    settings = _permitting_settings()
    kwargs = {"surface": "app.ledger.invoice.read", "evidence_content_address": "b" * 64}

    with pytest.raises(LLMConsentError):
        mint_evidence_consent_token(settings=settings, profile_eligible=False, acknowledged=True, **kwargs)

    # Positive control: minting genuinely works when the bar is on, so the
    # refusal above discriminates the bar rather than a broken minting path.
    token = mint_evidence_consent_token(settings=settings, profile_eligible=True, acknowledged=True, **kwargs)
    assert isinstance(token, EvidenceConsentToken)


def test_the_eligibility_argument_is_keyword_only_and_undefaultable() -> None:
    """What makes the zero-call-site sweep below safe rather than vacuous."""
    for function in (cloud_evidence_read_permitted, mint_evidence_consent_token):
        parameter = inspect.signature(function).parameters["profile_eligible"]
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY, function.__name__
        assert parameter.default is inspect.Parameter.empty, (
            f"{function.__name__}: a defaulted eligibility bar is one a minting surface can forget; "
            "omitting it must be a TypeError"
        )


# ------------------------------------------------------------------ #
# The surface sweep, derived from the production mechanism            #
# ------------------------------------------------------------------ #


def _production_modules() -> list[Path]:
    """Every shipped module, excluding test trees.

    EXCLUDED, and stated rather than silently capped: ``tests/`` trees (a test
    may mint with a literal to exercise the gate itself, which is the point of
    the positive controls above) and non-Python assets. Nothing else is skipped
    -- the walk is the whole ``src/cadrumo`` tree.
    """
    return [
        path
        for path in scan_directory(_PRODUCTION_ROOT, pattern="*.py", recursive=True)
        if "/tests/" not in f"/{path.relative_to(_PRODUCTION_ROOT).as_posix()}"
    ]


def _minting_call_sites() -> list[tuple[str, int, ast.Call]]:
    """Return every production call to the token minter, located by AST.

    An AST walk rather than a text scan: a source slice cannot tell a call from
    a mention in a docstring or a comment, and this module's own prose names the
    function repeatedly.
    """
    sites: list[tuple[str, int, ast.Call]] = []
    for path in _production_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            target = node.func
            name = target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", None)
            if name == _MINTER:
                sites.append((path.relative_to(_PRODUCTION_ROOT).as_posix(), node.lineno, node))
    return sites


def test_every_minting_surface_sources_eligibility_from_the_canonical_resolver() -> None:
    """No surface may assert its own eligibility.

    Passing a literal ``True`` -- or any value not read from the resolver --
    would reinstate a per-surface decision above a profile-scoped bar, which is
    the failure this test exists to prevent.

    **This is no longer vacuous: one production surface mints.** The sweep finds
    ``entrypoints/cli/_ledger_evidence_cli.py``, the off-host evidence extract
    verb, and it passes because that surface sources ``profile_eligible`` from
    the canonical resolver rather than asserting its own. The signature test
    above still holds the line for the next surface to appear.
    """
    offenders: list[str] = []
    for relative, lineno, call in _minting_call_sites():
        argument = next((kw.value for kw in call.keywords if kw.arg == "profile_eligible"), None)
        if argument is None:
            offenders.append(f"{relative}:{lineno} passes no profile_eligible")
            continue
        source = (
            argument.func.attr
            if isinstance(argument, ast.Call) and isinstance(argument.func, ast.Attribute)
            else (argument.func.id if isinstance(argument, ast.Call) and isinstance(argument.func, ast.Name) else None)
        )
        if source != _RESOLVER:
            offenders.append(f"{relative}:{lineno} sources profile_eligible from {ast.dump(argument)[:80]}")

    assert offenders == [], (
        f"consent-minting surface(s) do not read the per-profile eligibility bar through {_RESOLVER}: {offenders}"
    )


def test_the_canonical_resolver_reads_the_capability_it_claims_to() -> None:
    """Anchor the resolver to its capability, so a rename cannot make the sweep pass vacuously."""
    from cadrumo.application.user_profile.capabilities import cloud_evidence_upload_eligible_for_active_profile

    source = inspect.getsource(cloud_evidence_upload_eligible_for_active_profile)
    assert "ServiceCapability.CLOUD_EVIDENCE_UPLOAD" in source
