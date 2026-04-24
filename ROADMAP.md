# aeat roadmap

This roadmap is written for **Kent** — our target user, a Spanish autónomo who needs to file his tax returns (modelos 130, 303, 390, ...) without being an AEAT domain expert.

Every milestone answers ONE question: **_"What can Kent do at the end of this milestone that he could not do at the start?"_** Every milestone has ONE observable success moment — a single event that proves the milestone shipped.

Our product direction is **produce → verify → export**. The tool helps Kent produce verifiable filing data, lets him review and approve it, and exports an AEAT-importable file. Kent uploads the file himself via the AEAT portal. **The tool does not submit on Kent's behalf** until milestone 1.0.0, and even then only behind an explicit four-factor opt-in.

See also: product charter [#197](https://github.com/wgergely/aeat/issues/197) · PM governance [#240](https://github.com/wgergely/aeat/issues/240) · ADR [`export-first`](.vault/adr/2026-04-17-export-first-adr.md) · Kent journey audits [first-file](.vault/audit/2026-04-17-kent-ux-journey-audit.md) · [revise/review](.vault/audit/2026-04-17-kent-revise-review-audit.md).

---

## 0.0.2 — Kent can install the tool and see what he owes

### success moment

On a clean laptop, Kent runs `git clone && just bootstrap && aeat setup && aeat deadlines list --year 2026` and sees a table of his upcoming modelos with due dates. Zero hand-edited JSON, zero Python tracebacks.

### What Kent can do at the end of this milestone

- Install without hitting dead ends in `just bootstrap` ([#209](https://github.com/wgergely/aeat/issues/209))
- See the GCP-project prerequisite documented up front ([#210](https://github.com/wgergely/aeat/issues/210))
- Know where to store his FNMT certificate passphrase safely ([#212](https://github.com/wgergely/aeat/issues/212))
- Run `aeat setup` and get a valid profile without writing JSON ([#214](https://github.com/wgergely/aeat/issues/214))
- See which modelos apply to him and when ([existing deadline engine])
- Get Spanish (not Hungarian) CLI output by default ([#207](https://github.com/wgergely/aeat/issues/207))
- Read "file your Spanish tax returns" as the first line of `aeat --help` ([#208](https://github.com/wgergely/aeat/issues/208))
- See a humane message instead of `#8 not yet landed` jargon from `aeat status` ([#213](https://github.com/wgergely/aeat/issues/213))
- Record *why* when he manually classifies a transaction ([#223](https://github.com/wgergely/aeat/issues/223))

### charter-level commitments

- Live AEAT submission is not registered in the default CLI ([#198](https://github.com/wgergely/aeat/issues/198))
- Regression prevention CI checks pass ([#205](https://github.com/wgergely/aeat/issues/205))
- Public `ROADMAP.md` published ([#206](https://github.com/wgergely/aeat/issues/206))
- PM governance charter landed ([#240](https://github.com/wgergely/aeat/issues/240))
- Monthly + quarterly audit umbrellas open ([#241–246](https://github.com/wgergely/aeat/issues/241))

---

## 0.1.0 — Kent can feed his bank data in and trust the classification

### success moment

Kent imports three bank CSVs (BBVA, Wise EUR, Wise GBP — multi-currency work waits for 0.3.1 but the single-currency path must be complete) with one command. The pipeline classifies most rows automatically, leaves a small review queue, and gives Kent a single `aeat pipeline status --period 2026Q1` dashboard showing confidence scores per decision. **No live AEAT reads required** — the full T1→T6 pipeline works locally.

### What Kent can do at the end of this milestone

- Import bank statements and have them persisted in one command ([#216](https://github.com/wgergely/aeat/issues/216))
- Bulk-classify transactions via rules, not one at a time ([#217](https://github.com/wgergely/aeat/issues/217))
- See how much he owes for Modelo 130 this quarter ([#218](https://github.com/wgergely/aeat/issues/218) — T6 aggregation)
- See a confidence score on every pipeline decision ([#236](https://github.com/wgergely/aeat/issues/236))
- Distinguish pipeline-skipped from not-yet-seen transactions ([#237](https://github.com/wgergely/aeat/issues/237))
- Run one command to see pipeline health for a period ([#238](https://github.com/wgergely/aeat/issues/238))
- Mark transactions "reviewed and intentionally excluded" ([#224](https://github.com/wgergely/aeat/issues/224))
- See WHY each classification was made ([#231](https://github.com/wgergely/aeat/issues/231) — DecisionProvenance)
- See everything pending his review in one dashboard ([#232](https://github.com/wgergely/aeat/issues/232))
- Know the `reviewed_by` namespace is clean (corpus-review renamed) ([#225](https://github.com/wgergely/aeat/issues/225))

---

## 0.1.1 — Kent can see his AEAT filing history and inbox

### success moment

After pluggable auth lands (P12 certificate or Cl@ve), Kent runs `aeat status expedientes` and sees every return he has previously filed with AEAT — with casilla-level values, not just metadata. `aeat inbox list` shows pending notifications fetched live from his buzón electrónico.

### What Kent can do at the end of this milestone

- Authenticate against AEAT Sede Electrónica via a pluggable Auth Provider (P12 cert or Cl@ve 2FA) ([#141](https://github.com/wgergely/aeat/issues/141), [#270](https://github.com/wgergely/aeat/issues/270))
- Retrieve previously-filed casilla values from AEAT ([#272](https://github.com/wgergely/aeat/issues/272)) — **load-bearing for revise** (originally #222; closed 2026-04-18 and rescoped under #272 for the cert-dependent live path and #305 for the PDF-verified import path)
- Ask "what filings did I miss?" and get a correct answer ([#215](https://github.com/wgergely/aeat/issues/215))
- See live AEAT inbox notifications ([#170](https://github.com/wgergely/aeat/issues/170))

---

## 0.2.0 — Kent can produce, review, approve, and export his Modelo 130

### success moment

Kent runs `aeat workflow next` for Q1 2026. The tool computes his Modelo 130, shows him every casilla with formula and operand values inline, he runs `aeat review approve`, then `aeat submission export`, uploads the `.130` file himself via AEAT's portal — and AEAT accepts it.

### What Kent can do at the end of this milestone

- Build a Modelo 130 draft via a wizard (not by writing casilla-code JSON) ([#219](https://github.com/wgergely/aeat/issues/219))
- See formula expressions + operand values inline during review ([#220](https://github.com/wgergely/aeat/issues/220))
- Approve a draft and the tool remembers (approval state + staleness) ([#230](https://github.com/wgergely/aeat/issues/230))
- Export an AEAT-importable fichero BOE file ([#201](https://github.com/wgergely/aeat/issues/201))
- Upload the file himself via the AEAT portal (manual step — documented)

**Live AEAT submission writes are NOT in scope for this milestone.** Kent self-files via the AEAT portal.

---

## 0.3.0 — Kent can handle 303, 390, and fix past filings

### success moment

Kent files his quarterly Modelo 303 via the tool (produce + export + self-upload). Separately, he realises a past Modelo 303 had an error; he runs `aeat revise start --modelo 303 --period 2026Q1`; the tool fetches previously-filed casilla values from AEAT, walks him through the rectificativa wizard (post-Q3-2024 mechanism), and exports an amendment file AEAT accepts.

### What Kent can do at the end of this milestone

- Compute Modelo 303 and Modelo 390 via the formula engine ([#221](https://github.com/wgergely/aeat/issues/221))
- Import a past filing he made outside the tool ([#233](https://github.com/wgergely/aeat/issues/233))
- File autoliquidación rectificativa (post-Q3-2024 amendment mechanism) ([#234](https://github.com/wgergely/aeat/issues/234))
- Amend any supported modelo via wizard + export ([#235](https://github.com/wgergely/aeat/issues/235))

---

## 0.3.1 — Kent can work with multi-currency income and expenses

### success moment

Kent has GBP invoices via Wise and EUR invoices via BBVA. He runs the full pipeline; every transaction gets its correct base-currency (EUR) value per AEAT FX rules; his Modelo 130 accounts for FX gains/losses correctly. Retentions modelos (111, 115, 190) and operaciones con terceros (347) also become available.

### What Kent can do at the end of this milestone

- Pipeline correctly handles multi-currency transactions end-to-end ([#103](https://github.com/wgergely/aeat/issues/103))
- Compute + export Modelo 111 (retenciones), 115 (retenciones alquiler), 190 (resumen anual retenciones), 347 (operaciones con terceros)

---

## 0.4.0 — Kent can trust the tool's alerts, staleness checks, and verification loop

### success moment

Kent leaves the tool for a week. When he returns, `aeat doctor` tells him: two new AEAT notifications arrived, one approved draft went stale because new transactions landed, one deadline is approaching, and his uploaded Q1 2026 Modelo 130 matches AEAT's record byte-for-byte.

### What Kent can do at the end of this milestone

- Prove his exported numbers match AEAT's record ([#239](https://github.com/wgergely/aeat/issues/239) — aeat verify)
- Get proactive alerts on new notifications, stale drafts, approaching deadlines
- See the full verification loop close after every manual AEAT upload
- Rely on the rolling charter-compliance audit

---

## 1.0.0 — Kent can (opt-in) have the tool file for him

### success moment

Kent explicitly enables live submission (`AEAT_ALLOW_LIVE_SUBMIT_OPT_IN=1` + `AEAT_LIVE_SUBMIT_ENABLED=1`), types the confirmation phrase, approves the interactive prompt — and the tool submits a Modelo 130 live to AEAT. Every other Kent-capability milestone has closed first; the four-factor gate fires correctly; the rolling audit confirms no regression.

### Required gates, all four non-negotiable

1. **Install-time opt-in** — `AEAT_ALLOW_LIVE_SUBMIT_OPT_IN=1`
2. **Runtime env** — `AEAT_LIVE_SUBMIT_ENABLED=1` ([#117](https://github.com/wgergely/aeat/issues/117))
3. **Per-invocation phrase** — `--i-understand-this-is-real`
4. **Per-submission prompt** — interactive y/n

Until this milestone closes, the **default install NEVER calls AEAT's submit endpoint**.

---

## how we ship (cadence)

### every PR

- Charter compliance check (CI gate — [#205](https://github.com/wgergely/aeat/issues/205))
- Coverage matrices updated if relevant (`docs/coverage/`)
- Regression-prevention test if closing a Kent wall

### monthly (recurring audits)

- Feature + modelo coverage matrix refresh ([#241](https://github.com/wgergely/aeat/issues/241))
- Code duplication sweep ([#242](https://github.com/wgergely/aeat/issues/242))
- Code health — complexity, coverage delta, dead code ([#243](https://github.com/wgergely/aeat/issues/243))
- Kent journey regression — re-run every wall ([#244](https://github.com/wgergely/aeat/issues/244))

### quarterly (strategic audits)

- Charter compliance ([#245](https://github.com/wgergely/aeat/issues/245))
- Architectural + ADR review ([#246](https://github.com/wgergely/aeat/issues/246))

### per-milestone

- Rolling pipeline audit gate ([#109](https://github.com/wgergely/aeat/issues/109) methodology, [#110](https://github.com/wgergely/aeat/issues/110)–[#113](https://github.com/wgergely/aeat/issues/113))

---

## how we delegate

Up to six parallel agent slots across Claude, Codex, Gemini. An agent can pick up any issue labelled `ready` + `parallel-safe` without owner assignment. `parallel-risky` issues need serialising. `needs-design` requires an ADR before implementation. Every issue carries priority (`priority:P0-blocker`–`P3-low`) and effort (`effort:XS`–`XL`). PM charter: [#240](https://github.com/wgergely/aeat/issues/240).

---

## how to read this roadmap

- **Kent** is the user. Every milestone speaks in his voice — what he can *do*, not what we shipped.
- Milestones deliberately carry no calendar due dates yet. Scheduling happens when capacity conversations happen.
- Charter [#197](https://github.com/wgergely/aeat/issues/197) is the supreme authority on product direction. PM charter [#240](https://github.com/wgergely/aeat/issues/240) is the supreme authority on how we deliver.
- Two walls remain discoverable *only* via the monthly Kent-journey regression audit ([#244](https://github.com/wgergely/aeat/issues/244)) — we do not assume the current audit list is complete.
