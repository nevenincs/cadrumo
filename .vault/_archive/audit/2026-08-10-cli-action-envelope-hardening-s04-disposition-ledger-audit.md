---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:c53529b06a05d2d79c0f08d084ee50ad0aa1580a6da72d49f8d6d55f01e6cc93'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-adr]]"
---

# `cli-action-envelope-hardening` audit: `S04 disposition ledger review`

## Scope

Formal review of W01.P01.S04 and the narrow S03 identity correction against the
accepted ADR, reference, and plan. The review verified the exact current-census
join, whitespace-preserving identity round trips, and semantic adjudication
across every role cluster, with programmatic distributions and source-level
sampling of error registry, operator help, provisioning, diagnostics, overview,
workflow, modelo, and ledger concentrations.

## Findings

### s04-disposition-ledger | critical | Blanket command-literal exclusion rules misclassify actionable production guidance

The ledger is structurally complete but is not a trustworthy semantic
adjudication. All 85 excluded rows are command literals, and their reasons are
generated from the absence of a census-recognized alias, assignment, or renderer
sink rather than from the source behavior. Forty-six exclusions share the same
normalized claim that an expression is merely a reference/example. Direct
source inspection disproves that claim across multiple high-density families:

- `WorkflowState._no_active_profile_next_action` returns `aeat config login
  NAME` or the complete profile-create command as its operator-facing next
  action, yet both rows are excluded.
- `_next_wizard_action` returns five different profile, auth, and overview
  commands according to readiness state, yet all five are excluded.
- `_auth_configure_next_action` returns configure/test commands selected from
  auth preconditions, yet three command rows are excluded.
- `_bindings_discovery_command` returns the modelo missing-binding recovery
  command, yet both literals are excluded.
- `_profile_record_repair_next_action` selects and returns two repair commands,
  yet both are excluded.
- Ledger command literals are passed as `source_command` into real archive,
  remove, reset, split, merge, classification, import, and related mutations,
  yet the application and CLI clusters are broadly excluded as mere examples.

This is a campaign-critical false closure: formal symbol and enclosing-function
grounding is present, but the reasons do not ground the disposition in what the
function actually does. The pattern spans at least workflow, wizard, auth,
modelo, repair, ledger, review, and error-boundary code, so isolated row edits
would not repair the adjudication method.

Resolution: closed on final re-review. Seventy-two formerly excluded,
action-bearing command literals are now producers. The role delta is exact:
producer rose from 902 to 974 and exclusions fell from 85 to 13, while the
original 143 renderers, 126 transformers, and nine validators are unchanged.
Every remaining exclusion was independently inspected in source: six are
static `MutatingNounGroupContract.cli_path` group identifiers, six are MCP
`_DESCRIPTIONS` resource labels without an `app` or `config` CLI root, and one
is the bare `aeat ` prefix used only to render an already-resolved verb schema.
None is a runnable recovery action, action producer, or mutation provenance
value.

### s04-disposition-ledger | high | The conformance gate proves cardinality and shape but cannot detect semantic misadjudication

The new integration gate exercises missing, duplicate, stale, ungrounded, and
unknown-field failures against the real census. It never asserts role semantics
or source evidence, so all 85 false exclusions pass. The role distribution is
902 producers, 143 renderers, 126 transformers, 85 exclusions, nine validators,
and no canonical owners or tests. Candidate-role cross-tabs reveal broad
mechanical mapping: 343 command literals become producers, 105 become
renderers, and 85 become exclusions; all 50 field definitions become
transformers. Reasons are textually unique because each embeds path, line, and
symbol, but normalization exposes large templates: 160 error-code producer
reasons, 144 paired error-code command reasons, 99 help-entry renderer reasons,
50 legacy-field transformer reasons, and the 46 identical expression-exclusion
reasons. This is rule-generated classification presented as manual semantic
adjudication.

The dense clusters that were sampled outside the false exclusions were
internally plausible: all 304 error-registry rows are producers; all 103
operator-help rows are renderers; provisioning splits into 32 producers and ten
transformers; diagnostics into 16 producers, ten transformers, five validators,
and two renderers. Those samples do not offset the confirmed exclusion pattern.
Legacy free-form field definitions were labelled transformers rather than
canonical owners, so no concrete false `canonical_owner` row was found.

Resolution: closed on final re-review. The structural test remains identity-
based, while new semantic ratchets import the real ledger and pin representative
return/provenance producers across workflow, wizard, auth, modelo, repair, and
both application and CLI ledger layers. Exclusions are restricted to the three
reviewed source-context categories; former generic rationale markers are
forbidden. The normalized-reason invariant is active rather than observational:
it strips coordinates and quoted identities, detects a seventh repetition of a
category template in a constructed overflow proof, and does not assert the
ledger's total or today's role counts.

Validation evidence: the current census, TOML ledger, validated result, and
unique disposition-key set each contain 1,265 identities; this is an observed
join measurement, not a count gate. The validator completed successfully. All
ten S03 disposition tests passed, including exact action-identity whitespace
round trip and whitespace-only rejection. The focused real-census conformance
test passed. Ruff passed, and basedpyright reported zero errors, warnings, or
notes. These green checks establish representation integrity while the findings
above establish that semantic integrity remains open.

Final remediation evidence: the validator reconciled the full current ledger.
The three focused structural, recovered-producer, and exclusion-context tests
passed in 59.77 seconds. Ruff passed, and basedpyright reported zero errors,
warnings, or notes. No S04 findings remain open.

## Recommendations

1. Re-adjudicate all 85 exclusions from source behavior, beginning with the
   named workflow, wizard, auth, modelo, repair, and ledger clusters. An
   exclusion reason must explain why the concrete value cannot reach an
   operator-facing action or provenance contract, not merely list scanner
   constructs that were absent.
2. Remove blanket directory, candidate-role, and syntactic-sink disposition
   rules from the ledger-generation workflow. Preserve programmatic clustering
   for review queues, but require an evidence-backed semantic decision per row.
3. Add independent semantic ratchets for known producer-return helpers,
   action-bearing constructor/keyword arguments such as `source_command`, and
   representative rows from every dense cluster. Keep the exact 1:1 validator
   as the structural floor rather than treating it as semantic closure.
4. Re-run the full distribution/outlier review after re-adjudication and require
   every exclusion family to survive direct source sampling before S04 closes.

All recommendations are implemented and verified.
