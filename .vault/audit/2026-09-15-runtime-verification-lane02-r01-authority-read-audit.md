---
tags:
  - '#audit'
  - '#runtime-verification'
date: '2026-09-15'
modified: '2026-09-15'
body_schema: 'body-v2'
body_hash: 'sha256:00a6ab5616be5dc5aac79baf2bf69b1fba466b1236567e0f2796d54333648b56'
related:
  - "[[2026-09-15-runtime-verification-lane01-r01-cli-reachability-audit]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace runtime-verification with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `runtime-verification` audit: `lane02-r01 published authority read`

## Scope

Objective: prove that the current runtime reads one typed modelo directory from its published authority and identify the exact generation consumed. Session `lane02-r01-authority-read`, probe `L02-R01-P01`, run once with no repeat.

Checkout: branch `main`, HEAD `c36b855520f7664f57d3d5517097ab6cccefbfb9`. The worktree was dirty (110 porcelain entries from concurrent contributors), so the observation covers the working tree and not a clean commit.

Observation window (UTC): 2026-09-15T14:38:03.935Z to 2026-09-15T14:38:14.812Z.

Command: a standalone Python script piped to `uv run --no-sync python -` from the worktree root. It read the selector via `bundled_authority_descriptor_path()` and `AuthorityDescriptor.read`, opened `bundled_indexed_authority()`, took an `operation()` pin, and decoded `modelo_directory` for the lexicographically first id from `modelo_ids()`. It then compared `pin.logical_generation` with the descriptor and re-read the selector bytes. The script text is recorded in the lane02-r01 briefing.

Exit code: 0. No stderr.

Emitted JSON:

```json
{"database": "authority-06f66544cb3f04ed5bbdd2b7ec4d33622b057fab82ee687432786dfc5cbfa2dd.sqlite3", "database_sha256": "06f66544cb3f04ed5bbdd2b7ec4d33622b057fab82ee687432786dfc5cbfa2dd", "decoded_type": "ModeloRevisionDirectory", "descriptor_path": "Y:\\code\\cadrumo-worktrees\\main\\src\\cadrumo\\_data\\registry\\authority\\authority.current.json", "descriptor_sha256": "f7c4e2c26828a9bc6a980713598673cda889cc8e5ccac5db17c2d9e99231d118", "logical_generation": "2bdbfabc832b91e9ec77345b342abc08a7416e6e84f6ceb4aa85f79af8222c66", "reader_incarnation": "17ad67e00860a4f63cd4b58c0de718583349dfc34edfed76f48ddbc0026951d8", "selected_modelo": "036", "selector_stable": true}
```

Final signal: PROVEN.

## Findings

### l02-r01-f01 | low | Runtime reads a typed modelo directory at the selected generation

Observed: the probe exited 0. The published authority returned modelo identities, and modelo `036` decoded as `ModeloRevisionDirectory`. The operation pin's logical generation `2bdbfabc…2c66` equals the one declared by `authority.current.json` (sha256 `f7c4e2c2…d118`), which selects the SQLite artifact `authority-06f66544…a2dd.sqlite3`. The selector bytes were identical before and after the read. This is a confirming finding, not a defect.

Not observed: the script did not independently hash the SQLite file. `database_sha256` is the descriptor's declared value, and its match with the filename is by naming only.

### l02-r01-f02 | low | Reader incarnation and logical generation are distinct, but incarnation lifetime is unproven

Observed: `reader_incarnation` (`17ad67e0…51d8`) and `logical_generation` are different 64-hex values, so they are separate identifiers. Unproven: whether the incarnation changes per process or per reader while the generation stays fixed. One run cannot show this.

## Recommendations

Next evidence question (from l02-r01-f01): does one registry binding resolve against generation `2bdbfabc…2c66` to a target that was stated independently before the run?

This lane does not establish binding correctness, cross-revision or temporal selection, calculation correctness, source freshness against authored registry TOML, the integrity of the SQLite bytes against `database_sha256`, or adoption by a built package (the read came from the editable worktree's `src/cadrumo/_data`). l02-r01-f02 is low value and needs no dedicated probe unless a later lane depends on reader identity.
