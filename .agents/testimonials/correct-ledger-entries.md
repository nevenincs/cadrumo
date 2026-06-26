# Testimonial — Correct mistakes in your ledger

- **Doc path:** `docs/how-to/correct-ledger-entries.md`
- **Persona:** A first-time user who needs to update / correct / remove / archive / stash / split / merge a ledger entry.
- **Date:** 2026-06-18

## Walkthrough

### Prerequisite (NOT on the page) — create profile + add transaction
- **Command:** `aeat app ledger add --date 2026-02-10 --amount 100 --direction OUTGOING --description "test"`
- **Expected (from page):** "You need a ledger with transactions in it." The page assumes a ledger already exists.
- **Actual:** First refusal: `Refused. No hay un perfil activo. Ejecuta 'aeat config profile create NAME --tax-id <NIF/CIF/DNI/NIE>' primero.` Had to create a profile first (`aeat config profile create persona --quiet --tax-id 12345678Z`), then the add succeeded with `ID a3e9f33e...`.
- **Verdict:** DOC-ISSUE, MINOR. The "Before you start" section never mentions you need an active profile, nor that `add` requires `--quiet` to avoid the interactive wizard. A naive reader with no profile is blocked before reaching any documented command. (App refusal itself was instructive.)

### `aeat app ledger list` / `aeat app ledger view <transaction-id>`
- **Command:** `aeat app ledger list` then `aeat app ledger view a3e9f33e`
- **Expected:** See the transaction and its detail; find the ID to fix.
- **Actual:** OK. `list` printed the row; `view` accepted the 8-char prefix and printed all fields including `Estado de ciclo de vida ACTIVE`.
- **Verdict:** OK.

### Update fields — `aeat app ledger update`
- **Command:** `aeat app ledger update a3e9f33e --amount 121.00 --description "Office chair, corrected price"`
- **Expected:** Fields replaced; a NEW ID printed; old ID still resolves in `history`/`view`/`track`.
- **Actual:** OK. New `ID 79df03e9...` printed. Old prefix `a3e9f33e` still resolved: `view` showed the corrected row, `history` and `track` both reported the new canonical ID `79df03e9...`. Exactly as the page promised.
- **Verdict:** OK.

### Negative-amount refusal (page claims "a negative amount is refused")
- **Command:** `aeat app ledger update 79df03e9 --amount -5`
- **Expected:** Refused.
- **Actual:** OK. `Invalid value: El --amount -5 debe ser una magnitud no negativa. Indica el importe sin signo y define el flujo con --direction (OUTGOING para salidas, INCOMING para entradas, INTERNAL_TRANSFER entre tus propias cuentas).` Instructive and correct.
- **Verdict:** OK (Spanish-only friction noted below).

### Remove — `aeat app ledger remove` (dry-run then yes)
- **Command:** `aeat app ledger remove <id> --reason "wrong file imported" --dry-run` then `--yes`
- **Expected:** Preview without deleting; then delete.
- **Actual:** OK. Dry-run printed `Eliminado False / MODO DE PRUEBA (DRY RUN) True`; the `--yes` run printed `Eliminado True`.
- **Verdict:** OK.

### Split — `aeat app ledger split`
- **Command:** `aeat app ledger split <id> --child-amount 100.00 --child-description "office supplies" --child-amount 21.00 --child-description "personal items" --reason "mixed receipt" --yes`
- **Expected:** Original becomes split parent; two parts carry the balance.
- **Actual:** Works, but output is opaque: `id_padre ... / id_grupo_division ... / hijas 2 / id_evento ...`. The child IDs are NOT printed. To merge them back (next step) I had to run `list` and eyeball which two new rows were the children (3b7b299e=100, 6f6cf1fa=21). The split parent ALSO still appears in plain `list` (40416d1e, 121, "mixed payment") next to its two children, which is visually confusing.
- **Verdict:** DOC-ISSUE + APP-ISSUE, MAJOR. The page's very next section needs `--child-id <id1> --child-id <id2>`, but neither the doc nor the split output tells you where to get those IDs. The doc should say the split output omits child IDs and that you find them via `list`, or the split output should print them.

### Merge — `aeat app ledger merge`
- **Command:** `aeat app ledger merge --child-id 3b7b299e --child-id 6f6cf1fa --reason "undo split" --yes`
- **Expected:** Parts + parent move to history; a fresh transaction created.
- **Actual:** OK. Printed `id_fusionado 23208d3b...` (the fresh transaction) plus parent/group IDs.
- **Verdict:** OK (depends on the split-output gap above to obtain `--child-id`s).

### Stash — `aeat app ledger stash`
- **Command:** `aeat app ledger stash <id> --reason "waiting for invoice" --yes`
- **Expected:** Row leaves everyday lists/totals.
- **Actual:** Command succeeded but the output is the standard 5-line transaction summary (`ID/Fecha/Importe/Descripción/Estado de revisión`) with NO lifecycle indication — nothing says "stashed". Only `view` later confirms the lifecycle change.
- **Verdict:** APP-ISSUE, MINOR. The mutation output gives no confirmation that the lifecycle actually changed. Same for archive below.

### Archive — `aeat app ledger archive`
- **Command:** `aeat app ledger archive <id> --reason "duplicate imported row" --yes`
- **Expected:** Kept in history, out of ordinary work.
- **Actual:** Succeeded; same opaque summary, no lifecycle confirmation in output.
- **Verdict:** APP-ISSUE, MINOR.

### Restore + the documented filter
- **Command:** `aeat app ledger restore 3775e6d9 --reason "stashed by mistake" --yes`; then `aeat app ledger list --filter classification=NOT_YET_PROCESSED`
- **Expected (page):** "To recover several rows stashed by mistake, list the stashed rows first" with that filter, then restore each.
- **Actual:** Restore worked. But `list --filter classification=NOT_YET_PROCESSED` does NOT list "stashed rows" — it returned ACTIVE rows, the still-archived `to-archive` row, AND the merged-away split parent/children. The filter keys on classification, not on lifecycle (stashed vs active). So the documented recipe for "list the stashed rows" does not actually isolate stashed rows.
- **Verdict:** DOC-ISSUE, MAJOR. The page tells the user to use `--filter classification=NOT_YET_PROCESSED` to find stashed rows, but that filter is a classification filter, not a lifecycle filter; it surfaces archived/split/active rows too. A new user following this recipe would restore the wrong rows.

### Restore refusals (page claims it refuses active + already-filed rows)
- **Command:** `aeat app ledger restore 79df03e9 --reason "x" --yes` (an active row)
- **Actual:** OK. `Error. ledger transaction is already active; restore applies only to a stashed or archived row`. (Could not test the "already-filed period" refusal without a filed return; the page sets that expectation but I could not exercise it here.)
- **Verdict:** OK.

### Update on archived row refuses (page claims immutability)
- **Command:** `aeat app ledger update 66810304 --amount 99` (an archived row)
- **Actual:** OK. `Error. only active ledger transactions can be edited; archived, stashed, and split-parent rows are immutable` with `lifecycle_state: ARCHIVED`. Matches the page.
- **Verdict:** OK.

### History — `aeat app ledger history` and `--include-split-siblings`
- **Command:** `aeat app ledger history 79df03e9`; `aeat app ledger history 23208d3b --include-split-siblings`; `aeat app ledger history 40416d1e --include-split-siblings`
- **Expected:** Each action in order with timestamp + event reference; whole split family with the flag.
- **Actual:** OK on the updated row (2 events: created, updated). The split family history lives on the **parent** (40416d1e): created, split, merged — clear and complete. However, querying the freshly-merged transaction (`23208d3b`, the `id_fusionado`) with `--include-split-siblings` returned `eventos 0` — the merge result has no history events of its own, which is surprising and undocumented.
- **Verdict:** OK / MINOR APP note. To trace a split-merge family you must know to query the parent ID, not the merged result; the page does not say which ID to use.

### Reset — `aeat app ledger reset --dry-run`
- **Command:** `aeat app ledger reset --reason "re-importing all statements" --dry-run`
- **Expected:** Preview without clearing.
- **Actual:** OK. `Filas 7 / Reiniciado False / MODO DE PRUEBA (DRY RUN) True`. (Did not run the `--yes` form to preserve the test ledger.)
- **Verdict:** OK.

## Findings

1. **[MINOR][DOC]** "Before you start" assumes an active profile and a populated ledger but never says so. With no profile, every command refuses (`No hay un perfil activo...`). And `aeat app ledger add` needs `--quiet` or it tries to launch an interactive wizard. Repro: fresh profile-less env → run any documented command. Fix: add a one-line prerequisite ("create a profile with `aeat config profile create NAME --tax-id ...` and import some transactions first") and link the quickstart.

2. **[MAJOR][BOTH]** The `split` output does not print the child IDs, yet the next section (`merge`) requires `--child-id <id1> --child-id <id2>`. The doc gives no bridge between the two. Repro: run the documented `split`, then try the documented `merge` — you have no IDs to pass. Fix: either have `split` print the child IDs, or add a sentence: "Run `aeat app ledger list` to find the new part IDs to pass to `merge`."

3. **[MAJOR][DOC]** The restore recipe says to find stashed rows with `aeat app ledger list --filter classification=NOT_YET_PROCESSED`, but that is a *classification* filter, not a *lifecycle* filter. It returns active, archived, and split rows too — not the stashed set. Repro: stash one row, archive another, run that filter → both appear (plus active rows). Fix: point at the correct lifecycle filter (or document the real flag that lists stashed rows); do not imply the classification filter isolates stashed rows.

4. **[MINOR][APP]** `stash` and `archive` print the ordinary 5-line transaction summary with no indication the lifecycle changed. The operator gets no confirmation the row was actually set aside. Fix: include the new `Estado de ciclo de vida` (STASHED/ARCHIVED) in the mutation output.

5. **[MINOR][APP/DOC]** History tracing across a split/merge family is parent-anchored: `history <parent> --include-split-siblings` shows created/split/merged, but `history <merged-result>` shows `eventos 0`. The page does not say which ID to query to follow a merged family. Fix: note that the split/merge timeline lives on the parent ID.

6. **[NIT][BOTH]** All CLI output and errors are Spanish while the doc is English (e.g. `MODO DE PRUEBA (DRY RUN)`, `Eliminado`, `id_padre`, `hijas`). An English-only reader cannot map `id_padre`/`id_fusionado`/`hijas` to the doc's "split parent"/"merged transaction"/"parts" without guessing. Fix: a small glossary mapping the Spanish output labels to the English doc terms.

## Testimonial

Following the page top-to-bottom, the core promises held up well: update genuinely minted a new ID while my old prefix kept resolving, negative amounts and edits-on-archived rows were refused with clear messages, and dry-run previews behaved exactly as described. Where I tripped was the seam between `split` and `merge` — the split gave me no child IDs, so I had to detour through `list` and guess which rows were mine before I could merge. And the restore "find your stashed rows" recipe pointed me at a classification filter that surfaced archived and active rows too, which would have had me restoring the wrong things. The app delivered the substance the page promised; the documentation just leaves a couple of real gaps (profile prerequisite, child-ID hand-off, and the wrong filter for stashing) that a true first-timer would fall into.

## Scorecard

- **Doc clarity:** 3 / 5
- **App capability:** 4 / 5
- **Findings by severity:** BLOCKER 0 · MAJOR 2 · MINOR 3 · NIT 1
