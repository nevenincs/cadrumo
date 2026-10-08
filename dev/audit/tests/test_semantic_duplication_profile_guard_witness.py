#!/usr/bin/env python
"""Prove semantic detection of a copied profile-identity guard."""

from __future__ import annotations

from pathlib import Path

import pytest

from ..semantic_duplication import run

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _guard_source(
    *,
    function_name: str,
    request_name: str,
    context_name: str,
    profile_name: str,
    expected_name: str,
    normalization: str,
) -> str:
    """Write a renamed copy of the profile identity comparison into a fixture."""
    lines = (
        f"def {function_name}({request_name}, {context_name}, {profile_name}, {expected_name}=None):",
        f"    subject_ref = profile_operation_subject({normalization}) if {expected_name} is None else {expected_name}",
        "    if (",
        f"        {request_name}.subject_ref != subject_ref",
        f"        or {context_name}.identity.definition_id != {request_name}.definition_id",
        f"        or {context_name}.identity.subject_ref != {request_name}.subject_ref",
        "    ):",
        "        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)",
    )
    return "\n".join(lines) + "\n"


def _guard_pair(package: Path, *, right_normalization: str = "str(bucket_id)") -> Path:
    package.mkdir()
    (package / "left.py").write_text(
        _guard_source(
            function_name="require_identity",
            request_name="request",
            context_name="context",
            profile_name="profile_id",
            expected_name="expected_subject_ref",
            normalization="str(profile_id)",
        ),
        encoding="utf-8",
    )
    (package / "right.py").write_text(
        _guard_source(
            function_name="verify_identity",
            request_name="operation",
            context_name="executor",
            profile_name="bucket_id",
            expected_name="override_subject_ref",
            normalization=right_normalization,
        ),
        encoding="utf-8",
    )
    return package


def test_call_fingerprint_reports_renamed_profile_guard_copies(tmp_path: Path) -> None:
    package = _guard_pair(tmp_path / "cadrumo")

    candidates = run(package, ["call_fingerprint"])

    matches = [
        candidate
        for candidate in candidates
        if candidate.detector == "call_fingerprint"
        and {site.split(":", 1)[0] for site in candidate.sites} == {"left.py", "right.py"}
    ]
    assert len(matches) == 1
    assert {site.rsplit(" ", 1)[-1] for site in matches[0].sites} == {"require_identity", "verify_identity"}


def test_call_fingerprint_does_not_match_a_different_subject_normalizer(tmp_path: Path) -> None:
    package = _guard_pair(tmp_path / "cadrumo", right_normalization="canonical_profile_id(bucket_id)")

    assert run(package, ["call_fingerprint"]) == []
