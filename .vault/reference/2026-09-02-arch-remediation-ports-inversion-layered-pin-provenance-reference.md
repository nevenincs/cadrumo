---
tags:
  - '#reference'
  - '#arch-remediation-ports-inversion'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:857c29e79af3087c8916e5bac44ba315b0a467ee30f32175fd2937b9e8f57be0'
related: []
---

# `arch-remediation-ports-inversion` reference: `Displaced layered-contract pins: provenance of the eighty-two production edges`

Grounding for the layered import contract's eighty-two production violations,
established by reading the live import graph and then tracing each edge back
through the history of `.importlinter` and of the modules involved. The
question the trace had to settle was whether the edges were newly introduced
un-inverted dependencies or previously reviewed edges that had lost their pin.

## Summary

### What the gate reported

`lint-imports` reported ten contracts kept and one broken. The broken contract
was `AEAT layered architecture`, with eighty-two violations across thirty-four
source modules. Every source was under `cadrumo.application`; every target was
under `cadrumo.adapters` or `cadrumo.llm`, the two packages the contract
declares as one peer layer immediately outside `application`. Not a single
violation ran in any other direction, and no violation reached inward past the
application layer.

Concentration by source package: `application.ledger` 58, `application.modelo`
10, `application.live` 5, `application.aggregation` 2,
`application.calculations` 2, and one each in `application.auth`,
`application.bienes_inversion`, `application.diagnostic_models`,
`application.prorrata_register`, `application.user_profile`.

### The edge class is the one the contract already permits

The contract's own header prose states that the application layer may import
adapters directly for outbound wiring, on the authority of the architecture
restructure decision at section 538, and that the exception ledger pins each
existing application source module individually while full inversion remains
deferred. All eighty-two violations are that class. The contract carried
roughly 2833 `ignore_imports` entries at the time of measurement, grouped under
rationale comments in exactly this pattern.

### Why the pins were missing

Three findings, each reproducible from history.

First, a commit titled `chore(imports): retire relocated module allowances`
deleted forty-seven pin lines. Its subjects were modules the private-to-public
promotion campaign had renamed, for example `ledger._evidence_input` to
`ledger.evidence_input`. The commit deleted the stale lines rather than
re-keying them to the promoted names, and left every rationale comment in
place. The result was roughly fifteen orphaned rationale blocks in
`.importlinter` describing pins that no longer existed, and zero remaining pins
for `application.ledger`.

Second, a commit titled `refactor(ledger): split evidence_draft into the five
responsibilities it carried` split one 2413-line module into five. Its own
message records that the layering contracts were not verified, because
`lint-imports` evaluated zero contracts on every run that day, aborting first
on a stale ignore entry and then on a syntax error. The message states the
edge-set argument as structural rather than as a gate result. Reading the
pre-split module at its parent commit confirms the claim: its outward imports
were `adapters.inbound.einvoice`, `adapters.persistence.profile.invoices`,
`adapters.persistence.storage`, and eight `cadrumo.llm` modules. Every target
reached by the five successor modules appears in that list, so the split
redistributed a reviewed reach across new names without adding one.

Third, the gate was blind for an extended period for two independent reasons,
both fixed shortly before this measurement: a stale ignore entry aborted the
run before any contract was evaluated, and a `cp1252` encoding failure killed
the renderer before it printed a tally. Violations therefore accumulated
unreported rather than arriving at once, which is why a campaign that was
otherwise re-keying pins commit by commit was able to drop batches of them.

### Per-class inventory of the eighty-two

Every edge falls into one of five classes, each already carrying stated
rationale in the contract.

Relocated-concrete construction, the largest class. The ports-inversion
campaign moved concrete repositories into the persistence adapter behind their
protocols; the application module that composes the object still names the
concrete because it is the composition site. Targets:
`persistence.profile.transactions`, `.invoices`, `.buckets`,
`.modelos_work_units`, `.modelos_calculation`, `.modelos_edit_receipts`,
`.bienes_inversion`, `.prorrata_register`, `.justificante`, `.usage_ratios`,
and the storage substrate they resolve through -
`storage.runtime_repository`, `.attachment`, `.secure_object_namespaces`,
`.errors`, `.envelope.secure_bound_repository`, `.sql.secure_objects`.

Inbound-format consumption. Reading an externally authored format is
inbound-adapter work and the application layer consumes the answer. Targets:
`inbound.einvoice.parsers`, `.xml`, `.shape`,
`inbound.financial.providers.{base,csv,detection,ofx,pdf_n26,xlsx}`,
`inbound.pdf.page_text_extraction`.

Outbound AEAT integration. Driving the Sede and its authentication is the
purpose of the `application.live` and `application.auth` packages. Targets:
`outbound.aeat.sede.{censal_datos,declarations,declarations_capture,walker}`,
`outbound.aeat.auth.clave_movil_support`.

Outbound inference telemetry. Targets: `outbound.llm.usage`,
`outbound.llm.run_telemetry`.

Peer-tier inference consumption. `cadrumo.llm` is declared a sibling of
`cadrumo.adapters` on the adapter tier, so an application reach into it is an
outward edge of the same class. Targets: `llm.models`, `.errors`,
`.suggestions`, `.providers.local`, `.text_classifier`, `.vision_classifier`,
`.evidence_draft_text`, `.evidence_draft_vision`, `.supply_nature_proposal`.

### Modules whose reach genuinely went to zero

Four `application.ledger` modules that once held pins now import nothing
outward at all: `extracted_document_cache`, `extraction_draft_store`,
`confirmation_record`, and `rule_repository`. Their inversion completed. The
rationale comment describing two of them as reaching encrypted persistence was
therefore false at the time of measurement and was removed rather than
re-keyed.

### Measurement commands

The violation list comes from `lint-imports` with `PYTHONIOENCODING=utf-8` set;
without it the renderer dies before printing. Line numbers for each edge come
from the same output and were read back against the live source to confirm the
import site and the symbol imported. The contract sets
`unmatched_ignore_imports_alerting = error`, so a pin that overshoots its real
edge fails the run, which makes the re-keyed set self-checking.
