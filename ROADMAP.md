# aeat roadmap

This roadmap is anchored to **Kent**, our target user — a Spanish autónomo (self-employed person) who needs to file his tax returns (modelos 130, 303, 390, ...) without being an AEAT domain expert.

Each milestone answers one question: **_"What can Kent do at the end of this milestone that he could not do at the start?"_**

Our product direction is **produce → verify → export**. The tool helps Kent produce verifiable, reviewable filing data and export an AEAT-importable file. Kent uploads the file himself via the AEAT portal. **The tool does not submit on Kent's behalf** until milestone 1.0.0, and even then only behind an explicit four-factor opt-in.

See also: charter [#197](https://github.com/wgergely/aeat/issues/197) · ADR [`export-first`](.vault/adr/2026-04-17-export-first-adr.md) · Kent journey audit [`2026-04-17-kent-ux-journey-audit`](.vault/audit/2026-04-17-kent-ux-journey-audit.md) · revise/review audit [`2026-04-17-kent-revise-review-audit`](.vault/audit/2026-04-17-kent-revise-review-audit.md).

---

## 0.0.2-foundations — Kent can install, configure, and see his situation

What Kent can do at the end of this milestone:

- Install the tool on a clean machine without hitting dead ends in `just bootstrap` ([#209](https://github.com/wgergely/aeat/issues/209))
- Create a GCP project using documented step-by-step instructions ([#210](https://github.com/wgergely/aeat/issues/210))
- Configure his FNMT digital certificate and know where the passphrase lives ([#212](https://github.com/wgergely/aeat/issues/212))
- Run `aeat setup` and get a valid `AutonomoProfile` without hand-writing JSON ([#214](https://github.com/wgergely/aeat/issues/214))
- See which modelos apply to him via `aeat deadlines list` using his wizard-generated profile
- See when each modelo is due
- Get a friendly first-run greeting from the root CLI that talks about taxes, not GCP ([#208](https://github.com/wgergely/aeat/issues/208))
- Get Spanish (not Hungarian) output by default ([#207](https://github.com/wgergely/aeat/issues/207))
- Know the current state of `aeat status` instead of getting internal jargon ([#213](https://github.com/wgergely/aeat/issues/213))
- Record a reason when he manually classifies a transaction ([#223](https://github.com/wgergely/aeat/issues/223))

Charter-level work: live-submit relocation ([#198](https://github.com/wgergely/aeat/issues/198)); regression prevention ([#205](https://github.com/wgergely/aeat/issues/205)); this `ROADMAP.md` publication ([#206](https://github.com/wgergely/aeat/issues/206)).

---

## 0.1.0-pre-alpha — Kent can ingest his financial data and reconcile it with live AEAT reads

What Kent can do at the end of this milestone:

- Ingest bank CSV / XLSX / OFX and persist into the catalogue in one command ([#216](https://github.com/wgergely/aeat/issues/216))
- Classify transactions in bulk via rules and LLM-assisted matching ([#217](https://github.com/wgergely/aeat/issues/217))
- Aggregate a classified catalogue into casilla-level Decimal inputs for at least Modelo 130 ([#218](https://github.com/wgergely/aeat/issues/218))
- Fetch previously-filed casilla values from AEAT ([#222](https://github.com/wgergely/aeat/issues/222)) — **load-bearing for revise and for verification**
- See which filings are genuinely missed (not just "date passed") ([#215](https://github.com/wgergely/aeat/issues/215))
- Mark a transaction as "reviewed and intentionally excluded" ([#224](https://github.com/wgergely/aeat/issues/224))
- Run the semi-autonomous pipeline and see confidence scores on every decision ([#204](https://github.com/wgergely/aeat/issues/204) EPIC)
- Distinguish "UNCLASSIFIED because not yet seen" from "UNCLASSIFIED because the pipeline could not decide" ([#204](https://github.com/wgergely/aeat/issues/204) EPIC)
- Know when the corpus definition-review concept is cleanly separated from user-filing review ([#225](https://github.com/wgergely/aeat/issues/225))

---

## 0.2.0-alpha — Kent can compute, review, approve, and export a Modelo 130

What Kent can do at the end of this milestone:

- Run `aeat workflow next` end-to-end for Modelo 130 with real data
- Review every casilla with inline formula expression, operand refs, and operand values ([#220](https://github.com/wgergely/aeat/issues/220))
- Build a draft via a wizard instead of hand-writing inputs JSON ([#219](https://github.com/wgergely/aeat/issues/219))
- Approve the draft explicitly — a persisted human-in-the-loop gate ([#202](https://github.com/wgergely/aeat/issues/202) EPIC)
- Export a fichero BOE file that AEAT's portal accepts via "importar datos" ([#201](https://github.com/wgergely/aeat/issues/201) EPIC)
- Upload the file himself via the AEAT portal
- Get a reference PDF for manual cross-check before uploading

**Live AEAT submission writes are NOT in scope for this milestone.** Kent self-files via the AEAT portal.

---

## 0.3.0-beta — Kent has 303 + 390 + amendment coverage and can trust the pipeline

What Kent can do at the end of this milestone:

- Compute, review, approve, and export Modelo 303 and Modelo 390 ([#221](https://github.com/wgergely/aeat/issues/221))
- Amend a previously-filed Modelo 130, 303, or 390 via the revise surface ([#203](https://github.com/wgergely/aeat/issues/203) EPIC)
- File an **autoliquidación rectificativa** for Modelo 303 and Modelo 130 post-Q3-2024 (the current Spanish amendment mechanism; see RD-ley 13/2023 and Orden HFP/794/2024)
- Ingest a filing Kent made BEFORE using this tool (from justificante PDF or from AEAT live-read) and amend it
- Detect that his approved draft has gone stale because the underlying catalogue changed ([#202](https://github.com/wgergely/aeat/issues/202) EPIC)
- Verify his filing against AEAT's authoritative record after uploading (re-sync fetches the resulting justificante)

---

## 1.0.0 — Live filing opt-in

Live AEAT submission writes become available for users who explicitly accept the charter risks ([#116](https://github.com/wgergely/aeat/issues/116), [#117](https://github.com/wgergely/aeat/issues/117), [#197](https://github.com/wgergely/aeat/issues/197), [#198](https://github.com/wgergely/aeat/issues/198)).

Required gates, all four non-negotiable:

1. **Install-time opt-in** — `AEAT_ALLOW_LIVE_SUBMIT_OPT_IN=1` must be set. Without it, the `aeat live-submit` group is not registered and `--help` does not list it.
2. **Runtime env** — `AEAT_LIVE_SUBMIT_ENABLED=1` (per [#117](https://github.com/wgergely/aeat/issues/117)).
3. **Per-invocation phrase gate** — `--i-understand-this-is-real` flag.
4. **Per-submission confirmation prompt** — interactive y/n before the network write.

Until this milestone closes, the **default install of the tool never calls AEAT's submit endpoint**. A rolling charter-compliance audit gates every release to confirm this invariant holds.

---

## stability and support

- Our supported modelos expand across the 0.x line. 0.2.0-alpha supports Modelo 130 exports; 0.3.0-beta adds 303 + 390 + amendments; 1.0.0 adds live filing and broader modelo amendment coverage ([#203](https://github.com/wgergely/aeat/issues/203) C13l).
- All user-facing output is trilingual (es / en / hu). Spanish is the authoritative language for AEAT domain terminology; English for internal code and documentation; Hungarian is the target user-facing output.
- Every release is cut locally via `just release-apply`; CI never pushes releases.

## how to read this roadmap

- **Kent** is the user. Every milestone question is phrased from his perspective. Implementation details belong in the linked issues.
- Milestones have no calendar due dates yet. When work on a milestone is actively scheduled, due dates will appear on the GitHub milestone.
- The charter ([#197](https://github.com/wgergely/aeat/issues/197)) is the supreme authority on what makes sense to ship. If an issue's scope conflicts with the charter, the charter wins.
