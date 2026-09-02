"""Scratch conversion helper for the production-assert retirement batch."""

from __future__ import annotations

import pathlib

BASE = pathlib.Path("src/cadrumo/application")


def sub(name: str, old: str, new: str, count: int = 1) -> None:
    path = BASE / name
    text = path.read_text(encoding="utf-8")
    if text.count(old) != count:
        raise SystemExit(f"{name}: {text.count(old)} matches (want {count}) for {old[:70]!r}")
    path.write_text(text.replace(old, new, count), encoding="utf-8")


sub(
    "_provisioning_runtime.py",
    """        contention_verdict = snapshot.precondition_verdict
        assert contention_verdict is not None
""",
    """        contention_verdict = snapshot.precondition_verdict
        if contention_verdict is None:
            raise ValueError("a refused model-load contention snapshot must carry its precondition verdict")
""",
)

sub(
    "auth/operator_probes.py",
    """    if provider_kind not in (AuthProviderKind.CLAVE_MOVIL, AuthProviderKind.CLAVE_PERMANENTE):
        return settings
    assert provider_kind is not None
""",
    """    if provider_kind is None or provider_kind not in (
        AuthProviderKind.CLAVE_MOVIL,
        AuthProviderKind.CLAVE_PERMANENTE,
    ):
        return settings
""",
)

# The classification field is already typed to the enum; the isinstance assert
# restated the declaration.
sub(
    "calculations/registry_preconditions.py",
    '''    """Resolve one domain calculation-registry fact record into typed policy."""
    assert isinstance(failure.condition, RegistryFailureCondition), (
        f"unclassified calculation-registry failure condition: {failure.condition}"
    )
    condition_id = failure.condition.value
''',
    '''    """Resolve one domain calculation-registry fact record into typed policy."""
    condition_id = failure.condition.value
''',
)
sub(
    "calculations/registry_preconditions.py",
    """    assert failure.condition in {
        RegistryFailureCondition.QUERY_CASILLA_DECLARED,
        RegistryFailureCondition.SNAPSHOT_AUTHORITY_GRADE_SUFFICIENT,
        RegistryFailureCondition.SNAPSHOT_EXPORT_LAYOUT_DECLARED,
        RegistryFailureCondition.TREE_QUIESCENT,
    }, f"unclassified calculation-registry failure condition: {failure.condition}"
""",
    """    if failure.condition not in {
        RegistryFailureCondition.QUERY_CASILLA_DECLARED,
        RegistryFailureCondition.SNAPSHOT_AUTHORITY_GRADE_SUFFICIENT,
        RegistryFailureCondition.SNAPSHOT_EXPORT_LAYOUT_DECLARED,
        RegistryFailureCondition.TREE_QUIESCENT,
    }:
        raise ValueError(f"unclassified calculation-registry failure condition: {failure.condition}")
""",
)

# The FTS lane takes the connection it needs, so the caller's branch is the proof.
sub(
    "command_search/index.py",
    """        if self._connection is not None:
            return self._search_fts_keys(folded_terms)
        return self._search_degraded_keys(folded_terms)

    def _search_fts_keys(self, folded_terms: Sequence[str]) -> list[str]:
        assert self._connection is not None
""",
    """        connection = self._connection
        if connection is not None:
            return self._search_fts_keys(folded_terms, connection=connection)
        return self._search_degraded_keys(folded_terms)

    def _search_fts_keys(self, folded_terms: Sequence[str], *, connection: Connection) -> list[str]:
""",
)

sub(
    "config_reset.py",
    """    current_fingerprint = assessment.fingerprint
    assert current_fingerprint is not None
""",
    """    current_fingerprint = assessment.fingerprint
    if current_fingerprint is None:
        raise ConfigResetError(
            f"reset target {target.bucket_id!r} exists on disk but yielded no fingerprint to compare",
        )
""",
)
sub(
    "config_reset.py",
    """        fingerprint = target.fingerprint
        assert fingerprint is not None
""",
    """        fingerprint = target.fingerprint
        if fingerprint is None:
            raise ConfigResetError(
                f"reset target {target.bucket_id!r} reached the deleting phase with no recorded fingerprint",
            )
""",
)

sub(
    "config_reset_models.py",
    """        if any(target.phase is not ConfigResetTargetPhase.DELETED for target in self.targets):
            raise ValueError("complete reset operation requires every target to be deleted")
        assert self.summary is not None
        self._validate_summary_reconciliation(self.summary)
""",
    """        if any(target.phase is not ConfigResetTargetPhase.DELETED for target in self.targets):
            raise ValueError("complete reset operation requires every target to be deleted")
        summary = self.summary
        if summary is None:
            raise ValueError("complete reset operation requires exactly one summary")
        self._validate_summary_reconciliation(summary)
""",
)

sub(
    "export/tabular.py",
    """    worksheet = workbook.active
    assert worksheet is not None, "Workbook.active must not be None on a fresh Workbook"
""",
    """    worksheet = workbook.active
    if worksheet is None:
        raise ExportFormatError("a fresh workbook carries no active worksheet to write the ledger into")
""",
)

sub(
    "filing/_export_xml_dictionary.py",
    """    rendered = ElementTree.tostring(root, encoding=_UTF_8, xml_declaration=True)
    assert isinstance(rendered, bytes)
    return rendered
""",
    """    rendered = ElementTree.tostring(root, encoding=_UTF_8, xml_declaration=True)
    if not isinstance(rendered, bytes):
        raise FilingExportError(f"the XML dictionary serialiser returned {type(rendered).__name__}, not bytes")
    return rendered
""",
)

sub(
    "filing/export.py",
    """    if prepared.renders_filing_envelope:
        assert prior_domiciliation_election is not None
        assert product_software_identity is not None
""",
    """    if prepared.renders_filing_envelope:
        if prior_domiciliation_election is None or product_software_identity is None:
            raise FilingExportError(
                "a filing envelope renders only with both the prior domiciliation election and the "
                "product software identity the record design stamps",
            )
""",
)
sub(
    "filing/export.py",
    """    code = export_layout_renderability_reason_code(layout)
    assert code is not None
""",
    """    code = export_layout_renderability_reason_code(layout)
    if code is None:
        raise FilingExportError(
            f"modelo {modelo} export layout is not renderable and no reason code classifies why",
        )
""",
)

sub(
    "invoices/_bulk_import_columns.py",
    """    if _mapping_lane_not_needed(mapper, required_fields, claimed_fields):
        return False
    assert mapper is not None
""",
    """    if mapper is None or _mapping_lane_not_needed(mapper, required_fields, claimed_fields):
        return False
""",
)

sub(
    "invoices/source_resolver.py",
    """    assert party_tax_id is not None  # clave "C" only returns when collected_on_behalf_of_tax_id is set
""",
    """    if party_tax_id is None:
        raise RegistryValidationError(
            f"invoice {invoice.invoice_id!r} resolves modelo 347 clave {clave!r} with no declaring party tax id",
        )
""",
)

sub(
    "ledger/actions_split_merge.py",
    """    split_group_id = next(iter(split_group_ids))
    assert split_group_id is not None  # narrowed: None excluded by the guard above
""",
    """    split_group_id = next(iter(split_group_ids))
    if split_group_id is None:
        raise TransactionValidationError(
            "ledger merge children must all share one split_group_id",
            context={"bucket_id": bucket_id, "child_transaction_ids": tuple(child_transaction_ids)},
        )
""",
)

sub(
    "ledger/invoice_confirmation.py",
    """    assert evidence_id is not None  # narrowed by the caller's exactly-one guard
""",
    """    if evidence_id is None:
        raise InvoiceValidationError("confirming from evidence requires either an attachment id or an evidence id")
""",
)
sub(
    "ledger/invoice_confirmation.py",
    """    assert isinstance(resolved_counterparty_tax_id, str)
""",
    """    if not isinstance(resolved_counterparty_tax_id, str):
        raise InvoiceValidationError("the confirmed counterparty tax id must resolve to text")
""",
)
sub(
    "ledger/invoice_confirmation.py",
    """    assert isinstance(resolved_invoice_number, str)
""",
    """    if not isinstance(resolved_invoice_number, str):
        raise InvoiceValidationError("the confirmed invoice number must resolve to text")
""",
)
sub(
    "ledger/invoice_confirmation.py",
    """    assert isinstance(resolved_taxable_base, Decimal)
""",
    """    if not isinstance(resolved_taxable_base, Decimal):
        raise InvoiceValidationError("the confirmed taxable base must resolve to a decimal amount")
""",
)

sub(
    "ledger/invoice_draft_extraction.py",
    """        assert attachment_id is not None  # narrowed by the exactly-one guard above
""",
    """        if attachment_id is None:
            raise PurchaseInvoiceEvidenceInputError(
                translated_message="errors.refused.refused_ledger_evidence_input",
            )
""",
)

sub(
    "modelo/_calculation_modelo_adjustments.py",
    """    kinds: set[type] = set()
    for member in get_args(ModeloDetailRow):
        assert isinstance(member, type)
        kinds.add(member)
""",
    """    kinds: set[type] = set()
    for member in get_args(ModeloDetailRow):
        if not isinstance(member, type):
            raise ModeloError(f"the ModeloDetailRow union carries a non-class member {member!r}")
        kinds.add(member)
""",
)

sub(
    "modelo/_edit_execution.py",
    """        if intent.kind is ModeloEditDetailRowIntentKind.ADD_ROW:
            assert intent.row is not None
            rows.append(intent.row)
        elif intent.kind is ModeloEditDetailRowIntentKind.UPDATE_ROW:
            assert intent.row is not None
            if intent.address.natural_key not in keys:
                return _detail_row_natural_key_refusal(intent.address)
            rows[keys.index(intent.address.natural_key)] = intent.row
""",
    """        if intent.kind is ModeloEditDetailRowIntentKind.ADD_ROW:
            if intent.row is None:
                raise ModeloError("an add-row edit intent must carry the row it adds")
            rows.append(intent.row)
        elif intent.kind is ModeloEditDetailRowIntentKind.UPDATE_ROW:
            if intent.row is None:
                raise ModeloError("an update-row edit intent must carry the row it writes")
            if intent.address.natural_key not in keys:
                return _detail_row_natural_key_refusal(intent.address)
            rows[keys.index(intent.address.natural_key)] = intent.row
""",
)
sub(
    "modelo/_edit_execution.py",
    """    assert captured_receipt, "the calculation boundary must resolve exactly one revision id per call"
""",
    """    if not captured_receipt:
        raise ModeloError("the calculation boundary must resolve exactly one revision id per call")
""",
)

sub(
    "modelo/_m303_m349_reconcile.py",
    """    if resolution.state is ModeloWorkSelectorState.ABSENT:
        return None
    assert resolution.work_unit is not None
    return resolution.work_unit
""",
    """    if resolution.state is ModeloWorkSelectorState.ABSENT:
        return None
    work_unit = resolution.work_unit
    if work_unit is None:
        raise ModeloValidationError("a present work-unit selection must carry the work unit it selected")
    return work_unit
""",
)

sub(
    "modelo/_row_source_identity_replay.py",
    """        assert key is not None
""",
    """        if key is None:
            raise ModeloValidationError("row source identity replay requires the casilla key it attaches to")
""",
)

sub(
    "modelo/export.py",
    """    filing_instance_evidence = require_filing_instance_evidence_for_work_unit(
        work_unit=work_unit,
        revision=revision,
    )
    assert filing_instance_evidence is not None
""",
    """    filing_instance_evidence = require_filing_instance_evidence_for_work_unit(
        work_unit=work_unit,
        revision=revision,
    )
    if filing_instance_evidence is None:
        raise ModeloExportEvidenceMissingError(
            f"work unit {work_unit.work_unit_id!r} carries no filing-instance evidence valid for its revision",
        )
""",
)

sub(
    "modelo/work_lifecycle.py",
    """        assert binding.source_key is not None
        evidence_value = continuation.evidence.values.get(binding.source_key)
        if evidence_value is None and binding.source_key not in continuation.evidence.values:
""",
    """        source_key = binding.source_key
        if source_key is None:
            raise ValueError("lifecycle continuation arguments must name the evidence key they read")
        evidence_value = continuation.evidence.values.get(source_key)
        if evidence_value is None and source_key not in continuation.evidence.values:
""",
)

# ``model_fields`` is declared ``dict[str, FieldInfo]``; the three asserts
# restated that declaration and the copy they guarded served nothing.
sub(
    "modelo/workspace_manifest.py",
    """        raw_fields = model_type.model_fields
        assert isinstance(raw_fields, dict)
        fields: dict[str, FieldInfo] = {}
        for field_name_raw, field_info_raw in raw_fields.items():
            assert isinstance(field_name_raw, str)
            assert isinstance(field_info_raw, FieldInfo)
            fields[field_name_raw] = field_info_raw
        for field_name, field in fields.items():
""",
    """        for field_name, field in model_type.model_fields.items():
""",
)

sub(
    "modelo/workspace_producers.py",
    '''        """Return the one law-selected revision id, whichever admission shape carries it."""
        if self.inspection is not None:
            return self.inspection.revision_id
        assert self.snapshot is not None
        return self.snapshot.revision.id
''',
    '''        """Return the one law-selected revision id, whichever admission shape carries it."""
        if self.inspection is not None:
            return self.inspection.revision_id
        snapshot = self.snapshot
        if snapshot is None:
            raise ValueError("a workspace admission must carry either an inspection or a graded snapshot")
        return snapshot.revision.id
''',
)
sub(
    "modelo/workspace_producers.py",
    '''        """Return the revision's own governance stamp, whichever admission shape carries it."""
        if self.inspection is not None:
            return self.inspection.review_status
        assert self.snapshot is not None
        return self.snapshot.revision.review_status
''',
    '''        """Return the revision's own governance stamp, whichever admission shape carries it."""
        if self.inspection is not None:
            return self.inspection.review_status
        snapshot = self.snapshot
        if snapshot is None:
            raise ValueError("a workspace admission must carry either an inspection or a graded snapshot")
        return snapshot.revision.review_status
''',
)

sub(
    "operations/projection_services.py",
    """        capability.close()
        assert token is not None
""",
    """        capability.close()
        if token is None:
            raise ValueError("a bound secure-response authority requires the token its capability issued")
""",
)

sub(
    "operations/supervisor.py",
    """        if may_resume_checkpoint:
            assert checkpoint is not None
""",
    """        if may_resume_checkpoint and checkpoint is not None:
""",
)
sub(
    "operations/supervisor.py",
    """        if may_resume_continuation:
            assert continuation is not None
""",
    """        if may_resume_continuation and continuation is not None:
""",
)

sub(
    "operator_surface/action_resolution.py",
    """    input_schema = resolved_catalogue_action.target_leaf.input_schema
    assert input_schema is not None
""",
    """    input_schema = resolved_catalogue_action.target_leaf.input_schema
    if input_schema is None:
        raise ValueError("a resolvable catalogue action must declare the input schema its arguments bind to")
""",
)

sub(
    "prorrata_register/seed.py",
    """    provenance = entry.provisional_provenance
    assert provenance is not None
""",
    """    provenance = entry.provisional_provenance
    if provenance is None:
        raise ValueError("a regulated-override seed finding requires the entry's provisional provenance")
""",
)

sub(
    "registry/filing_export_coverage.py",
    """    assert proof is not None
""",
    """    if proof is None:
        raise ValueError("a satisfied filing-export limb requires the conformance proof it rests on")
""",
)

sub(
    "storage/calc_sheets/workbook_export.py",
    """    workbook = Workbook()
    default = workbook.active
    assert default is not None
""",
    """    workbook = Workbook()
    default = workbook.active
    if default is None:
        raise ValueError("a fresh workbook carries no active worksheet to name as the first tab")
""",
)
sub(
    "storage/calc_sheets/workbook_export.py",
    """        if cell.note is not None:
            assert isinstance(target, Cell)
            target.comment = Comment(cell.note, "AEAT")
""",
    """        if cell.note is not None:
            if not isinstance(target, Cell):
                raise ValueError(f"cell {cell.address!r} carries a note but is not a writable cell")
            target.comment = Comment(cell.note, "AEAT")
""",
)

sub(
    "user_profile/capsule_record.py",
    """        assert raw.revision_id is not None
""",
    """        if raw.revision_id is None:
            raise ProfileRecordIntegrityError("the stored profile record row carries no revision id")
""",
)

# The refusal above already narrowed the pointer; the assert restated it.
sub(
    "user_profile/login_session.py",
    """    assert pointer.bucket_id is not None
    resolved = resolve_profile_bucket(pointer.bucket_id)
""",
    """    resolved = resolve_profile_bucket(pointer.bucket_id)
""",
)

sub(
    "wizard/commands.py",
    '''_missing_option_infos = _SETUP_CATALOGUE_IDS - frozenset(_SETUP_OPTION_INFOS)
assert not _missing_option_infos, (
    f"_SETUP_OPTION_INFOS is missing entries for catalogue question ids: "
    f"{sorted(_missing_option_infos)!r}. "
    "Add a typer.Option entry for each missing id."
)
''',
    '''_missing_option_infos = _SETUP_CATALOGUE_IDS - frozenset(_SETUP_OPTION_INFOS)
if _missing_option_infos:  # pragma: no cover - option-coverage invariant
    raise ValueError(
        f"_SETUP_OPTION_INFOS is missing entries for catalogue question ids: "
        f"{sorted(_missing_option_infos)!r}. "
        "Add a typer.Option entry for each missing id.",
    )
''',
)

sub(
    "wizard/persistence.py",
    """    birth_date = parse_iso8601_date(row["birth-date"])
    assert birth_date is not None
""",
    """    birth_date = parse_iso8601_date(row["birth-date"])
    if birth_date is None:
        raise WorkflowInputMismatchError("a stored descendant row must carry a readable birth date")
""",
)

sub(
    "workflow/profile_health.py",
    """        assert resolution.unavailability is not None
        unavailability = resolution.unavailability
""",
    """        unavailability = resolution.unavailability
        if unavailability is None:
            raise RuntimeError("an absent profile record must carry the reason it is unavailable")
""",
)

sub(
    "workflow/resume.py",
    """    resolution = resolve_modelo_work_target(target, catalogue=catalogue, bucket_id=bucket_id)
    assert resolution.work_unit is not None
""",
    """    resolution = resolve_modelo_work_target(target, catalogue=catalogue, bucket_id=bucket_id)
    if resolution.work_unit is None:
        raise WorkflowError("a resolved modelo work target must carry the work unit the resume reads")
""",
)
sub(
    "workflow/resume.py",
    """    assert run.obligation is not None
    return WorkflowResumeRunCandidate(
""",
    """    if run.obligation is None:
        raise WorkflowError("a resumable workflow run must carry the obligation it filed against")
    return WorkflowResumeRunCandidate(
""",
)

print("ok")
