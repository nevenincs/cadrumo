# Testimonial — Asesoría Gómez, gestor managing multiple clients on one workstation

Slug: `gestor-multiclient` · Storage root: `tmp/personas/gestor-multiclient` ·
Workstation passphrase: one shared secret-store passphrase for all clients.

> **RE-AUDIT 2026-06-19.** Original run was 2026-06-18. Overnight, peer commits
> `3fdcde42c` (silent-zero 303 + draft gate) and the M130 casilla-02 binding change
> landed. I re-ran both clients end-to-end against current HEAD. **Result: 3 of the 4
> defects below are now FIXED — both clients reach a compliant `.boe`.** One finding
> (the `work dependencies` diagnostic, Finding 3) remains open. Each finding is
> stamped with its current status. Isolation re-confirmed PASS both directions.

> **DEEP AUDIT 2026-06-19 (multi-period, safety gate, export fidelity).** Beyond the
> four findings (all now fixed), I drove three higher-risk areas end-to-end on Beto's
> M130, all **PASS — no defects found**:
>
> - **Cross-period carry correctness.** Added Beto's 2T ledger rows and calculated
>   M130 2T. The cumulative compounding is arithmetically correct: casilla 01 = 9000
>   (6000+3000), 02 = 1500 (1000+500), 03 = 7500, 04 = 1500 (20%), **casilla 05
>   (pagos fraccionados anteriores) = 1000** = exactly 1T's casilla 07 (BOE rule
>   Σ max(0, prior 07) − Σ prior 16, RD 439/2007 art. 110 — *not* the 900 net pago),
>   casilla 07 = 500, casilla 19 (2T pago) = 400. When the prior observation is
>   absent, the carry binding **blocks calculate explicitly** ("la vinculación … no
>   tiene valor asignado", with `--binding` / `bindings list --missing` guidance) —
>   no silent zero.
> - **Cross-period safety gate.** Even with the carry values supplied manually so
>   *calculate* succeeds, *verify* of 2T correctly returns `completeness blocked` /
>   `granted false` with a `cross_period_dependency_unclean` **blocking** finding,
>   because 1T carries no official evidence (`missing_observation`,
>   `missing_current_filing_record`). Manual binding values feed calculation but
>   never satisfy verify-complete — the layered `no-silent-under-declaration` /
>   `aeat-safety-legal-gates` invariant holds. Remediation guidance is instructive
>   (`live filed pull-sources`, `reconcile file`). Note: `work file` is window-gated
>   — refused for 2024 periods at today's date, so the *auto*-carry path can only be
>   exercised within an open obligation window (by design; export is the local
>   finish line regardless).
> - **Export fidelity.** Both `.boe` are faithful fixed-width fichero-BOE records:
>   Ana `<T303020241T0000>` + NIF `45678901G`; Beto `<T130020241T0000>` + NIF
>   `56789012B` + name + pago fraccionado `0000000900`, at registry-declared
>   (`export_layouts/*.toml`) positions.
>
> Net: every audited surface is clean at HEAD; no open issues remain.

> **ADVERSARIAL SWEEP 2026-06-19 (attack the ledger surface).** Nine deliberate
> break-attempts, RAG-grounded and code-verified. One actionable item — a *peer's*
> uncommitted WIP — plus a robust HEAD:
>
> 1. **Peer-WIP regression (REPORTED, not a HEAD bug, not mine to fix).** A peer's
>    uncommitted edit to `_modelo_iva_wallet_cli.py` imports an undefined
>    `record_iva_compensation_override_for_bucket` from `aeat.application.modelo`;
>    via `_modelo.py:110` it cascades to break the **entire `app modelo` tree**
>    (work list/dependencies/calculate/verify/export → ImportError) in the shared
>    worktree. Absent at HEAD (`git show HEAD` confirms), so it's transient
>    working-tree contamination. Escalated to the coordinator; abort-on-WIP, untouched.
> 2. **Cross-profile by-id access (deferred).** Could not run live (blocked by #1).
>    Code carries `ModeloExportCrossBucketRefusedError` /
>    `ReconciliationCrossBucketRefusedError` — verify the live refusal once the modelo
>    tree recovers.
> 3. **Duplicate re-import → PASS.** Re-importing Beto's 1T CSV: `Omitidos 2`,
>    `Entradas importadas 0`, count stays 4 — fingerprint dedup, no double-count.
> 4. **Zero-amount row → PASS.** Refused: "a ledger movement must be non-zero".
> 5. **Negative manual amount → PASS.** `ledger add --amount -500` refused: "debe ser
>    una magnitud no negativa" (`ledger-amount-is-absolute-direction-is-authority`).
> 6. **base+iva ≠ gross → PASS.** Refused: "taxable_base + iva_amount must equal the
>    gross to the cent".
> 7. **base×rate ≠ iva_amount → WORKS AS DESIGNED.** classify accepts an inconsistent
>    rate (e.g. base 3500 / rate 0.21 / iva 130), but the IVA aggregation uses the
>    operator-entered `iva_amount` as the authoritative cuota (`_iva_ledger.py:503`);
>    `iva_rate` only selects the rate-kind/category, and the gross invariant is
>    enforced. The **assets** model's hard `iva_amount==base×rate` check is a
>    constraint-shape mismatch for transactions — porting it would wrongly reject
>    legitimate mixed-rate / line-rounding invoices. Not a defect; divergence-tolerant
>    by design.
> 8. **Non-EUR (USD) import → PASS.** Accepted at the ledger, but every aggregation
>    pipeline excludes it with a **surfaced** `UNSUPPORTED_CURRENCY` diagnostic (test
>    `test_non_eur_transaction_excluded_with_reason`) — not a silent drop.
> 9. **Income tagged with a deductible gasto category → inert (LOW hygiene).** classify
>    accepts an INCOMING row with a gasto category, but aggregation routes by
>    **direction** (INCOMING→casilla 01), so the category is inert — no deduction
>    inflation. Cosmetic only.
>
> Verdict: HEAD is robust against every attack; the sole breakage is transient peer
> WIP (escalated). Test data restored (corrupted tx re-classified, USD + throwaway
> rows removed); Beto's ledger back to his real 4 transactions.

> **PERSPECTIVE-CHANGE PROBE 2026-06-19 (look for *dropped-good-data*, not blocked-bad-data).**
> Re-aimed the sweep at silent under-declaration — "does a gate wrongly drop legitimate
> data?" One candidate, honestly downgraded after verification:
>
> - **Genuine same-signature twins on one statement → FIXED (commit `dda7a4e79`).** A
>   statement with two real movements sharing date + amount + narrative but different
>   running balance (Saldo 5000 vs 5605) previously imported as 1, skipped 1 — dropping a
>   legitimate recurring twin (common for autónomos: two identical retainers/subscriptions
>   same day). Root cause: the import dedup classifier (`_evaluate_import_rows`) skipped on
>   an **intra-batch import-fingerprint** collision, but the fingerprint
>   (date + amount + narrative) is coarser than the transaction id — and the provider's
>   `synthesize_transaction_id` embeds the source **row index**, so the twins carry
>   distinct, collision-free ids and both should persist. Fix: skip only on a fingerprint
>   already in the **persisted catalogue** (re-import / cross-format dedup, unchanged) or a
>   true intra-batch **transaction-id** collision; genuine distinct-id twins now both
>   import. Verified live (4→6 on first import, 6→6 on re-import) and with two real-behaviour
>   regressions (one proven to fail under the old skip). Re-import dedup and the cross-format
>   fingerprint contract are untouched. (My first framing called this a "silent HIGH"; it was
>   actually WARNED via `_import.py` `message_053465`, hence the calmer fix path — but the
>   data-drop was real and is now closed.)
>
> - **Peer WIP worsened (still peer-owned, escalated).** A second uncommitted breakage —
>   `ModeloIvaWalletOverrideSealedError` (`_iva_wallet_seed.py`, ` M`) missing its
>   ErrorCode registry entry — now crashes `application.modelo` at import, cascading
>   through `_participation_cli` to break the `app ledger` tree as well as `app modelo`.
>   Beto's data is intact (crash at import-time, before any read/write).

| Finding | Original severity | Status at HEAD (2026-06-19, all resolved) |
|---|---|---|
| 1 — M303 casilla 65 silent-zero / un-exportable | CRITICAL | **FIXED** (`3fdcde42c`) |
| 2 — `DRAFT_HAS_ERRORS` abort lists no findings | HIGH | **FIXED** — root cause `3fdcde42c` + abort now enumerates blocking findings (`19d0c53d8`) |
| 3 — `work dependencies` ignores activity-start-date | MEDIUM | **FIXED** — my one-line fix + real-CLI regression, landed at HEAD (in `39ea37493`) |
| 4 — M130 deductible expense not auto-aggregated (F2) | LOW | **FIXED** (casilla 02 now source-bound) |

**Net at HEAD: every identified issue is resolved and committed.** Re-verified
end-to-end: both clients export (`ana-303` 7994 B `3f74ded4…`, `beto-130` 946 B
`c7eabb98…`), `work dependencies` for Ana 303 reports `clean True`, and isolation holds
both directions.

## 1. Persona

I am a gestor (tax agent). I run one workstation and file for many clients from it.
Today I onboarded two: **Ana** (autónoma, Modelo 303 IVA 1T 2024) and **Beto**
(autónomo, Modelo 130 IRPF 1T 2024). My whole business depends on one promise: one
client's money never shows up in another client's return. So my real test was not "can
I file a 303" — it was "if I switch from Ana to Beto, do I see *only* Beto?"

## 2. What worked (first try)

- **Two profiles, one storage root, one passphrase.** `profile create cliente-ana` then
  `profile create cliente-beto` both succeeded under the same `AEAT_SECRET_PASSPHRASE`.
  `aeat config profile list` showed both, with `*` marking the active one. No collision.
- **Profile switching is genuinely easy.** `aeat config switch cliente-ana` /
  `aeat config switch cliente-beto` each printed `active_profile <name>` and persisted.
  The `AEAT_ACTIVE_PROFILE` env var also selects the profile per-invocation. For a gestor
  this is the right ergonomics: one short verb, no re-login, no re-entering the passphrase.
- **Ledger import + classify + preflight** worked first try for both clients
  (semicolon CSV, comma decimals, dd/mm/YYYY). Both preflights: `issues 0, ready true`.
- **Beto's Modelo 130 ran end to end**: create → calculate → verify (`granted true`) →
  export `.boe`. Clean.

## 3. THE ISOLATION CHECK — the trust test (PASS)

This is the result I care about most. Evidence, both directions, at two storage layers:

| Probe | Active profile | `aeat app ledger list` shows | Cross-leak? |
|---|---|---|---|
| Before Beto had data | cliente-beto | **empty** (Ana's 2 rows absent) | NO |
| After Beto import | cliente-beto | only `503f2548`, `f3a54046` | NO |
| After `switch cliente-ana` | cliente-ana | only `7a6aaa45`, `e26eaae1` | NO |

Modelo work units are isolated too:
- Active **Beto** → `work list` = **130** only (1 work unit).
- Active **Ana** → `work list` = **303** only (1 work unit).

**Verdict: PASS.** No transaction, no work unit, no calculation crossed the profile
boundary in either direction. A real gestor's confidentiality requirement is met.

## 4. Friction / breakage

### 4.1 Both test NIFs were rejected for a wrong control letter (worked as designed)
- `45678901C` refused: "la letra de control debe ser **G**, no C." → used `45678901G`.
- `56789012D` refused: "la letra de control debe ser **B**, no D." → used `56789012B`.
- The refusal is **excellent**: it names the exact correct letter. A gestor typing a
  client NIF will be caught before bad data lands. (The brief's fixtures carried invalid
  letters; the CLI is right to reject them.) Not a bug — a strength.

### 4.2 Ana's Modelo 303 cannot be verified or exported (CRITICAL — see Finding 1)
This is a hard wall, unrelated to multi-profile. Detail below.

## 5. Input → Output reconciliation

### Client A — Ana, Modelo 303 IVA 1T 2024  (re-run at HEAD 2026-06-19)
| Input | EUR | Casilla | Expected | Actual | Match |
|---|---|---|---|---|---|
| Income base (21%) | 4000 | 01/09 base, repercutido | 840 cuota | devengada **840** | ✓ |
| Expense base (21%) | 500 | 45 soportado | 105 cuota | deducible **105** | ✓ |
| Resultado régimen general | | 64 | 735 | **735.00** | ✓ |
| % atribuible al Estado | | 65 | 100 | **100** (auto-default) | ✓ |
| **Resultado final (official)** | | **71** | **735** | **735.00** | ✓ |

At HEAD, casilla 65 **auto-defaults to 100** (común-territory) with no override needed,
so casilla 66 = [64]×[65]/100 = 735 and the official final box 71 = **735.00**. Verify
**GRANTED** (`completeness complete`), export produced a `.boe`.
*(Original 2026-06-18 run: 71 read 0.00 and export was blocked — Finding 1, now fixed.)*

### Client B — Beto, Modelo 130 IRPF 1T 2024
| Input | EUR | Casilla | Actual | Note |
|---|---|---|---|---|
| Income base | 6000 | 01 | **6000** | ✓ |
| Expense base | 1000 | 02 | **1000** | manual via `--casilla 02=1000` (F2) |
| Rendimiento neto | | 03 | 5000.00 | 6000−1000 ✓ |
| 20% s/ rendimiento | | 04/07 | 1000.00 | ✓ |
| Deducción | | 13 | 100.00 | |
| **Pago fraccionado (final)** | | **19** | **900.00** | 1000 − 100 |

At HEAD, casilla 02 = 1000 is now **auto-aggregated** from the ledger expense with **no
`AVISO` and no manual override** — and a `--casilla 02=...` override is now correctly
*refused* ("cannot override bucket-derived source-bound casillas"). Verify granted with
non-blocking advisories (cross-period to M100/2023 scoped out by `activity-start-date
2024-01-01` — **F3 scoping works**; plus a missing-evidence attach advisory).
*(Original 2026-06-18 run: expense was dropped with an AVISO and required manual
`--casilla 02=1000` — Finding 4 / HARNESS F2, now fixed.)*

## 6. Final artefacts  (at HEAD 2026-06-19)

| Client | Modelo | `.boe` | byte_size | file_sha256 |
|---|---|---|---|---|
| Ana | 303 1T 2024 | `ana-303-1T-2024.boe` | 7994 | `3f74ded4277679aa3a245e2e5898c910d5dc16567a1380aca48b67fcd24ba16c` |
| Beto | 130 1T 2024 | `beto-130-1T-2024.boe` | 946 | `c7eabb98e5f6975fae85a0ade2d20d08b6d4177925be0cd0c8e5832aaa89eb8c` |

Both clients reach a compliant `.boe`. Beto's export is byte-deterministic (same sha256
from the auto-aggregated revision as from the original manual-override revision).
*(Original 2026-06-18 run: Ana's 303 could not export.)*

## 7. Findings

### Finding 1 — [CRITICAL][APP] → ✅ FIXED at HEAD — Modelo 303 silent-zero / un-exportable
**Status: FIXED by commit `3fdcde42c` (2026-06-19 07:14).** Re-run live: casilla 65
auto-defaults to 100 (común), casilla 71 = 735.00, verify GRANTED, `.boe` exported
(7994 B, `3f74ded4…`). The fix defaults the absent-scope case to común-100% (CCAA enum
is común-only; foral refused at creation — Concierto Económico, Ley 12/2002 art. 29) and
also resolves profile bindings feeding a *bound numeric casilla*, not only
formula-consumed ones. The original CRITICAL report stands as the pre-fix record below.

**(Original 2026-06-18 report) The state-attribution ratio (casilla 65) had no operator-settable source.**

`aeat app modelo work verify --modelo 303 --year 2024 --period 1T` →
```
Refused. Draft 49b86fd5a369d933 not ready: status=BORRADOR
  abort_code: DRAFT_HAS_ERRORS   stage: ABORTED
```
…with **no findings listed**. Root cause traced in source:
- The verify *revision-level* checks pass (`granted=True`) once `activity-start-date`
  scopes out the cross-period dependency. But verify then runs a **workflow gate** that
  **rebuilds its own draft from profile + ledger inputs** (`_verification_actions.py`
  `_run_revision_workflow_gate`), ignoring any `--casilla 65=100` override on my revision.
- That rebuilt draft's casilla 65 comes from `_inject_derived_state_attribution_facts`
  (`application/modelo/_profile_binding.py:229`), which reads
  `tax_residence.jurisdiction_scope`: `common_regime`→100, `foral_unsupported`→0, **absent
  → key left absent → casilla 65 = 0 → silent zero → ERROR finding → draft stays BORRADOR
  → DRAFT_HAS_ERRORS**.
- **There is no CLI or wizard flag that sets `tax_residence.jurisdiction_scope`.**
  `profile create --help` / `profile edit --help` have no `--jurisdiction-scope`;
  `grep jurisdiction_scope src/aeat --include=*.py` shows it written **only in tests**
  (via direct `UserProfileFact`), never by any production code path. The profile records
  `tax_residence.ccaa = madrid` (a común-territory region) but nothing maps CCAA →
  `common_regime`.
- **Impact:** a gestor cannot file *any* Modelo 303 for a normal peninsular client through
  the supported CLI. The block is silent twice over — the headline box reads 0 (not a
  refusal), and the verify abort lists no finding explaining why.
- **Fix:** (a) add a `--jurisdiction-scope {common_regime|foral_unsupported}` flag (or
  derive `common_regime` from a común CCAA) so casilla 65 can be 100; and (b) make
  casilla 65 = 0 on positive devengada a *blocking, explained* finding, not a silent zero.
- Matches `no-silent-under-declaration`. Independently reproduced by the older
  `modelo-303.md` testimonial (its Findings 2 & 4).

### Finding 2 — [HIGH][APP] → ✅ FIXED at HEAD (both layers)
**Status: FIXED.** Two complementary peer fixes closed this:
- `3fdcde42c` fixed the 303 *trigger* — build_draft uses declared `formula_inputs` for a
  computed-casilla trace, so the prorrata conditional no longer trips a spurious
  formula-divergence that left the gate draft BORRADOR.
- `19d0c53d8` ("make draft-not-ready abort legible") fixed the *ergonomics* — the
  `DRAFT_HAS_ERRORS` abort now computes `_draft_blocking_finding_descriptions(draft)` and
  threads them into both the summary line and a `blocking_findings` detail field
  (`workflow/_engine.py:808–824`), so an abort enumerates the findings that kept the draft
  out of the ready state. Verified by the peer regression
  `test_draft_not_ready_abort_surfaces_blocking_findings` (green at HEAD). The original
  "no findings listed" report below is the pre-fix record.

**(Original 2026-06-18 report)** When the workflow-gate draft was BORRADOR, verify aborted
with `abort_code: DRAFT_HAS_ERRORS` and no enumeration of the underlying errors; no report
was persisted, so `verification-report list` returned `report_count 0`.

### Finding 3 — [MEDIUM][APP] → ✅ FIXED (this re-audit) — `work dependencies` honours `activity-start-date`
**Status: FIXED and committed at HEAD.** The handler called
`evaluate_cross_period_clean_state` **without** `activity_start_date`, so the diagnostic
reported a 303/2023-4T blocker that verify itself scopes out. Fix (grounded via
`vaultspec-rag --type code`, matching the verify/export/filing call-sites): thread
`activity_start_date=workflow_profile.activity_start_date` into the call
(`_modelo_work_verification_cli.py:253`). Added a real-CLI regression,
`test_work_dependencies_honours_activity_start_date_pre_activity_scoping` (proven to fail
without the fix). Live at HEAD: `work dependencies --modelo 303 --year 2024 --period 1T`
now reports `clean True` / no blockers. Both files landed at HEAD (swept into peer commit
`39ea37493` under shared-index contention; my exact +1/+47 content, test green). The
pre-fix analysis below is the original record.

`aeat app modelo work dependencies --modelo 303 --year 2024 --period 1T` reports
`clean false`, blockers `missing_observation, missing_current_filing_record` for 303/2023
4T — even though my `activity-start-date 2024-01-01` scopes that period out (and the verify
path *does* honour it). The CLI handler calls `evaluate_cross_period_clean_state` **without**
passing `activity_start_date` (`_modelo_work_verification_cli.py` ~L245), so its diagnostic
display contradicts the actual verify behaviour and would scare an operator into thinking a
first-period filing is blocked when it is not. Fix: thread the profile's `activity_start_date`
into the dependencies command, matching the verify path.

### Finding 4 — [LOW][APP] → ✅ FIXED at HEAD — M130 deductible expense now auto-aggregates
**Status: FIXED.** Re-run live at HEAD: M130 casilla 02 = 1000 is now **auto-aggregated**
from the ledger expense with **no `AVISO`**; the prior manual `--casilla 02=...` workaround
is now correctly *refused* ("Caller casilla inputs cannot override bucket-derived
source-bound casillas: ['02']"). The auto-aggregated revision verifies and exports to the
identical `.boe` (sha256 `c7eabb98…`).

**(Original 2026-06-18 report)** M130 did not aggregate the OUTGOING deductible expense into
casilla 02 (Gastos); it emitted an `AVISO` and dropped it, so the return overstated
rendimiento neto unless the operator manually supplied `--casilla 02=<bases>`.

### Finding 5 — [INFO] Multi-profile isolation is solid; switching is gestor-friendly
No defect. Recorded as the positive result of the trust test (§3). One shared passphrase +
`AEAT_SECRET_STORE_DIR` under the storage root gives clean per-workstation custody, and two
clients coexisting in one root never leaked across each other.

## 8. Verdict  (re-audited at HEAD 2026-06-19)

**Multi-profile workflow: PASS.** Two clients, one workstation, one passphrase, zero
data bleed in either direction — re-confirmed at ledger and modelo levels at HEAD.
Profile switching (`aeat config switch <name>`) is a single easy verb; a real gestor
would have no trouble keeping clients apart.

**End-to-end filing: PASS for both clients.** At HEAD both Ana's **Modelo 303**
(sha256 `3f74ded4…`) and Beto's **Modelo 130** (sha256 `c7eabb98…`) reach a compliant
`.boe` *unaided* — no manual casilla workarounds. The original CRITICAL 303 blocker
(Finding 1) and the M130 expense-drop (Finding 4) were both fixed overnight by peer
commits; the opaque-abort root cause (Finding 2) was fixed alongside.

**Remaining open issues: none.** All four findings are fixed and committed at HEAD —
Findings 1, 2, 4 by overnight peer commits; Finding 3 by this re-audit (one-line fix +
regression, landed at HEAD). Re-verified end-to-end at HEAD: both `.boe` export
deterministically, `work dependencies` reports clean, isolation holds both directions.

A real gestor onboarding these two clients today would keep them cleanly isolated and
file **both** the IVA and IRPF returns end-to-end, with the `work dependencies` diagnostic
now agreeing with verify. No rough edges remain in this persona's surface.
