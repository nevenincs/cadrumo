---
tags:
  - '#plan'
  - '#cli-persona-testimonials'
date: '2026-06-30'
modified: '2026-08-15'
body_hash: 'sha256:61e3ae0c52976d5c01e0f24a0cf3dd1b76252b8b3a75c8831a7cf0052ccc0619'
tier: L3
related:
  - '[[2026-06-04-cli-persona-testimonials-adr]]'
  - '[[2026-06-04-cross-campaign-hardening-adr]]'
  - '[[2026-06-02-ledger-operator-hardening-adr]]'
  - '[[2026-06-30-cli-persona-testimonials-audit]]'
---
# `cli-persona-testimonials` plan

## Wave `W01` - campaign intake and evidence authority

Classify the open-ended testimonial corpus, concurrent worktree state, and prior closeout evidence before assigning code changes. This wave feeds every downstream hardening wave and keeps artifact truth separate from product truth.

### Phase `W01.P01` - testimonial corpus and artifact authority

Build a current, append-only inventory of persona roots, transcripts, final summaries, and closeout evidence without assuming the corpus is bounded.

- [x] `W01.P01.S01` - Inventory persona roots transcripts summaries and closeout gaps; `tmp/personas`.
- [x] `W01.P01.S02` - Reconcile testimonial closeout ledger against the vault audit trail; `.vault/audit`.
- [x] `W01.P01.S03` - Record the current campaign tracker as the canonical wave schedule; `.vault/plan`.

### Phase `W01.P02` - shared worktree ownership and agent routing

Classify dirty files, concurrent agent ownership, and safe assignment boundaries before any worker mutates code.

- [x] `W01.P02.S04` - Classify shared worktree dirty files and active ownership before assignment; `.`.
- [x] `W01.P02.S05` - Brief worker agents with RAG no-fallback and worktree-safety constraints; `agent orchestration`.

## Wave `W02` - P0 calculation and data-safety hardening

Harden the highest-risk calculation and data-loss paths first: IVA first-period compensation, ledger import provenance and deduplication, and cross-profile identity resolution. Later replay and live waves depend on these invariants.

### Phase `W02.P03` - M303 first-period compensation authority

Prove or harden the legal and implementation boundary for first-period zero compensation, prior filing evidence, and cross-period suppression.

- [x] `W02.P03.S06` - Audit first-period IVA compensation suppression against registry requirements; `src/aeat/application/modelo/_iva_wallet_gate.py`.
- [x] `W02.P03.S07` - Add real-behavior M303 first-period and prior-filing regression coverage; `src/aeat/application/modelo/tests/test_local_cross_period_carry.py`.
- [x] `W02.P03.S08` - Verify operator-visible M303 wallet guidance and translations; `src/aeat/locales`.

### Phase `W02.P04` - ledger import and provider provenance

Verify that raw bank imports, provider detection, duplicate handling, and corpus-scale import/export behavior preserve financial facts without data loss.

- [x] `W02.P04.S09` - Harden ledger provider detection and unsupported-source diagnostics; `src/aeat/adapters/inbound/financial/providers`.
- [x] `W02.P04.S10` - Harden import deduplication provenance and gap diagnostics; `src/aeat/application/ledger`.
- [x] `W02.P04.S11` - Exercise corpus import-export roundtrip without permissive imports; `src/aeat/entrypoints/cli/tests/test_ledger_corpus_import_export.py`.

### Phase `W02.P05` - cross-profile identity resolution

Sweep profile-id, bucket-id, display-label, active-profile, and command-family resolution so one taxpayer cannot bleed into another.

- [x] `W02.P05.S12` - Audit active-profile label-to-UUID normalization at the CLI root; `src/aeat/entrypoints/cli/__init__.py`.
- [x] `W02.P05.S13` - Harden workflow bucket-scan ambiguity and tombstone behavior; `src/aeat/application/workflow/_profile_bucket_scan.py`.
- [x] `W02.P05.S14` - Sweep profile identity CLI journeys for by-id and by-label parity; `src/aeat/entrypoints/cli/tests`.

## Wave `W03` - persona replay and export evidence closure

Re-run the weak persona/export roots as concrete operator journeys and close the local-export and annual Renta evidence edges that were not honestly proven by prior summaries.

### Phase `W03.P06` - weak testimonial replay roots

Replay the known weak persona roots as real operator journeys and turn any reproduced defect into a bounded fix step.

- [x] `W03.P06.S15` - Replay weak IVA cross-period company and pos-chain persona roots; `tmp/personas`.
- [x] `W03.P06.S16` - Replay mixed-income autonomo and employee persona roots; `tmp/personas`.
- [x] `W03.P06.S17` - Replay raw Ana and Taller transcript roots through the current CLI; `tmp/personas`.

### Phase `W03.P07` - annual Renta and local export evidence

Close Modelo 100 annual Renta, borrador, filing-record, and local export evidence gaps without treating local files as official AEAT proof.

- [x] `W03.P07.S18` - Harden Modelo 100 borrador observation binding and parser coverage; `src/aeat/adapters/inbound/borrador`.
- [x] `W03.P07.S19` - Verify Modelo 100 calculation and export closure from annual Renta journeys; `src/aeat/application/modelo`.
- [x] `W03.P07.S20` - Harden local export evidence receipts and no-official-evidence messaging; `src/aeat/application/modelo/_export.py`.

## Wave `W04` - legal live-read and adapter hardening

Ground remaining ambiguity in official sources and harden read-only live AEAT, borrador, justificante, and EU VAT surfaces without introducing submission or mutation behavior.

### Phase `W04.P08` - read-only live AEAT surfaces

Verify live-read gates, justificante capture, filed-observation capture, and portal/borrador commands remain read-only and evidence-backed.

- [x] `W04.P08.S21` - Verify live-read command tree has no submit or mutation verbs; `src/aeat/entrypoints/cli/tests/test_live_read_subgroups.py`.
- [x] `W04.P08.S22` - Harden justificante capture matching and evidence stamping; `src/aeat/application/live/_justificante.py`.
- [x] `W04.P08.S23` - Harden filed observation capture and registry enrollment provenance; `src/aeat/application/live/_filed_data_capture.py`.

### Phase `W04.P09` - legal grounding and EU VAT UX

Resolve remaining legal ambiguity against official sources and harden EU/non-domestic VAT messaging where calculation evidence is advisory or unsupported.

- [x] `W04.P09.S24` - Ground remaining M303 compensation and carryover legal text in official sources; `.vault/reference`.
- [x] `W04.P09.S25` - Harden EU VAT and unsupported-currency operator diagnostics; `src/aeat/domain/iva`.
- [x] `W04.P09.S26` - Verify legal-source bundles used by calculation tests are authoritative; `src/aeat/domain/calculations/registry`.

## Wave `W05` - certification and campaign closure

Run owner-aware gates, vault hygiene, and closure audits so the campaign can distinguish fixed behavior from residual risk and newly opened persona testimony.

### Phase `W05.P10` - owner-aware quality gates

Run scoped and broad gates with explicit owner classification so concurrent-agent WIP is not misreported as this campaign fixed or broken.

- [x] `W05.P10.S27` - Run calculation registry CLI and ledger gates for touched surfaces; `src/aeat`.
- [x] `W05.P10.S28` - Run owner-aware full-tree gate and classify unrelated failures; `.vault/audit`.
- [x] `W05.P10.S29` - Run vault plan and vault schema checks for changed campaign documents; `.vault/plan`.

### Phase `W05.P11` - honest closure and residual queue

Publish closure records that enumerate fixed work, not-yet-fixed edges, residual risks, and follow-up waves for newly arrived testimonials.

- [x] `W05.P11.S30` - Publish campaign closure audit with fixed and residual edges; `.vault/audit`.
- [x] `W05.P11.S31` - Update open follow-up queue for new testimonials without claiming boundedness; `.vault/plan`.
- [x] `W05.P11.S32` - Review completed fixes with code-review agents before closure; `src/aeat`.

## Wave `W06` - ongoing testimonial intake and residual hardening queue

Keep the open-ended persona campaign active after the W05 checkpoint. New roots, transcripts, summaries, and closeout messages enter this queue, and artifact hygiene stays separate from product correctness.

### Phase `W06.P12` - rolling intake and artifact hygiene

Reconcile newly arrived persona artifacts and evidence gaps while keeping artifact completeness separate from calculation and CLI product correctness.

- [x] `W06.P12.S33` - Inventory newly arrived persona roots and transcript summary evidence since the W05 checkpoint; `tmp/personas`.
- [x] `W06.P12.S34` - Repair or document persona artifact evidence gaps for roots lacking local transcript BOE export or approval proof; `tmp/personas`.
- [x] `W06.P12.S35` - Keep the ignored closeout ledger and vault audit in sync without promoting scratch roots to product truth; `tmp/personas/_cpdefix-closeout-ledger.md`.

### Phase `W06.P13` - next behavior defect dispatch

Convert only reproduced operator-visible product defects into code work, with RAG-grounded briefs, disjoint ownership, review, and owner-aware gates.

- [x] `W06.P13.S36` - Replay new transcript final messages for under-declaration data-loss cross-profile legal-evidence and live-read risks; `tmp/personas`.
- [x] `W06.P13.S37` - Dispatch RAG-grounded code fixers for reproduced campaign-owned behavior defects; `agent orchestration`.
- [x] `W06.P13.S38` - Run owner-aware touched-surface gates for W06 fixes and classify unrelated baseline or concurrent failures; `src/aeat`.

## Description

This continuation plan turns open-ended persona testimony into a supervised
hardening queue. New `tmp/personas` roots may appear while work is in flight, so
the campaign separates artifact completeness from runtime correctness and keeps
the tracker append-only. The highest priority is any edge that can under-declare
tax, lose financial facts, cross-contaminate taxpayer profiles, or let local
evidence masquerade as official AEAT evidence.

The orchestrator owns briefing, sequencing, verification, and plan updates.
Worker agents own bounded Steps, must ground their investigation with
`uvx vaultspec-rag search ... --type code` before code changes, and must not
mutate the plan structure themselves. Every code Step closes through real
tests, an execution record, review, and a commit.

## Steps

The canonical L3 Step queue is the Wave and Phase structure in this document.
W01 establishes evidence authority and shared-worktree ownership. W02 handles
P0 calculation and data-safety risks. W03 replays weak persona/export roots.
W04 resolves live-read, adapter, and legal-source ambiguity. W05 certifies the
campaign and leaves an honest continuation queue for new testimony.

## Parallelization

Waves are sequenced by default. W01 must close before mutating code work starts.
After W01, W02.P03, W02.P04, and W02.P05 may run in parallel if their agents own
separate files and commit one Step at a time. W03 read-only replay may begin
after W01, but any reproduced code fix waits for the relevant W02 invariant when
it overlaps calculation, import, or profile identity.

W04 legal research can run in parallel as a read-only activity. W04 code changes
wait for official-source grounding when a legal claim or operator message is at
stake. W05 is strictly last and cannot close until worker code, reviewer checks,
execution records, and owner-aware gates are complete.

## Verification

- Every worker brief records RAG grounding with `uvx vaultspec-rag` and no
  fallback before code changes.
- Every code Step has real-behavior tests for the touched surface, with no fake,
  stub, monkeypatch, skip, or xfail shortcut.
- `vaultspec-core vault plan check` passes for this plan after each structural
  update and before closure.
- Touched calculation, registry, CLI, ledger, live-read, and export gates pass
  or are classified by owner when unrelated concurrent WIP is present.
- Reviewer agents audit completed code Steps before the orchestrator marks them
  closed.
- The final closure audit names fixed issues, not-honestly-fixed edges, suspected
  wrong domains, and any newly opened testimonial follow-up queue.
