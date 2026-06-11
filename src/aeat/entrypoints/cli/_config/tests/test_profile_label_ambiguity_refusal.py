"""Real-behavior CLI tests for ambiguous-profile-label refusal.

``read_profile_bucket`` raises :class:`ProfileLabelAmbiguousError` (a
``WorkflowError``, NOT a ``ValueError``) when two or more LIVE profiles share a
casefold-equal label. The three ``_read_profile_bucket`` call sites in the
config facade (``_resolve_profile_by_label``, ``config profile show``,
``config profile validate``) previously guarded only ``except ValueError``, so
an ambiguous label escaped to an unhandled traceback rather than producing a
clean operator-facing refusal.

These tests provision two LIVE profiles whose manifest labels differ only by
case, then drive each surface and assert a clean refusal: a non-zero exit, the
dedicated ambiguity message, and — critically — the absence of the
``ProfileLabelAmbiguousError`` exception name in the output (its presence is the
unhandled-traceback signature the fix eliminates).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from click.testing import Result

from .....adapters.persistence.storage.bucket import (
    bucket_paths,
    read_manifest,
    write_manifest,
)
from .....core.config import load_settings, override_settings
from .....tests.cli_runner import invoke_cached_cli
from .....tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_cli_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        override_settings(
            aeat_token_dir=tmp_path / "tokens",
            aeat_runs_dir=tmp_path / "runs",
            aeat_financial_txs_dir=tmp_path / "txs",
            aeat_invoices_dir=tmp_path / "invoices",
            aeat_drafts_dir=tmp_path / "drafts",
        ),
    ):
        yield


def _create_profile(name: str, tax_id: str) -> None:
    """Provision a real live profile through the canonical CLI create path."""
    result = invoke_cached_cli(
        [
            "config",
            "profile",
            "create",
            name,
            "--quiet",
            "--tax-id",
            tax_id,
            "--activity",
            "Servicios",
            "--iva-regime",
            "GENERAL",
        ],
    )
    assert result.exit_code == 0, result.output


def _relabel_bucket(bucket_id: str, new_label: str) -> None:
    """Rewrite one live bucket's manifest label, leaving everything else intact.

    The CLI create path enforces label uniqueness, so two casefold-equal labels
    cannot be provisioned directly. Two profiles are created with distinct
    labels, then their on-disk manifest labels are rewritten to a casefold-equal
    pair — both profiles remain ACTIVE with a real bucket directory, DB, and
    keystore; only the plaintext manifest label changes.
    """
    root = load_settings().aeat_local_storage_root
    assert root is not None
    paths = bucket_paths(root, bucket_id)
    manifest = read_manifest(paths)
    write_manifest(paths, manifest.model_copy(update={"label": new_label}))


def _provision_casefold_collision() -> None:
    """Create two live profiles whose manifest labels are casefold-equal."""
    # Distinct, valid NIFs: the per-taxpayer uniqueness guard refuses a second
    # profile reusing the first tax id. Control letters per AEAT mod-23 table:
    # 0 -> "T", 1 -> "R".
    _create_profile("ambig-alpha", "00000000T")
    _create_profile("ambig-beta", "00000001R")

    from .....application.workflow import list_profile_buckets

    root = load_settings().aeat_local_storage_root
    assert root is not None
    pointers = list(list_profile_buckets(root=root).values())
    by_label = {p.label: p.bucket_id for p in pointers}
    assert "ambig-alpha" in by_label, pointers
    assert "ambig-beta" in by_label, pointers

    # Collapse the two distinct labels onto a casefold-equal pair: "Ambig"
    # and "ambig" compare equal under ``str.casefold`` but are distinct strings.
    _relabel_bucket(by_label["ambig-alpha"], "Ambig")
    _relabel_bucket(by_label["ambig-beta"], "ambig")


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
