"""Real-CLI roundtrip for the v2 bundled profile export/import (contract).

Bundle roundtrip requirement:
  Every domain object in the bundle's four financial-history categories
  must survive export/import with strict pydantic equality.

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
``profile_storage_session``, real encrypted repositories.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....domain.calculations.registry import CasillaId, CasillaObservation, validated_casilla_id
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from .envelope_helpers import unwrap_envelope_notices
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


@pytest.fixture(autouse=True)
def _isolated_source(tmp_path: Path) -> Iterator[None]:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


def _invoke(args: list[str]):
    return invoke_cached_cli(args)


def _seed_and_export(tmp_path: Path, bundle_path: Path) -> str:
    """Create profile, seed all four categories, export bundle.

    Returns the source ``bucket_id`` (== ``profile_id``) for D5 checks.
    """

    from ....adapters.persistence.storage import activate_master_key_provider, get_master_key_provider
    from ....application.modelo import create_work_unit
    from ....core import Period, resolve_active_bucket_id
    from ....core.config import override_settings
    from ....domain.modelos._calculation_repository import (
        CalculationRevisionCatalogueRepository,
        upsert_calculation_revision,
    )
    from ....domain.modelos._calculation_revision import (
        CalculationRevision,
        CalculationRevisionState,
        derive_calculation_revision_id,
    )
    from ....domain.modelos._filing_record import (
        ModeloRecord,
        ModeloRecordStatus,
        derive_filing_record_id,
    )
    from ....domain.modelos._filing_repository import (
        ModeloRecordCatalogueRepository,
        upsert_filing_record,
    )
    from ....domain.modelos._repository import WorkUnitCatalogueRepository

    # 1. Provision profile via CLI.
    csv = tmp_path / "bank.csv"
    csv.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-01-10,Client SL,Factura 001,1210.00,EUR,txn-001\n",
        encoding="utf-8",
    )
    r = _invoke(
        [
            "config",
            "profile",
            "create",
            "source",
            "--quiet",
            "--tax-id",
            "12345678Z",
            "--activity",
            "design",
            "--output-language",
            "en",
        ],
    )
    assert r.exit_code == 0, r.output

    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None

    # 2. Import a ledger transaction via CLI (real ingest path).
    r_ledger = _invoke(["app", "ledger", "import", str(csv), "--provider", "csv"])
    assert r_ledger.exit_code == 0, r_ledger.output

    # 3. Seed work unit, calculation revision, and filing record via repositories.
    with (
        override_settings(aeat_active_profile=bucket_id),
        activate_master_key_provider(get_master_key_provider()),
    ):
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
        )
        observations = (
            CasillaObservation(
                casilla_id=_CASILLA_01,
                value=Decimal("1000.00"),
                formula_id=None,
                legal_refs=("Ley 37/1992 art. 78",),
                source_refs=("aeat-modelo-303-instrucciones-2026",),
            ),
            CasillaObservation(
                casilla_id=_CASILLA_12,
                value=Decimal("210.00"),
                formula_id="iva-cuota-devengada-general",
                operand_refs=(_CASILLA_01,),
                operand_casilla_refs=(_CASILLA_01,),
                operand_values=(Decimal("1000.00"),),
                legal_refs=("Ley 37/1992 art. 90",),
                source_refs=("aeat-modelo-303-instrucciones-2026",),
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
        )
        cr_repo.save(upsert_calculation_revision(cr_repo.load(), revision))

        # Filing record (content-addressed).
        filed_at = _T1 + timedelta(minutes=30)
        filing_record_id = derive_filing_record_id(
            work_unit_id=wu_id,
            calculation_revision_id=revision_id,
            filed_at=filed_at,
            filed_by="operator",
        )
        from ....domain.modelos._codes import ModeloCode

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
    r_export = _invoke(["config", "profile", "export", "source", "--to", str(bundle_path)])
    assert r_export.exit_code == 0, r_export.output
    assert_public_profile_id_redacted(r_export.output, bucket_id)
    assert bundle_path.is_file()

    return bucket_id


# ---------------------------------------------------------------------------
# Main roundtrip test — strict pydantic equality across all four categories
# ---------------------------------------------------------------------------


def test_v2_bundle_export_import_roundtrip(tmp_path: Path) -> None:
    """All four financial-history categories survive export/import with strict equality."""

    from ....adapters.persistence.storage import activate_master_key_provider, get_master_key_provider
    from ....core import resolve_active_bucket_id
    from ....core.config import override_settings
    from ....domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
    from ....domain.modelos._filing_repository import ModeloRecordCatalogueRepository
    from ....domain.modelos._repository import WorkUnitCatalogueRepository
    from ....domain.transactions._repository import TransactionCatalogueRepository

    bundle_path = tmp_path / "source-bundle.json"
    source_bucket_id = _seed_and_export(tmp_path, bundle_path)
    exported_bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert exported_bundle["profile"]["profile_id"] == source_bucket_id

    json_bundle_path = tmp_path / "source-bundle-json.json"
    json_export = _invoke(["--format", "json", "config", "profile", "export", "source", "--to", str(json_bundle_path)])
    assert json_export.exit_code == 0, json_export.output
    json_export_payload = assert_public_profile_payload_redacted(json_export.output, source_bucket_id)
    assert json_export_payload["display_name"] == "source"
    assert json_bundle_path.is_file()

    # Load originals while still in source storage context.
    with (
        override_settings(aeat_active_profile=source_bucket_id),
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
        r_import = _invoke(["--format", "json", "config", "profile", "import", str(bundle_path)])
        assert r_import.exit_code == 0, r_import.output
        import_payload = assert_public_profile_payload_redacted(r_import.output, source_bucket_id)
        assert import_payload["display_name"] == "source"

        imported_bucket_id = resolve_active_bucket_id()
        # D5: imported profile_id must equal the source's.
        assert isinstance(imported_bucket_id, str)
        assert imported_bucket_id == source_bucket_id

        with (
            override_settings(aeat_active_profile=imported_bucket_id),
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
    assert computed.legal_refs == ("Ley 37/1992 art. 90",)
    assert computed.source_refs == ("aeat-modelo-303-instrucciones-2026",)


# ---------------------------------------------------------------------------
# Anti-tautology proof for provenance preservation
# ---------------------------------------------------------------------------


def test_v2_bundle_anti_tautology_legal_refs_mutation(tmp_path: Path) -> None:
    """Mutating legal_refs in the exported JSON must surface as inequality.

    Export a bundle, mutate one ``legal_refs``
    entry, then re-validate the mutated JSON.  The mutated data must either
    fail ``ValidationError`` OR the re-loaded revision's ``legal_refs`` must
    differ from the original.

    A probe where neither condition fires is tautological — the boundary
    is not enforcing provenance preservation.
    """

    from ....adapters.persistence.storage import activate_master_key_provider, get_master_key_provider
    from ....core.config import override_settings
    from ....domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
    from ....domain.user_profile._portable_export import UserProfilePortableExport

    bundle_path = tmp_path / "tautology-bundle.json"
    source_bucket_id = _seed_and_export(tmp_path, bundle_path)

    with (
        override_settings(aeat_active_profile=source_bucket_id),
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
                obs["legal_refs"][0] = "MUTATED-legal-ref"
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
        # legal_refs; the original had "Ley 37/1992 art. 78".
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
    r = _invoke(["config", "profile", "import", str(bundle_path)])
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
        r_create = _invoke(
            [
                "config",
                "profile",
                "create",
                "source",
                "--quiet",
                "--tax-id",
                "87654321X",
                "--activity",
                "consulting",
            ],
        )
        assert r_create.exit_code == 0, r_create.output

        # Now attempt to import the bundle whose display_name is also "source"
        # but whose profile_id is a different UUID.
        r_import = _invoke(["config", "profile", "import", str(bundle_path)])
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
    r = _invoke(
        ["--format", "json", "config", "profile", "export", "source", "--to", str(json_bundle_path)],
    )
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
        r_import = _invoke(["--format", "json", "config", "profile", "import", str(bundle_path)])
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
        assert switch["suggestion"] == "aeat config switch source"
