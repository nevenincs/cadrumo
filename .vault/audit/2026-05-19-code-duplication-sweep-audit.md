---
tags:
  - '#audit'
  - '#code-duplication-sweep'
date: '2026-05-19'
modified: '2026-05-19'
related:
  - "[[2026-05-19-spanish-stem-terminology-authority-adr]]"
  - "[[2026-05-19-code-duplication-sweep-adr]]"
---

# code-duplication-sweep audit: spanish-stem-parent-trace

## Scope

The spanish-stem terminology-authority ADR (2026-05-19) reverses the prior
code-duplication-sweep direction on Value-Added Tax identifiers: Spanish stems
become authoritative, the domain/vat package migrates into domain/iva,
VatClassification / VATClassification and its companion symbols
(VatRegulation, VATRateKind, VATCatalogue, IssuerResidency,
CustomerResidency, InvoiceDirection) consolidate into
IvaInvoiceClassification and Spanish-stem equivalents.

The superseding ADR Consequences section explicitly defers a
Parent-ADR-supersession ripple trace pass. This audit performs that pass,
inventories every vault ADR that touches the reversed direction, classifies
each as SUPERSEDED-DIRECTION, INCIDENTAL-MENTION, or INDEPENDENT, and records
the annotation action taken.

This audit is read-only on source code. No production code was modified.
Frontmatter on the traced ADRs was not mutated; supersession is expressed via
a top-of-body block-quote note that matches the established precedent already
landed on the now-superseded code-duplication-sweep ADR.

## Findings

### SUPERSEDED-DIRECTION (six ADRs)

Each ADR below pins the now-reversed domain/vat direction at a structural
level: package path, public symbol names, or the VAT-canonical English form
for tax-classification identifiers. A top-of-body block-quote
PARTIALLY-SUPERSEDED note has been inserted into each ADR pointing back to
the spanish-stem terminology-authority ADR.

- 2026-04-13-r1-vat-enumeration-adr. Established the
  src/aeat/domain/financial/vat/ subpackage and the original
  VATCategory, VATRateKind, VATRegulation, VATCatalogue
  English-form enumeration. The IVA cluster table in the superseding ADR
  renames each of these symbols and migrates the package path; the
  enumeration substrate itself remains in force, but the names and home
  package reverse. Annotation added.
- 2026-04-17-modelo-303-formulas-adr. Declares the _classification.py
  module under domain/financial/vat and the VATClassification,
  VATClassificationCriteria, IssuerResidency, CustomerResidency,
  InvoiceDirection, CasillaRole, Modelo303Contribution, and
  MODELO_303_CASILLA_MAPPING symbol set. The Modelo 303 ruleset shape
  is unaffected; every classification-side identifier named in this ADR
  is on the rename ledger. Annotation added.
- 2026-05-06-modelo-369-vat-centralization-adr. Extends aeat.domain.vat
  with the OSS/IOSS regime substrate, classifier rules, and the
  ledger_oss_aggregation binding source. Decisions 1 and 4 to 8 are
  written against the domain/vat module path which the superseding ADR
  reverses to domain/iva. The decisions themselves (regime taxonomy,
  ledger-binding shape, Modelo 369 single-modelo three-revisions shape,
  teardown sequencing) survive; only the package home and the spelling
  of IvaRate, VatRateKind change. Annotation added.
- 2026-05-12-cli-workflow-redesign-domain-harvest-vat-classification-adr.
  Title and body pin VATClassification, VATClassificationCriteria, and
  domain/vat/_classification.py as the deterministic resolver behind
  aeat.application.ledger.classify_ledger_transaction. CLI surface
  app-ledger-classify and the application wrapper survive; symbols
  rename on the IVA cluster ledger. Annotation added.
- 2026-05-12-cli-workflow-redesign-domain-harvest-oss-ioss-adr. Pins
  domain/vat/_oss.py as the OSS/IOSS substrate path; the superseding ADR
  renames the package to domain/iva/_oss.py. App-modelo orchestration,
  profile keys iva.regime and iva.oss_enrolled, binding flow, and event
  surface are unaffected. Annotation added.
- 2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-adr.
  Implementation directive reads: Create a legal IVA prorrata substrate
  under domain/vat. Path reverses to domain/iva. LIVA arts. 101-103
  grounding and the application-aggregation observation contract are
  unaffected. Annotation added.

### INCIDENTAL-MENTION (four ADRs)

These ADRs mention VAT or IVA terminology or symbol paths but do not depend
on the reversed direction; their core decisions stand. An Updated 2026-05-19
annotation note has been inserted at the top of each pointing to the
superseding ADR so future readers can resolve symbol renames at the call
site. Frontmatter unchanged.

- 2026-05-19-iva-compensation-chain-adr. Uses Modelo 303 casilla
  identifiers and the internal id iva.compensacion-anteriores (already
  Spanish-stem). No domain/vat or VatClassification reference; the
  compensation-chain remediation lives in registry TOML and
  _relation_prefill.py. Already flagged by the prior ADR-Specialist pass;
  annotation added.
- 2026-05-19-live-iva-compensation-wallet-adr. Defines
  IvaCompensationWalletObservation and
  IvaCompensationReconciliationDecision (already Spanish-stem aligned).
  The adapter path _iva_compensation_wallet.py and the reconciliation
  module _iva_wallet_reconciliation.py are already Spanish-stem
  compliant. Already flagged by the prior ADR-Specialist pass; annotation
  added.
- 2026-05-12-cli-workflow-redesign-adr. The apex CLI roadmap mentions
  domain/vat/_classification.py and domain/vat/_oss.py as backend
  exit-cap targets and domain/vat legal prorrata substrate. The ADR
  core decision is the CLI verb tree; module-path mentions resolve
  through the rename ledger when the IVA migration lands. Annotation
  added.
- 2026-05-16-resource-management-api-adr. References vat_catalogues
  VatCatalogueRepository, vat_rate_tables VatRateTableRepository, and
  VAT_CATALOGUES_BY_YEAR. The resource-management API direction (typed
  accessor surface, single env-override seam) is independent of
  VAT-vs-IVA stem. Repository identifiers will follow the cluster
  rename when it lands. Annotation added.

### INDEPENDENT (one ADR examined)

- 2026-04-20-classification-harmonization-adr. Issue 255 umbrella
  for manual classification provenance and confidence contract. VAT
  appears as one of several classification dimensions (income or expense
  nature, category, deductible proportion, VAT treatment). No directional
  claim on VAT-vs-IVA naming, no module-path pin, no symbol decision
  that the superseding ADR reverses. No action taken.

### Other 60+ ADRs with VAT or IVA mentions

The broad VAT-or-IVA word-boundary scan returned 69 ADRs. After targeted
filtering on direction-bearing references (VatClassification,
VATClassification, domain/vat, english-form, invoice classification,
value-added tax) the candidate set collapses to the 11 ADRs catalogued
above plus the two 2026-05-19 ADRs already authored by the spanish-stem
ADR itself. The remaining 60+ ADRs reference IVA only at the modelo-domain
level (Modelo 303, 130, 100 calculation content, IRPF cross-references,
deadline windows, profile keys already spelled iva.something) and do not
pin the reversed direction. No action required.

## Recommendations

- Plan-authoring agent should retarget code-duplication-sweep plan W03.P04
  per the superseding ADR Plan-retargeting block.
- When the IVA cluster rename lands, the six SUPERSEDED-DIRECTION ADRs
  above should be revisited and either confirmed as fully implemented
  against the new symbol set, or re-superseded by a follow-up ADR if any
  reversed decision needs further amendment.
- Future ADR scaffolding should consider adopting an explicit status
  frontmatter key on every new ADR so supersession state is
  machine-readable in vault stats and vault check.

## Tally

- ADRs scanned by targeted greps: 11 catalogued, plus 1 INDEPENDENT
  examined, plus 2 authored by the spanish-stem ADR itself, plus 60+
  incidentally IVA-mentioning ADRs filtered out as non-directional.
- SUPERSEDED-DIRECTION: 6.
- INCIDENTAL-MENTION: 4.
- INDEPENDENT: 1.
- Supersession markers added: 6.
- Annotation notes added: 4.
- ADRs with pre-existing supersession (no further action): 1
  (2026-05-19-code-duplication-sweep-adr).
