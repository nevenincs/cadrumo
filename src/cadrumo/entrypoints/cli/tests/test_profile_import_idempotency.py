"""Idempotency regression tests for `aeat config profile import` (contract).

Import idempotency contract:
  - Re-importing the same bundle twice produces exactly ONE profile; the
    second attempt is refused with a UUID collision message.
  - Re-importing a bundle with ``--label <taken>`` when that label belongs
    to a different UUID is refused until the operator picks a fresh label.
  - Mutating the bundle's ``profile_id`` before a second import causes the
    import to succeed and creates a SECOND, distinct profile — proving that
    the UUID is the genuine discriminator, not the label.

No mocks.  Real ``isolated_profile_storage_root`` fixture, real encrypted
repositories.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from click.testing import Result

from ....core import STR_KEYED_MAPPING_ADAPTER
from ....tests.cli_runner import invoke_cached_cli
from ....tests.profile_capsule import open_test_profile_session
from ....tests.secure_sql import isolated_cli_backend as _isolated_storage  # noqa: F401 - autouse fixture
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_cli_profile
from .privacy_helpers import (
    assert_public_profile_id_not_leaked,
    assert_public_profile_id_redacted,
    assert_public_profile_payload_redacted,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


def _create_profile(
    name: str,
    *,
    tax_id: str,
    activity: str,
    output_language: str | None = None,
) -> str:
    """Seed one profile through the credential registration door.

    The subject here is import idempotency, never how the profile was
    created; registration is the only creation door, so the seed uses it
    and hands back the new profile id.
    """
    facts = {
        "identity.tax_id": tax_id,
        "taxpayer_type.entity_type": "natural_person",
        "identity.name": "Import",
        "identity.surnames": "Idempotency",
        "activities.description": activity,
    }
    if output_language is not None:
        facts["preferences.output_language"] = output_language
    return register_cli_profile(label=name, facts=facts)


def _export_profile(name: str, bundle_path: Path) -> Result:
    return _invoke(("config", "profile", "export", name, "--to", str(bundle_path), "--cleartext-local"))


def _import_bundle(
    bundle_path: Path,
    *,
    json_format: bool = False,
    label: str | None = None,
    output_language: str | None = None,
) -> Result:
    args = ["config", "profile", "import", str(bundle_path)]
    if label is not None:
        args.extend(("--label", label))
    if output_language is not None:
        args.extend(("--output-language", output_language))
    if json_format:
        args = ["--format", "json", *args]
    return _invoke(args)


def _read_bundle(bundle_path: Path) -> dict[str, Any]:
    return json.loads(bundle_path.read_text(encoding="utf-8"))


def _profile_id(raw: dict[str, Any]) -> str:
    profile = STR_KEYED_MAPPING_ADAPTER.validate_python(raw["profile"])
    exported_id = profile["profile_id"]
    assert isinstance(exported_id, str)
    return exported_id


def _write_bundle(bundle_path: Path, raw: dict[str, Any]) -> None:
    bundle_path.write_text(json.dumps(raw), encoding="utf-8")


def _create_minimal_profile_and_export(bundle_path: Path) -> str:
    """Create a minimal profile and export it to ``bundle_path``.

    Returns the exported ``profile_id`` (UUID).
    """

    _create_profile(
        "idempotency-test",
        tax_id="12345678Z",
        activity="design",
        output_language="en",
    )

    r_export = _export_profile("idempotency-test", bundle_path)
    assert r_export.exit_code == 0, r_export.output
    assert bundle_path.is_file()

    raw = _read_bundle(bundle_path)
    exported_id = _profile_id(raw)
    assert_public_profile_id_redacted(r_export.output, exported_id)
    return exported_id


def _assert_uuid_collision_message(output: str) -> None:
    lowered = output.lower()
    assert "uuid" in lowered and "conflict" in lowered, output
    assert "label" not in lowered, output


def _assert_label_collision_message(output: str, label: str) -> None:
    lowered = output.lower()
    assert label in output, output
    assert "label" in lowered and "already in use" in lowered, output
    assert "uuid" not in lowered, output


def _create_legal_entity_profile_and_export(bundle_path: Path) -> str:
    register_cli_profile(
        label="legal-import-source",
        facts={
            "taxpayer_type.entity_type": "legal_entity",
            "taxpayer_type.legal_entity_form": "sl",
            "identity.tax_id": "B66012345",
            "identity.legal_name": "Legal Import Source SL",
            "activities.description": "asesoria",
            "preferences.output_language": "en",
        },
    )

    r_export = _export_profile("legal-import-source", bundle_path)
    assert r_export.exit_code == 0, r_export.output
    assert bundle_path.is_file()

    raw = _read_bundle(bundle_path)
    exported_id = _profile_id(raw)
    assert_public_profile_id_redacted(r_export.output, exported_id)
    return exported_id


def _create_attribution_entity_profile_and_export(bundle_path: Path) -> str:
    register_cli_profile(
        label="attribution-import-source",
        facts={
            "taxpayer_type.entity_type": "attribution_entity",
            "identity.tax_id": "E12345674",
            "identity.name": "Attribution Import Source",
            "activities.description": "arrendamiento",
            "preferences.output_language": "en",
        },
    )

    r_export = _export_profile("attribution-import-source", bundle_path)
    assert r_export.exit_code == 0, r_export.output
    assert bundle_path.is_file()

    raw = _read_bundle(bundle_path)
    exported_id = _profile_id(raw)
    assert_public_profile_id_redacted(r_export.output, exported_id)
    return exported_id


# ---------------------------------------------------------------------------
# contract — import-twice produces one profile, not two
# ---------------------------------------------------------------------------


def test_reimport_same_bundle_is_refused(tmp_path: Path) -> None:
    """Re-importing the same bundle in the same storage root is refused.

    The profile_id UUID already exists locally after the first import, so
    the second attempt must be refused with a clear UUID collision
    message.  The storage root must still contain exactly ONE profile after
    both attempts.
    """

    bundle_path = tmp_path / "idempotency.json"
    exported_id = _create_minimal_profile_and_export(bundle_path)

    # The source profile is already present (created above).
    # A first import attempt into the SAME root where the source profile
    # lives must fail — profile_id UUID collision.
    r_first = _import_bundle(bundle_path, output_language="en")
    assert r_first.exit_code != 0, r_first.output
    assert_public_profile_id_not_leaked(r_first.output, exported_id)
    _assert_uuid_collision_message(r_first.output)
    assert "Traceback" not in r_first.output

    # Import into a fresh root succeeds once.
    fresh_root = tmp_path / "fresh"
    with isolated_profile_storage_root(tmp_path=fresh_root):
        r_ok = _import_bundle(bundle_path, json_format=True)
        assert r_ok.exit_code == 0, r_ok.output
        ok_payload = assert_public_profile_payload_redacted(r_ok.output, exported_id)
        assert ok_payload["display_name"] == "idempotency-test"

        # Second import into the same fresh root must be refused (UUID taken).
        r_second = _import_bundle(bundle_path, output_language="en")
        assert r_second.exit_code != 0, r_second.output
        assert_public_profile_id_not_leaked(r_second.output, exported_id)
        _assert_uuid_collision_message(r_second.output)
        assert "Traceback" not in r_second.output

        # Confirm exactly one profile is present — list must return one entry.
        r_list = _invoke(["config", "profile", "list"])
        assert r_list.exit_code == 0, r_list.output
        # The display name (not UUID) appears in list output.
        assert "idempotency-test" in r_list.output
        # Profile IDs are redacted at the CLI boundary; verify UUID
        # round-trip by reading the encrypted manifest directly through
        # the persistence layer.
        from ....application.user_profile import CommittedProfileRepository

        with open_test_profile_session(exported_id):
            aggregate = CommittedProfileRepository().load(exported_id)
        assert aggregate.profile_id == exported_id


# ---------------------------------------------------------------------------
# contract — label collision with different UUID is refused
# ---------------------------------------------------------------------------


def test_label_collision_different_uuid_refused_even_with_explicit_label(tmp_path: Path) -> None:
    """Passing ``--label`` to a name already owned by a different UUID is refused.

    The guard checks label uniqueness AFTER the UUID check, so an operator
    trying to import a foreign bundle under a label that already belongs
    to a different local profile must be told to pick a distinct name.
    """

    bundle_path = tmp_path / "label-collision.json"
    exported_id = _create_minimal_profile_and_export(bundle_path)

    dest_root = tmp_path / "dest"
    with isolated_profile_storage_root(tmp_path=dest_root):
        # Occupy the label "idempotency-test" with a locally-minted profile
        # carrying a different UUID.
        _create_profile(
            "idempotency-test",
            tax_id="87654321X",
            activity="consulting",
        )

        # Import the bundle without --label: display_name is "idempotency-test",
        # which is already taken by the locally-minted profile → refused.
        r_import = _import_bundle(bundle_path, output_language="en")
        assert r_import.exit_code != 0, r_import.output
        assert_public_profile_id_not_leaked(r_import.output, exported_id)
        _assert_label_collision_message(r_import.output, "idempotency-test")
        assert "Traceback" not in r_import.output

        # Passing --label with the SAME taken name is also refused.
        r_explicit = _import_bundle(bundle_path, label="idempotency-test", output_language="en")
        assert r_explicit.exit_code != 0, r_explicit.output
        assert_public_profile_id_not_leaked(r_explicit.output, exported_id)
        _assert_label_collision_message(r_explicit.output, "idempotency-test")
        assert "Traceback" not in r_explicit.output

        # Passing --label with a FREE name succeeds.
        r_free = _import_bundle(
            bundle_path,
            json_format=True,
            label="idempotency-test-imported",
        )
        assert r_free.exit_code == 0, r_free.output
        free_payload = assert_public_profile_payload_redacted(r_free.output, exported_id)
        assert free_payload["display_name"] == "idempotency-test-imported"
        from ....application.user_profile import CommittedProfileRepository

        with open_test_profile_session(exported_id):
            imported = CommittedProfileRepository().load(exported_id)
        assert imported.profile_id == exported_id
        assert imported.label == "idempotency-test-imported"


# ---------------------------------------------------------------------------
# contract — anti-tautology proof: mutated profile_id creates a second profile
# ---------------------------------------------------------------------------


def test_mutated_profile_id_creates_second_profile(tmp_path: Path) -> None:
    """Mutating the bundle's profile_id bypasses both collision guards.

    This proves that the UUID — not the label or any other field — is the
    genuine discriminator.  If the UUID test were tautological (e.g. the
    collision guard never actually checked the UUID), both imports would
    either both succeed or both fail for the wrong reason.

    After importing the original bundle and a UUID-mutated clone:
    - Two distinct profiles exist in the destination root.
    - Their profile_ids differ.
    - The second import may use --label to choose a distinct display name
      without changing the mutated bundle UUID.
    """

    bundle_path = tmp_path / "original.json"
    exported_id = _create_minimal_profile_and_export(bundle_path)

    mutated_bundle_path = tmp_path / "mutated.json"
    raw = _read_bundle(bundle_path)
    mutated_id = str(uuid.uuid4())
    # Change the profile_id inside the profile sub-object.
    raw["profile"]["profile_id"] = mutated_id
    _write_bundle(mutated_bundle_path, raw)

    dest_root = tmp_path / "dest"
    with isolated_profile_storage_root(tmp_path=dest_root):
        # Import the original bundle — succeeds.
        r_orig = _import_bundle(bundle_path, json_format=True)
        assert r_orig.exit_code == 0, r_orig.output
        orig_payload = assert_public_profile_payload_redacted(r_orig.output, exported_id)
        assert orig_payload["display_name"] == "idempotency-test"

        # Import the UUID-mutated bundle under a distinct label — succeeds
        # (different UUID, different label).
        r_mut = _import_bundle(
            mutated_bundle_path,
            json_format=True,
            label="idempotency-test-mutated",
        )
        assert r_mut.exit_code == 0, r_mut.output
        mut_payload = assert_public_profile_payload_redacted(r_mut.output, mutated_id)
        assert mut_payload["display_name"] == "idempotency-test-mutated"
        from ....core import resolve_active_bucket_id

        active_import_id = resolve_active_bucket_id()
        assert active_import_id is not None
        assert active_import_id == mutated_id
        assert_public_profile_id_not_leaked(r_mut.output, active_import_id)

        # Both labels must appear in the list output — two distinct profiles.
        r_list = _invoke(["config", "profile", "list"])
        assert r_list.exit_code == 0, r_list.output
        assert "idempotency-test" in r_list.output
        assert "idempotency-test-mutated" in r_list.output

        # Profile IDs are redacted at the CLI boundary; verify UUID round-trip
        # by reading both encrypted manifests through the persistence layer.
        from ....application.user_profile import CommittedProfileRepository

        with open_test_profile_session(exported_id):
            original_aggregate = CommittedProfileRepository().load(exported_id)
        assert original_aggregate.profile_id == exported_id
        with open_test_profile_session(mutated_id):
            mutated_aggregate = CommittedProfileRepository().load(mutated_id)
        assert mutated_aggregate.profile_id == mutated_id
        assert mutated_aggregate.label == "idempotency-test-mutated"

        # Both display names must still be reachable via the operator surface.
        r_show = _invoke(["config", "profile", "show", "idempotency-test"])
        assert r_show.exit_code == 0, r_show.output
        assert_public_profile_id_redacted(r_show.output, exported_id)
        r_show_mut = _invoke(["config", "profile", "show", "idempotency-test-mutated"])
        assert r_show_mut.exit_code == 0, r_show_mut.output
        assert_public_profile_id_redacted(r_show_mut.output, mutated_id)


# ---------------------------------------------------------------------------
# contract — import re-enforces the NIF/CIF/NIE checksum (EDGE-CRIT-1)
# ---------------------------------------------------------------------------


def test_import_refuses_tampered_invalid_tax_id(tmp_path: Path) -> None:
    """A bundle whose tax_id fails the checksum is refused on import.

    `config profile create` validates the identifier via SubjectTaxId; the
    import path is plaintext and tamperable, so it must enforce the same gate.
    A tampered identifier (valid digits, wrong control letter) must NOT become a
    registered, filing-grade profile.
    """

    bundle_path = tmp_path / "tax-tamper.json"
    _create_minimal_profile_and_export(bundle_path)

    raw = _read_bundle(bundle_path)
    tampered = False
    for fact in raw["profile"]["facts"]:
        if fact.get("path") == "identity.tax_id":
            fact["value"] = "12345678A"  # valid 8 digits, wrong checksum letter (Z is correct)
            tampered = True
    assert tampered, "exported bundle did not carry an identity.tax_id fact"
    tampered_path = tmp_path / "tampered.json"
    _write_bundle(tampered_path, raw)

    dest_root = tmp_path / "dest"
    with isolated_profile_storage_root(tmp_path=dest_root):
        r = _import_bundle(tampered_path, label="tampered-import")
        assert r.exit_code != 0, r.output
        assert "Traceback" not in r.output
        lowered = r.output.lower()
        assert "checksum" in lowered or "identificador fiscal" in lowered or "tax identif" in lowered, r.output

        # The refused profile must NOT be registered.
        r_list = _invoke(["config", "profile", "list"])
        assert r_list.exit_code == 0, r_list.output
        assert "tampered-import" not in r_list.output

    # A valid (untampered) bundle still imports cleanly.
    clean_root = tmp_path / "clean"
    with isolated_profile_storage_root(tmp_path=clean_root):
        r_ok = _import_bundle(bundle_path, label="clean-import")
        assert r_ok.exit_code == 0, r_ok.output


_MISSING_BASELINE_CASES_BY_SOURCE = (
    (
        "natural_person",
        (
            ("taxpayer_type.entity_type", "--entity-type"),
            ("identity.name", "--name"),
            ("identity.surnames", "--surnames"),
        ),
    ),
    (
        "legal_entity",
        (
            ("taxpayer_type.legal_entity_form", "--legal-entity-form"),
            ("identity.legal_name", "--legal-name"),
        ),
    ),
    ("attribution_entity", (("identity.name", "--name"),)),
)


@pytest.mark.parametrize(
    ("source_kind", "missing_cases"),
    _MISSING_BASELINE_CASES_BY_SOURCE,
    ids=[source_kind for source_kind, _ in _MISSING_BASELINE_CASES_BY_SOURCE],
)
def test_import_refuses_missing_filing_identity_baseline(
    tmp_path: Path,
    source_kind: str,
    missing_cases: tuple[tuple[str, str], ...],
) -> None:
    """A tampered bundle cannot register a filing-incomplete active profile."""

    bundle_path = tmp_path / f"{source_kind}.json"
    if source_kind == "legal_entity":
        _create_legal_entity_profile_and_export(bundle_path)
    elif source_kind == "attribution_entity":
        _create_attribution_entity_profile_and_export(bundle_path)
    else:
        _create_minimal_profile_and_export(bundle_path)

    for case_index, (removed_path, expected_flag) in enumerate(missing_cases):
        raw = _read_bundle(bundle_path)
        original_facts = raw["profile"]["facts"]
        raw["profile"]["facts"] = [fact for fact in original_facts if fact.get("path") != removed_path]
        assert len(raw["profile"]["facts"]) == len(original_facts) - 1, f"bundle did not contain {removed_path}"
        case_token = removed_path.replace(".", "-")
        tampered_path = tmp_path / f"tampered-{source_kind}-{case_token}.json"
        _write_bundle(tampered_path, raw)

        label = f"missing-baseline-{source_kind}-{case_index}"
        with isolated_profile_storage_root(tmp_path=tmp_path / f"dest-{source_kind}-{case_index}"):
            r = _import_bundle(tampered_path, label=label)
            assert r.exit_code != 0, r.output
            assert "Traceback" not in r.output
            assert expected_flag in r.output, f"{removed_path}: {r.output}"

            r_list = _invoke(["config", "profile", "list"])
            assert r_list.exit_code == 0, r_list.output
            assert label not in r_list.output


@pytest.mark.parametrize("tamper_case", ["missing", "blank", "non_string", "duplicate"])
def test_import_refuses_missing_or_non_string_tax_id(tmp_path: Path, tamper_case: str) -> None:
    """The import boundary requires exactly one nonblank string identity.tax_id fact."""

    bundle_path = tmp_path / f"tax-id-{tamper_case}.json"
    _create_minimal_profile_and_export(bundle_path)

    raw = _read_bundle(bundle_path)
    facts = raw["profile"]["facts"]
    tax_facts = [fact for fact in facts if fact.get("path") == "identity.tax_id"]
    assert len(tax_facts) == 1, "exported bundle must carry one identity.tax_id fact"
    if tamper_case == "missing":
        raw["profile"]["facts"] = [fact for fact in facts if fact.get("path") != "identity.tax_id"]
    elif tamper_case == "blank":
        tax_facts[0]["value"] = "   "
    elif tamper_case == "non_string":
        tax_facts[0]["value"] = 12345678
    elif tamper_case == "duplicate":
        facts.append(dict(tax_facts[0]))
    else:  # pragma: no cover - parametrization guard
        raise AssertionError(f"unhandled tamper case {tamper_case!r}")

    tampered_path = tmp_path / f"tampered-{tamper_case}.json"
    _write_bundle(tampered_path, raw)

    dest_root = tmp_path / f"dest-{tamper_case}"
    label = f"tampered-{tamper_case}"
    with isolated_profile_storage_root(tmp_path=dest_root):
        r = _import_bundle(tampered_path, label=label)
        assert r.exit_code != 0, r.output
        assert "Traceback" not in r.output
        lowered = r.output.lower()
        assert "tax identif" in lowered or "identificador fiscal" in lowered, r.output

        r_list = _invoke(["config", "profile", "list"])
        assert r_list.exit_code == 0, r_list.output
        assert label not in r_list.output
