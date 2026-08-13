---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:c042e9b6f5bddb7b2d6a166a161874e726a4477b7f031c60782d009311efead2'
step_id: 'S66'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# Bundle and adjudicate the official DANA primary authorities required by S65 by acquiring RDL 6/2024 article 1 and its mutable municipal annex, RDL 7/2024 article 11.2 and final provision 14, and the BOE-A-2024-24097 correction provenance, pinning exact official bytes and hashes, authoring canonical legal/source references for the affected geography and the 25 percent 2024 annual simplified-regime IVA reduction, and refusing timeless geography, inferred applicability, missing correction provenance, or invented identifiers

## Scope

- `src/cadrumo/_data/corpus/`
- `src/cadrumo/_data/registry/aeat/legal/`
- `src/cadrumo/_data/registry/aeat/sources/`
- `dev/registry/tests/`

## Description

- Confirm the three BOE identifiers against the official daily-summary open-data API before writing any of them down: RDL 6/2024 is `BOE-A-2024-22928` (published 2024-11-06), RDL 7/2024 is `BOE-A-2024-23422` (2024-11-12), and the correccion de errores is `BOE-A-2024-24097` (2024-11-20).
- Discover that both consolidated norms were ALREADY bundled under `real-decreto-ley-6-2024.html` and `real-decreto-ley-7-2024.html`; delete the freshly fetched duplicates and cite the shipped artefacts instead.
- Generate the missing extraction sidecars for RDL 6/2024, which shipped with none and was therefore uncitable, and regenerate RDL 7/2024's, which was stale against its own bytes.
- Add the as-published acquisition shape to the BOE acquirer for instruments BOE never consolidates, and acquire the correccion de errores through it.
- Canonicalise CRLF to LF in every acquirer writer, so a pinned digest identifies the document rather than one fetch of it.
- Author a dedicated legal catalogue file carrying three pinned sources, five legal references and the 25 per cent parameter, kept out of the hot shared IVA catalogue.
- Repoint the pre-existing IRPF estimacion objetiva citation at the complete consolidated article and retire the truncated hand-sliced excerpt behind it.
- Add a refusal gate covering timeless geography, inferred applicability, missing correction provenance and invented identifiers, and prove each refusal reds by breaking the authority from outside the repository.

## Outcome

The 25 per cent reduction of the 2024 annual regimen simplificado cuota devengada por operaciones corrientes is grounded on official BOE bytes, and the three artefacts are pinned by digest and byte count.

The geography is never a list. RDL 7/2024 art. 11.2 defers to the RDL 6/2024 anexo rather than enumerating municipalities, and that anexo is expressly amendable by Acuerdo de Consejo de Ministros under art. 1.4, so the catalogue answers "which municipalities" only as a citation to consolidated bytes carrying a consolidation date. A sweep of BOE daily summaries from 2024-11-06 to 2025-04-30 found no publication amending the anexo, and the consolidated text carries no amendment note, so the 78-entry list is current as of the recorded consolidation date; that is an observation about the bytes, not a guarantee, which is exactly why the date is recorded.

Applicability is read off disposicion final decimocuarta, which states the norm takes effect the day after publication. The gate derives the date from that provision's own publication date and refuses a reduction whose start date does not equal it, so nobody can date the measure by judgement.

Correction provenance survives at two levels: the correccion de errores ships as its own artefact with its digest pinned, and the corrected article's own consolidation note naming that document is a required phrase, so a corpus that lost the correction cannot satisfy the citation.

Every identifier resolves. The gate checks the BOE identifier grammar, that the permalink is HTTPS on the official host and names the same identifier, that the cited artefact exists, and that the artefact itself declares the identifier claimed for it rather than merely being asserted to.

Two defects in the surrounding corpus were absorbed. RDL 6/2024 had shipped with no extraction sidecars at all, so no legal reference could resolve against it. And the hand-sliced article excerpt the IRPF citation used was truncated one sentence early, dropping precisely the sentence that scopes the reduction to the ANNUAL cuota rather than to each quarter; its consumer now reads the complete article, its three required phrases having been verified against the new block first.

The acquirer gained a third shape. A correccion de errores has no consolidated view, so the consolidated fetcher refuses it correctly. Measured against live BOE, the single-document view of a norm that IS consolidated is shape-identical to one that is not, so no payload check can tell them apart and the guard is a second request that asks whether consolidated text exists. That measurement also retired a payload-level clause that looked defensive but could never fire.

## Notes

Every refusal was proven to bite by mutating the authority from a scratch directory outside the repository, never by editing a tracked file. Timeless geography reds on a missing consolidation date and on an unbounded pinning source; hand-dating the reduction reds against the final provision; a deleted correction artefact and a wrong pinned byte count both red; a fabricated identifier reds against the bundled document that never declares it; and deleting any of the three entries from the catalogue reds in the loader with the missing id named. The unmodified authority stays green throughout.

An incident: a concurrent bare commit by another agent swept this step's three staged excerpt deletions into an unrelated vault-documentation commit before this work was ready to land. The tree state is correct and nothing was lost, but the deletion's provenance now sits under a message that does not describe it, and between that commit and this one the tree briefly held a citation pointing at a deleted artefact. The commit here completes and explains the removal. The root cause is local: staging a deletion early and continuing to work widened the exposure window.

One repository-wide gate remains red and is not owned by this step. Roughly ninety committed normative sidecars differ from current extractor output in their `preprocessor_version` stamp alone, 1.1 against 1.3, with identical extracted units. It is a corpus-wide re-stamp belonging to the legal-corpus vintage campaign; re-stamping it here would sweep several campaigns' evidence artefacts through a grounding commit. The three artefacts this step touched all carry the current stamp.

Also outside this surface and left to their owners: a collection error from a symbol mid-move in the CLI overview rendering module, and three Modelo 100 failures traced to uncommitted peer edits in that modelo's registry constructs.

The catalogue entries are stamped as agent-prepared and pending operator review, following the precedent already set for the RDL 4/2024 IVA entry. The legal catalogue is a filing-grade, human-reviewed surface, and none of these entries has been read by a human reviewer.

One acquisition hazard worth carrying forward: a re-fetch of the same BOE consolidated document does not reproduce its digest, because the page embeds a per-response cache-busting nonce in a script tag. Two fetches minutes apart differ by three digits and nothing else. A drift investigation must diff the bytes rather than conclude from an unequal hash that the law changed.
