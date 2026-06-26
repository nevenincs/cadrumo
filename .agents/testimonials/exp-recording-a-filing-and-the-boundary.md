# Testimonial — docs/explanation/recording-a-filing-and-the-boundary.md

- **Doc path:** `docs/explanation/recording-a-filing-and-the-boundary.md`
- **Persona:** A curious autónomo reading the explanation of *why the tool never
  files for me* and what "recording a filing" actually means — fact-checking the
  SAFETY boundary against the real CLI and source, not running a tutorial.
- **Date:** 2026-06-18

This is an EXPLANATION page, not a command page, so the walkthrough below is
claim-by-claim verification against source/CLI rather than literal command runs.
The 4-field record shape (command/expect/actual/verdict) is adapted: for each
claim I record **Claim**, **What I checked**, **What I found**, **Verdict**.

---

## Walkthrough (claim-by-claim)

### Claim 1 — "The tool can never submit a return... There is no setting, no flag, and no expert mode that turns it on. The submit path is built to refuse, every time, with a clear error."
- **What I checked:** the AEAT outbound submitter surface and the runtime
  click/navigation guards.
- **What I found:** `src/aeat/adapters/outbound/aeat/export/_submitters/__init__.py`
  is an **intentionally empty package**:
  > "Empty package: no AEAT remote submitter surface is exposed. Live AEAT
  > submission and write-shaped portal walks are permanently forbidden. This
  > package intentionally exports no submitter ABC and no browser-session
  > contract; `__all__` is the empty list..."
  Belt-and-suspenders runtime enforcement lives in
  `sede/_renta_web_open_safety.py`:
  > "under NO circumstance may any calculation be submitted, signed, presented,
  > paid, or persisted to AEAT — even on the open simulator."
  Every Playwright button click routes through `assert_click_target_safe`, which
  blocks clicks whose text matches a forbidden-actions denylist; navigation to
  `/Presentar`, `/Firmar`, `/Pagar`, `/Sign` raises before the request leaves the
  browser; browser dialogs auto-dismiss. Layered: policy-registration first,
  runtime denylist second, each sufficient alone.
- **Verdict:** OK — the absolute "never submits" claim is **fully substantiated**.
  This is the single most important claim on the page and the code backs it
  emphatically, with multiple independent layers and CI guards.

### Claim 2 — "Read-only access is the only connection... Nothing flows the other way. The connection has no path that writes, edits, or registers."
- **What I checked:** the sede (AEAT portal) adapter boundary records and its
  write-guard tests.
- **What I found:** `sede/_schema.py` declares every boundary-crossing record with
  a structural `mode: Literal["read"] = "read"` marker. Two grep-guard test
  modules enforce it at CI:
  `adapters/outbound/aeat/sede/tests/test_no_write_surface.py`
  (`TestNoCallContextWriteVerbs` + `TestNoWriteModeLiteral` — no non-read `mode`
  literal allowed) and a mirrored guard for the sanitizer subpackage. Forbidden
  verbs guarded: submit, send, commit, enviar, presentar, firmar, radicar,
  remitir, modificar, anular, cancelar, rechazar. The CLI `app live` surface
  exposes only read verbs (`filed`, `justificante` — both labelled "solo
  lectura").
- **Verdict:** OK — read-only-only is structurally enforced, not just documented.

### Claim 3 — "You upload the file yourself... The tool never holds your credentials for this and never stands between you and the agency at that moment." + link to file-at-aeat.md
- **What I checked:** link target existence; CLI export surface.
- **What I found:** `docs/how-to/file-at-aeat.md` exists. The
  `aeat app modelo export` help confirms the boundary: "Exporta una revisión de
  modelo... a un fichero local compatible con AEAT (fichero-BOE). **Local; nunca
  contacta con AEAT.**" The tool produces a local file the user uploads manually.
- **Verdict:** OK.

### Claim 4 — "Recording a filing... marks one version as the answer you actually filed... It changes nothing at the agency. It does not submit, re-send, or confirm anything with AEAT."
- **What I checked:** the `work file` verb and its persistence path.
- **What I found:** `aeat app modelo work file` help: "Marcar una revisión
  verificada como internamente presentada. **NO envía a la AEAT.**" The
  persistence path (`_revision_persistence.py`) co-emits a cross-period carry
  observation stamped with the **NON-official `app_filing` source_kind**, which
  by design "never satisfies the cross-period clean-state filing gate." Confirmed
  in `_cross_period_clean_state.py`: `_OFFICIAL_SOURCE_KINDS` =
  {`aeat_sede_justificante`, `aeat_sede_live_capture`, `aeat_csv_register`} — and
  `app_filing` is correctly NOT a member, so a local-only chain hits
  `LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE`.
- **Verdict:** OK — "local note, non-official evidence" is exactly true in code.

### Claim 5 — "Checking your record against the agency's receipt... The comparison reads only the receipt you supply. It does not contact the agency to do its work." + link to reconcile.md
- **What I checked:** link existence; the reconcile CLI; reconcile source.
- **What I found:** `docs/how-to/reconcile.md` exists. `reconcile file` help: "Solo
  local; nunca contacta con AEAT." `reconcile pull` help: "Contacta con AEAT (solo
  lectura)." `_reconcile.py` docstring: compares header fields "(modelo, period,
  ejercicio, tax id) inline against the justificante." The page's claim that the
  *file* path reads only the supplied receipt is accurate.
- **Verdict:** OK (with the nuance in Finding 1 below — see Claim 6).

### Claim 6 — "The comparison confirms that your local record matches the receipt's headline figures - the modelo, the period, your tax ID, and the totals the receipt prints."
- **What I checked:** what the reconciliation actually compares, in source and in
  the sibling how-to.
- **What I found:** `_reconcile.py` compares **four header fields only**: modelo,
  period, ejercicio (filing year), tax id. The how-to (`reconcile.md` line 69-71)
  is explicit: "Reconciliation compares four header fields only: the modelo code,
  the filing year, the period, and the taxpayer identifier... **It does not
  compare box (casilla) values.**" The explanation page instead lists "the
  modelo, the period, your tax ID, **and the totals the receipt prints**" — it
  substitutes "the totals" where the real fourth field is the **filing year
  (ejercicio)**, and "totals" strongly implies amount/casilla comparison that the
  tool explicitly does NOT perform.
- **Verdict:** DOC-ISSUE / MINOR — see Finding 1. The page even acknowledges in
  the next section that it is "not a live re-check of your maths," but the word
  "totals" in Claim 6 directly contradicts the how-to and the code and risks an
  operator trusting a totals-match the tool never made.

### Claim 7 — "The tool can also save read-only copies of the agency's own record as evidence - keeping a copy of what AEAT holds."
- **What I checked:** the live filed/justificante capture surface.
- **What I found:** `app live filed pull` and `app modelo reconcile pull` both
  store encrypted copies of AEAT-sourced records (read-only), stamped with the
  official `aeat_sede_*` source_kinds. Matches the claim.
- **Verdict:** OK.

### Claim 8 — cross-links in "Where this sits in the journey"
- **What I checked:** `index.md`, `editing-and-verifying.md`,
  `building-on-earlier-filings.md`.
- **What I found:** all three target files exist in `docs/explanation/`.
- **Verdict:** OK — all cross-links resolve.

---

## Findings

### Finding 1 — "the totals the receipt prints" overstates the comparison
`[MINOR] [DOC]`
- **Repro:** Page section "What this comparison can and can't tell you" says the
  comparison confirms "the modelo, the period, your tax ID, and **the totals the
  receipt prints**." But `src/aeat/application/modelo/_reconcile.py` compares only
  four *header* fields (modelo, period, ejercicio/filing-year, tax id), and the
  sibling how-to `docs/how-to/reconcile.md` (lines 69-71) states plainly: "It
  does not compare box (casilla) values."
- **Why it matters (safety-relevant precision):** On a page whose whole purpose is
  to set honest expectations about the boundary, telling the reader the tool
  confirms "the totals" invites exactly the false confidence the section is trying
  to prevent. A user could read a `matches` verdict as "my numbers were checked"
  when no amount was compared.
- **Suggested fix:** Replace "and the totals the receipt prints" with the real
  fourth field, e.g. "the modelo, the filing year, the period, and your tax ID —
  the header fields the receipt prints," and drop the word "totals." This also
  aligns the explanation with `reconcile.md`'s own wording.

### Finding 2 — terms "justificante" and "Cl@ve" introduced without a glossary link
`[NIT] [DOC]`
- **Repro:** The page uses `justificante` (defined inline as "the official
  receipt") and `Cl@ve` (defined inline). The how-to pages use the `{term}`
  glossary role for `justificante`. The explanation page defines them in prose
  only.
- **Why it matters:** Minor inconsistency with the Terminology Handbook surface;
  a first-time reader gets the inline gloss, which is adequate, so this is purely
  a cross-link consistency nit.
- **Suggested fix:** Optionally cross-reference the glossary term on first use, as
  the how-to guides do. Not blocking — the inline definitions are clear.

### Finding 3 — no passphrase mention (expected for an explanation page)
`[NIT] [DOC]`
- **Repro:** The brief flags a missing master-key-passphrase warning as a finding
  for command pages. This is a pure explanation page with no runnable commands, so
  the omission is appropriate; recording it only for completeness.
- **Verdict:** Not actionable — the linked how-to pages are where the passphrase
  prerequisite belongs.

---

## Testimonial

As a wary first-time user, this is the page I most wanted to be true, and it held
up under scrutiny better than almost any safety claim I've checked. The promise
that "there is no flag, no expert mode" is not marketing — it is an empty
`_submitters` package, a `mode: Literal["read"]` on every boundary record, grep
guards in CI, and a runtime denylist that blocks the very button click. I came in
ready to catch an overstatement and instead found the code is *stricter* than the
prose. The one place the page reaches too far is calling the reconcile check a
match of "the totals the receipt prints" — the tool only checks four header
fields and the how-to says so outright, so that single word undersells the
boundary the rest of the page so carefully draws. Fix that line and the page is a
model of honest expectation-setting.

## Scorecard

- **Doc clarity:** 4.5 / 5 (one factual overstatement; otherwise precise and well
  cross-linked)
- **App capability:** 5 / 5 (the safety boundary is real, layered, and
  CI-enforced; the app delivers exactly what the page promises)
- **Findings by severity:** BLOCKER 0 · MAJOR 0 · MINOR 1 · NIT 2
- **Safety verdict:** CONFIRMED — the app truly never submits to AEAT; the
  boundary the page describes matches the code.
