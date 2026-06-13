---
tags:
  - '#audit'
  - '#cli-operator-surface'
date: '2026-06-10'
modified: '2026-06-10'
related:
  - '[[2026-06-10-aeat-cli-userdocs-hardening-audit]]'
  - '[[2026-06-04-aeat-cli-userdocs-hardening-plan]]'
---

# `cli-operator-surface` audit: `CRUD and workflow capability validation of the operator CLI`

## Scope

This audit answers one product question: is the `aeat` CLI usable end-to-end for
the work a Spanish taxpayer (or the gestor who helps them) actually does, and
does it support CRUD-shaped lifecycle operations across the ledger, modelo, and
calculation domains? The evidence base is the hardened user-docs corpus (the
twenty-plus `docs/how-to/*` pages, the Modelo 130 tutorial, the
`ledger-to-calculation` explanation, and the index pages) — these were
deliberately rewritten to state limitations honestly, so each documented
workaround and bolded "no command exists" line is read as a product signal, not
a docs defect. Every capability cell and journey verdict below is grounded
either in a named docs page or a live `--help` spot-check
(`AEAT_OUTPUT_LANGUAGE=en uv run --no-sync aeat ... --help`). Cells that could
not be verified are marked. This audit modifies no production code; it produces
an inventory plus prioritised recommendations. It cross-checks the known backlog
(TRUST-002 in `2026-06-10-aeat-cli-userdocs-hardening-audit`; plan steps
`W03.P06.S20`, `W04.P08.S26`, `W05.P10.S32`, `W06.P11.S37`, `W05.P09.S52`) and
flags genuinely new gaps separately. A sibling audit on the same campaign tag,
`2026-06-10-cli-operator-surface-audit`, catalogues the operator-surface *design
weaknesses* (verb naming, lifecycle shape, id churn, help drift) as findings F1
to F8; this audit is the *capability-coverage and journey* companion to it and
references its findings where they overlap rather than re-deriving them.

## Capability matrix

Verbs are real CLI verbs. `Read-one` = inspect a single object; `List` =
enumerate; `Update` = mutate fields in place; `Delete-or-retire` = remove or set
aside; `Undo-or-restore` = reverse the prior action.

| Object | Create | Read-one | List | Update | Delete-or-retire | Undo-or-restore |
|---|---|---|---|---|---|---|
| Taxpayer profile | `config profile create` | `config profile show` | `config profile list` | `config profile edit` / `rename` | `config profile delete --yes` / `logout` | PARTIAL: `import` re-creates from an `export` bundle; no in-tool restore of a deleted profile |
| Censo snapshot | `config profile censo refresh` | `config profile censo show [--snapshot-id]` | PARTIAL: `show` reads one; no enumerate-all-snapshots verb seen | NONE: snapshots are immutable AEAT reads; `apply` writes the profile, not the snapshot | NONE | NONE |
| M036 declaration record | `app modelo m036 alta/modificacion/baja` | NONE — **no read-back verb; printed output is the only confirmation** | NONE | NONE (re-recording a corrected kind/date appends a new record) | NONE | NONE |
| Ledger transaction | `app ledger add` / `import` | `app ledger view` | `app ledger list` (filters, limit/offset) | `app ledger update` (full-replace; **re-derives the id**) | `app ledger remove --yes` / `archive` / `stash` | PARTIAL: `merge` undoes `split`; **no un-stash, no un-archive, no un-remove** |
| Evidence record | `app ledger evidence add` | `app ledger evidence view` | `app ledger evidence list` | `app ledger evidence update` | `app ledger evidence remove --yes` | NONE |
| Document link | `app ledger doclink` (GMAIL/GOOGLE_DRIVE/URL) | PARTIAL: surfaces via `ledger view`; no dedicated doclink read | PARTIAL: no dedicated doclink list | NONE (re-issue doclink) | NONE — no doclink-remove verb documented | NONE |
| Attachment | `app ledger attach --attachment-id` | PARTIAL: via `ledger view` | PARTIAL: via `ledger view` | NONE | NONE — no detach verb documented | NONE |
| Classification | `app ledger classify` / `allocate` / rule `apply` / `--from-csv` | via `ledger view` | `ledger list --filter classification=` | `app ledger classify` (re-run replaces) | NONE (no "unclassify"; revert by re-classifying) | NONE |
| Work unit | `app modelo work create` (idempotent) | `app modelo work status` | `app modelo work list [--include-discarded]` | `app modelo work rename` | `app modelo work discard --yes` | NONE — discard is one-way; re-create a fresh unit |
| Calculation revision | `app modelo work calculate` (new revision per change) | `app modelo work revision [--select]` | `app modelo work revisions` | NONE — revisions are immutable; recalculate to supersede | NONE (superseded, never deleted) | PARTIAL: address an older revision via `--select`/id; no rollback verb |
| Manual casilla / binding values | `work calculate --casilla X=V` / `--binding K=V` / `--relation K=V` | `app modelo bindings list` / `modelo casillas` | `app modelo bindings list [--missing]` | re-run calculate with new value (new revision) | NONE | PARTIAL: `bindings preview` is non-destructive; no clear-a-supplied-value verb seen |
| Verification report | `app modelo work verify` (writes a report) | `app modelo verification-report view` | `app modelo verification-report list` | NONE (immutable; re-verify writes a new one) | NONE | NONE |
| Local filing record | `app modelo work file` / `app modelo filing-record import` | `app modelo filing-record view` | `app modelo filing-record list` | NONE — no edit-in-place | NONE — **no un-file / reopen verb** | NONE |
| Exported artifact | `app modelo export --output` | file on disk; checksum printed | NONE (filesystem, not tracked by a list verb) | re-export overwrites | filesystem delete (outside tool) | NONE |
| Reconciliation result | `app modelo reconcile` / `reconcile-from-justificante` | verdict printed | NONE — **no reconciliation-history list verb seen** | NONE | NONE | NONE |
| IVA wallet balance | `app modelo iva-wallet seed --confirm` | `app modelo iva-wallet balance` | PARTIAL: `live iva-wallet history` reads remote-derived history; local `iva-wallet` has only `balance`/`seed` | NONE — **seed refuses if a record exists; no re-seed/correct** | NONE | NONE |

Worst rows by missing coverage: **M036 declaration record** (Create only — no
read, list, update, retire, or undo), **Reconciliation result** (Create only; no
list/history), **IVA wallet balance** (seed-once, no correction path), **Local
filing record** (no un-file), and **Document link / Attachment** (no
remove/detach verb).

## Operator journeys

### (a) Quarter-end full loop — FRICTION (passes, with one sharp edge)

Import (`ledger import --dry-run` then real) → classify (`ledger classify` /
`--from-csv`) → calculate (`work calculate`) → fix a wrong transaction
(`ledger update`) → recalculate → verify (`work verify`) → export
(`modelo export`) → record filed (`work file`) → reconcile (`modelo reconcile`)
is fully documented and every verb is live. The loop holds together. The sharp
edge: `ledger update` **re-derives the transaction id** (per
`correct-ledger-entries.md`; confirmed by `ledger update --help`, "full-replace
field semantics"), so a late fix invalidates any id the operator wrote down and
forces a re-`list` to recover it before recalculating — a real mid-loop stumble
the docs warn about but the CLI does not smooth over. Recalculation is
non-destructive (a new revision supersedes), which is correct. Verdict: usable,
with the id-churn friction (this is the sibling audit's finding F3).

### (b) "What did I file last year, and what is still due?" — FRICTION

Two half-answers, no single surface. "Still due" comes from `app overview
agenda` / `backlog` / `calendar`, all explicitly local planning tools that "do
not prove what AEAT has received" (`filing-calendar.md`). "What I filed" splits
three ways: `app modelo filing-record list` (local markers only), `app live
expedientes` / `live filed` (AEAT's own record, requires live auth), and the
local work-unit history. No single command answers the taxpayer's actual
question across a tax year. This is exactly backlog step `W05.P09.S52` (plain
tax-year filing-history surface). Verdict: answerable by an expert stitching
three surfaces; not answerable plainly. FRICTION.

### (c) Fix a mistake AFTER filing (amendment) — PASS (narrow but real)

A genuine amendment path exists: `app modelo work amend --from-filing-record
<id> --kind complementaria --reason ... --set <casilla>=<value>` (per
`review-calculation-values.md`; confirmed by `work amend --help`, "Build a
corrective amendment over an externally-filed return"). The docs correctly warn
not to just recalculate the same period, and the precondition — import the
justificante as a filing record first (`filing-record import`) — is stated. The
path is narrow (you must know the casilla and the filing-record id; no guided
prompt) but it is real and grounded. Verdict: PASS with expert-level friction on
id discovery.

### (d) Multi-taxpayer operation (gestor with several clients) — FAIL for bulk

Switching and isolation are sound: `config profile list` / `config unlock NAME`
switch the active taxpayer, and every guide states each profile keeps its own
ledger, calculations, and filings (`troubleshooting.md`: "the wrong profile is
active … shows someone else's data"). Cross-profile *visibility* exists in
exactly one place — `app overview calendar --all-profiles`. But there is **no
bulk operation across profiles**: no "calculate 303 Q1 for all clients", no
"export every due filing", no batch verify. The gestor unlocks, works one
client, unlocks the next, repeats — entirely serial. For the named persona (a
gestor with several clients) this is the weakest journey. Verdict: isolation
PASS, switching PASS, **bulk FAIL** (new gap — not in the cited backlog).

### (e) Recover from "I imported the wrong file twice and stashed half my rows by mistake" — FAIL

This is the recovery the docs are most honest about and the product is weakest
at. Duplicate import is remediable (`ledger remove` / `archive` per row, or
`ledger reset --yes` to clear and re-import). But the "stashed half my rows by
mistake" half has **no recovery**: `correct-ledger-entries.md` states plainly
"No command currently restores a stashed transaction to active, and the same is
true of archived transactions. Both are permanent." So an accidental bulk stash
is unrecoverable short of `ledger reset` — nuke the whole ledger and re-import
everything. There is no selective un-stash, no "show me what I stashed and put
it back." Verdict: FAIL — the only escape is the scorched-earth reset. This is
the sibling audit's finding F2; the *journey-level* consequence (a routine slip
with a catastrophic-only remedy) is recorded here.

## Findings

### F-01 | HIGH | No reversal for set-aside ledger rows forces a whole-ledger reset

`ledger stash` and `ledger archive` are one-way; the only documented recovery
from an accidental stash/archive is `ledger reset` (clear the entire active
ledger and re-import). Evidence: `correct-ledger-entries.md` ("Both are
permanent"), confirmed by `ledger --help` showing `archive` / `stash` / `reset`
but no inverse verb. This is the single highest-leverage usability gap: a
routine operator slip (stash the wrong selection) has a catastrophic-only
remedy. It overlaps TRUST-002 and the sibling audit's F2; this audit records the
*capability and journey-level* consequence. **Recommendation:** add an `unstash`
/ `unarchive` (or `ledger restore --id`) verb returning a set-aside row to
active; until it lands, treat the honest-limitation sentence in
`correct-ledger-entries.md` as the acceptance criterion.

### F-02 | HIGH | No plain tax-year filing-history surface (already backlogged)

The taxpayer question "what did I file, what did I miss, what is still due" has
no single answer; it requires stitching `overview backlog`, `modelo
filing-record list`, and `live expedientes` / `filed`. Evidence: journey (b);
`filing-calendar.md` (backlog "does not prove what AEAT has received");
`check-aeat-notifications.md`. This is plan step `W05.P09.S52` verbatim.
**Recommendation:** prioritise `S52` — a `modelo filing-history --year` style
surface that fuses local markers with optionally-pulled AEAT state and is
explicit about which rows are local-only vs AEAT-attested.

### F-03 | MEDIUM | M036 declaration record is write-only

`app modelo m036 alta/modificacion/baja` records a declaration but there is **no
list and no view** — "no command yet lists recorded declarations afterwards"
(`modelo-036.md`), confirmed by `app modelo m036 --help` (only the three record
verbs). The printed output is the sole confirmation, and the record has no
downstream calendar/profile effect. Overlaps TRUST-002 and the sibling audit's
F7. **Recommendation:** add `m036 list` / `m036 view`; a small, self-contained
read surface that removes a documented dead end.

### F-04 | MEDIUM | No bulk / cross-profile operations for the gestor persona

The landing page (`docs/index.md`) names "the people who help them prepare …
filing records" as a target user, yet every mutating verb is
single-active-profile and the only cross-profile surface is `overview calendar
--all-profiles`. Evidence: journey (d); `config --help`; `modelo work list
--help` (filters by `--bucket-id`, not "all profiles"). **New gap** — not in the
cited backlog and not in the sibling audit. **Recommendation:** scope a
gestor-mode decision (ADR): at minimum a cross-profile "what is due across all
my clients" agenda; optionally batch calculate/verify/export. Decide explicitly
whether bulk mutation is in product scope or deliberately excluded, and document
the chosen stance.

### F-05 | MEDIUM | IVA wallet seed is one-shot with no correction path

`iva-wallet seed` "refuses if a record already exists for the period"
(`iva-wallet seed --help`) and there is no re-seed, edit, or delete. A wrong
seed (a typo'd carry-forward amount for a pre-history period) appears
unrecoverable through the documented surface. Evidence:
`review-calculation-values.md`; `iva-wallet --help` (only `balance`, `seed`).
**Recommendation:** verify against source whether a correction path exists (e.g.
a remote `live iva-wallet pull` overwriting local); if not, add a guarded
`iva-wallet seed --force` / `correct`. MEDIUM because mis-seeds are rare and the
value feeds only M303 compensation.

### F-06 | LOW | No remove/detach verb for doclinks and generic attachments

`ledger doclink` and `ledger attach --attachment-id` create links but no
documented verb removes a doclink or detaches a generic attachment
(purchase-invoice evidence is removable via `evidence remove`, but that is a
different role). Evidence: `ledger-evidence.md`; `ledger --help` (no
detach/unlink verb). **Recommendation:** confirm against source; if genuinely
absent, add a detach verb. LOW because the link is metadata-only and a row can
be re-`update`d or re-`link`ed.

### F-07 | LOW | No reconciliation-history list

`modelo reconcile` prints a verdict but no verb lists past reconciliation
results. Evidence: journey; `modelo --help` (reconcile verbs present, no
reconcile-list). **Recommendation:** low priority; reconciliation is repeatable
on demand from the justificante, so the absence of history is a convenience gap,
not a correctness gap.

### F-08 | INFO | Verified positive surfaces (no action needed)

For balance: profile, evidence record, and ledger transaction have full or
near-full CRUD; calculation revisions are correctly immutable-and-superseded (an
append-only audit model, not a gap); `work create` / `work file` / `reconcile`
are idempotent where they should be; destructive verbs (`remove`, `reset`,
`discard`, `delete`, `split`, `merge`, `stash`, `archive`) consistently gate on
`--yes` and most offer `--dry-run`. The core single-taxpayer quarter-end loop is
coherent and grounded.

## Recommendations

In priority order for the ADR/plan to take up:

- **P1 — Ledger set-aside reversal (F-01).** Highest leverage: converts a
  catastrophic-only recovery into a routine one. Pair with backlog `W04.P08.S26`
  and the sibling audit's F2 decision.
- **P1 — Plain tax-year filing-history surface (F-02 / step `W05.P09.S52`).**
  Closes the most natural taxpayer question that today has no plain answer.
- **P2 — Gestor cross-profile scope decision (F-04).** Needs an ADR to decide
  in/out of scope before any build; the product currently under-serves a named
  persona without a recorded decision.
- **P2 — M036 read-back (F-03).** Small, self-contained, removes a documented
  dead end; aligns with backlog follow-on to `W03.P06.S20` and the sibling
  audit's F7.
- **P3 — IVA wallet seed correction (F-05)** and **P3 — doclink/attachment
  detach (F-06)**, both pending a source confirmation of true absence.
- **P4 — Reconciliation history (F-07).** Convenience only.
- **Process:** keep the live-CLI technical-review gate the userdocs audit
  mandates; it is what kept these honest-limitation sentences accurate, and the
  backlog acceptance criteria depend on them staying true.

## Codification candidates

Applying the three durability criteria (cross-session, constraint-shaped,
project-bound) strictly:

- **Source:** finding F-01, generalised across the matrix (stash, archive,
  discard, the filing marker, and iva-wallet seed are all one-way set-aside or
  mark actions with no inverse verb).
  **Rule slug:** `set-aside-verbs-need-a-reversal-or-a-documented-permanence`.
  **Rule:** Every CLI verb that sets a record aside or marks a one-way lifecycle
  transition (stash, archive, discard, file, seed) MUST either ship a paired
  reversal verb or carry an explicit, tested honest-permanence statement in its
  help text and the owning docs page; a set-aside action whose only recovery is a
  whole-collection reset is a product defect, not an acceptable limitation.

This candidate is offered, not asserted — it borders the existing
`vaultspec-dry-run-discipline` rule (preview before destruction) and the userdocs
audit's honest-limitation discipline. It is distinct because it governs the
*existence of a reversal path*, not the preview of a destructive one. If the team
judges it sufficiently covered by the dry-run rule plus the per-page honesty
sentences, decline it. No other finding meets the bar: F-02/F-03/F-04/F-05 are
tracked or to-be-tracked product gaps (one-off backlog items, not cross-session
constraints), and F-06/F-07 are convenience gaps.

## Overall verdict

The `aeat` CLI is **usable today for a single, hands-on taxpayer or a gestor
working one client at a time through one quarter-end loop at a time.** The core
spine — profile → import → classify → calculate → verify → export → record →
reconcile, plus a real post-filing amendment path — is complete, grounded, and
internally consistent, with destructive verbs uniformly gated. It is **not yet
usable** as a multi-client practice tool (no bulk or cross-profile operation),
and it is **fragile on recovery**: an accidental bulk stash/archive has only a
scorched-earth remedy. The single highest-leverage capability gap is **F-01 —
the absence of any reversal for set-aside ledger rows**, which turns a routine
operator slip into a whole-ledger reset; closing it (alongside the
already-backlogged plain filing-history surface) would move the product from
"usable by a careful expert" to "usable by an ordinary taxpayer who makes
ordinary mistakes."
