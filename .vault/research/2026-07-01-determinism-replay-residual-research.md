---
tags:
  - '#research'
  - '#determinism-replay-residual'
date: '2026-07-01'
modified: '2026-07-17'
related:
  - '[[2026-06-30-deterministic-output-replay-substrate-adr]]'
  - '[[2026-06-30-deterministic-output-replay-substrate-research]]'
  - '[[2026-06-30-ledger-add-idempotency-adr]]'
  - '[[2026-07-02-agent-harness-refoundation-adr]]'
---

# `determinism-replay-residual` research: `residual non-determinism: surrogate ids, seam-coverage gate, output-ordering`

The `deterministic-output-replay-substrate` ADR (`proposed`) designed and landed (commit
`ab537f926`) the reusable determinism substrate: the `core.time` context-var clock seam
(`now()`/`frozen_clock()`), the identity levers (inject `profile_id`, mask `snapshot_id`/`run_id`),
verbatim `SchemaEnvelope` golden capture, and the shared canonicalise/mask/compare primitive with
its anti-tautology proof. This research is a NARROW residual pass on top of that PARENT. It does
NOT re-open any substrate decision. It grounds three gaps the substrate left out of scope, each
verified still open at HEAD, that let non-determinism re-enter operator output after the substrate
itself is correct: (1) two `uuid4` surrogate keys that surface in operator output but are neither
masked nor deterministic; (2) the clock seam has no enforcement gate, so a bare wall-clock read
bypasses it silently; (3) a handful of unsorted directory scans that could feed ordered output
with no discipline keeping them sorted. Every cited source read at HEAD; substrate files carry no
working-tree modification.

## Findings

### F1 - `evidence_id` / `invoice_id` are unmasked uuid surrogates AND load-bearing across trajectories

`GOLDEN_MASK_FIELDS = frozenset({"snapshot_id", "run_id"})` at HEAD
(`core/observability/_golden.py:59`) - the two residual uuid-tail leaves the substrate enumerated
for the harness Q5 scenarios. Two more opaque `uuid4().hex[:16]` surrogate keys surface in operator
`--format json` output and are absent from the mask:

- `evidence_id` minted `uuid.uuid4().hex[:16]` at `application/ledger/_evidence.py:384`.
- `invoice_id` minted `uuid.uuid4().hex[:16]` at `application/ledger/_business_operation_invoice.py:421`.
- They surface downstream as `purchase_invoice_evidence_id` / `evidence_id` fields on ledger and
  renta output models (`application/ledger/_models.py` lines 95/235/322/834,
  `application/aggregation/_renta_ledger.py:121`, `application/ledger/_llm_classification.py`).

The critical HEAD finding that shapes the fix: these ids are NOT purely opaque output leaves - they
are LOAD-BEARING `typer.Argument` values consumed by downstream verbs. `evidence_id: str =
typer.Argument(...)` appears at `entrypoints/cli/_ledger_evidence_cli.py:133,192,239` (evidence
show / remove / link), `invoice_id: str = typer.Argument(...)` at
`entrypoints/cli/_ledger_business_invoice_cli.py:260,344`, and `link --invoice-id` resolves an
invoice_id. An agent trajectory that does `evidence add` then `evidence link <evidence_id>` reads
the id emitted by the first command and passes it back as an argument to the second. This is the
distinction from `snapshot_id`/`run_id`, which are never re-consumed as arguments.

Consequence for the lever choice: for a SINGLE-command golden (assert only `evidence add`'s
envelope), the id is an opaque leaf and masking suffices. For a MULTI-command golden trajectory
that chains on the id (the harness Q5 gate asserts the tool trajectory INCLUDING passed arguments),
masking erases the referential linkage the trajectory depends on - a masked id cannot be
trajectory-asserted. So the faithful lever for a load-bearing id is a DETERMINISTIC id, not a mask.
The established in-project precedent is content-addressing: `derive_transaction_id`,
`derive_work_unit_id`, `derive_import_fingerprint` are already deterministic (no timestamp in the
digest) and need no mask; `evidence_id`/`invoice_id` are the odd ones out, using a random `uuid4`
surrogate rather than a content digest.

Self-surfacing confirmed: the substrate anti-tautology gate
(`test_mask_equals_the_residual_diff_under_frozen_clock`) fails on any undeclared differing path,
so the FIRST ledger-evidence or invoice golden capture will red the gate on these ids - the design
working. The current mask is knowingly incomplete for this surface; the inject-vs-mask decision is
unmade.

### F2 - The clock seam has no enforcement gate; bare wall-clock reads bypass it

The seam landed (`core/time/_clock.py`: `now()` consults `_FROZEN_INSTANT` else real UTC;
`frozen_clock()` sets/restores and refuses under `AEAT_LIVE_TESTS_ENABLED`; `clock_is_frozen()`),
and `test_clock.py` tests the seam's own behaviour - but nothing enforces that production code reads
the clock THROUGH the seam. A grep of bare `datetime.now(` / `datetime.utcnow(` in `src/aeat`
(excl. tests, excl. the clock module) at HEAD finds reads that bypass it:

- `core/corpus_manifest/__init__.py:269` - `generated_at = _dt.now(UTC)`. A genuine bypass: the
  corpus manifest `generated_at` never consults the seam, so a manifest emitted under `frozen_clock`
  still flaps. Same class of field the substrate froze elsewhere.
- `application/auth/_acquisition_lock.py:100`, `adapters/outbound/aeat/auth/certificate.py`
  (lines 232, 494, 584), `adapters/outbound/aeat/auth/_authenticator_types.py:135`,
  `adapters/outbound/aeat/browser/_site_health_parsers.py:99` - each takes an injectable
  `now`/`clock` param and falls back to bare UTC. These are live-AEAT adapters measuring real
  external time; they are seam-compatible by injection and are the natural documented carve-out,
  not golden-replay targets (auth is live-gated, and the seam refuses under the live opt-in anyway).

No `test_*` enforces seam routing today (confirmed at HEAD: no AST/conformance gate for bare
wall-clock; only `test_clock.py` exercises the seam). The project already uses static AST gates for
exactly this shape of invariant: `test_modelo_string_usage.py` (bare modelo-id literals) and the
locale-parity gates. The seam's coverage is therefore incidental (whatever calls `now()`), not an
enforced invariant; a new bare `datetime.now()` silently re-introduces a flapping output field,
caught only later by a mask failure on a captured scenario - if that command is captured. A whole
ambient-input gate could also cover output-feeding random/uuid and unsorted-fs reads (F1, F3) in
one structural surface, but the wall-clock arm is the concrete, verified-open case.

### F3 - Residual unsorted directory scans; no discipline keeps output-feeding scans sorted

Output-feeding directory scans already sort (`application/workflow/_profile_bucket_scan.py:235,273`,
`application/registry/_corpus.py:1070,1076,1090`, `application/filing/runtime.py:446` wrap
`iterdir()`/`rglob()` in `sorted(...)`), and envelope key-order is neutralised at compare by
`canonicalise(sort_keys=True)`. The residual unsorted scans at HEAD split into two classes:

- Order-INDEPENDENT (leave alone): `application/provisioning.py:183` (`any(... for child in
  root.iterdir())` membership test) and `application/wizard/_translations.py:116`
  (`rglob("*.py")` feeding a translation-key aggregation, order-independent).
- Potentially output-feeding (VERIFY before touching): `application/user_profile/_profile_repository.py:633`
  (`for entry in buckets_root.iterdir():` - depends whether the iteration builds an ordered profile
  listing that reaches output) and `entrypoints/cli/_ledger_import_cli.py:159` (builds the list of
  files to import from a directory; if import order affects created-row order or an output listing,
  the scan order leaks into output).

So filesystem ordering is not a live defect today, but there is no gate keeping output-feeding
scans sorted as new code lands: this is a discipline to codify (sort at the output boundary),
targeted only at scans that can feed ordered output, not the membership/aggregation uses.

## Open questions carried to the ADR

1. Surrogate-id lever (F1). Given `evidence_id`/`invoice_id` are load-bearing `typer.Argument`
   values: make them DETERMINISTIC (content-addressed like `derive_transaction_id`, faithful and
   trajectory-referenceable) versus MASK them in `GOLDEN_MASK_FIELDS` (cheap, but breaks multi-
   command trajectory referential assertion). Which per id, and is masking acceptable only for
   single-command goldens?
2. Seam-coverage gate (F2). A static AST gate banning bare `datetime.now()`/`utcnow()` outside the
   seam - scoped to wall-clock only, or widened to a whole ambient-input gate also covering
   output-feeding uuid/random and unsorted-fs? Carve-out shape for the injectable live-AEAT
   adapters. Fix the `corpus_manifest` bypass in the same change?
3. Ordering discipline (F3). Codify sort-at-output-boundary as a rule and fix the two verified
   output-feeding scans, or leave the two ambiguous sites to per-review judgement after confirming
   whether they reach output?
