# Ledger review, imports, rules, inventory and read surfaces

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-160` · **Topic:** [Operator interfaces, part 1: command graph and principal workflows](../topics/operator-interfaces-part-1.md)

<!-- preserved:article -->
## Scope and capability

This chunk contains 14 CLI modules, 5,384 source lines and 46,112 measured proxy tokens. Every assigned range was read across nine bounded pages; there are no unread portions. This is static inspection only: no application imports, command execution or behavioral tests were performed.

The modules turn ledger records into a broad operator workflow. Users can review purchase-invoice drafts before confirmation; import statements with a dry-run and optional verification; create inventory ledgers, append movements and preview valuation; inspect, filter, export and audit transactions; manage usage-ratio overrides and classification rules; and request manual, rule-based or LLM-assisted classification.

The evidence-review queue can filter by blocking reason, finding, advisory or blocking-only status. A single-document view emits every scalar draft field, value, origin, grounding result, anchor, refused anchor, candidate and note, plus discrepancies and blockers. The handler exposes no bulk “confirm all”: a caller must supply one typed resolution for each blocking finding, choosing a candidate, supplying a value or attesting with a note (review queue/view (`src/cadrumo/entrypoints/cli/_ledger_evidence_review_cli.py`), resolution parser (`src/cadrumo/entrypoints/cli/_ledger_evidence_review_cli.py`)). Party attribution and country-code vocabulary findings remain advisory and distinct from blockers; the surface explains uncertainty rather than deriving tax residence itself.

Statement import normalizes a closed provider ID, resolves files or a folder through the source planner, caps the operation at the application-declared maximum number of files, and passes period/year, dry-run, verification and optional verification source to the profile operation. Results report counts, duplicate indicators, source digests and validation summaries; detailed parser diagnostics are intentionally bounded or withheld. Refused files are separately listed, and dry-run is represented in both result and notice channels (import handler (`src/cadrumo/entrypoints/cli/_ledger_import_cli.py`)). Inventory commands can create a profile ledger, append a typed movement, preview canonical valuation, and record a closing-authority DTO. Acquisition-cost data can be supplied as JSON on stdin; malformed JSON is refused with localized detail (inventory create/movement (`src/cadrumo/entrypoints/cli/_ledger_inventory_cli.py`)).

The read facade includes list/view/status, check and preflight, history, track, export and diagnostics. Lists expose pagination and truncation metadata; status reports active lifecycle counts, readiness findings, stale filings and the count of unconverted-currency rows excluded from gross EUR totals. Check adds one-sided invoice/transaction links and can resolve a repair action for a single inconsistency. Export writes a caller-selected artifact while the JSON envelope excludes raw bytes and reports the destination and digest (check/preflight (`src/cadrumo/entrypoints/cli/_ledger_read_cli.py`), export/list (`src/cadrumo/entrypoints/cli/_ledger_read_cli.py`), status/tracking (`src/cadrumo/entrypoints/cli/_ledger_read_cli.py`), export schema (`src/cadrumo/entrypoints/cli/_ledger_payloads.py`)). LLM diagnostics aggregate usage, estimated cost, tokens and classification-confidence distributions without returning model response text (diagnostics (`src/cadrumo/entrypoints/cli/_ledger_read_cli.py`)).

## Decisions, automation and data

The LLM path separates proposal from decision. Without `--apply`, classification and saturated-IVA suggestions are previews marked non-persisted. With explicit apply, the handler uses the registered review operation, correlates the settled receipt to the same profile, transaction, suggestion kind, reviewed digest and provenance, and checks the terminal effect before presenting the mutation. Reject records a declined audit event while leaving the transaction unclassified. In saturated mode the model selects classification/category; the system derives IVA rate, base and amount through the registry. Autosplit likewise uses model-selected child proportions/categories while the registry supplies regulated amounts (registered review driver (`src/cadrumo/entrypoints/cli/_ledger_llm_cli.py`), LLM routes (`src/cadrumo/entrypoints/cli/_ledger_llm_cli.py`), LLM payloads (`src/cadrumo/entrypoints/cli/_ledger_llm_payloads.py`)). An operator can also select an IVA category and request system derivation without invoking an LLM. Separate Modelo 210 options are confined to direct classification and delegate incoming-only/completeness checks to the application resolver (M210 options (`src/cadrumo/entrypoints/cli/_ledger_m210_classify_cli.py`)).

Classification rules are stored per profile, content-addressed and ordered by priority. Add/list expose those records; ordinary apply writes to eligible transactions, while `--dry-run` previews the same first-match result and already-classified transactions are skipped unless the operator requests reaffirmation (rule command (`src/cadrumo/entrypoints/cli/_ledger_rules_cli.py`), rule result contracts (`src/cadrumo/entrypoints/cli/_ledger_rule_payloads.py`)). Usage-ratio commands list eligible categories, set/unset per-category overrides and validate persisted overrides against current eligibility and the censo-consistency rule. Omitted year defaults to the Madrid calendar year, while list/set/eligible accept an explicit historical year (ratio handlers (`src/cadrumo/entrypoints/cli/_ledger_ratios_cli.py`), ratio schemas (`src/cadrumo/entrypoints/cli/_ledger_ratios_payloads.py`)).

The payload layer carries typed transaction identities, ISO dates, currencies, history, import references, removal blockers, filing participation and lifecycle/evidence/edit lineage. It adds branch validation to the review result, validates M210 money/rate bounds, and reasserts required export-row dates and nonnegative decimal fields after conversion to string. Ledger status and check outputs make readiness and stale filing facts actionable instead of returning only counts. Data still includes sensitive amounts, descriptions, tax identifiers, notes, source filenames and actor identities; this CLI layer displays them to the active operator. Profile-worker authentication and storage protection are dependencies, not guarantees established by these presentation modules.

## Security and implementation assessment

The strongest controls in this slice are the per-document evidence-review boundary, explicit LLM apply/reject decision, receipt/digest correlation, verified distinction between preview and persisted output, import dry-run, maximum import-file count, and typed output constraints. Ledger remove/reset result schemas preserve dry-run state, cascaded evidence/attachment IDs and finalized-modelo blockers; they expose the consequence surface even though mutation handlers live in adjacent modules.

One local transport-schema weakness is visible in `RuleApplyResult`: every dry-run and live-apply branch field is optional and there is no model validator requiring exactly one complete branch. Its current sole CLI producer selects fields from a projection outcome, so this alone does not establish that the product emits a malformed result. It does mean the DTO itself accepts empty or mixed shapes if constructed elsewhere; compare the explicit three-branch invariant in `LedgerReviewResult` (rule apply schema (`src/cadrumo/entrypoints/cli/_ledger_rule_payloads.py`), review branch validator (`src/cadrumo/entrypoints/cli/_ledger_payloads.py`)). Synthesis should check whether the registered schema conformance tests exercise producer branches and whether the application projection enforces the same distinction.

Several inputs are passed onward to profile workers after this boundary reads local files or stdin. The inventory cost payload is validated as a domain DTO, import source planning imposes its file-count bound, and export omits raw bytes from JSON. This chunk does not show universal byte-size limits, filesystem containment, path-symlink handling or log redaction; those controls must be checked in the worker and storage layers rather than inferred from the CLI. LLM review responses include free-form reason text, and the operators' confirmation choices may contain values or notes; the downstream registered operation and audit trail own their retention.

## Dependencies and follow-up

The handlers depend on authenticated runtime workers for ledger import, inventory, list/read, LLM review, rule application and ratio operations. They also use the registry for category/IVA derivation, the model/review domain for evidence blockers, and operation receipt types to distinguish preview, rejection and applied effects. Synthesis should reconcile these with the application authorization, persistence and operation journal, confirm that live-write policy matches each runtime route, and review file limits and output retention. No legal calculation or current-law claim is certified here.

## Complete assigned-file coverage

All 14 manifest files are linked below; every assigned line was read.

- _ledger_evidence_review_cli.py (`src/cadrumo/entrypoints/cli/_ledger_evidence_review_cli.py`)
- _ledger_import_cli.py (`src/cadrumo/entrypoints/cli/_ledger_import_cli.py`)
- _ledger_inventory_cli.py (`src/cadrumo/entrypoints/cli/_ledger_inventory_cli.py`)
- _ledger_list.py (`src/cadrumo/entrypoints/cli/_ledger_list.py`)
- _ledger_llm_cli.py (`src/cadrumo/entrypoints/cli/_ledger_llm_cli.py`)
- _ledger_llm_payloads.py (`src/cadrumo/entrypoints/cli/_ledger_llm_payloads.py`)
- _ledger_m210_classify_cli.py (`src/cadrumo/entrypoints/cli/_ledger_m210_classify_cli.py`)
- _ledger_payloads.py (`src/cadrumo/entrypoints/cli/_ledger_payloads.py`)
- _ledger_ratios_cli.py (`src/cadrumo/entrypoints/cli/_ledger_ratios_cli.py`)
- _ledger_ratios_payloads.py (`src/cadrumo/entrypoints/cli/_ledger_ratios_payloads.py`)
- _ledger_read_cli.py (`src/cadrumo/entrypoints/cli/_ledger_read_cli.py`)
- _ledger_review_cli.py (`src/cadrumo/entrypoints/cli/_ledger_review_cli.py`)
- _ledger_rule_payloads.py (`src/cadrumo/entrypoints/cli/_ledger_rule_payloads.py`)
- _ledger_rules_cli.py (`src/cadrumo/entrypoints/cli/_ledger_rules_cli.py`)
<!-- /preserved:article -->
