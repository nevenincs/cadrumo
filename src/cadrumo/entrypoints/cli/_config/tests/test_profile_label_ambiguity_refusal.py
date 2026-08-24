"""Real-behavior CLI tests for ambiguous-profile-label refusal.

``read_profile_bucket`` raises :class:`ProfileLabelAmbiguousError` (a
``WorkflowError``, NOT a ``ValueError``) when two or more LIVE profiles share a
casefold-equal label. The three ``_read_profile_bucket`` call sites in the
config facade (``_resolve_profile_by_label``, ``config profile show``,
``config profile validate``) previously guarded only ``except ValueError``, so
an ambiguous label escaped to an unhandled traceback rather than producing a
clean operator-facing refusal.

These tests provision two LIVE profiles whose committed capsule labels differ
only by case, then drive each surface and assert a clean refusal: a non-zero exit, the
dedicated ambiguity message, and — critically — the absence of the
``ProfileLabelAmbiguousError`` exception name in the output (its presence is the
unhandled-traceback signature the fix eliminates).
"""

from __future__ import annotations

from uuid import UUID

import pytest
from click.testing import Result

from .....tests.cli_runner import invoke_cached_cli
from .....tests.profile_capsule import forge_colliding_capsule_label
from .....tests.secure_sql import isolated_cli_backend as _isolated_cli_backend  # noqa: F401 - autouse fixture
from .....tests.user_profile import register_cli_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _create_profile(name: str, tax_id: str) -> str:
    """Register one live profile through the credential-only creation door."""
    return register_cli_profile(
        label=name,
        facts={
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Test",
            "identity.surnames": "Operator",
            "identity.tax_id": tax_id,
            "activities.description": "Servicios",
            "iva.regime": "GENERAL",
            "tax_residence.jurisdiction_scope": "common_regime",
            "iva.m303_regime_composition": "general",
            "iva.redeme_enrolled": "false",
            "iva.cash_accounting_regime_enrolled": "false",
            "iva.voluntary_sii_enrolled": "false",
            "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
        },
    )


def _provision_casefold_collision() -> None:
    """Create two live profiles, then forge casefold-equal labels onto them.

    Label uniqueness is enforced casefolded by every writer, so this pair
    cannot be provisioned through any operator action -- which is precisely why
    the read-side refusal under test needs the state forged for it.
    """
    # Distinct, valid NIFs: the per-taxpayer uniqueness guard refuses a second
    # profile reusing the first tax id. Control letters per AEAT mod-23 table:
    # 0 -> "T", 1 -> "R".
    alpha = _create_profile("ambig-alpha", "00000000T")
    beta = _create_profile("ambig-beta", "00000001R")

    # "Ambig" and "ambig" compare equal under ``str.casefold`` but are
    # distinct strings, which is the ambiguity the reader must refuse.
    forge_colliding_capsule_label(profile_id=UUID(alpha), label="Ambig")
    forge_colliding_capsule_label(profile_id=UUID(beta), label="ambig")


# English rendering of the dedicated CLI refusal key
# ``errors.refused.refused_profile_label_ambiguous`` (en.yml:3911). The fix
# routes the three call sites to THIS message.
_DEDICATED_REFUSAL_FRAGMENT = "Use the profile UUID to disambiguate"

# English rendering of the workflow-layer error's own translated message
# ``application.workflow.errors.profile_label_ambiguous`` (en.yml:990). Pre-fix,
# ``ProfileLabelAmbiguousError`` escaped the ``except ValueError`` guard to the
# global command boundary, which rendered THIS workflow-layer message instead of
# the dedicated CLI refusal. Its presence is the pre-fix signature.
_WORKFLOW_LAYER_FRAGMENT = "active buckets carry it"


def _assert_clean_ambiguity_refusal(result: Result) -> None:
    """Assert a clean refusal routed through the dedicated CLI ambiguity key.

    Distinguishes the post-fix dedicated CLI refusal from the pre-fix
    workflow-layer message that leaked when the error escaped ``except
    ValueError``. English output is forced by the caller so the assertion is
    locale-stable.
    """
    assert result.exit_code != 0, result.output
    combined = result.output
    stderr = getattr(result, "stderr", None)
    if stderr:
        combined = f"{combined}\n{stderr}"
    # The dedicated CLI refusal key must render (GREEN only after the fix).
    assert _DEDICATED_REFUSAL_FRAGMENT in combined, combined
    # The workflow-layer message must NOT render — its presence is the pre-fix
    # leak the fix eliminates (RED before the fix).
    assert _WORKFLOW_LAYER_FRAGMENT not in combined, combined
    # The raw exception class name must never reach the operator surface.
    assert "ProfileLabelAmbiguousError" not in combined, combined


def test_config_profile_show_ambiguous_label_refuses_cleanly() -> None:
    """``config profile show <label>`` refuses cleanly on a casefold-ambiguous label.

    RED against the pre-fix code: ``read_profile_bucket`` raises
    ``ProfileLabelAmbiguousError`` which escapes the ``except ValueError`` guard
    to an unhandled traceback. GREEN once the ``except
    ProfileLabelAmbiguousError`` clause renders the dedicated refusal.
    """
    _provision_casefold_collision()

    result = invoke_cached_cli(["config", "profile", "show", "ambig", "--language", "en"])

    _assert_clean_ambiguity_refusal(result)


def test_config_profile_validate_ambiguous_label_refuses_cleanly() -> None:
    """``config profile validate <label>`` refuses cleanly on an ambiguous label."""
    _provision_casefold_collision()

    result = invoke_cached_cli(["config", "profile", "validate", "ambig", "--language", "en"])

    _assert_clean_ambiguity_refusal(result)


def test_resolve_profile_by_label_ambiguous_refuses_cleanly() -> None:
    """The ``_resolve_profile_by_label`` path refuses cleanly on an ambiguous label.

    Driven through ``config profile delete <label> --yes``, which resolves the
    operator label via ``_resolve_profile_by_label`` before any destructive
    action — exercising the third patched call site.
    """
    _provision_casefold_collision()

    result = invoke_cached_cli(["config", "profile", "delete", "ambig", "--yes", "--language", "en"])

    _assert_clean_ambiguity_refusal(result)
