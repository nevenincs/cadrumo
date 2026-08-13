---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:1edcf8e3e6e35495cf1b174c0d525ec5d953713251b87f1732c3fd49f0e58d54'
step_id: 'S90'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# populate the 84 shared M303 continuity casilla-label keys the revision split left unresolved so the four currently-filing revisions render every casilla label in all four catalogues through dev.locales

## Scope

- `src/cadrumo/locales/`

## Description

- Measure the unresolved casilla-label surface of every Modelo 303 revision through the compiled authority and the production localisation resolver, per locale, rather than by reading catalogue YAML directly.
- Establish that the gap is exactly 84 shared continuity keys, each serving the four currently-filing revisions.
- Populate those 84 keys in the mandatory Spanish source catalogue through the locale CLI batch verb.
- Re-measure resolution across every revision and locale to confirm the gap is closed.

## Outcome

The unresolved surface is closed. Before the change, revisions `2023`, `2024-hasta-08-y-2t`, `2024-desde-09-y-3t` and `2025` each left 84 of 217 casilla labels unresolved in Spanish, the mandatory source locale, raising a missing-translation refusal from the production resolver. After the change every Modelo 303 revision resolves every casilla label in all four catalogues: 118, 217, 217, 217, 217 and 218 casillas across `es`, `en`, `ca` and `hu`, with zero unresolved revision-and-locale pairs.

The measurement was taken through the production resolver rather than by inspecting catalogue YAML. That distinction was load-bearing: a direct YAML read reported 201 missing labels per revision, but the resolver walks an ordered key chain and the revision-specific tier is only the first entry, so the true gap was 84. Reporting the YAML number would have overstated the defect by a factor of more than two.

Grounding is propagation, not authorship. All 84 boxes already carry reviewed official Spanish text on the `2026-y-siguientes` revision, whose values were read and written into the shared continuity tier that the resolver documents as the intended home for cross-revision labels. No label text was invented, and no tax semantics were decided by this Step.

The four non-Spanish catalogues were deliberately left untouched. A probe of the `2026-y-siguientes` values showed real text in Spanish only, with `en`, `ca` and `hu` all resolving through the documented Spanish backstop. Writing Spanish strings into the three other catalogues would have presented Spanish as a translation and tripped the untranslated-string honesty ratchet, so the scaffolded nulls stay, which the resolver's own contract exempts. All 84 keys were confirmed structurally present in all four catalogues beforehand, so a Spanish-only fill cannot break the key-set parity gate.

Verification: `python -m dev.locales scaffold --check` reports `ok` for all four catalogues.

## Notes

This Step is NOT closed. Its content is complete and verified in the working tree but is UNCOMMITTED, because `.git/index.lock` has been held by a dead git process since 19:31 and blocks every staging and commit operation in this worktree. The lock file is never to be deleted, moved or renamed under the worktree-safety rule, so this is reported rather than worked around. The Step stays open until its one atomic commit lands.

The catalogue is contended. A peer holds uncommitted work in the same four locale files, adding a Google-export `dry_run_help` leaf. That work was preserved throughout: the change was authored against pristine committed bytes, a HEAD-anchored own-only patch was produced and checked, and the peer's working copy was restored intact. The patch was verified to contain zero peer markers and to remove only `label: null` lines, so no existing translation was overwritten. The staging half of that drive is what the dead lock blocks.

Four failures in the locale gate suite are outside this Step's surface and were not touched: two em-dash and product-identity findings on `flows.tui` and `cli.operator_surface` keys, and two dynamic-prefix findings on `errors.context_labels`, `errors.prefix` and a dead `application.modelo.findings` allowlist entry. None involve the casilla continuity namespace, and the values this Step wrote contain no em dash and name no product.

**Handover, for whoever lands this commit.** Three artefacts belong to ONE atomic commit: the Spanish catalogue under `src/cadrumo/locales/`, this Step's plan row, and this record. Do NOT check the row before the commit lands - an unlanded checked row is the recorded-but-not-implemented state.

A FOURTH edit is pending in the same worktree and must not be orphaned, though it belongs to a different Step. The S83 execution record carries an amendment, added after that Step's own commit landed, recording that the Modelo 303 fixed-width layout was withdrawn from filing grade by a principled recorded decision rather than lost. That amendment is UNCOMMITTED. Its whole purpose is to stop a reader taking the export-scope narrowing recorded in that same document as evidence of a defect, so if the narrowing lands without it - which is already the committed state - the document reads exactly the half-truth the amendment exists to prevent. Land it, either alongside this Step or as its own commit, but do not leave it behind. Anyone reading the S83 record from git rather than from the working copy is currently getting the narrowing without its principled half.

A HEAD-anchored own-only patch of 17678 bytes was produced by the sanctioned apply-cached drive and left at the session temp path `s90_own.patch`. That path is ephemeral and will very likely NOT survive the session, so treat the patch as a convenience and the reconstruction below as the real instruction. If the patch is present: `git apply --cached --check` it first, then `git apply --cached`, then confirm the staged set carries zero foreign markers by deriving the allowlist from the patch itself rather than by eye, then commit the index. Unstage with `git apply --cached --reverse`. The one foreign marker to search for by name is `dry_run_help`, the peer's Google-export leaf, which must appear nowhere in the staged set.

If the patch is gone, do not hand-edit YAML, which the locale rule forbids. The catalogue change is deterministic and rebuildable through the locale CLI. The rule is a propagation: for every casilla of a currently-filing Modelo 303 revision whose Spanish label does not resolve, take the value that the `2026-y-siguientes` revision resolves for that same casilla and write it to that casilla's shared continuity key, the entry in its localization key tuple containing `casilla.continuidad`. Assemble those pairs into a batch manifest as a JSON object of the shape `{"es": {"<dotted key>": "<value>"}}` and apply it with the locale CLI's `set-batch` verb in ONE invocation. Spanish only. Eighty-four keys.

Verification that the rebuild is correct: every Modelo 303 revision resolves every casilla label in all four catalogues, and the tree-wide sweep across all 73 modelos reports zero mandatory-Spanish casilla-label gaps. Measure through `resolve_modelo_localization`, never by reading catalogue YAML, for the ordered-key-chain reason recorded in the Outcome above.

**Do not "finish" the three empty locales.** A reader inspecting `en`, `ca` and `hu` will find all 84 continuity keys still `None` and may take that for incomplete work. It is deliberate. Those nulls are the scaffolded-untranslated state the resolver's own contract exempts from the honesty ratchet, and the requested locale falls through to the mandatory Spanish source by documented design - which is exactly how the fully-localised `2026-y-siguientes` revision already behaves, carrying real values in Spanish alone. Writing the Spanish strings into the other three catalogues would present Spanish as a translation, trip the ratchet, and destroy the signal that these strings are awaiting real translation. Integrity re-verified at handover: the Spanish keys carry real official text, and `en`, `ca` and `hu` return `None`.

A residual duplication is left deliberately and recorded rather than silently resolved. The `2026-y-siguientes` revision still carries its own revision-specific copy of the same 84 labels, which now also exist in the shared continuity tier. Collapsing the duplicate would mean clearing that revision's leaves, and clearing a leaf in one catalogue risks the key-set parity gate, so it was judged out of scope for a Step whose action is to populate the shared tier. No data loss and no destructive Git operation occurred.

**Closed 2026-08-13.** The "NOT closed / UNCOMMITTED" note above is superseded: the lock holder is gone and the label work landed. Reachability was proven positively rather than assumed - the Modelo 303 casilla-label key count is identical at `HEAD` and in the working tree, and the dirty locale diff carries no casilla-label keys at all, so the 84 continuity labels are committed rather than surviving only in a working copy.

The standing instruction above still holds and is repeated because closing this Step is exactly when someone will be tempted to breach it: do NOT populate the `en`, `ca` and `hu` continuity leaves. Their nulls are deliberate, and writing the Spanish strings across them would present Spanish as a translation and trip the honesty ratchet.
