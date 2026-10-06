---
tags:
  - '#research'
  - '#user-docs-weight'
date: '2026-10-06'
modified: '2026-10-06'
body_schema: 'body-v2'
body_hash: 'sha256:a82d83cbf6121690526b992f620cdc5318f6a312377ecbe306a3be5c159671ff'
related:
  - "[[2026-07-18-user-docs-localization-adr]]"
  - "[[2026-07-13-docs-cli-sequences-adr]]"
  - "[[2026-09-24-docs-build-performance-adr]]"
  - "[[2026-07-15-docs-terminology-search-adr]]"
---

# `user-docs-weight` research: `where the bundled user documentation's weight comes from and what removes it`

The Windows package 0.5.1 b2115 carried 432 MB of user documentation in 62,771 files, a complete tree per language. The question was which of that weight is accident, which is decided, and what would remove it. Measured on 2026-10-06 on a snapshot of the working tree (commit `af1fb06015`), one English desktop root was 109.0 MB in 15,702 shippable files. The changes made the same day inside existing decisions bring it to 93.8 MB (Spanish 111.3 MB to 95.8 MB). The rest is content the accepted decisions require on every page or in every language, plus recorded command output. Four further options would each remove more than everything removed so far; each needs a decision or work outside the documentation tooling.

## Findings

### Every language tree is translated, so whole pages cannot be shared between languages

No page body is identical between the English and Spanish roots in any area. The share of English text segments that reappear verbatim in Spanish is 36% in `technical`, 57% in `_generated/casillas`, 61% in `_generated/legal`, 96% in `how-to` and 98% in `explanation`. The two high figures are recorded command output, which stays English by decision (`2026-07-18-user-docs-localization-adr`, Constraints). Byte-identical files across the four trees are static assets only, about 4 MB per language (`mermaid.min.js` is 2.7 MB of it). Shipping one copy of language-neutral pages is therefore not available; the repetition is inside the pages.

### What was removed on 2026-10-06 without changing a decision

English desktop root, before and after, in MB:

| Area | Before | After | Cause removed |
| --- | --- | --- | --- |
| `_generated/legal` (185 pages) | 14.0 | 8.6 | each page's sidebar listed the 184 other documents (`dev/docs/navigation.py:65`); theme variables in every head |
| `_generated/casillas` (59 pages) | 35.0 | 32.0 | a class attribute on each of about 79,900 legal links and 13,133 index chips (`dev/docs/casilla_legal_grounding.py:162`) |
| `technical` (232 pages) | 16.2 | 14.1 | 6 KB of theme variables and 2.3 KB of chrome strings inline in every head (`dev/docs/shared_page_assets.py:1`) |
| root files | 2.1 | 0.0 | Sphinx's own `searchindex.js`, which no page reads (`docs/conf.py:1732`) |
| `_static` | 5.8 | 4.1 | the landing image copied to both `_static` and `_images` |
| all other pages | 17.1 | 16.3 | the same head blocks; Open Graph tags in the desktop flavor |
| images and downloads | 2.6 | 2.6 | |
| Pagefind index | 16.3 | 16.1 | recorded JSON envelopes indexed as page text (`docs/pagefind.yml:26`) |
| Total | 109.0 | 93.8 | |

A deflate estimate of the shippable files falls from 30.5 MB to 26.6 MB. The build no longer writes the 39 MB `_sources` copy of every page into each root (`docs/conf.py:415`). The package staging scan accepts the result with no refused reference and the same five inline-script hashes.

### Casilla pages are 32 MB per language because every card renders its full provenance

The 59 modelo pages hold 13,133 cards. Their legal-basis blocks are 12.3 MB, of which the links are 8.6 MB, and their registry-identifier disclosures are 7.3 MB. D6 of `2026-07-15-docs-terminology-search-adr` requires each entry to render the record's `legal_refs`, `source_refs`, `segmento` and `source_revisions`, and `dev/docs/tests/test_casilla_anchor_parity.py:102` gates it per entry. 6.2 MB of the link markup repeats references that every card of the same section shares; on Modelo 200 about 2,900 of 3,731 cards cite article 19 of Ley 27/2014, and a sampled card cites 17 articles of that law. Whether those are per-casilla grounding or a section-level basis copied onto each casilla in the registry was not investigated.

### Recorded JSON envelopes are 8 MB per language, and 21 frames hold most of it

297 `<pre>` blocks hold JSON command envelopes, 8.1 MB with markup in each language. 21 recorded frames exceed the 64 KiB advisory (`dev/docs/sequences/checks.py:91`) and hold 5.9 MB of golden text; four of them hold 3.8 MB (`renta-assembly-requires` frame 0, `review-values-relation` frame 3, `modelo-100-renta-2025` frame 2, `modelo-100-inspect-inputs` frame 5, each about 0.9 to 1.0 MB). A3 of the output weight amendment in `2026-07-13-docs-cli-sequences-adr` already says a reader-facing frame prints text unless a capture, an expectation or the page's teaching needs JSON; A4 makes the limit an advisory, and the same amendment rejects truncating displayed output. These frames were left untouched: `dev/docs/sequences/` had another session's uncommitted edits, and a refresh needs a tree where the product runs.

### The search index repeats every casilla record in every language

A root's Pagefind index is 16 MB in about 15,100 files. 13,133 fragments (6.5 MB) are casilla records, 502 are pages (2.9 MB), 830 legal provisions and 323 CLI commands. A casilla record's content is its title, aliases and all four languages' descriptions (`dev/docs/pagefind_inject.py:360`), so the four language indexes carry the same text four times: about 52,500 of the package's documentation files. Per-language indexes and the cross-language content follow D4 and D5 of the terminology-search decisions.

### The package stores four uncompressed trees, and text is most of it

`dev/packaging/native/docs_build.py:93` builds one root per declared language and `dev/packaging/native/docs_stage.py:475` copies each whole. The files are stored as built; deflate reduces the English root from 93.8 MB to about 27 MB, and the package ZIP holds the 432 MB tree in 123 MB. The `cadrumo-docs` scheme handler is about 500 lines and serves files by manifest path (`native/desktop/src-tauri/src/docs/site.rs:47`). The manifest itself is 7.2 MB of indented JSON, one digest per file (`dev/packaging/native/docs_stage.py:548`).

### Options not yet taken, by size

- Store the documentation compressed and inflate in the scheme handler: about 375 MB to about 110 MB on disk with no content change. A single archive per language would also cut about 62,000 files to four. Changes the package contract (`native/CONTRACT.md`), the handler and the staging manifest. Not prototyped; WebView behaviour with a pre-compressed body was not tested, so the estimate assumes the handler inflates.
- Ship the selected language plus English, or make languages separately installable: the tree count falls from four to two or one. The language set is `user_docs.languages` in `native/package-layout.json`; the localization decision governs the site, not the package.
- State a section's shared legal basis once and keep per-card references that differ: about 6 MB per language. Amends D6 of `2026-07-15-docs-terminology-search-adr` and its per-entry gates, or is resolved in the registry if the shared references are an authoring shortcut.
- Re-author the 21 over-limit frames as text or narrower commands, and make the limit a refusal: up to 6 MB per language. A3 already covers the authoring; refusal amends A4.
- Index a casilla record once for all languages, or with the build language and Spanish only: up to 6.5 MB and 13,000 files for each language after the first. Amends D4 and D5 of the terminology-search decisions and changes what a query in another language finds.
- Share byte-identical static assets across language roots: about 12 MB. Needs a content-addressed manifest or a handler fallback.

Rejected on the evidence: sharing page bodies between languages (none is identical), and rendering casilla data in the browser from one data file, which the no-JavaScript constraint in `2026-09-24-docs-build-performance-adr` excludes for the shared source.

The evidence favours compressed storage and the frame re-authoring first: the first removes more than all other options together and touches no content, the second is already decided and only unexecuted. Two questions belong to the owner: whether the casilla reference may state shared grounding once per section, and whether a package must carry all four languages at install.

## Sources

- `dev/docs/navigation.py:65`
- `dev/docs/shared_page_assets.py:1`
- `dev/docs/casilla_legal_grounding.py:162`
- `dev/docs/casilla_card_rendering.py:161`
- `dev/docs/tests/test_casilla_anchor_parity.py:102`
- `dev/docs/sequences/checks.py:91`
- `dev/docs/pagefind_inject.py:360`
- `docs/pagefind.yml:26`
- `docs/conf.py:415`
- `docs/conf.py:1732`
- `dev/packaging/native/docs_build.py:93`
- `dev/packaging/native/docs_stage.py:475`
- `dev/packaging/native/docs_stage.py:548`
- `native/desktop/src-tauri/src/docs/site.rs:47`
- `native/package-layout.json` (`user_docs.languages`)
- `native/CONTRACT.md`
- Measurements: English and Spanish desktop roots built from commit `af1fb06015` with and without the 2026-10-06 changes, compared file by file over the media types the package serves. The scripts and roots were session scratch and are not retained; the same roots are produced by `python -m dev.docs.build --language <code> --flavor desktop --isolated-source --out-dir <dir>`.
