---
tags:
  - '#audit'
  - '#branch-reconciliation'
date: '2026-05-20'
modified: '2026-05-20'
related: []
---



# `branch-reconciliation` audit: unmerged feature branch reconciliation

## Scope

The `chore/eliminate-shims` branch has become the de-facto principal line of
development (1895 commits ahead of `origin/main`, 53 behind). Standard
branch-and-PR flow lapsed during the restructure campaign. This raised a
concern: the remote feature branches never merged into this line may carry
meaningful work absent from the codebase.

This audit gauges the **actual** state of every unmerged branch. It is a
read-only assessment — no branches were merged, ported, archived, or deleted,
and no destructive git was run. Surfaces audited:

- The 53-commit gap by which `chore/eliminate-shims` trails `origin/main`.
- All 41 remote `feature/*` branches reported unmerged into both
  `origin/main` and `origin/chore/eliminate-shims`.
- The one branch (`feature/330-modelo-347-calc-verify`) merged into
  `origin/main` but not into this line.

## Method

Git history alone is unreliable here: the restructure independently
re-implemented most feature work, so a branch can be large yet fully
superseded. Three independent signals were combined per branch:

1. **Issue-number cross-reference.** This line's commit log uses a
   `(#NN) (#MM)` convention recording the originating issue and its merge
   PR. Searching the `chore/eliminate-shims` log for each branch's issue
   number surfaces already-landed equivalents, often with exact commit-
   subject matches.
2. **Defining-artifact verification.** For branches with no clean issue
   match, the branch's intent diff (against its merge-base with old `main`)
   was compared feature-by-feature against current HEAD code, matching by
   capability rather than file path — HEAD uses the hexagonal layout
   (`domain/`, `application/`, `adapters/`, `entrypoints/`) while the
   branches predate it and use the old flat layout.
3. **Anti-trust spot-check.** A sample of six branches classified
   "superseded" by issue-grep was re-verified by confirming the feature
   genuinely exists and is substantive in HEAD — guarding against a
   commit message that mentions an issue without delivering it.

Signals 2 and 3 were executed by a four-agent verification swarm; every
finding below is grounded in HEAD code, not commit messages alone.

4. **ADR authority grounding.** Every architectural verdict — what counts
   as a deliberate deletion, a sanctioned supersession, an obsolete-by-
   design surface, or the canonical structure — is traced to an
   **accepted** ADR in `.vault/adr/`. A commit message or a code change
   is not authority; an accepted ADR is. Where a deletion or
   re-architecture has no accepted ADR behind it, that absence is
   recorded as a finding in its own right (an undocumented change). ADRs
   carrying `proposed` or `superseded` status are explicitly noted and do
   not confer authority. This signal was executed by a six-agent ADR
   adjudication swarm reading the governing ADRs in full.

## Findings

### The 1895/53 divergence is benign

The 53 commits on `origin/main` absent from this line are the `#476`
hexagonal-restructure WIP, the `feature/330` modelo-347 merge, phase-1
dead-code chores, and two `Merge branch 'chore/eliminate-shims'` commits.
The `#476` restructure executes the accepted
`2026-04-30-aeat-restructure-adr`, which decides the hexagonal layered
layout (`domain/`, `application/`, `adapters/`, `entrypoints/`, `core/`)
and states "after the layout PR lands, the new layout is the only valid
layout." `origin/main` absorbed an early snapshot of this line, then
layered an earlier draft of the `#476` restructure on top. This line then
continued independently for 1895 commits and carries its **own, newer**
`#476` work (merged here as PR `#501`, `884a75021`). The 53-commit gap is
therefore **fully superseded** by this line — nothing in it needs
porting.

`feature/330-modelo-347-calc-verify` ("Kent can extract + verify-totals
Modelo 347") is the only branch merged to `main` but not here. Modelo 347
is nonetheless well-represented on this line: the 347/349 counterpart
aggregator (`dee57e782`), informative-regime grounding across modelos
including 347 (`5e03eaa49`), and full registry artifacts
(`modelo_347` diseños-registro corpus, casilla definitions). It is
treated as superseded, with a low-risk recommendation to confirm a
347-specific calc-verify-roundtrip test exists before final archival.

### All 41 unmerged feature branches — triage

Every branch is authored by the project owner, dated 2026-04-12 to
2026-04-30, and equally unmerged into both `main` and this line. None
carries verified unique work except the two flagged PARTIAL below.

**Superseded — work landed on this line via a later PR (issue-grep exact
match, anti-trust validated):**

| Branch | Files | Landed as |
| --- | --- | --- |
| `108-modelo-inventory-catalogue` | 45 | `ac41b1eb5` inventory parity gaps (#108) (#180) |
| `118-audit` | 3 | `1b7821b6f` live-write static audit (#118) (#147) |
| `15-pytest-only` | 10 | `185c21eb6` pytest-only posture lock (#15) (#160) |
| `162-relative-imports` | 429 | `a0eb5b6f7` relative-imports enforcement (#162) |
| `163-pytest-markers` | 189 | `846699c82` granular pytest markers (#163) (#178) |
| `167-aeat-access-gate` | 27 | `844cc9062` live AEAT access gate (#167) (#181) |
| `168-aeat-filing-history` | 29 | `33c3da8e9` filing-history read surface (#168) (#195) |
| `169-live-obligations-sync` | 7 | `5853b8a40` #169 capture batch + #171 H6 |
| `173-modelo-formulas` | 30 | folded into registry runtime; `185a81997` (#173) (#182) |
| `183-modelo-303-formulas` | 27 | `10108729a` Modelo 303 ruleset + VAT backbone (#183) (#196) |
| `218-t6-aggregation` | 26 | `6efd4e5fa` Modelo 130 aggregation (#218) (#473) |
| `225-rename-corpus-review` | 34 | `297ec4de3` rename definition review fields (#251) |
| `232-unified-review-queue` | 20 | `487582ea8` unified review queue (#232) (#258) |
| `236-confidence-scores` | 21 | `dc5a52997` decision provenance + confidence (#236) (#250) |
| `237-disambiguate-unclassified` | 19 | `29da231f8` pipeline-state split (#237) (#252) |
| `239-aeat-verify` | 138 | `7ab18f300` (#239) (#391) + `49857668a` (#239) (#434) |
| `281-auth-protocol` | 21 | folded into pluggable AuthProvider (#279/#287/#285) |
| `285-auth-cli` | 20 | `723dbed3d` auth CLI (#285) (#304) — see note below |
| `320-modelo-123-calc-verify` | 29 | `b51e82083` Modelo 123 calc-verify (#320) (#447) |
| `323-modelo-180-calc-verify` | 23 | `4edba715f` Modelo 180 calc-verify-roundtrip (#323) |
| `327-modelo-390-calc-verify` | 25 | `f4ffb1ec8` Modelo 390 calc-verify-roundtrip (#327) (#449) |
| `338-mutation-harness-extension` | 11 | `dae0ff23e` mutation harness (#338) (#429) |
| `340-kent-workflows-expansion` | 7 | `162afd9ed` Tier-L CLI integration (#340) (#430) |
| `453-inventory-management` | 32 | `fc3493ed6` inventory amortization ledgers (#453) (#474) |
| `59-workflow-engine` | 27 | `068df2a48` composite workflow engine (#59) (#63) |
| `7-portal-catalogue` | 89 | `b5ddee8d2` typed AEAT portal catalogue (#7) (#164) |
| `76-attachment-service` | 22 | `1d44c4c0c` content-addressed attachment service (#76) |
| `85-r1-vat-enumeration` | 26 | `f0c22daf4` R-1 VAT enumeration (#85) (#115) |
| `93-filing-complementaria` | 24 | `91e203259` filing complementaria engine (#93) (#132) |
| `95-aeat-mantenimiento-detection` | 73 | `26e51df73` mantenimiento/WAF/rate-limit detection (#131) |
| `99-run-trace` | 48 | `fd541c836` run-trace + JSONL audit + replay (#99) (#140) |
| `117-live-cert` | 21 | `b973e973f` ADR records PR #148 superseded by CertificateAuthProvider |
| `live-sync-engine` | 26 | `566f4ad2f` notificaciones reader + past-filing import (#170, #272) (#312) |

**Superseded — confirmed by semantic verification (no clean issue-grep
match; swarm checked HEAD directly):**

| Branch | Files | Finding |
| --- | --- | --- |
| `192-session-persistence` | 11 | Squash-merged as `0360a9b6f` (#200); `StorageStatePaths`, `load_persisted_session`, `capture_storage_state`, `resume_from_storage_state` all present and extended in HEAD. |
| `153-mcp` | 38 | Three fixes: `env_ignore_empty` and path-hardening helpers survive in `core/config.py` and `core/paths.py`; the Google Workspace MCP launcher was intentionally co-deleted with the whole Google stack. No work lost. |
| `117-live-submit-hardening` | 39 | Earliest iteration of #117 gate hardening; landed via PR #157 (`9bf831e9c`), then superseded by the permanent prohibition of `2026-04-27-live-submit-permanently-forbidden-adr` (accepted; PR #432). Abandoned spike. |
| `pytest-only` | 34 | Narrower duplicate spike of `epic1`; both themes absorbed via PR #157 and surpassed by `2026-04-27-live-submit-permanently-forbidden-adr` (accepted; #432). Abandoned duplicate. |

**No unique work — empty or planning-only:**

| Branch | Files | Finding |
| --- | --- | --- |
| `398-error-code-registry` | 0 | Empty ghost — only `Merge` commits, zero file changes. The error-code registry it intended landed independently (used by `c4fe52cf9` #454). |
| `255-vat-classification-cli` | 3 | Research/ADR/plan documents only, no implementation. VAT classification shipped via #183/#85. Dev-history docs already preserved by `ad60ef3cb`. |

### Branches with potentially unported work (PARTIAL) — verify before archiving

#### `271-pdf-import` (EPIC #305) — 150 commits, 266 files

Confirmed **PARTIAL** by a dedicated five-agent deep-dive — see the
section "Deep-dive: `271-pdf-import` gap resolution" below. This is the
sole branch carrying genuinely unported work and **must not be archived
until its gap backlog is resolved or each gap explicitly accepted.**

#### `epic1` — 3 commits — superseded (ADR-confirmed)

Two of three themes (live-submit gate hardening; deadlines profile path
validation) are superseded — the gate work landed via PR #157 then was
replaced by the permanent live-submit prohibition of
`2026-04-27-live-submit-permanently-forbidden-adr` (accepted; PR #432),
and the profile path guard is architecturally obsolete (profiles no
longer pass as CLI file paths under the two-root CLI of
`2026-05-12-cli-workflow-redesign-adr`). The third theme — a streaming
**submission audit-log read surface** (`aeat submission audit-log` CLI
verb plus an engine `list_audit_records` method) — is **ADR-resolved as
obsolete**: `2026-04-27-live-submit-permanently-forbidden-adr` explicitly
makes the `.aeat/live-submit-audit.log` unreachable as a security
mitigation, so there are no live-submit events to read. No unported work
remains.

### Anti-trust validation result

Six branches classified "superseded" by issue-grep were re-verified
against HEAD code. Five (`59`, `173`, `232`, `99`, `76`) confirmed cleanly
— the feature exists and is substantive. One discrepancy: `285-auth-cli`
— the auth *application layer* is fully present, but the top-level
`aeat auth login / list-providers / status / logout` CLI surface named in
the branch does **not** exist; it was retired and replaced by
`aeat config auth` with a different verb set (`providers`, `configure`,
`status`, `test`, `clear`). This is supersession-by-redesign sanctioned
by an accepted ADR: `2026-05-12-cli-workflow-redesign-config-auth-shape-
adr` states "Top-level `aeat auth` is not introduced" and places auth
under `aeat config auth`. No work is lost — the capability exists. The
case shows issue-grep "exact subject match" can mask a deliberate,
ADR-sanctioned surface change. The 5/6 clean rate supports trusting the
issue-grep verdict for the remaining branches.

A note on ADR hygiene surfaced by this case: `2026-04-21-auth-cli-adr`
(accepted) originally designed the top-level `aeat auth` surface and is
not formally marked superseded, despite `2026-05-12-cli-workflow-
redesign-config-auth-shape-adr` overriding it. The supersession link
should be recorded. Likewise, the pluggable `AuthProvider` abstraction
(behind `281-auth-protocol` / `285-auth-cli`) is referenced as merged
fact by accepted ADRs, but its defining ADR `2026-04-18-auth-provider-
abstraction-adr` remains `proposed` — its status should be resolved.
`117-live-cert` is cleanly ADR-grounded: `2026-04-21-live-cert-auth-
supersession-adr` (accepted) records "Close PR #148 without merging ...
No code from PR #148 is ported forward."

## Deep-dive: `271-pdf-import` gap resolution

A five-agent capability swarm deep-dived branch
`origin/feature/271-pdf-import` (EPIC #305); a six-agent ADR adjudication
swarm then traced every verdict to accepted-ADR authority. **Overall
verdict: PARTIAL — confirmed, but materially narrowed by ADR grounding.**
Under accepted-ADR authority the branch's genuinely actionable gaps are
far fewer than a capability-only read suggested: several "gaps" were
explicitly *rejected* by an accepted ADR or are named by no ADR, while —
conversely — one finding exposes an *undocumented re-architecture* on
this line that itself lacks ADR sanction.

### ADR authority basis

| ADR | Status | Governs |
| --- | --- | --- |
| `2026-04-20-pdf-import-adr` | accepted | scope of #271 (justificante import) |
| `2026-04-21-declaracion-extractor-adr` | accepted | declaración extraction architecture + modelo scope |
| `2026-04-22-aeat-fichero-boe-export-adr` | accepted | fichero-BOE export; modelos 130/303/390 named |
| `2026-04-24-aeat-verify-adr` | accepted | verify / reconcile CLI surface |
| `2026-04-21-calc-verification-adr` | accepted | verification orchestrator |
| `2026-05-03-calculation-truth-registry-pending-adr` | accepted | registry-data calculations; `_generate.py` disposition |
| `2026-05-04-calculation-authority-evidence-tiering-adr` | accepted | mandatory legal grounding on filing-grade formulas |
| `2026-05-12-cli-workflow-redesign-adr` (+ shape children) | accepted | two-root CLI (`config` / `app`) |
| `2026-05-15-corpus-registry-packaging-adr` | accepted | registry data path `src/aeat/_data/registry/` |
| `2026-04-17-modelo-formulas-adr` | accepted | original Python `_rulesets/` surface (superseded by `2026-05-03`) |
| `2026-04-22-ruleset-architecture-adr` | **proposed** | no authority |
| `2026-04-28-modelo-200-calc-verify-adr` | accepted | M200 page-14 scope |
| `2026-04-27-modelo-100-renta-full-calc-adr` | accepted | M100 RENTA universe |
| `2026-04-27-modelo-111-calc-verify-adr` | **no status field** | names M111 casillas 09/12/28/30 — authority unconfirmed |
| `2026-04-27-modelo-130-calc-verify-adr` | **no status field** | M130 calc-verify — authority unconfirmed |

### Present and ADR-aligned — no action

- **Justificante import (#271)** — `2026-04-20-pdf-import-adr` (accepted)
  scoped #271 to justificante-PDF import only, *explicitly excluding*
  casilla-level extraction, persisted via what is now
  `aeat app modelo filing-record import`
  (`2026-05-13-cli-workflow-redesign-modelo-external-filing-import-adr`,
  accepted). HEAD delivers this; the branch's broader EPIC-#305 ambition
  is not what the #271 ADR committed.
- **`export` verb** — `aeat app modelo export`; grounded in
  `2026-04-22-aeat-fichero-boe-export-adr` and the two-root CLI of
  `2026-05-12-cli-workflow-redesign-adr`.
- **Verification orchestrator** — `2026-04-21-calc-verification-adr`
  (accepted) sanctions it; `2026-05-03` mandates the registry-backed
  shape HEAD now has. HEAD is the ADR target state.
- **Formula calculations as registry data; Python `_rulesets/` retired**
  — grounded in `2026-05-03-calculation-truth-registry-pending-adr`
  (accepted), which quarantines the `Engine` / `Ruleset` surface that
  `2026-04-17-modelo-formulas-adr` had established.
  `2026-04-22-ruleset-architecture-adr`, which would have extended the
  Python surface, is `proposed` — no authority. Registry data under
  `src/aeat/_data/registry/` is canonical per
  `2026-05-15-corpus-registry-packaging-adr` (accepted).
- **Citation blocklist** — consistent with the mandatory-legal-grounding
  rule of `2026-05-04-calculation-authority-evidence-tiering-adr`.

### Gap 1 (ADR-backed) — Fichero-BOE export layouts for Modelo 130 and 303

**Unfulfilled requirement of an accepted ADR.**
`2026-04-22-aeat-fichero-boe-export-adr` (accepted) explicitly names
`modelo_130_2024`, `modelo_130_2025`, `modelo_303_2024`,
`modelo_303_2025` and `modelo_390_*` as deliverables and declares "Modelo
130 is the first target." No later ADR descopes them. HEAD has working
export layouts for modelos 100/180/202/232 but **none for 130 or 303**,
and therefore cannot serialise a Modelo 130 or 303 to a byte-accurate
fichero-BOE. This is the clearest ADR-grounded gap; the per-modelo
modules and golden round-trip tests were deleted in `ac4c7fd77`.

`_generate.py`'s deletion **is** ADR-sanctioned — `2026-05-03` migration
disposition reads "Delete or quarantine; export layouts must be reviewed
registry data." The deletion of `_ingest.py` and the DR-spec JSON
fixtures (`97dac2be7`) has **no accepted-ADR sanction** — an undocumented
deletion to be recorded in an ADR or reversed.

### Gap 2 (ADR-process gap) — declaración extraction is an undocumented re-architecture

The accepted `2026-04-21-declaracion-extractor-adr` mandates **per-modelo
Python extractor classes** (subclasses of a `DeclaracionExtractor` ABC)
and scopes the capability to **six modelos** — 130, 303, 111, 115, 180,
190 — with MVP v1 limited to 130 + 303. It does **not** authorise a
21-modelo set.

HEAD deleted every extractor class (`1f301c9e1`, `624e7d7cf`,
`39d5bbc99`) and replaced them with a registry-profile-driven generic
parser. **No accepted ADR sanctions that re-architecture or that
deletion** — it contradicts the only accepted ADR on the subject. This is
first an ADR-process gap: the registry-driven design must be ratified by
a new ADR, or the per-modelo extractors restored.

Measured against the accepted ADR's own six-modelo scope, HEAD's delivery
is also incomplete: 111 and 115 work; 130 works but lost the structural
cross-check; 180 has no profile; 190 is a non-functional stub; 303 has no
profile. **Four of the six ADR-scoped modelos lack working declaración
extraction.** The branch's other modelos (036, 037, 123, 131, 193, 200,
202, 232, 347, 349, 369, 390, 720, 840) are beyond accepted-ADR scope —
porting them is not ADR-required and must not be done without an ADR
widening the scope.

### Gap 3 (mostly NOT ADR-backed) — submission CLI verbs

The capability swarm flagged `verify`, `diff`, `check-nif`, `schemas` as
absent. ADR grounding dissolves most of this:

- **`verify` and `diff`** — `2026-04-24-aeat-verify-adr` (accepted)
  catalogued `submission verify` and `submission diff` as candidate
  surfaces and **explicitly declined them**, adopting `aeat filing
  reconcile` (now `aeat app modelo reconcile`) instead. Porting `verify`
  or `diff` would **contradict an accepted ADR.** The ADR-sanctioned
  equivalent — the reconcile verb — already landed on this line with the
  #239 aeat-verify work. No action; confirm reconcile covers the need.
- **`check-nif` and `schemas`** — no accepted ADR commits either as a CLI
  verb. Porting them needs a new ADR first; absent one, out of scope.
- A standalone `aeat submission` root is in any case prohibited by the
  two-root CLI contract (`2026-05-12-cli-workflow-redesign-adr`).

### Gap 4 (tax-correctness — MUST restore) — formula registry population

**Correction of authority precedence.** An earlier revision of this audit
treated formula gaps not named by an accepted ADR as "do not port." That
is wrong. Tax-calculation correctness is the product's overriding
obligation; the calculation-grounding rule requires every casilla to
carry its legal provenance to the operator surface. A formula the branch
computed that the registry does not is a **correctness regression**,
whether or not an ADR names the specific casilla. ADR silence is not
licence to drop a calculation — it is a gap in the ADR record, to be
closed by **authoring the ADR that scopes it**. All four flagged gaps are
therefore **must-restore**:

- **Modelo 200 cuota íntegra (`00562`) / cuota diferencial (`00611`)** —
  within the described page-14 scope of accepted
  `2026-04-28-modelo-200-calc-verify-adr` ("computes cuota íntegra, cuota
  diferencial, and líquido a ingresar / devolver"). Restore the formulas;
  accepted-ADR scope already covers them.
- **Modelo 111 casillas `09` / `12` (19 % retención formulas)** — named
  by `2026-04-27-modelo-111-calc-verify-adr` ("four computed casillas 09,
  12, 28, 30"). That ADR has no status field — resolve it to `accepted`,
  then restore.
- **IRPF ahorro-base estatal escala (art. 66 Ley 35/2006)** — not named
  by `2026-04-27-modelo-100-renta-full-calc-adr`. This is an ADR-record
  gap: author an extension ADR bringing the art. 66 savings tariff into
  M100 registry scope, then restore the bracket table and the
  `0536`/`0538`/`0540` formulas. The savings cuota must be computed and
  verifiable, never left as an unverified extracted input.
- **Modelo 130 structural cross-check `03 = 01 − 02`** — not named by
  `2026-04-27-modelo-130-calc-verify-adr`. Restore it as a
  `verification_expectations` registry stanza; amend the M130 ADR to name
  it.

Every restored formula must derive its expected values from BOE / AEAT
authority (workbooks, BOE worked examples, registry-authoritative
fixtures, oracle replay) — never hand-computed from the formula under
test (the no-tautological-calculation-tests rule).

### Conformance constraints on all port-back work

The branch is ~April-2026 vintage — old flat layout, loosely typed,
English-named. The codebase has since hardened. Every ported item is
**re-implemented** to current convention, not transplanted:

- **Spanish-stem terminology** (`2026-05-19-spanish-stem-terminology-
  authority-adr`, accepted) — tax-domain identifiers use canonical
  Spanish stems (`iva`, `irpf`, `modelo`, `declaracion`, `justificante`,
  `borrador`, `renta`, `finca`/`fincas`, `censo`, `expediente`); English
  infrastructure suffixes (`Record`, `Repository`, `Snapshot`, `Spec`,
  `Result`, `Error`, ...) compose onto the stem; international
  identifiers (`NIF`, `IBAN`, `BIC`) stay English; no stem-stuttering;
  `iva` not `vat`.
- **Strict typing / schema hardening** (`2026-05-18-schema-hardening-
  adr`, accepted) — registry / casilla / formula models follow the
  `strict` / `frozen` / `extra="forbid"` discipline of the
  `ValidatedRegistryAuthority` load surface; new casilla definitions use
  the richest applicable typed `data_type` (no `"text"` fallback);
  `CasillaConstraints` carry `pattern` / `min_length` / `max_length` /
  `enum` where the legal contract specifies a shape; no bare
  `dict[str, Any]`, no `cast(...)` escapes; validation is a hard error at
  snapshot build.
- **Registry-data-driven** (`2026-05-03`) — formulas and layouts are
  authored as reviewed registry TOML, not Python ruleset modules.
- **Hexagonal layout** (`2026-04-30-aeat-restructure-adr`) — ported code
  lands under `domain/` / `application/` / `adapters/` / `entrypoints/`.
- **Roundtrip + anti-tautology tests** — every persistence boundary and
  every new typed alias carries a strict roundtrip test and an
  anti-tautology proof.
- **Legal provenance preserved** — every ported casilla keeps its
  `legal_refs` / `source_refs` / `formula_id` triple intact.

### Consolidated, sequenced backlog

Ordered by precedence: tax-correctness restorations first (highest
obligation, BOE-grounded, well-defined), then the ADR decisions that gate
other work, then capability ports, then cleanup. Every **Port** and
**Decide via ADR** row is subject to the conformance constraints above.

| # | Item | ADR basis | Action |
| --- | --- | --- | --- |
| 1 | Modelo 200 cuota íntegra (`00562`) / diferencial (`00611`) formulas | `2026-04-28-modelo-200-calc-verify-adr` (accepted) | **Port** — author formulas, BOE-grounded |
| 2 | Modelo 111 casillas `09`/`12` (19 % retención) formulas | `2026-04-27-modelo-111-calc-verify-adr` (no status field) | **Resolve ADR status → `accepted`, then port** |
| 3 | IRPF ahorro-base estatal escala (art. 66 Ley 35/2006) | no ADR — record gap | **Author extension ADR, then port** bracket table + `0536`/`0538`/`0540` |
| 4 | Modelo 130 structural cross-check `03 = 01 − 02` | no ADR — record gap | **Amend M130 ADR, then port** as `verification_expectations` |
| 5 | Declaración extraction architecture | `2026-04-21-declaracion-extractor-adr` (accepted) mandates per-modelo extractors; HEAD's registry approach has no ADR | **Decide via ADR** — ratify the registry-driven design or restore extractors |
| 6 | Declaración extraction for ADR-scoped 130/180/190/303 | same ADR, six-modelo scope | **Port** the 4-of-6 ADR-scoped modelos lacking working extraction (gated on #5) |
| 7 | Modelo 130 + 303 fichero-BOE export layouts | `2026-04-22-aeat-fichero-boe-export-adr` (accepted) — named, not descoped | **Port** — author registry export-layout TOML for 130 and 303 |
| 8 | `_ingest.py` + DR-spec fixture deletion | no ADR | **Document** — record the deletion in an ADR or reverse it |
| 9 | CLI `verify` / `diff` | `2026-04-24-aeat-verify-adr` declined them for `reconcile` | **Do not port** — confirm `aeat app modelo reconcile` covers the need |
| 10 | CLI `check-nif` / `schemas` | no ADR | **Defer** — needs a new ADR before any port |

Rows 1–7 carry genuine work to add back; the tax-correctness rows (1–4)
are the highest obligation and must be restored regardless of current ADR
silence — where an ADR does not yet scope the calculation, authoring that
ADR is part of the row. Row 9 is the only true do-not-port (an accepted
ADR rejected it); row 10 is deferred pending a new ADR.

## Modelo 200 casilla finding and blast radius

Discovered while executing the port-back backlog (port of the Modelo 200
cuota formulas). Recorded here as a registry-data finding in its own
right.

**The finding.** AEAT Modelo 200 casilla numbers are *segment-scoped*:
in the official Diseño de Registros the same five-digit number recurs
across record segments (`DP200010` ECPN, `DP200014` Liquidación,
`DP200032` Banco de España, `DP200042` aseguradoras, `DP200DID`) with a
different meaning each time — `00562` is "Cuota íntegra" in the
Liquidación segment and "distribución de dividendos" in the ECPN
segment. The registry casilla model uses `id == number` and forbids
duplicate numbers. When an M200 number collides across segments only one
occurrence survives; the registry kept the ECPN occurrences of
`00552`/`00558`/`00562`/`00611`/`00621` and **silently dropped the
Liquidación cuota-chain casillas** (cuota íntegra, tipo de gravamen, base
imponible liquidación, cuota diferencial). Snapshot-build validation does
not catch this — it checks duplicate ids and semantic-role consistency,
not completeness against the Diseño — so M200 loads green while missing
its filing-grade calculation casillas.

**Blast radius.** A four-agent discovery swarm scoped the reach:

- *Registry data.* Modelo 200 confirmed defective. Modelo 202 was flagged
  "suspect" but is a false alarm — M202 (pago fraccionado) legitimately
  has no accounting-statement casillas. Modelos 220/303/347/349/390/190/
  193/720 carry no casilla data in the registry yet — no present defect,
  no coverage either. Other modelos (036/100/111/115/123/130/131/232/
  353/369) are clean.
- *AEAT source.* Modelo 200 and Modelo 303 are the multi-segment forms
  that reuse numbers across record segments; M303's reuse sits in the
  fichero-BOE record layout (the 303 export-layout backlog row) rather
  than the casilla registry. The ten PDF-only Diseños (145/180/184/190/
  193/347/349/360/720/840) were not machine-verified.
- *Code consumers.* Small. The five mis-segmented M200 casillas are
  referenced only by the M200 export page-bindings (eight export TOML
  files); no formula, binding, cross-modelo relation, or aggregation
  depends on them, and the existing `modelo-200-cuota-ejercicio-a-
  ingresar-devolver` formula is sound. Correcting the registry will not
  cascade into broken calculations — but the M200 export page-014
  binding to `00562` currently resolves to the ECPN casilla and must be
  re-pointed once the Liquidación casillas are registered.

**Root cause is a schema limitation, not bad data.** The registry's
casilla-identity model (`id == number`, globally unique) structurally
cannot represent any AEAT form that reuses casilla numbers across record
segments. This is the architecture question that must be settled by ADR;
it applies to Modelo 200 now and to Modelo 220 and the multi-segment
fichero-BOE forms when they enter the registry. The current validation
passing "green" for M200 is itself a finding: the registry validator
needs a Diseño-completeness check so a silently-dropped casilla fails
the gate.

## Recommendations

1. **Treat 39 of 41 branches as carrying no unique work.** The 33 issue-
   grep matches, 4 semantically-verified supersessions, and 2 empty/
   planning-only branches can be archived without porting. The original
   concern — meaningful work stranded outside the codebase — is, for
   these 39, unfounded.

2. **Work the sequenced `271-pdf-import` backlog (rows 1–8) before
   archiving that branch.** Execute in the table order: the four
   tax-correctness restorations first (rows 1–4) — the highest obligation
   and the most defined work — then the declaración-extraction
   architecture ADR (row 5, which gates row 6), then the Modelo 130/303
   fichero-BOE export layouts (row 7), then the `_ingest.py`
   documentation (row 8). Every item is **re-implemented** to the
   conformance constraints — Spanish-stem naming, strict-pydantic schema
   hardening, registry-TOML, hexagonal layout, roundtrip + anti-tautology
   tests — never merged or cherry-picked from the branch. Every restored
   formula is BOE/AEAT-grounded, never hand-derived from the formula
   under test. Row 9 (`verify`/`diff`) is not ported; row 10
   (`check-nif`/`schemas`) is deferred pending a new ADR. The branch is
   archived only once rows 1–8 are each ported or closed by an explicit
   ADR.

3. **Open new ADRs to close the ADR-record gaps.** The declaración-
   extraction architecture (row 5) needs an ADR ratifying the
   registry-driven design or restoring the per-modelo extractors mandated
   by `2026-04-21-declaracion-extractor-adr`. The IRPF art. 66 ahorro
   escala (row 3) needs an extension ADR bringing it into M100 registry
   scope. The Modelo 130 `03 = 01 − 02` check (row 4) needs the M130
   calc-verify ADR amended to name it. The `_ingest.py` / DR-spec
   deletion (row 8) needs recording in an ADR. The unstatused
   `2026-04-27-modelo-111-calc-verify-adr` and
   `2026-04-27-modelo-130-calc-verify-adr` must have their `status`
   resolved. (`_generate.py`'s deletion and the `_rulesets/` retirement
   are already ADR-sanctioned by `2026-05-03` — no action.)

4. **`epic1`'s audit-log read surface is ADR-resolved as obsolete.**
   `2026-04-27-live-submit-permanently-forbidden-adr` (accepted)
   explicitly makes the `.aeat/live-submit-audit.log` unreachable as a
   security mitigation; with no live submits possible there are no
   events to read. No re-implementation is warranted; no further
   decision is needed.

5. **Confirm a Modelo 347 calc-verify-roundtrip test exists** before
   archiving `feature/330-modelo-347-calc-verify`; modelo 347 is otherwise
   well-covered on this line.

6. **Archive, do not delete.** When the two PARTIAL branches are resolved,
   record final disposition for all 41 in inventory and, if archival is
   wanted, create `archive/` refs rather than deleting remote branches —
   remote refs cost nothing and deletion is needless risk on a shared
   remote. Branch deletion and any force-push of `origin/main` are
   separate, deliberate, owner-level decisions and are explicitly out of
   scope for this audit.

7. **Settle the registry casilla-identity limitation by ADR, and add a
   Diseño-completeness validator gate.** The `id == number` casilla model
   cannot represent multi-segment AEAT forms (Modelo 200 now; 220 and the
   multi-segment fichero-BOE forms later). An ADR must decide a
   segment-scoped casilla identity, the Modelo 200 Liquidación casillas
   must then be registered, and snapshot-build validation must gain a
   completeness check against the AEAT Diseño so a dropped casilla fails
   the gate instead of loading green.

8. **Verification reuse.** The reconciliation effort should re-run the
   issue-grep + defining-artifact + anti-trust method per branch rather
   than trusting this audit's table blindly; sub-agent findings are
   inventory, and every branch should be re-confirmed against current
   HEAD at the moment of archival.
