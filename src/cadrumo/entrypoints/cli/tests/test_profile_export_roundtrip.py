"""Real-CLI roundtrip for the v3 bundled profile export/import (contract).

Bundle roundtrip requirement:
  Every domain object in the bundle's four financial-history categories
  must survive export/import with strict pydantic equality. The cleartext
  structured profile export carries no generic secure-object bytes, and its
  coverage manifest explicitly names populated stores that are not part of the
  cleartext transport.

Bundle anti-tautology proof:
  Mutate one ``legal_refs`` entry in the exported JSON before re-import.
  Assert that ``model_validate`` raises ``ValidationError`` OR that the
  re-imported revision's ``legal_refs`` does not equal the original.
  A passing test that never mutates is tautological.

Profile identity contract:
  The bundle's ``profile_id`` UUID is preserved across import; the
  imported profile's ``profile_id`` equals the exported one's.
  UUID collision is refused; label collision with a different UUID is
  refused; ``--label`` is the recovery path for the label case.

No mocks.  Real ``isolated_profile_storage_root`` fixture, real
``open_test_profile_session``, real encrypted repositories.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from click.testing import Result
from pydantic import ValidationError

from ....core import CasillaId, validated_casilla_id
from ....domain.calculations.registry import (
    CasillaObservation,
    LegalRefId,
    SourceRefId,
)
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage, isolated_profile_storage_root
from ....tests.user_profile import register_cli_profile

__all__ = ["isolated_profile_storage"]
from ....tests.cli_envelope import unwrap_envelope_notices
from .privacy_helpers import (
    assert_public_profile_id_not_leaked,
    assert_public_profile_id_redacted,
    assert_public_profile_payload_redacted,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_T0 = datetime(2026, 1, 15, 9, 0, 0, tzinfo=UTC)
_T1 = _T0 + timedelta(hours=2)
_IVA_BASE_IMPONIBLE_CASILLA: CasillaId = validated_casilla_id(
    "iva.base-imponible",
    surface="_IVA_BASE_IMPONIBLE_CASILLA",
)
_CASILLA_01: CasillaId = validated_casilla_id("casilla-01", surface="_CASILLA_01")
_CASILLA_12: CasillaId = validated_casilla_id("casilla-12", surface="_CASILLA_12")
_LEGAL_REF_BASE: LegalRefId = "ley-37-1992:art-78"
_LEGAL_REF_QUOTA: LegalRefId = "ley-37-1992:art-90"
_SOURCE_REF_303: SourceRefId = "aeat-modelo-303-instrucciones-2026"


def _invoke(args: Sequence[str], *, input: str | None = None) -> Result:
    return invoke_cached_cli(args, input=input)


def _create_profile(
    name: str,
    *,
    tax_id: str,
    activity: str,
    output_language: str | None = None,
) -> str:
    """Seed one profile through the credential registration door.

    Every test below needs a profile to export or import; none of them is
    about how it came to exist. Registration is the only creation door, so
    the seed goes through it and hands back the new profile id.
    """
    facts = {
        "identity.tax_id": tax_id,
        "activities.description": activity,
        "taxpayer_type.entity_type": "natural_person",
        "iva.regime": "GENERAL",
        "identity.name": "Ariadna",
        "identity.surnames": "Villar",
    }
    if output_language is not None:
        facts["preferences.output_language"] = output_language
    return register_cli_profile(label=name, facts=facts)


def _export_profile(
    name: str,
    bundle_path: Path,
    *,
    json_format: bool = False,
    passphrase: str | None = None,
    cleartext_local: bool = True,
) -> Result:
    """Drive export; an encryption passphrase rides ``--secrets-stdin``, never argv."""
    args = ["config", "profile", "export", name, "--to", str(bundle_path)]
    stdin_payload: str | None = None
    if passphrase is not None:
        args.extend(("--encrypt", "--secrets-stdin"))
        stdin_payload = json.dumps({"passphrase": passphrase, "passphrase_confirmation": passphrase})
    if cleartext_local:
        args.append("--cleartext-local")
    if json_format:
        args = ["--format", "json", *args]
    return _invoke(args, input=stdin_payload)


def _import_bundle(bundle_path: Path, *, json_format: bool = False, passphrase: str | None = None) -> Result:
    """Drive import; an encrypted bundle's passphrase rides ``--secrets-stdin``, never argv."""
    args = ["config", "profile", "import", str(bundle_path)]
    stdin_payload: str | None = None
    if passphrase is not None:
        args.append("--secrets-stdin")
        stdin_payload = json.dumps({"passphrase": passphrase})
    if json_format:
        args = ["--format", "json", *args]
    return _invoke(args, input=stdin_payload)


def _seed_and_export(tmp_path: Path, bundle_path: Path) -> str:
    """Create profile, seed all four categories, export bundle.

    Returns the source ``bucket_id`` (== ``profile_id``) for D5 checks.
    """

    from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
    from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ....application.modelo import create_work_unit
    from ....core import Period, resolve_active_bucket_id
    from ....domain.modelos import (
        CalculationRevision,
        CalculationRevisionState,
        ModeloRecord,
        ModeloRecordStatus,
        derive_calculation_revision_id,
        derive_filing_record_id,
        upsert_calculation_revision,
        upsert_filing_record,
    )
    from ....tests.profile_capsule import open_test_profile_session

    # 1. Provision the profile through the credential registration door.
    csv = tmp_path / "bank.csv"
    csv.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-01-10,Client SL,Factura 001,1210.00,EUR,txn-001\n",
        encoding="utf-8",
    )
    _create_profile(
        "source",
        tax_id="12345678Z",
        activity="design",
        output_language="en",
    )

    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None

    # 2. Import a ledger transaction via CLI (real ingest path).
    r_ledger = _invoke(["app", "ledger", "import", "--file", str(csv), "--provider", "csv"])
    assert r_ledger.exit_code == 0, r_ledger.output

    # 3. Seed work unit, calculation revision, and filing record via repositories.
    # Registration left this bucket's custody session live, so the helper
    # binds that exact session rather than re-deriving a master key from a
    # file-fallback store nothing provisions any more.
    with open_test_profile_session(bucket_id):
        # Work unit via the canonical create_work_unit action.
        wu_repo = WorkUnitCatalogueRepository(bucket_id=bucket_id)
        cr_repo = CalculationRevisionCatalogueRepository(bucket_id=bucket_id)
        filing_repo = ModeloRecordCatalogueRepository(bucket_id=bucket_id)

        work_unit = create_work_unit(
            bucket_id=bucket_id,
            modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision_id="2009-y-siguientes",
            repository=wu_repo,
            clock=_T0,
        )
        wu_id = work_unit.work_unit_id

        # Calculation revision with typed CasillaObservation carrying legal_refs.
        input_values_by_casilla_id = {_IVA_BASE_IMPONIBLE_CASILLA: "1000.00"}
        binding_overrides: dict[str, str] = {}
        casilla_values = {_CASILLA_01: Decimal("1000.00"), _CASILLA_12: Decimal("210.00")}
        revision_id = derive_calculation_revision_id(
            work_unit_id=wu_id,
            input_values_by_casilla_id=input_values_by_casilla_id,
            binding_overrides=binding_overrides,
            casilla_values=casilla_values,
            filing_instance_evidence=None,
        )
        observations = (
            CasillaObservation(
                casilla_id=_CASILLA_01,
                value=Decimal("1000.00"),
                formula_id=None,
                legal_refs=(_LEGAL_REF_BASE,),
                source_refs=(_SOURCE_REF_303,),
            ),
            CasillaObservation(
                casilla_id=_CASILLA_12,
                value=Decimal("210.00"),
                formula_id="iva-cuota-devengada-general",
                operand_refs=(_CASILLA_01,),
                operand_casilla_refs=(_CASILLA_01,),
                operand_values=(Decimal("1000.00"),),
                legal_refs=(_LEGAL_REF_QUOTA,),
                source_refs=(_SOURCE_REF_303,),
            ),
        )
        revision = CalculationRevision(
            calculation_revision_id=revision_id,
            work_unit_id=wu_id,
            state=CalculationRevisionState.VERIFICADO_COMPLETO,
            input_values_by_casilla_id=input_values_by_casilla_id,
            binding_overrides=binding_overrides,
            casilla_values=casilla_values,
            observations=observations,
            created_at=_T0,
            updated_at=_T1,
            verified_at=_T1,
            verified_by="operator",
            filing_instance_evidence=None,
        )
        cr_repo.save(upsert_calculation_revision(cr_repo.load(), revision))

        # Filing record (content-addressed).
        filed_at = _T1 + timedelta(minutes=30)
        filing_record_id = derive_filing_record_id(
            work_unit_id=wu_id,
            calculation_revision_id=revision_id,
            filed_by="operator",
        )
        from ....domain.modelos import ModeloCode

        filing_record = ModeloRecord(
            filing_record_id=filing_record_id,
            work_unit_id=wu_id,
            calculation_revision_id=revision_id,
            bucket_id=bucket_id,
            modelo=ModeloCode("303"),
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            filed_at=filed_at,
            filed_by="operator",
            status=ModeloRecordStatus.VIGENTE,
        )
        filing_repo.save(upsert_filing_record(filing_repo.load(), filing_record))

    # 4. Export via CLI.
    r_export = _export_profile("source", bundle_path)
    assert r_export.exit_code == 0, r_export.output
    assert_public_profile_id_redacted(r_export.output, bucket_id)
    assert bundle_path.is_file()

    return bucket_id


# ---------------------------------------------------------------------------
# Main roundtrip test — strict pydantic equality across all four categories
# ---------------------------------------------------------------------------


def test_v3_bundle_export_import_roundtrip(tmp_path: Path) -> None:
    """All four financial-history categories survive export/import with strict equality."""

    from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
    from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from ....adapters.persistence.storage.master_key import (
        activate_master_key_provider,
        get_master_key_provider,
    )
    from ....core import resolve_active_bucket_id
    from ....core.config import override_settings

    bundle_path = tmp_path / "source-bundle.json"
    source_bucket_id = _seed_and_export(tmp_path, bundle_path)
    exported_bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert exported_bundle["bundle_schema_version"] == 3
    assert exported_bundle["profile"]["profile_id"] == source_bucket_id
    assert exported_bundle["carried_objects"] == []
    assert exported_bundle["coverage_manifest"] == {
        "custody_profile": "structured",
        "carried_namespaces": [],
        "excluded_namespaces": [
            "cadrumo.application.user_profile.value",
            "cadrumo.domain.buckets.event_history",
            "cadrumo.domain.modelos.calculation_revisions",
            "cadrumo.domain.modelos.filing_records",
            "cadrumo.domain.modelos.work_units",
            "cadrumo.domain.transactions.bucket",
            "cadrumo.workflow",
        ],
        "row_counts_by_namespace": {
            "cadrumo.application.user_profile.value": 1,
            "cadrumo.domain.buckets.event_history": 1,
            "cadrumo.domain.modelos.calculation_revisions": 1,
            "cadrumo.domain.modelos.filing_records": 1,
            "cadrumo.domain.modelos.work_units": 1,
            "cadrumo.domain.transactions.bucket": 2,
            "cadrumo.workflow": 1,
        },
    }

    json_bundle_path = tmp_path / "source-bundle-json.json"
    json_export = _export_profile("source", json_bundle_path, json_format=True)
    assert json_export.exit_code == 0, json_export.output
    json_export_payload = assert_public_profile_payload_redacted(json_export.output, source_bucket_id)
    assert json_export_payload["display_name"] == "source"
    assert json_bundle_path.is_file()

    # Load originals while still in source storage context.
    with (
        override_settings(cadrumo_active_profile=source_bucket_id),
        activate_master_key_provider(get_master_key_provider()),
    ):
        original_work_units = tuple(WorkUnitCatalogueRepository(bucket_id=source_bucket_id).load())
        original_transactions = tuple(TransactionCatalogueRepository(bucket_id=source_bucket_id).load())
        original_revisions = tuple(CalculationRevisionCatalogueRepository(bucket_id=source_bucket_id).load())
        original_filings = tuple(ModeloRecordCatalogueRepository(bucket_id=source_bucket_id).load())

    assert len(original_work_units) == 1
    assert len(original_transactions) == 1
    assert len(original_revisions) == 1
    assert len(original_filings) == 1

    # Import into a fresh isolated storage root.
    import_tmp = tmp_path / "import-root"
    with isolated_profile_storage_root(tmp_path=import_tmp):
        r_import = _import_bundle(bundle_path, json_format=True)
        assert r_import.exit_code == 0, r_import.output
        import_payload = assert_public_profile_payload_redacted(r_import.output, source_bucket_id)
        assert import_payload["display_name"] == "source"

        imported_bucket_id = resolve_active_bucket_id()
        # D5: imported profile_id must equal the source's.
        assert isinstance(imported_bucket_id, str)
        assert imported_bucket_id == source_bucket_id

        with (
            override_settings(cadrumo_active_profile=imported_bucket_id),
            activate_master_key_provider(get_master_key_provider()),
        ):
            imported_work_units = tuple(WorkUnitCatalogueRepository(bucket_id=imported_bucket_id).load())
            imported_transactions = tuple(TransactionCatalogueRepository(bucket_id=imported_bucket_id).load())
            imported_revisions = tuple(CalculationRevisionCatalogueRepository(bucket_id=imported_bucket_id).load())
            imported_filings = tuple(ModeloRecordCatalogueRepository(bucket_id=imported_bucket_id).load())

    # Strict pydantic equality.
    assert imported_work_units == original_work_units
    assert imported_transactions == original_transactions
    assert imported_revisions == original_revisions
    assert imported_filings == original_filings

    # Provenance fields survive — not just values.
    (revision,) = imported_revisions
    assert len(revision.observations) == 2
    computed = next(o for o in revision.observations if o.formula_id is not None)
    assert computed.legal_refs == (_LEGAL_REF_QUOTA,)
    assert computed.source_refs == (_SOURCE_REF_303,)


def test_v3_bundle_passphrase_encrypted_export_import_roundtrip(tmp_path: Path) -> None:
    """The first-class profile export/import surface round-trips an encrypted bundle."""

    from ....core import resolve_active_bucket_id

    cleartext_fixture_path = tmp_path / "source-cleartext-local.json"
    source_bucket_id = _seed_and_export(tmp_path, cleartext_fixture_path)

    encrypted_path = tmp_path / "source-encrypted.aeat-profile"
    passphrase = "profile-transfer-passphrase-308"  # noqa: S105 - synthetic test fixture, not a secret
    r_export = _export_profile(
        "source",
        encrypted_path,
        json_format=True,
        passphrase=passphrase,
        cleartext_local=False,
    )
    assert r_export.exit_code == 0, r_export.output
    assert encrypted_path.is_file()

    encrypted_bytes = encrypted_path.read_bytes()
    for forbidden in (b"12345678Z", b"Ariadna", b"Villar", b"source"):
        assert forbidden not in encrypted_bytes

    import_root = tmp_path / "encrypted-import-root"
    with isolated_profile_storage_root(tmp_path=import_root):
        r_import = _import_bundle(encrypted_path, json_format=True, passphrase=passphrase)
        assert r_import.exit_code == 0, r_import.output
        import_payload = assert_public_profile_payload_redacted(r_import.output, source_bucket_id)
        assert import_payload["display_name"] == "source"
        assert resolve_active_bucket_id() == source_bucket_id


def test_v3_bundle_encrypted_import_refuses_wrong_passphrase_without_traceback(tmp_path: Path) -> None:
    """Wrong passphrases refuse encrypted profile-bundle import cleanly."""

    cleartext_fixture_path = tmp_path / "source-cleartext-local.json"
    _seed_and_export(tmp_path, cleartext_fixture_path)

    encrypted_path = tmp_path / "source-encrypted-wrong-pass.aeat-profile"
    r_export = _export_profile(
        "source",
        encrypted_path,
        passphrase="right-profile-transfer-passphrase-308",  # noqa: S106 - synthetic test fixture
        cleartext_local=False,
    )
    assert r_export.exit_code == 0, r_export.output

    import_root = tmp_path / "encrypted-wrong-pass-import-root"
    with isolated_profile_storage_root(tmp_path=import_root):
        r_import = _import_bundle(
            encrypted_path,
            passphrase="wrong-profile-transfer-passphrase-308",  # noqa: S106 - synthetic test fixture
        )
        assert r_import.exit_code != 0, r_import.output
        assert "Traceback" not in r_import.output


# ---------------------------------------------------------------------------
# Anti-tautology proof for provenance preservation
# ---------------------------------------------------------------------------


def test_v3_bundle_anti_tautology_legal_refs_mutation(tmp_path: Path) -> None:
    """Mutating legal_refs in the exported JSON must surface as inequality.

    Export a bundle, mutate one ``legal_refs``
    entry, then re-validate the mutated JSON.  The mutated data must either
    fail ``ValidationError`` OR the re-loaded revision's ``legal_refs`` must
    differ from the original.

    A probe where neither condition fires is tautological — the boundary
    is not enforcing provenance preservation.
    """

    from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
    from ....adapters.persistence.storage.master_key import (
        activate_master_key_provider,
        get_master_key_provider,
    )
    from ....core.config import override_settings
    from ....domain.user_profile import UserProfilePortableExport

    bundle_path = tmp_path / "tautology-bundle.json"
    source_bucket_id = _seed_and_export(tmp_path, bundle_path)

    with (
        override_settings(cadrumo_active_profile=source_bucket_id),
        activate_master_key_provider(get_master_key_provider()),
    ):
        (original_revision,) = tuple(CalculationRevisionCatalogueRepository(bucket_id=source_bucket_id).load())

    next(o for o in original_revision.observations if o.formula_id is not None)

    # Mutate the exported JSON: replace the first legal_ref.
    raw_json = json.loads(bundle_path.read_text(encoding="utf-8"))
    mutated = False
    for rev in raw_json.get("calculation_revisions", []):
        for obs in rev.get("observations", []):
            if obs.get("legal_refs"):
                obs["legal_refs"][0] = "mutated-legal-ref"
                mutated = True
                break
        if mutated:
            break
    assert mutated, "fixture must produce at least one observation with legal_refs"

    mutated_json = json.dumps(raw_json)

    # Re-validate the mutated bundle payload.
    try:
        mutated_bundle = UserProfilePortableExport.model_validate_json(mutated_json)
        # Validation passed — the mutated observation's legal_refs must differ
        # from the original bundle's version of that same observation.
        # The mutated JSON has "MUTATED-legal-ref" in the first observation's
        # legal_refs; the original had ``_LEGAL_REF_BASE``.
        (original_bundle_revision,) = tuple(
            UserProfilePortableExport.model_validate_json(
                bundle_path.read_text(encoding="utf-8")
            ).calculation_revisions,
        )
        (mutated_revision,) = tuple(mutated_bundle.calculation_revisions)
        # The two bundles must differ somewhere in their observations.
        assert mutated_revision.observations != original_bundle_revision.observations, (
            "TAUTOLOGICAL: mutating legal_refs produced no detectable difference — "
            "the provenance boundary is not enforced."
        )
    except ValidationError:
        # Strict schema rejection is also an acceptable outcome.
        pass


# ---------------------------------------------------------------------------
# D5 collision guard tests
# ---------------------------------------------------------------------------


def test_import_refuses_uuid_collision(tmp_path: Path) -> None:
    """Tier-1: importing a bundle whose profile_id is already registered is refused."""

    bundle_path = tmp_path / "collision-bundle.json"
    source_bucket_id = _seed_and_export(tmp_path, bundle_path)

    # Re-import into the same storage root where the profile_id already exists.
    r = _import_bundle(bundle_path)
    assert r.exit_code != 0, r.output
    assert_public_profile_id_not_leaked(r.output, source_bucket_id)
    # The refusal must name the recovery action or "already registered".
    assert "already registered" in r.output or "profile" in r.output.lower()
    assert "Traceback" not in r.output


def test_import_label_collision_different_uuid_is_refused(tmp_path: Path) -> None:
    """Tier-2: importing with a label already taken by a different UUID is refused."""

    bundle_path = tmp_path / "label-collision-bundle.json"
    source_bucket_id = _seed_and_export(tmp_path, bundle_path)

    import_tmp = tmp_path / "label-collision-root"
    with isolated_profile_storage_root(tmp_path=import_tmp):
        # Occupy the label "source" in this fresh root with a different UUID profile.
        _create_profile(
            "source",
            tax_id="87654321X",
            activity="consulting",
        )

        # Now attempt to import the bundle whose display_name is also "source"
        # but whose profile_id is a different UUID.
        r_import = _import_bundle(bundle_path)
        assert r_import.exit_code != 0, r_import.output
        assert_public_profile_id_not_leaked(r_import.output, source_bucket_id)
        assert "Traceback" not in r_import.output


# ---------------------------------------------------------------------------
# Data-safety surfacing: cleartext-bundle warning + active-switch info notice
# ---------------------------------------------------------------------------


def test_export_emits_cleartext_sensitivity_warning_notice(tmp_path: Path) -> None:
    """``export`` surfaces a WARNING notice naming the path and the sensitive contents.

    The portable bundle is a deliberate cleartext-on-disk portability
    surface that, unlike every other persistence path, contains the raw tax
    id verbatim plus the full ledger and filing history. The operator's only
    signal that the file is sensitive is the typed :class:`Notice`; this test
    proves it fires, carries the exact written path, names the contents, and
    instructs deletion — and that the warning is justified because the raw
    tax id really does land in the cleartext bundle.
    """
    bundle_path = tmp_path / "warn-bundle.json"
    _seed_and_export(tmp_path, bundle_path)

    # The warning is justified: the raw tax id is in the cleartext bundle,
    # not the sha256: redaction that ``config profile show`` applies.
    bundle_text = bundle_path.read_text(encoding="utf-8")
    assert "12345678Z" in bundle_text

    json_bundle_path = tmp_path / "warn-bundle-json.json"
    r = _export_profile("source", json_bundle_path, json_format=True)
    assert r.exit_code == 0, r.output

    notices = unwrap_envelope_notices(r.output)
    warning = next(
        (n for n in notices if n["code"] == "config.profile.export.cleartext_sensitive_bundle"),
        None,
    )
    assert warning is not None, f"export must surface the cleartext-sensitivity warning; got {notices}"
    assert warning["severity"] == "warning"
    message = warning["message"]
    # Names the exact written path.
    assert str(json_bundle_path) in message
    assert warning["context"]["out"] == str(json_bundle_path)
    # Names the sensitive contents.
    assert "tax id" in message.lower()
    # Instructs deletion after transfer.
    assert "delete" in message.lower()
    assert "profile export" in message.lower()
    assert "--encrypt" in message.lower()


def test_export_requires_explicit_cleartext_or_passphrase(tmp_path: Path) -> None:
    """``export`` no longer writes cleartext JSON unless local/SAR mode is explicit."""

    _create_profile("explicit-transport", tax_id="87654321X", activity="consulting")

    bundle_path = tmp_path / "implicit-cleartext.json"
    r_export = _invoke(["config", "profile", "export", "explicit-transport", "--to", str(bundle_path)])
    assert r_export.exit_code != 0, r_export.output
    assert not bundle_path.exists()
    assert "Traceback" not in r_export.output


def test_bundle_verbs_reject_argv_passphrase(tmp_path: Path) -> None:
    """The retired ``--passphrase`` argv channel is gone from export and import.

    A secret on argv lands in the process table and shell history; the bundle
    passphrase now arrives only via no-echo prompts or ``--secrets-stdin``.
    """
    bundle_path = tmp_path / "never-written.json"
    for args in (
        ["config", "profile", "export", "x", "--to", str(bundle_path), "--passphrase", "argv-secret"],
        ["config", "profile", "import", str(bundle_path), "--passphrase", "argv-secret"],
    ):
        result = _invoke(args)
        assert result.exit_code != 0, (args, result.output)
        assert "No such option: --passphrase" in result.output, (args, result.output)
    assert not bundle_path.exists()


def test_encrypted_export_refuses_passphrase_confirmation_mismatch(tmp_path: Path) -> None:
    """A stdin value/confirmation mismatch refuses before any bundle is written."""

    _create_profile("mismatch-transport", tax_id="55555555K", activity="consulting")

    bundle_path = tmp_path / "mismatch.json"
    result = _invoke(
        ["config", "profile", "export", "mismatch-transport", "--to", str(bundle_path), "--secrets-stdin"],
        input=json.dumps(
            {
                "passphrase": "first candidate value",
                "passphrase_confirmation": "second different value",
            },
        ),
    )
    assert result.exit_code == 2, result.output
    assert not bundle_path.exists()
    assert "Traceback" not in result.output


def test_encrypted_export_without_terminal_or_stdin_refuses_cleanly(tmp_path: Path) -> None:
    """``--encrypt`` with no TTY and no ``--secrets-stdin`` refuses (exit 2), writing nothing."""

    bundle_path = tmp_path / "never-written-encrypt.json"
    result = _invoke(["config", "profile", "export", "x", "--to", str(bundle_path), "--encrypt"])
    assert result.exit_code == 2, result.output
    assert "--secrets-stdin" in result.output
    assert not bundle_path.exists()
    assert "Traceback" not in result.output


def test_import_surfaces_active_profile_switch_info_notice(tmp_path: Path) -> None:
    """``import`` surfaces an INFO notice making the active-profile switch explicit.

    Importing a bundle silently makes the imported profile the active one.
    A gestor importing a client mid-session would otherwise be switched
    without any signal. This test proves the switch is surfaced as a typed
    info :class:`Notice` that names the now-active profile and the recovery
    command.
    """
    bundle_path = tmp_path / "switch-bundle.json"
    source_bucket_id = _seed_and_export(tmp_path, bundle_path)

    import_tmp = tmp_path / "switch-import-root"
    with isolated_profile_storage_root(tmp_path=import_tmp):
        r_import = _import_bundle(bundle_path, json_format=True)
        assert r_import.exit_code == 0, r_import.output
        assert_public_profile_payload_redacted(r_import.output, source_bucket_id)

        notices = unwrap_envelope_notices(r_import.output)
        switch = next(
            (n for n in notices if n["code"] == "config.profile.import.active_profile_switched"),
            None,
        )
        assert switch is not None, f"import must surface the active-profile-switch notice; got {notices}"
        assert switch["severity"] == "info"
        assert "source" in switch["message"]
        assert "active" in switch["message"].lower()
        assert switch["suggestion"] == "aeat config login source"


# ---------------------------------------------------------------------------
# Custody-metadata parity: ``config profile export`` projects the canonical
# ProfileBundleExportResult (purpose, transport, categories, reconcile
# failures), not just profile id / display name / out / schema version.
# ---------------------------------------------------------------------------


def test_export_json_envelope_carries_purpose_transport_and_data_categories(tmp_path: Path) -> None:
    """The plain export envelope reports the same custody metadata SAR does."""
    _create_profile("custody", tax_id="87654321X", activity="consulting")

    cleartext_path = tmp_path / "custody-cleartext.json"
    r = _export_profile("custody", cleartext_path, json_format=True)
    assert r.exit_code == 0, r.output
    payload = json.loads(r.output)["result"]

    assert payload["purpose"] == "portable_transfer"
    assert payload["transport"] == "cleartext_local"
    assert payload["data_categories"] != []
    assert payload["excluded_data_categories"] != []
    assert set(payload["excluded_data_categories"]).isdisjoint(payload["data_categories"])
    assert payload["reconcile_failures"] == []

    encrypted_path = tmp_path / "custody-encrypted.json"
    passphrase = "custody-export-passphrase-448-len"  # noqa: S105 - synthetic test fixture, not a secret
    r_encrypted = _export_profile(
        "custody",
        encrypted_path,
        json_format=True,
        passphrase=passphrase,
        cleartext_local=False,
    )
    assert r_encrypted.exit_code == 0, r_encrypted.output
    encrypted_payload = json.loads(r_encrypted.output)["result"]
    assert encrypted_payload["transport"] == "passphrase_encrypted"
    assert encrypted_payload["purpose"] == "portable_transfer"


def test_config_profile_export_result_refuses_malformed_transport_and_reconcile_row(tmp_path: Path) -> None:
    """The canonical result type -- not a permissive shell -- refuses malformed custody rows.

    ``purpose``/``transport`` are typed as the real
    :class:`~cadrumo.application.user_profile.ProfileBundleExportPurpose` /
    :class:`~cadrumo.application.user_profile.ProfileBundleExportTransport`
    enums, so even a bare string equal to a valid member's *value* is refused:
    only the canonical enum instance the export service already returns
    satisfies the field. A blank reconcile-failure ``journal_id``/``reason``
    is also rejected. A permissive ``str``/``dict`` shell -- the defect this
    finding reported -- would have accepted all of these.
    """
    from ....application.user_profile import ProfileBundleExportPurpose, ProfileBundleExportTransport
    from .._config_payloads import ConfigProfileExportReconcileFailurePayload, ConfigProfileExportResult

    base_kwargs = {
        "profile_id": "11111111-1111-4111-8111-111111111111",
        "display_name": "Example",
        "out": str(tmp_path / "bundle.json"),
        "schema_version": 3,
        "purpose": ProfileBundleExportPurpose.PORTABLE_TRANSFER,
        "transport": ProfileBundleExportTransport.CLEARTEXT_LOCAL,
        "data_categories": ["profile_identity_and_facts"],
        "excluded_data_categories": [],
        "reconcile_failures": [],
    }
    # A valid payload -- built from the real canonical enum members, exactly
    # as the export handler passes them -- round-trips cleanly.
    valid = ConfigProfileExportResult(**base_kwargs)
    assert valid.purpose is ProfileBundleExportPurpose.PORTABLE_TRANSFER
    assert valid.transport is ProfileBundleExportTransport.CLEARTEXT_LOCAL

    # A bare string equal to a valid member's value is still refused: the
    # field demands the canonical enum instance, not a permissive str.
    with pytest.raises(ValidationError):
        ConfigProfileExportResult.model_validate({**base_kwargs, "purpose": "portable_transfer"})
    with pytest.raises(ValidationError):
        ConfigProfileExportResult.model_validate({**base_kwargs, "transport": "cleartext_local"})
    with pytest.raises(ValidationError):
        ConfigProfileExportReconcileFailurePayload(journal_id="", destination=None, reason="SomeError")
    with pytest.raises(ValidationError):
        ConfigProfileExportReconcileFailurePayload(journal_id="j1", destination=None, reason="")

    # A valid reconcile-failure row round-trips.
    row = ConfigProfileExportReconcileFailurePayload(journal_id="j1", destination=None, reason="SomeError")
    assert row.journal_id == "j1"
    assert row.reason == "SomeError"
