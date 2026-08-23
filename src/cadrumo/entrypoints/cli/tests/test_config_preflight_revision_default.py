"""CLI surface tests for `aeat config profile preflight` revision defaulting.

These tests prove the operator-surface decision: ``--revision-id`` is no longer
required. When omitted, the active registry revision for the natural key
(modelo, filing year, period) is resolved through the modelo-addressing
resolver, which consumes the :class:`ValidatedRegistryAuthority`. An explicit
``--revision-id`` is honoured as an exact-replay override. An unresolvable or
ambiguous natural key refuses instructively, never with a bare error.

Every test runs against a real encrypted profile bucket and the real bundled
calculation registry; no mocks, stubs, or patches participate. The ambiguous
case installs a forged twin revision into the live authority's modelo map and
restores it in ``finally`` so the genuine ``select_revision`` dedup branch and
the genuine refusal-translation path are exercised end to end.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import cast
from uuid import UUID

import pytest
from click.testing import Result

from ....core import Period
from ....core.resources import resources
from ....tests.cli_runner import invoke_cached_cli
from ....tests.profile_capsule import open_test_profile_session
from ....tests.secure_sql import isolated_profile_storage
from ....tests.user_profile import register_minimal_profile

__all__ = ["isolated_profile_storage"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _seed_active_profile(name: str = "operator", *, overrides: Mapping[str, str] | None = None) -> None:
    """Provision and activate a real minimal profile bucket.

    ``register_minimal_profile`` populates ``identity.tax_id`` and an
    activity so the profile carries the basics; preflight then reports
    only the modelo-specific selectors still missing (or none).
    """
    digest = bytearray(hashlib.sha256(name.encode("utf-8")).digest()[:16])
    digest[6] = (digest[6] & 0x0F) | 0x40
    digest[8] = (digest[8] & 0x3F) | 0x80
    profile_id = str(UUID(bytes=bytes(digest)))
    with open_test_profile_session(profile_id):
        register_minimal_profile(profile_id=profile_id, display_name=name, overrides=overrides)


def _json_payload(result: Result) -> dict[str, object]:
    match = re.search(r"\{.*\}", result.output, re.DOTALL)
    assert match, result.output
    parsed: object = json.loads(match.group(0))
    assert isinstance(parsed, dict)
    assert all(isinstance(key, str) for key in parsed)
    return cast(dict[str, object], parsed)


def _active_revision_for(modelo: str, *, filing_year: int, period: str) -> str:
    """Resolve the expected active revision from the registry authority.

    Derives the expected value from the same authority the production
    resolver reads, not from a hand-copied literal: a registry edit that
    moves the active revision moves this expectation with it.
    """
    from ....application.modelo import resolve_registry_revision_for_work_target

    return resolve_registry_revision_for_work_target(
        modelo=modelo,
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, period),
        registry_revision_id=None,
    )


def test_preflight_defaults_revision_from_natural_key() -> None:
    """Preflight answers from modelo, filing year, and period alone."""
    _seed_active_profile()
    expected_revision = _active_revision_for("303", filing_year=2026, period="1T")

    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "config",
            "profile",
            "preflight",
            "--modelo",
            "303",
            "--filing-year",
            "2026",
            "--period",
            "1T",
        ],
    )

    assert result.exit_code in (0, 2), result.output
    payload = _json_payload(result)
    result_data_obj = payload["result"]
    assert isinstance(result_data_obj, dict)
    assert all(isinstance(key, str) for key in result_data_obj)
    result_data = cast(dict[str, object], result_data_obj)
    assert result_data["modelo"] == "303"
    assert result_data["filing_year"] == 2026
    # ``period`` is the typed Period, not a bare registry-token string, so a
    # malformed or year-mismatched coordinate is refused at the CLI boundary.
    assert result_data["period"] == {"filing_year": 2026, "code": "1T"}
    # The resolved active revision is reported back, proving the natural-key
    # default fired rather than leaving the field blank or erroring.
    assert result_data["revision_id"] == expected_revision


def test_preflight_explicit_revision_override_is_honoured() -> None:
    """An explicit --revision-id selects that exact revision for replay."""
    _seed_active_profile()
    expected_revision = _active_revision_for("303", filing_year=2026, period="1T")

    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "config",
            "profile",
            "preflight",
            "--modelo",
            "303",
            "--filing-year",
            "2026",
            "--period",
            "1T",
            "--revision-id",
            expected_revision,
        ],
    )

    assert result.exit_code in (0, 2), result.output
    payload = _json_payload(result)
    result_data_obj = payload["result"]
    assert isinstance(result_data_obj, dict)
    assert all(isinstance(key, str) for key in result_data_obj)
    result_data = cast(dict[str, object], result_data_obj)
    assert result_data["revision_id"] == expected_revision


def test_preflight_reports_legal_entity_export_legal_name_requirement() -> None:
    """Legal-entity M202 preflight must include export-header profile facts.

    The command resolves a registry revision from the natural key, then passes
    that revision into the profile preflight service. Without the revision,
    export-header requirements such as ``identity.legal_name`` are invisible
    and the CLI can claim readiness before modelo work creation refuses.
    """
    _seed_active_profile(
        "sl-no-legal-name",
        overrides={
            "identity.tax_id": "B66012345",
            "identity.name": "Visible SL",
            "identity.surnames": "Visible SL",
            "activities.description": "asesoria",
            "taxpayer_type.entity_type": "legal_entity",
            "taxpayer_type.legal_entity_form": "sl",
            "taxpayer_type.irpf_income_categories": "",
            "taxpayer_type.incn_prior_12_months": "500000",
            "irpf.estimation_regime": "",
        },
    )

    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "config",
            "profile",
            "preflight",
            "--modelo",
            "202",
            "--filing-year",
            "2026",
            "--period",
            "1P",
        ],
    )

    assert result.exit_code == 2, result.output
    payload = _json_payload(result)
    result_data_obj = payload["result"]
    assert isinstance(result_data_obj, dict)
    assert all(isinstance(key, str) for key in result_data_obj)
    result_data = cast(dict[str, object], result_data_obj)
    assert result_data["ready"] is False
    missing_obj = result_data["missing"]
    assert isinstance(missing_obj, list)
    legal_name_rows = [
        row
        for row in missing_obj
        if isinstance(row, dict)
        and row.get("selector") == "export.header.legal_name"
        and row.get("section_key") == "identity"
        and row.get("field_key") == "legal_name"
    ]
    assert len(legal_name_rows) == 1
    assert legal_name_rows[0]["label"]
    assert legal_name_rows[0]["label"] != "export.header.legal_name"

    text_result = invoke_cached_cli(
        [
            "config",
            "profile",
            "preflight",
            "--modelo",
            "202",
            "--filing-year",
            "2026",
            "--period",
            "1P",
        ],
    )
    assert text_result.exit_code == 2, text_result.output
    assert "identity\tlegal_name" in text_result.output


def test_preflight_refuses_unresolvable_natural_key_with_discovery_pointer() -> None:
    """A period the modelo never declares refuses with a discovery pointer."""
    _seed_active_profile()

    result = invoke_cached_cli(
        ["config", "profile", "preflight", "--modelo", "303", "--filing-year", "2026", "--period", "ZZ"],
    )

    assert result.exit_code != 0
    # The refusal must point at the discovery command, never a bare error.
    assert "aeat app modelo describe 303" in result.output


def test_preflight_refuses_invalid_explicit_override_with_registered_revisions() -> None:
    """An explicit --revision-id unknown to the modelo refuses instructively."""
    _seed_active_profile()

    result = invoke_cached_cli(
        [
            "config",
            "profile",
            "preflight",
            "--modelo",
            "303",
            "--filing-year",
            "2026",
            "--period",
            "1T",
            "--revision-id",
            "not-a-real-revision",
        ],
    )

    assert result.exit_code != 0
    assert "aeat app modelo describe 303" in result.output


def test_preflight_refuses_ambiguous_natural_key_with_candidates() -> None:
    """When two revisions match the natural key, preflight lists candidates.

    The bundled registry is authored without overlapping revisions, so a
    real twin revision is installed into the live authority's modelo map for
    the duration of the test and restored afterwards. This exercises the
    genuine ``select_revision`` dedup branch and the genuine candidate-listing
    refusal translation, with no mock or patch object in play.
    """
    _seed_active_profile()
    authority = resources().modelos.authority
    definition = authority.modelo("303")
    base_revision = authority.snapshot("303", filing_year=2026, period="1T").revision
    twin = base_revision.model_copy(update={"id": f"{base_revision.id}-twin"})
    ambiguous = definition.model_copy(update={"revisions": {**definition.revisions, twin.id: twin}})
    original = authority._modelos_by_id["303"]
    authority._modelos_by_id["303"] = ambiguous
    try:
        result = invoke_cached_cli(
            ["config", "profile", "preflight", "--modelo", "303", "--filing-year", "2026", "--period", "1T"],
        )
    finally:
        authority._modelos_by_id["303"] = original

    assert result.exit_code != 0
    # Both candidate revision ids must be named so the operator can pick one.
    assert str(base_revision.id) in result.output
    assert str(twin.id) in result.output
    assert "--revision-id" in result.output


def test_ambiguous_resolution_carries_candidates_on_typed_field_not_message() -> None:
    """The preflight resolver discriminates the ambiguous case by exception
    TYPE and reads the candidate ids from the typed field, not by matching a
    substring of the human-readable message.

    This pins the robustness contract: a rewording of the
    ``AmbiguousRevisionSelectionError`` ``str()`` message must NOT break the
    operator-facing candidate listing, because the resolver never parses the
    message. The test installs a real twin revision into the live authority
    (no mock) so the genuine ``select_revision`` dedup branch fires, then
    asserts the refusal context carries both candidate ids verbatim.
    """
    from ....domain.calculations.registry import AmbiguousRevisionSelectionError
    from .._config._profile_inspect import _resolve_preflight_revision_id
    from .._errors import CliRefusedBoundaryError

    authority = resources().modelos.authority
    definition = authority.modelo("303")
    base_revision = authority.snapshot("303", filing_year=2026, period="1T").revision
    twin = base_revision.model_copy(update={"id": f"{base_revision.id}-twin"})
    ambiguous = definition.model_copy(update={"revisions": {**definition.revisions, twin.id: twin}})
    original = authority._modelos_by_id["303"]
    authority._modelos_by_id["303"] = ambiguous
    try:
        with pytest.raises(CliRefusedBoundaryError) as excinfo:
            _resolve_preflight_revision_id(
                modelo="303",
                period=Period.from_year_and_code(2026, "1T"),
                revision_id=None,
            )
    finally:
        authority._modelos_by_id["303"] = original

    refusal = excinfo.value
    # The refusal was raised from the typed ambiguous subclass...
    cause = refusal.__cause__
    assert isinstance(cause, AmbiguousRevisionSelectionError)
    # ...and the candidate ids rode on the typed field, sorted.
    assert cause.candidate_ids == tuple(sorted((str(base_revision.id), str(twin.id))))
    # The refusal context lists both ids so the operator surface stays intact
    # even though no message substring was parsed.
    assert refusal.context is not None
    candidates = refusal.context["candidates"]
    assert isinstance(candidates, str)
    assert str(base_revision.id) in candidates
    assert str(twin.id) in candidates
