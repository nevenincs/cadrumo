"""Ratchet gate: an identifier-named model field carries an alias, not bare ``str``.

WHAT THIS ASSERTS. Every field on a production pydantic model whose NAME matches
the identifier-namespace vocabulary must carry a type, not a bare ``str``. A
value that names an expediente, a CSV, a bucket or a transaction is a member of
some identity namespace; declaring it ``str`` means the model boundary asserts
nothing about it, and two values from unrelated namespaces become mutually
substitutable with no layer objecting.

HOW THE VOCABULARY IS DERIVED, and why it is derived rather than listed. It is
computed at runtime from the alias family :mod:`~core.identity` actually
exports: every name in that package's ``__all__`` that IS a type alias -- a
:class:`typing.TypeAliasType` from a PEP 695 ``type X = ...``, or an
``Annotated[...]`` object -- contributes its name in snake_case, plus the same
name with a leading ``aeat_`` issuer token stripped (so ``AeatExpedienteId``
admits the field name ``expediente_id`` as well as ``aeat_expediente_id``). A
field matches when a vocabulary token is the field name itself or a trailing
token-run of it, so ``parent_transaction_id`` and ``winning_expediente_id``
match while ``financial_default_csv_encoding`` does not.

Deriving from the live family is what keeps the gate honest as the family
grows: a new alias widens the vocabulary with no edit here. It also means this
gate cannot be satisfied by DELETING an alias, because deleting one narrows the
vocabulary and strands its sites in the ledgers below, which the staleness
assertions then fail.

Only the ISSUER token is stripped, never a distinguishing one. Reducing
``filing_record_id`` to ``record_id``, or ``calculation_revision_id`` to
``revision_id``, would erase exactly the token that separates two namespaces --
a registry revision id and a calculation revision id are different concepts
that share a suffix -- so the reduction that looks like generosity is really a
conflation, and it is not performed. The single exception is DECLARED in
:data:`_SHARED_STEMS` with its reason and is anchored by a test.

WHAT THIS DOES NOT ASSERT: that a field carries the RIGHT alias. The property
is enrolment -- something other than bare ``str`` -- because a field may be
correctly typed by an authority outside this package (a registry casilla id, a
:class:`enum.StrEnum`), and a gate demanding a ``core.identity`` name
specifically would report those as violations. Choosing between two aliases
stays a review judgement.

THE REHOMED FREE-TEXT EXCLUSIONS. Three sub-populations were documented as
deliberately outside this taxonomy on the ``IdentifierNamespace`` enum, which
has since been deleted as a dormant symbol with no consumer. The documentation
outlived the enum because the exclusions are still true, so it lives here now,
in :data:`_FREE_TEXT_POPULATIONS`, where this gate is its only consumer. Each
population is falsifiable rather than prose: a test asserts its representative
field tokens are NOT in the derived vocabulary, so adding an alias that named
one of them would fail the claim and force a re-adjudication rather than
silently widening the gate.

TWO LEDGERS, DELIBERATELY SEPARATE. :data:`_ADJUDICATED` names sites ruled
bare-by-design, each with its own reason -- these are decisions, permanent
until re-decided. :data:`_UNENROLLED_BASELINE` names sites that are simply NOT
YET ENROLLED. Collapsing the two would make a recorded gap indistinguishable
from a considered carve-out, which is the precise failure a ratchet exists to
prevent. Both are keyed by ``(path, model, field)`` and never by line number,
because a line number is invalidated by every edit above it and an exemption
that moves silently is an exemption nobody re-reads.

The baseline's size IS the finding: an enumerated, greppable ledger of open
work, not an excuse. It is asserted as a SET of identities, never as a count --
a tally would encode the moment it was written, train the next author to bump a
constant, and then detect nothing. The gate reds when a NEW bare identifier
field appears, and reds when a ledger entry has been enrolled but not struck
from the ledger, so the population can only ratchet down.

KNOWN LIMITS, stated rather than left implied by a green run.

Only pydantic models are in reach. Model membership is resolved by walking
every production class's base names and taking the fixpoint from ``BaseModel``,
matched by bare class name across the corpus. A frozen ``dataclass`` is
therefore invisible: ``AeatParty.tax_id`` in the einvoice record batch is a real
dual-role identifier field this gate does not see, and it is named here so a
green run is not read as covering it.

Function parameters and return annotations are out of reach for the same
reason -- the subject is a field on a model -- so a bare ``str`` parameter naming
an identifier is not reported.

A ``short_``-prefixed field is excluded structurally, not by allowlist. It is a
TRUNCATED display companion -- twelve characters of a sixty-four character
identity -- so the full alias is strictly NARROWER than the value the field
exists to carry, and typing it would refuse every value the surface serves. The
exclusion is anchored: a test asserts every excluded ``short_<x>`` has a sibling
``<x>`` field on the same model, so dropping or renaming the full field makes
the companion's exclusion fail rather than pass vacuously.

The scan reads a PINNED revision rather than the working tree, matching the
sibling censuses under ``dev/identity/``: this repository is written to by many
agents at once, and a gate whose subject moves between collection and assertion
reports a tree nobody can reproduce.

See Also:
    :mod:`~core.identity`
        The alias family the vocabulary is derived from.
"""

from __future__ import annotations

import ast
import re
import typing
from dataclasses import dataclass
from typing import Final

import pytest
from dev.identity.identifier_noun_census import annotation_text, is_bare_str
from dev.quality.cli_action_census import production_sources

from ..core import identity

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Scanned at ``HEAD`` rather than the working tree, for the reason the module
#: docstring states.
_REVISION: Final[str] = "HEAD"

#: The root pydantic base every model in this tree ultimately derives from.
_MODEL_ROOT: Final[str] = "BaseModel"

#: Prefix marking a truncated display companion of a full identity.
_DISPLAY_COMPANION_PREFIX: Final[str] = "short_"

#: Leading token naming the ISSUING AUTHORITY rather than the concept. Stripped
#: so an alias named for AEAT admits the unqualified field spelling the tree
#: actually uses. Only the issuer is stripped; see the module docstring.
_ISSUER_PREFIX: Final[str] = "aeat_"

_CAMEL_BOUNDARY: Final[re.Pattern[str]] = re.compile(r"(?<!^)(?=[A-Z])")


@dataclass(frozen=True, slots=True)
class _SharedStem:
    """One identity concept spelled by more than one alias.

    A stem is admitted ONLY when two or more aliases name the same underlying
    identifier and the field spelling in the tree is the common stem rather
    than either alias name. Every entry is anchored by a test asserting its
    aliases still exist, so a rename cannot leave the stem asserting a
    vocabulary nothing backs.

    Attributes:
        stem: The snake_case field-name token the concept is spelled with.
        aliases: The alias names on the identity facade that share it.
        reason: Why one stem covers both, stated rather than assumed.
    """

    stem: str
    aliases: tuple[str, ...]
    reason: str


#: The declared stem reductions. Deliberately tiny: each is a claim that two
#: aliases name one concept, which is a judgement, not a derivation.
_SHARED_STEMS: Final[tuple[_SharedStem, ...]] = (
    _SharedStem(
        stem="tax_id",
        aliases=("SubjectTaxId", "TaxIdIdentityToken"),
        reason=(
            "A tax identifier is spelled tax_id throughout the tree, and TWO aliases "
            "carry it: SubjectTaxId asserts the Spanish NIF/NIE/CIF checksum, and "
            "TaxIdIdentityToken is the checksum-free comparison form for a bearer who "
            "may not be Spanish. Neither alias NAME is the field spelling, so without "
            "this stem every tax_id field would fall outside the vocabulary entirely."
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class _FreeTextPopulation:
    """One sub-population deliberately outside the identifier taxonomy.

    Rehomed from the deleted ``IdentifierNamespace`` enum, whose trailing
    comment block recorded these three as deliberately not members of the
    taxonomy, "recorded here so a later sweep does not enroll them by
    name-shape and call the surface closed". That enum is gone; the exclusions
    are still true, and this gate is now their home.

    Attributes:
        name: Short label for the population.
        reason: Why its members are not identity-namespace members.
        field_tokens: Representative field-name tokens. Asserted ABSENT from
            the derived vocabulary, so the exclusion is falsifiable: adding an
            alias that named one of these would fail the claim rather than
            quietly widen the gate.
    """

    name: str
    reason: str
    field_tokens: tuple[str, ...]


#: The three sub-populations, verbatim in substance from the deleted enum.
_FREE_TEXT_POPULATIONS: Final[tuple[_FreeTextPopulation, ...]] = (
    _FreeTextPopulation(
        name="AEAT-printed adjudicated-case prose",
        reason=(
            "Bounded free text the app neither controls nor can enumerate -- a "
            "declaration's estado, a debt's situacion. Typing them as a closed set "
            "would assert a vocabulary AEAT has never published, and a value outside "
            "it would be refused at the model boundary rather than reported."
        ),
        field_tokens=("estado", "situacion"),
    ),
    _FreeTextPopulation(
        name="Counterparty-issued document numbers",
        reason=(
            "An invoice_number is minted by a third party, not by AEAT and not by this "
            "app. It has no shape this codebase may constrain, because the issuer's "
            "numbering scheme is the issuer's to choose."
        ),
        field_tokens=("invoice_number", "document_number"),
    ),
    _FreeTextPopulation(
        name="Non-AEAT issuing authorities",
        reason=(
            "Google file, folder and spreadsheet ids; an X.509 certificate serial; an "
            "SPDX id. Each belongs to some other authority's namespace and none "
            "belongs in the AEAT group. Whether any warrants typing at all is a "
            "separate question this taxonomy does not answer."
        ),
        field_tokens=("file_id", "folder_id", "spreadsheet_id", "serial_number", "spdx_id"),
    ),
)

#: Live occurrences anchoring the AEAT-prose population. Each MUST still be a
#: bare free-text field on a production model: if one gains a closed type, the
#: population's claim is obsolete and must be re-adjudicated rather than left
#: standing as a stale carve-out.
_FREE_TEXT_ANCHORS: Final[tuple[tuple[str, str, str], ...]] = (
    ("src/cadrumo/adapters/outbound/aeat/sede/_declarations_schema.py", "Declaracion", "estado"),
    ("src/cadrumo/adapters/outbound/aeat/sede/_deudas.py", "Deuda", "situacion"),
)


@dataclass(frozen=True, slots=True)
class _Adjudication:
    """One site ruled bare-by-design, with the reason it was ruled so.

    Attributes:
        path: Repository-relative module path.
        model: Enclosing model class name.
        field: Field name.
        reason: Why this field must NOT be retyped. Required: an exemption
            whose reason is not stated is indistinguishable from an oversight.
    """

    path: str
    model: str
    field: str
    reason: str

    def key(self) -> tuple[str, str, str]:
        """The identity this adjudication matches occurrences on."""
        return (self.path, self.model, self.field)


#: Sites ruled bare, each surviving the substitutability check in the opposite
#: direction: the alias is NARROWER than what the site legitimately accepts, so
#: promoting it would refuse a value the site exists to handle.
_ADJUDICATED: Final[tuple[_Adjudication, ...]] = (
    _Adjudication(
        path="src/cadrumo/application/auth/_sessions.py",
        model="ClaveAuthFacts",
        field="tax_id",
        reason=(
            "Auth facts are read from the authenticated session BEFORE the identity is "
            "known to be well-formed; the value is whatever the provider asserted. "
            "Validating at this boundary would refuse a session AEAT itself issued."
        ),
    ),
    _Adjudication(
        path="src/cadrumo/application/auth/_sessions.py",
        model="ClaveCredentials",
        field="profile_tax_id",
        reason=(
            "The credential carries the identifier as SUPPLIED for the login attempt, "
            "not as validated. Refusing a malformed one here would turn a failed "
            "authentication into a model construction error with no operator diagnosis."
        ),
    ),
    _Adjudication(
        path="src/cadrumo/core/setup_answers.py",
        model="SetupAnswers",
        field="tax_id",
        reason=(
            "Wizard answers are captured before validation runs, so the setup surface "
            "can report a bad identifier as an answerable question rather than crash "
            "while constructing the answer record."
        ),
    ),
    _Adjudication(
        path="src/cadrumo/core/setup_answers.py",
        model="SetupAnswers",
        field="spouse_tax_id",
        reason=(
            "As SetupAnswers.tax_id: captured pre-validation, so a placeholder must "
            "survive capture to be corrected in a later answer."
        ),
    ),
    _Adjudication(
        path="src/cadrumo/llm/_invoice_field_grounding.py",
        model="_ExtractedInvoiceFieldClaims",
        field="supplier_tax_id",
        reason=(
            "An LLM-extracted CLAIM, held verbatim as it appears in the document. "
            "SubjectTaxId canonicalises and uppercases, which broke anchor matching "
            "against the source text -- a real regression, not a hypothetical: the "
            "grounding step must find the claim back in the document byte-for-byte."
        ),
    ),
    _Adjudication(
        path="src/cadrumo/llm/_invoice_field_grounding.py",
        model="_ExtractedInvoiceFieldClaims",
        field="customer_tax_id",
        reason="As the supplier claim on this model: verbatim extraction, anchor matching.",
    ),
    _Adjudication(
        path="src/cadrumo/llm/_invoice_field_grounding.py",
        model="ExtractedRoleEvidence",
        field="supplier_tax_id",
        reason="As the claim model: role evidence quotes the extracted text verbatim for anchoring.",
    ),
    _Adjudication(
        path="src/cadrumo/llm/_invoice_field_grounding.py",
        model="ExtractedRoleEvidence",
        field="customer_tax_id",
        reason="As the claim model: role evidence quotes the extracted text verbatim for anchoring.",
    ),
)

#: Identifier-named fields that are NOT YET ENROLLED. Every entry is an open
#: gap, not a carve-out: the concept belongs in a namespace and the field has
#: simply never been retyped. Kept separate from :data:`_ADJUDICATED` precisely
#: so a gap can never be mistaken for a decision.
#:
#: The ledger may only SHRINK. Enrolling a field and leaving its entry here
#: fails :func:`test_no_stale_baseline_entry`, so the ratchet cannot be loosened
#: by inattention; and a new bare field cannot join without an explicit edit a
#: reviewer sees.
_UNENROLLED_BASELINE: Final[frozenset[tuple[str, str, str]]] = frozenset(
    {
        (
            "src/cadrumo/adapters/inbound/borrador/_schema.py",
            "InboundBorradorObservation",
            "registry_extraction_profile_id",
        ),
        ("src/cadrumo/adapters/inbound/borrador/_schema.py", "InboundBorradorObservation", "tax_id"),
        (
            "src/cadrumo/adapters/inbound/declaracion/_schema.py",
            "InboundDeclaracionObservation",
            "extraction_profile_id",
        ),
        ("src/cadrumo/adapters/inbound/declaracion/_schema.py", "InboundDeclaracionObservation", "tax_id"),
        ("src/cadrumo/adapters/persistence/storage/attachment.py", "AttachmentStore", "bucket_id"),
        ("src/cadrumo/adapters/persistence/storage/runtime.py", "StorageRuntime", "bucket_id"),
        ("src/cadrumo/application/_workflow_review_models.py", "InvoiceReviewRecord", "invoice_id"),
        ("src/cadrumo/application/_workflow_review_models.py", "LedgerReviewRecord", "transaction_id"),
        ("src/cadrumo/application/aggregation/_invoice_retencion.py", "InvoiceRetencionProjection", "invoice_id"),
        ("src/cadrumo/application/aggregation/_invoice_retencion.py", "InvoiceRetencionRouteRequest", "invoice_id"),
        ("src/cadrumo/application/aggregation/_iva_ledger.py", "IvaLedgerAggregationIssue", "transaction_id"),
        ("src/cadrumo/application/aggregation/_source_mesh.py", "BorradorSourceProvenance", "snapshot_id"),
        ("src/cadrumo/application/auth/_diagnostics.py", "AuthDiagnosticSummary", "active_profile_id"),
        ("src/cadrumo/application/auth/_diagnostics.py", "AuthDiagnosticSummary", "active_profile_label"),
        ("src/cadrumo/application/auth/_operator_results.py", "AuthLogoutResult", "bucket_id"),
        ("src/cadrumo/application/auth/_operator_results.py", "AuthResetResult", "bucket_id"),
        ("src/cadrumo/application/auth/_operator_scope.py", "AuthOperationScope", "bucket_id"),
        ("src/cadrumo/application/calculations/_cross_period_models.py", "CrossPeriodCleanStateVerdict", "bucket_id"),
        ("src/cadrumo/application/invoices/_linking.py", "InvoiceTransactionLinkResult", "transaction_id"),
        ("src/cadrumo/application/invoices/_reconciliation.py", "ReconciliationSkippedSuggestion", "transaction_id"),
        ("src/cadrumo/application/ledger/_confirmation_record.py", "ConfirmationRecordDocument", "bucket_id"),
        ("src/cadrumo/application/ledger/_confirmation_record.py", "InvoiceConfirmationRecord", "bucket_id"),
        ("src/cadrumo/application/ledger/_confirmation_record.py", "InvoiceConfirmationRecord", "invoice_id"),
        ("src/cadrumo/application/ledger/_evidence_draft.py", "CounterpartyDraftSide", "tax_id"),
        ("src/cadrumo/application/ledger/_extracted_document_cache.py", "ExtractedDocumentCacheDocument", "bucket_id"),
        ("src/cadrumo/application/ledger/_extraction_draft_store.py", "ExtractionDraftDocument", "bucket_id"),
        ("src/cadrumo/application/ledger/_llm_review_workflow.py", "InvoiceDraftDeclineResult", "bucket_id"),
        ("src/cadrumo/application/ledger/_llm_review_workflow.py", "LlmReviewRequest", "bucket_id"),
        ("src/cadrumo/application/ledger/_models.py", "BulkClassifyFailure", "transaction_id"),
        ("src/cadrumo/application/ledger/_preflight.py", "LedgerPreflightIssue", "transaction_id"),
        ("src/cadrumo/application/live/_filed_data.py", "FiledDataListingRow", "expediente_id"),
        ("src/cadrumo/application/live/_filed_data_capture.py", "FiledPeriodSelectionRow", "winning_expediente_id"),
        ("src/cadrumo/application/live/_justificante.py", "JustificanteCaptureSnapshot", "expediente_id"),
        ("src/cadrumo/application/live/_justificante.py", "JustificanteCaptureSnapshot", "snapshot_id"),
        ("src/cadrumo/application/live/_justificante.py", "JustificanteCaptureSnapshot", "superseded_by_snapshot_id"),
        ("src/cadrumo/application/live/_justificante.py", "_JustificanteCaptureRequest", "expediente_id"),
        ("src/cadrumo/application/live/_remote_state_models.py", "ExpedientesBulkCaptureReport", "bucket_id"),
        ("src/cadrumo/application/live/_remote_state_models.py", "FiledCasillaSkipRow", "expediente_id"),
        ("src/cadrumo/application/live/_remote_state_models.py", "FiledDataCaptureFailureRow", "expediente_id"),
        (
            "src/cadrumo/application/modelo/_borrador_binding.py",
            "Modelo100BorradorBindingCommand",
            "borrador_snapshot_id",
        ),
        ("src/cadrumo/application/modelo/_quickfile.py", "QuickfileCommand", "bucket_id"),
        (
            "src/cadrumo/application/modelo/_review_package_recipient_encryption.py",
            "RecipientEncryptionKeypair",
            "bucket_id",
        ),
        (
            "src/cadrumo/application/modelo/_review_package_recipient_encryption.py",
            "RecipientEncryptionPublicKey",
            "bucket_id",
        ),
        ("src/cadrumo/application/modelo/_review_package_signing.py", "ReviewPackageSigningKeypair", "bucket_id"),
        ("src/cadrumo/application/modelo/_review_package_signing.py", "ReviewPackageSigningPublicKey", "bucket_id"),
        ("src/cadrumo/application/modelo/_review_package_signing.py", "SignedReviewPackage", "bucket_id"),
        ("src/cadrumo/application/modelo/_selectors.py", "ModeloWorkUnitCandidate", "current_filing_record_id"),
        ("src/cadrumo/application/overview/_calendar_models.py", "OverviewCalendarEvent", "snapshot_id"),
        ("src/cadrumo/application/overview/_calendar_models.py", "OverviewCalendarFilingEvidence", "aeat_snapshot_id"),
        (
            "src/cadrumo/application/overview/_calendar_models.py",
            "OverviewCalendarFilingEvidence",
            "local_filing_record_id",
        ),
        ("src/cadrumo/application/overview/_pipeline_health.py", "ModeloHealthRow", "work_unit_id"),
        ("src/cadrumo/application/overview/_pipeline_health.py", "PipelineHealthReport", "bucket_id"),
        ("src/cadrumo/application/state_projection.py", "ProjectionActiveProfile", "profile_id"),
        ("src/cadrumo/application/storage/calc_sheets/_records.py", "SheetEvidenceContributorRow", "transaction_id"),
        ("src/cadrumo/application/storage_management/_models.py", "StorageInventoryReport", "active_bucket_id"),
        ("src/cadrumo/application/storage_management/_models.py", "StorageInventoryRow", "bucket_id"),
        ("src/cadrumo/application/user_profile/_bundle_export_contracts.py", "ProfileBundleExportResult", "profile_id"),
        (
            "src/cadrumo/application/user_profile/_bundle_export_operation.py",
            "ProfileBundleExportOperation",
            "profile_id",
        ),
        ("src/cadrumo/application/user_profile/_commands.py", "ProfileSnapshot", "snapshot_id"),
        ("src/cadrumo/application/user_profile/_commands.py", "ProfileStaleCheckReport", "snapshot_id"),
        ("src/cadrumo/application/user_profile/_login_session.py", "ProfileLoginOutcome", "bucket_id"),
        ("src/cadrumo/application/user_profile/_login_session.py", "ProfileLoginOutcome", "closed_previous_bucket_id"),
        ("src/cadrumo/application/user_profile/_overview.py", "ProfileOverview", "profile_id"),
        ("src/cadrumo/application/user_profile/_registration.py", "ProfileRegistrationOutcome", "bucket_id"),
        ("src/cadrumo/application/user_profile/_registration.py", "ProfileRegistrationOutcome", "profile_id"),
        ("src/cadrumo/application/workflow/_events.py", "WorkflowStateResetFingerprint", "recovered_bucket_id"),
        ("src/cadrumo/application/workflow/_profile_health.py", "ActiveProfileHealth", "_active_profile_label"),
        ("src/cadrumo/application/workflow/_resume.py", "WorkflowResumeRunCandidate", "work_unit_id"),
        ("src/cadrumo/application/workflow/_resume.py", "WorkflowResumeTargetResolution", "work_unit_id"),
        ("src/cadrumo/core/_config_support.py", "StorageRouteClassification", "bucket_id"),
        ("src/cadrumo/domain/attachments/_service.py", "AttachmentIngestionRequest", "bucket_id"),
        (
            "src/cadrumo/domain/calculations/registry/_counterpart_bindings.py",
            "CounterpartAggregationObservation",
            "party_tax_id",
        ),
        (
            "src/cadrumo/domain/calculations/registry/_detail_record_bindings.py",
            "AtributionMemberObservation",
            "member_tax_id",
        ),
        (
            "src/cadrumo/domain/calculations/registry/_detail_record_bindings.py",
            "RefundOperationObservation",
            "supplier_tax_id",
        ),
        (
            "src/cadrumo/domain/calculations/registry/_detail_record_bindings.py",
            "RelatedPartyOperationObservation",
            "counterparty_tax_id",
        ),
        ("src/cadrumo/domain/calculations/registry/_donativo_bindings.py", "DonativoDonorObservation", "donor_tax_id"),
        ("src/cadrumo/domain/calculations/registry/_invoice_bindings.py", "InvoiceObservation", "invoice_id"),
        ("src/cadrumo/domain/calculations/registry/_invoice_bindings.py", "InvoiceObservation", "party_tax_id"),
        ("src/cadrumo/domain/evidence_consent/_record.py", "EvidenceConsentLedgerEntry", "profile_bucket_id"),
        ("src/cadrumo/domain/invoices/_models.py", "Invoice", "counterparty_tax_id"),
        ("src/cadrumo/domain/invoices/_service.py", "LinkInconsistency", "invoice_id"),
        ("src/cadrumo/domain/justificante/_schema.py", "Justificante", "tax_id"),
        ("src/cadrumo/domain/modelos/_calculation_revision.py", "CalculationRevision", "borrador_snapshot_id"),
        ("src/cadrumo/domain/modelos/_ledger_filing_snapshot.py", "LedgerEvidenceRow", "invoice_id"),
        ("src/cadrumo/domain/renta/_ledger_expenses.py", "RentaDeductibilityResult", "invoice_id"),
        ("src/cadrumo/domain/renta/_ledger_expenses.py", "RentaDeductibilityResult", "transaction_id"),
        ("src/cadrumo/domain/renta/_ledger_expenses.py", "RentaDeductibleExpenseFact", "invoice_id"),
        ("src/cadrumo/domain/renta/_ledger_expenses.py", "RentaDeductibleExpenseFact", "transaction_id"),
        ("src/cadrumo/domain/renta/_ledger_expenses.py", "RentaDeductibleExpenseObservation", "invoice_id"),
        ("src/cadrumo/domain/renta/_ledger_expenses.py", "RentaDeductibleExpenseObservation", "transaction_id"),
        ("src/cadrumo/domain/retention/_floor.py", "RetentionBlockingRecord", "filing_record_id"),
        ("src/cadrumo/domain/transactions/_models.py", "OutOfWindowTransactionIndexEntry", "transaction_id"),
        ("src/cadrumo/domain/transactions/_models.py", "Transaction", "invoice_id"),
        ("src/cadrumo/domain/transactions/_raw_transaction.py", "RawTransaction", "provider_transaction_id"),
        ("src/cadrumo/entrypoints/cli/_app_live_payloads.py", "DeudaRowPayload", "clave_liquidacion"),
        ("src/cadrumo/entrypoints/cli/_app_live_payloads.py", "DeudaSnapshotSummaryPayload", "snapshot_id"),
        ("src/cadrumo/entrypoints/cli/_app_live_payloads.py", "DeudasLatestResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_app_live_payloads.py", "DeudasLatestResult", "snapshot_id"),
        ("src/cadrumo/entrypoints/cli/_app_live_payloads.py", "DeudasListResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_app_live_payloads.py", "DeudasViewResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_app_live_payloads.py", "DeudasViewResult", "snapshot_id"),
        ("src/cadrumo/entrypoints/cli/_app_live_payloads.py", "ExpedienteSnapshotSummaryPayload", "snapshot_id"),
        ("src/cadrumo/entrypoints/cli/_app_live_payloads.py", "ExpedientesCaptureResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_app_live_payloads.py", "ExpedientesCaptureResult", "snapshot_id"),
        ("src/cadrumo/entrypoints/cli/_app_live_payloads.py", "ExpedientesLatestResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_app_live_payloads.py", "ExpedientesLatestResult", "snapshot_id"),
        ("src/cadrumo/entrypoints/cli/_app_live_payloads.py", "ExpedientesListResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_app_live_payloads.py", "ExpedientesViewResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_app_live_payloads.py", "ExpedientesViewResult", "snapshot_id"),
        ("src/cadrumo/entrypoints/cli/_app_live_payloads.py", "FiledCaptureFailurePayload", "expediente_id"),
        ("src/cadrumo/entrypoints/cli/_app_live_payloads.py", "FiledListingRowPayload", "expediente_id"),
        ("src/cadrumo/entrypoints/cli/_app_live_payloads.py", "JustificanteCaptureResult", "csv"),
        ("src/cadrumo/entrypoints/cli/_app_live_payloads.py", "JustificanteCaptureResult", "expediente_id"),
        ("src/cadrumo/entrypoints/cli/_app_live_payloads.py", "JustificanteCaptureResult", "filing_record_id"),
        ("src/cadrumo/entrypoints/cli/_app_live_payloads.py", "JustificanteCaptureResult", "snapshot_id"),
        ("src/cadrumo/entrypoints/cli/_app_live_payloads.py", "JustificanteListResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_app_live_payloads.py", "JustificanteSnapshotSummaryPayload", "snapshot_id"),
        ("src/cadrumo/entrypoints/cli/_app_live_payloads.py", "JustificanteViewResult", "csv"),
        ("src/cadrumo/entrypoints/cli/_app_live_payloads.py", "JustificanteViewResult", "expediente_id"),
        ("src/cadrumo/entrypoints/cli/_app_live_payloads.py", "JustificanteViewResult", "snapshot_id"),
        ("src/cadrumo/entrypoints/cli/_app_live_payloads.py", "NotificationRowPayload", "certificado_id"),
        ("src/cadrumo/entrypoints/cli/_app_live_payloads.py", "VerifyLatestResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_app_live_payloads.py", "VerifyListResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_app_live_payloads.py", "VerifyObservationPayload", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_app_quickfile_payloads.py", "QuickfileResultPayload", "work_unit_id"),
        ("src/cadrumo/entrypoints/cli/_bienes_inversion_payloads.py", "BienesInversionDeclareResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_bienes_inversion_payloads.py", "BienesInversionListResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_config/_capabilities_payloads.py", "CapabilitiesShowResult", "profile_id"),
        ("src/cadrumo/entrypoints/cli/_config/_capabilities_payloads.py", "CapabilitySetResult", "profile_id"),
        ("src/cadrumo/entrypoints/cli/_config/_check_payloads.py", "ConfigCheckResult", "profile_id"),
        ("src/cadrumo/entrypoints/cli/_config_bucket_history_payloads.py", "BucketHistoryResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_config_payloads.py", "AuthLogoutPayload", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_config_payloads.py", "AuthResetPayload", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_config_payloads.py", "ConfigProfileArchiveExportResult", "profile_id"),
        ("src/cadrumo/entrypoints/cli/_config_payloads.py", "ConfigProfileExportResult", "profile_id"),
        ("src/cadrumo/entrypoints/cli/_config_payloads.py", "ConfigProfileImportResult", "profile_id"),
        ("src/cadrumo/entrypoints/cli/_config_payloads.py", "ConfigProfileShowResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_config_payloads.py", "ConfigProfileSubjectAccessRequestResult", "profile_id"),
        ("src/cadrumo/entrypoints/cli/_config_payloads.py", "ConfigResetTargetPayload", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_config_payloads.py", "ConfigStatusResult", "profile_id"),
        ("src/cadrumo/entrypoints/cli/_config_payloads.py", "RepairProfileResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_config_payloads.py", "RepairProfileResult", "profile_id"),
        ("src/cadrumo/entrypoints/cli/_config_payloads.py", "WorkflowFingerprintPayload", "recovered_bucket_id"),
        ("src/cadrumo/entrypoints/cli/_config_sandbox_payloads.py", "SandboxDiskUsagePayload", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_business_payloads.py", "EvidenceConfirmResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_business_payloads.py", "EvidenceConfirmResult", "counterparty_tax_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_business_payloads.py", "EvidenceConfirmResult", "invoice_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_business_payloads.py", "EvidenceConsentListResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_business_payloads.py", "EvidenceConsentRederiveResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_business_payloads.py", "EvidenceExtractResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_business_payloads.py", "EvidenceListResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_business_payloads.py", "EvidenceRecordPayload", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_business_payloads.py", "EvidenceReviewListResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_business_payloads.py", "EvidenceReviewShowResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_business_payloads.py", "InventoryListResult", "bucket_id"),
        (
            "src/cadrumo/entrypoints/cli/_ledger_catalogue_invoice_payloads.py",
            "CatalogueInvoiceRecordPayload",
            "counterparty_tax_id",
        ),
        ("src/cadrumo/entrypoints/cli/_ledger_evidence_batch_payloads.py", "EvidenceBatchResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_llm_payloads.py", "LedgerClassifyLlmRejectResult", "transaction_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_llm_payloads.py", "LedgerClassifyLlmSaturateResult", "transaction_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_llm_payloads.py", "LedgerClassifyLlmSuggestResult", "transaction_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_payloads.py", "BulkClassifyFailurePayload", "transaction_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_payloads.py", "LedgerCheckResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_payloads.py", "LedgerDocLinkPullFolderResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_payloads.py", "LedgerHistoryEventPayload", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_payloads.py", "LedgerHistoryResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_payloads.py", "LedgerHistoryResult", "transaction_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_payloads.py", "LedgerLinkInconsistencyPayload", "invoice_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_payloads.py", "LedgerLinkInconsistencyPayload", "transaction_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_payloads.py", "LedgerLinkResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_payloads.py", "LedgerLinkResult", "invoice_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_payloads.py", "LedgerLinkResult", "transaction_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_payloads.py", "LedgerListResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_payloads.py", "LedgerListRowPayload", "transaction_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_payloads.py", "LedgerMergeResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_payloads.py", "LedgerMergeResult", "merged_transaction_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_payloads.py", "LedgerMergeResult", "parent_transaction_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_payloads.py", "LedgerPreflightIssuePayload", "transaction_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_payloads.py", "LedgerPreflightResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_payloads.py", "LedgerRemovalBlockerPayload", "work_unit_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_payloads.py", "LedgerRemoveResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_payloads.py", "LedgerRemoveResult", "transaction_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_payloads.py", "LedgerResetResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_payloads.py", "LedgerSplitResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_payloads.py", "LedgerSplitResult", "parent_transaction_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_payloads.py", "LedgerTrackResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_payloads.py", "LedgerTrackingEditPayload", "previous_transaction_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_payloads.py", "LedgerTrackingPayload", "transaction_id"),
        (
            "src/cadrumo/entrypoints/cli/_ledger_payloads.py",
            "LedgerTransactionParticipationEntryPayload",
            "filing_record_id",
        ),
        (
            "src/cadrumo/entrypoints/cli/_ledger_payloads.py",
            "LedgerTransactionParticipationEntryPayload",
            "work_unit_id",
        ),
        ("src/cadrumo/entrypoints/cli/_ledger_payloads.py", "LedgerTransactionParticipationPayload", "transaction_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_payloads.py", "LedgerViewResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_payloads.py", "LedgerViewResult", "transaction_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_payloads.py", "_LedgerMutationResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_payloads.py", "_LedgerMutationResult", "transaction_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_ratios_payloads.py", "RatiosEligibleResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_ratios_payloads.py", "RatiosListResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_ratios_payloads.py", "RatiosSetResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_ratios_payloads.py", "RatiosUnsetResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_ratios_payloads.py", "RatiosValidateResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_rule_payloads.py", "RuleApplyAppliedPayload", "transaction_id"),
        ("src/cadrumo/entrypoints/cli/_ledger_rule_payloads.py", "RuleApplyMatchPayload", "transaction_id"),
        ("src/cadrumo/entrypoints/cli/_modelo_aux_payloads.py", "WorkHistoryResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_modelo_aux_payloads.py", "WorkHistoryResult", "work_unit_id"),
        ("src/cadrumo/entrypoints/cli/_modelo_payloads.py", "CrossPeriodDependencyEvidencePayload", "filing_record_id"),
        ("src/cadrumo/entrypoints/cli/_modelo_payloads.py", "LedgerIssuePayload", "transaction_id"),
        ("src/cadrumo/entrypoints/cli/_modelo_payloads.py", "ModeloExportPayload", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_modelo_payloads.py", "ModeloExportPayload", "work_unit_id"),
        ("src/cadrumo/entrypoints/cli/_modelo_payloads.py", "ModeloReadinessResult", "profile_id"),
        ("src/cadrumo/entrypoints/cli/_modelo_payloads.py", "WorkResumeResult", "work_unit_id"),
        ("src/cadrumo/entrypoints/cli/_modelo_payloads_m036.py", "M036DeclarationRecordResult", "profile_id"),
        ("src/cadrumo/entrypoints/cli/_modelo_payloads_m036.py", "M036DeclarationRowPayload", "profile_id"),
        ("src/cadrumo/entrypoints/cli/_modelo_payloads_m036.py", "M036DeclarationShowResult", "profile_id"),
        (
            "src/cadrumo/entrypoints/cli/_modelo_review_package_payloads.py",
            "ModeloReviewPackageSignResult",
            "bucket_id",
        ),
        ("src/cadrumo/entrypoints/cli/_overview_payloads.py", "OverviewCalendarEntryPayload", "local_work_unit_id"),
        ("src/cadrumo/entrypoints/cli/_overview_payloads.py", "OverviewCalendarEventPayload", "snapshot_id"),
        (
            "src/cadrumo/entrypoints/cli/_overview_payloads.py",
            "OverviewCalendarFilingEvidencePayload",
            "aeat_snapshot_id",
        ),
        (
            "src/cadrumo/entrypoints/cli/_overview_payloads.py",
            "OverviewCalendarFilingEvidencePayload",
            "local_filing_record_id",
        ),
        ("src/cadrumo/entrypoints/cli/_overview_payloads.py", "OverviewCalendarProfilePayload", "profile_id"),
        ("src/cadrumo/entrypoints/cli/_overview_payloads.py", "OverviewPipelineModeloPayload", "work_unit_id"),
        ("src/cadrumo/entrypoints/cli/_prorrata_register_payloads.py", "ProrrataDeclareSectorResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_prorrata_register_payloads.py", "ProrrataElectResult", "bucket_id"),
        ("src/cadrumo/entrypoints/cli/_prorrata_register_payloads.py", "ProrrataListResult", "bucket_id"),
        ("src/cadrumo/llm/_suggestions.py", "LLMClassificationSuggestion", "transaction_id"),
        ("src/cadrumo/llm/_suggestions.py", "LLMSaturatedSuggestion", "transaction_id"),
        ("src/cadrumo/llm/_suggestions.py", "LLMSplitApplyResult", "bucket_id"),
        ("src/cadrumo/llm/_suggestions.py", "LLMSplitApplyResult", "parent_transaction_id"),
        ("src/cadrumo/llm/_suggestions.py", "LLMSplitSuggestion", "transaction_id"),
        ("src/cadrumo/llm/_suggestions.py", "LLMSuggestionRejectionResult", "bucket_id"),
        ("src/cadrumo/llm/_suggestions.py", "LLMSuggestionRejectionResult", "transaction_id"),
        ("src/cadrumo/llm/_suggestions.py", "OperatorIvaDerivationResult", "transaction_id"),
    }
)


def _snake(name: str) -> str:
    """Render a CamelCase alias name as its snake_case field spelling."""
    return _CAMEL_BOUNDARY.sub("_", name).lower()


def identifier_aliases() -> tuple[str, ...]:
    """Every identifier ALIAS exported by :mod:`~core.identity`.

    An alias is a PEP 695 :class:`typing.TypeAliasType` or an ``Annotated[...]``
    object. Classes, functions and scalar constants on the same facade are not
    aliases and contribute no vocabulary: ``validate_identity`` is a function,
    ``IdentityDocument`` an enum, ``SPANISH_TAX_ID_WIDTH`` an int.
    """
    names: list[str] = []
    for name in identity.__all__:
        member = getattr(identity, name)
        if isinstance(member, typing.TypeAliasType) or typing.get_origin(member) is not None:
            names.append(name)
    return tuple(sorted(names))


def namespace_vocabulary() -> frozenset[str]:
    """The field-name tokens the live alias family names.

    Derived, never listed: see the module docstring for why, and for why only
    the issuer prefix is stripped.
    """
    tokens: set[str] = set()
    for alias in identifier_aliases():
        spelling = _snake(alias)
        tokens.add(spelling)
        if spelling.startswith(_ISSUER_PREFIX):
            tokens.add(spelling.removeprefix(_ISSUER_PREFIX))
    tokens.update(stem.stem for stem in _SHARED_STEMS)
    return frozenset(tokens)


def matched_token(field: str, vocabulary: frozenset[str]) -> str | None:
    """The vocabulary token a field name carries, or ``None``.

    Matched against every trailing token-run of the field name, so a qualifier
    the tree adds in front (``parent_``, ``winning_``, ``closed_previous_``)
    does not hide the concept. Anchoring at the TAIL rather than searching
    anywhere is what keeps an unrelated head token from matching.
    """
    parts = field.split("_")
    for index in range(len(parts)):
        candidate = "_".join(parts[index:])
        if candidate in vocabulary:
            return candidate
    return None


@dataclass(frozen=True, slots=True)
class IdentifierField:
    """One identifier-named field on a production model.

    Attributes:
        path: Repository-relative module path at the pinned revision.
        line: Line of the field's annotated assignment.
        model: Enclosing model class name.
        field: Field name.
        annotation: The annotation as written.
        token: The vocabulary token the field name matched.
        enrolled: Whether the annotation carries anything other than bare ``str``.
    """

    path: str
    line: int
    model: str
    field: str
    annotation: str
    token: str
    enrolled: bool

    def key(self) -> tuple[str, str, str]:
        """The identity a ledger entry matches on."""
        return (self.path, self.model, self.field)

    def rendered(self) -> str:
        """A single deterministic line for a report or a failure message."""
        state = "enrolled" if self.enrolled else "BARE"
        return f"{self.path}:{self.line} {self.model}.{self.field}: {self.annotation} [{state}] token={self.token}"


def _base_names(node: ast.ClassDef) -> tuple[str, ...]:
    """Every base of ``node`` reduced to its bare trailing name."""
    names: list[str] = []
    for base in node.bases:
        if isinstance(base, ast.Name):
            names.append(base.id)
        elif isinstance(base, ast.Attribute):
            names.append(base.attr)
        elif isinstance(base, ast.Subscript):
            inner = base.value
            names.append(inner.id if isinstance(inner, ast.Name) else getattr(inner, "attr", ""))
    return tuple(name for name in names if name)


def _model_class_names(trees: dict[str, ast.Module]) -> frozenset[str]:
    """Class names reachable from ``BaseModel`` by inheritance, as a fixpoint.

    Matched by BARE class name across the corpus rather than by resolved import,
    which is the deliberate trade: resolving imports would need the whole module
    graph, and a bare-name collision between a model and a non-model of the same
    name is the only way this over-reaches. The limit is stated in the module
    docstring rather than hidden behind a green run.
    """
    bases: dict[str, set[str]] = {}
    for tree in trees.values():
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases.setdefault(node.name, set()).update(_base_names(node))
    models = {_MODEL_ROOT}
    changed = True
    while changed:
        changed = False
        for name, parents in bases.items():
            if name not in models and parents & models:
                models.add(name)
                changed = True
    return frozenset(models)


def _parsed(sources: tuple[tuple[str, str], ...]) -> dict[str, ast.Module]:
    """Parse each source, skipping any module that does not parse.

    A module that does not parse at the pinned revision contributes neither a
    field nor a silent skip: it cannot carry one, and counting it either way
    would misstate the denominator.
    """
    trees: dict[str, ast.Module] = {}
    for path, source in sources:
        try:
            trees[path.replace("\\", "/")] = ast.parse(source)
        except SyntaxError:
            continue
    return trees


def identifier_fields(sources: tuple[tuple[str, str], ...]) -> tuple[IdentifierField, ...]:
    """Every identifier-named production model field across pinned sources.

    Split from a revision-reading entry point so the bite proof and the
    contract tests can drive an explicit source snapshot, keeping them
    independent of whatever happens to be committed when they run.
    """
    trees = _parsed(sources)
    models = _model_class_names(trees)
    vocabulary = namespace_vocabulary()
    found: list[IdentifierField] = []
    for path, tree in trees.items():
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef) or node.name not in models:
                continue
            for statement in node.body:
                if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name):
                    continue
                name = statement.target.id
                if name.startswith(_DISPLAY_COMPANION_PREFIX):
                    continue
                token = matched_token(name, vocabulary)
                if token is None:
                    continue
                annotation = annotation_text(statement)
                found.append(
                    IdentifierField(
                        path=path,
                        line=statement.lineno,
                        model=node.name,
                        field=name,
                        annotation=annotation,
                        token=token,
                        enrolled=not is_bare_str(annotation),
                    )
                )
    return tuple(sorted(found, key=lambda item: (item.path, item.line, item.field)))


def unenrolled(fields: tuple[IdentifierField, ...]) -> tuple[IdentifierField, ...]:
    """The identifier-named fields still declared as a bare ``str``."""
    return tuple(item for item in fields if not item.enrolled)


def _ledgered() -> frozenset[tuple[str, str, str]]:
    """Every key answered by either ledger."""
    return _UNENROLLED_BASELINE | {entry.key() for entry in _ADJUDICATED}


def _worklist(lines: tuple[str, ...], header: str) -> str:
    """Render a failure as a worklist, so a red gate is actionable rather than noisy."""
    body = "\n".join(f"  {line}" for line in lines)
    return f"{header}\n{body}\n"


@pytest.fixture(scope="module")
def production_fields() -> tuple[IdentifierField, ...]:
    """The identifier-named production model fields at the pinned revision."""
    return identifier_fields(production_sources(_REVISION))


def test_vocabulary_derives_from_the_live_alias_family() -> None:
    """The vocabulary is computed from aliases that exist, not from a stale list.

    A fixture anchor for the derivation itself: if the identity facade stopped
    exporting aliases, the vocabulary would empty and every other assertion here
    would pass vacuously.
    """
    aliases = identifier_aliases()
    vocabulary = namespace_vocabulary()
    assert aliases, "core.identity exports no type aliases; the vocabulary would be empty"
    for alias in aliases:
        assert _snake(alias) in vocabulary, f"alias {alias} contributed no vocabulary token"
    assert "expediente_id" in vocabulary, "the aeat_ issuer prefix is no longer being stripped"


def test_declared_shared_stems_still_name_live_aliases() -> None:
    """Every declared stem's aliases still exist, so the stem is not vacuous.

    A stem is a hand-made claim that two aliases name one concept. If either
    alias is renamed or removed, the claim is no longer backed and must be
    re-made rather than left asserting a vocabulary token nothing supports.
    """
    exported = set(identifier_aliases())
    for stem in _SHARED_STEMS:
        missing = tuple(alias for alias in stem.aliases if alias not in exported)
        assert not missing, (
            f"shared stem {stem.stem!r} names aliases that no longer exist on core.identity: "
            f"{missing}. Re-adjudicate the stem rather than leaving it standing."
        )
        assert len(stem.aliases) >= 2, f"shared stem {stem.stem!r} needs two or more aliases to be a stem"


def test_free_text_populations_are_outside_the_vocabulary() -> None:
    """The rehomed exclusions still hold against the derived vocabulary.

    This is the falsifiable half of the rehoming. If an alias were ever added
    naming one of these populations, the exclusion prose would silently become
    a lie; here it fails instead and forces a re-adjudication.
    """
    vocabulary = namespace_vocabulary()
    for population in _FREE_TEXT_POPULATIONS:
        assert population.reason.strip(), f"free-text population {population.name!r} states no reason"
        for token in population.field_tokens:
            assert token not in vocabulary, (
                f"{token!r} is excluded as {population.name!r} but IS now in the derived "
                f"vocabulary. An alias was added that names it; re-adjudicate the exclusion."
            )


def test_free_text_anchors_are_still_bare_free_text(production_fields: tuple[IdentifierField, ...]) -> None:
    """The AEAT-prose anchors still exist and still carry free text.

    Without this the population would pass vacuously once the fields were
    renamed or retyped: the exclusion would keep excusing code that no longer
    exists. The anchors are read from the class body directly rather than from
    the candidate set, because these fields deliberately do NOT match the
    vocabulary and so never appear as candidates.
    """
    trees = _parsed(production_sources(_REVISION))
    for path, model, field in _FREE_TEXT_ANCHORS:
        tree = trees.get(path)
        assert tree is not None, f"free-text anchor module {path} no longer exists"
        annotations = {
            statement.target.id: annotation_text(statement)
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef) and node.name == model
            for statement in node.body
            if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name)
        }
        assert field in annotations, f"free-text anchor {model}.{field} no longer exists in {path}"
        assert is_bare_str(annotations[field]), (
            f"{model}.{field} is no longer free text ({annotations[field]}). The "
            f"AEAT-prose exclusion is obsolete and must be re-adjudicated."
        )


def test_display_companions_have_a_full_sibling() -> None:
    """Every excluded ``short_<x>`` field has a sibling ``<x>`` on the same model.

    The anchor for the structural ``short_`` exclusion. A truncated companion is
    excusable only because the full identity is declared beside it; if the full
    field is renamed or dropped, the companion is no longer a companion and the
    exclusion must be revisited rather than passing vacuously.

    Scoped to companions whose full sibling name is itself identifier
    vocabulary, so an unrelated ``short_description`` is not swept in.
    """
    trees = _parsed(production_sources(_REVISION))
    models = _model_class_names(trees)
    vocabulary = namespace_vocabulary()
    orphans: list[str] = []
    for path, tree in trees.items():
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef) or node.name not in models:
                continue
            names = {
                statement.target.id
                for statement in node.body
                if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name)
            }
            for name in sorted(names):
                if not name.startswith(_DISPLAY_COMPANION_PREFIX):
                    continue
                full = name.removeprefix(_DISPLAY_COMPANION_PREFIX)
                if matched_token(full, vocabulary) is None or full in names:
                    continue
                orphans.append(f"{path} {node.name}.{name} has no sibling {full}")
    assert not orphans, _worklist(
        tuple(orphans),
        "Truncated display companions without the full identity beside them. The "
        "short_ exclusion assumes the full field is declared on the same model:",
    )


def test_no_unenrolled_identifier_field_outside_the_ledgers(
    production_fields: tuple[IdentifierField, ...],
) -> None:
    """No identifier-named model field is bare ``str`` unless a ledger names it.

    The ratchet. A new bare identifier field fails here and must either be
    typed or entered in a ledger with a reason -- never silently accepted.
    """
    ledgered = _ledgered()
    open_sites = tuple(item for item in unenrolled(production_fields) if item.key() not in ledgered)
    assert not open_sites, _worklist(
        tuple(item.rendered() for item in open_sites),
        "Identifier-named model fields declared as bare `str` and named by no ledger. "
        "Type each with its core.identity alias, or record it with a stated reason:",
    )


def test_no_stale_adjudication(production_fields: tuple[IdentifierField, ...]) -> None:
    """Every adjudicated site still answers a live bare occurrence.

    A stale exemption is worse than a missing one: it reads as a considered
    judgement about code that has since moved or been fixed, and it silently
    widens to whatever later occupies its key.
    """
    live = {item.key() for item in unenrolled(production_fields)}
    stale = tuple(entry for entry in _ADJUDICATED if entry.key() not in live)
    assert not stale, _worklist(
        tuple(f"{entry.path} {entry.model}.{entry.field}" for entry in stale),
        "Adjudicated exemptions answering no live bare field. The site was typed, "
        "renamed or removed; strike the entry:",
    )


def test_every_adjudication_states_a_reason() -> None:
    """An exemption without a stated reason is indistinguishable from an oversight."""
    silent = tuple(entry for entry in _ADJUDICATED if not entry.reason.strip())
    assert not silent, _worklist(
        tuple(f"{entry.path} {entry.model}.{entry.field}" for entry in silent),
        "Adjudicated exemptions with no stated reason:",
    )


def test_no_stale_baseline_entry(production_fields: tuple[IdentifierField, ...]) -> None:
    """Every baseline entry still names a live bare field, so the ledger only shrinks.

    Enrolling a field is the intended outcome; leaving its entry standing is
    not. Failing here is the ratchet tightening -- strike the entry in the same
    change that types the field.
    """
    live = {item.key() for item in unenrolled(production_fields)}
    stale = tuple(sorted(entry for entry in _UNENROLLED_BASELINE if entry not in live))
    assert not stale, _worklist(
        tuple(f"{path} {model}.{field}" for path, model, field in stale),
        "Baseline entries that are no longer bare. The field was enrolled, renamed or "
        "removed: strike the entry so the ledger keeps shrinking:",
    )


def test_the_two_ledgers_do_not_overlap() -> None:
    """A site is either a decision or a gap, never recorded as both."""
    overlap = tuple(sorted(_UNENROLLED_BASELINE & {entry.key() for entry in _ADJUDICATED}))
    assert not overlap, _worklist(
        tuple(f"{path} {model}.{field}" for path, model, field in overlap),
        "Sites recorded in BOTH ledgers. An adjudicated decision must not also be carried as an unenrolled gap:",
    )


def test_detector_reports_a_bare_identifier_field_and_ignores_an_enrolled_one() -> None:
    """The detector fires on a bare identifier field and stays silent on a typed one.

    Drives the real scanner over an explicit source snapshot, which is the same
    shape the sibling censuses under ``dev/identity/`` use for their contract
    tests. Without this, a matcher that silently stopped matching would make
    every assertion above pass while detecting nothing.
    """
    source = (
        "from pydantic import BaseModel\n"
        "class Probe(BaseModel):\n"
        "    expediente_id: str\n"
        "    transaction_id: TransactionId\n"
        "    short_work_unit_id: str\n"
        "    unrelated_label: str\n"
    )
    found = identifier_fields((("src/cadrumo/probe.py", source),))
    by_field = {item.field: item for item in found}
    assert set(by_field) == {"expediente_id", "transaction_id"}, (
        f"unexpected candidate set {sorted(by_field)}: a short_ companion and a "
        f"non-vocabulary field must not be reported"
    )
    assert not by_field["expediente_id"].enrolled
    assert by_field["transaction_id"].enrolled
    assert unenrolled(found) == (by_field["expediente_id"],)
