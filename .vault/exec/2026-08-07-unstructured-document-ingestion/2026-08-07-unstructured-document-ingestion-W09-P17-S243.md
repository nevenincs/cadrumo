---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:6939bec60bace14c156f7a61674cf9aff30afe722826779063f03c531e1ec598'
step_id: 'S243'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# `unstructured-document-ingestion` exec W09.P17.S243

## Scope

- `src/cadrumo/locales`

## Description

- Re-derive every reported figure from the catalogues rather than trusting the brief.
- Author the six generic application key-echoes in all four locales, taking English verbatim from each call site's in-code fallback so the catalogue and the fallback cannot disagree.
- Verify every write by re-reading the leaf, never by the exit status.
- Judge the one remaining identical-source key and record it as deliberately identical with its reason.
- Establish what the modelo block actually is, and stop rather than author regulated guidance the row did not scope.

## Outcome

**Every key-echo outside the modelo casilla help block is closed. The block itself is a different job and was rowed separately.**

**The brief's figures did not survive re-derivation, and the difference changes the work.** It reported `ca.yml` carrying 49 key-echoes with `ca` and `hu` each carrying 7 keys identical to `en` and 40 identical to `es`. Measured: key-echoes were `ca` 47, `en` 46, `es` 46, `hu` 49; `ca` and `hu` each carried 6 identical to `en`, not 7; and a seventh finding the brief did not name — `es` itself carried 7 values identical to `en`.

**The reframing is that 46 of the 50 distinct key-echoes were placeholders in ALL FOUR catalogues, English and Spanish included.** So the bulk was never an untranslated-Catalan-and-Hungarian problem: there was no source text to translate from. A key-echo in `en` and `es` means the string was never authored at all, and no amount of translation work reaches it.

**What was closed.** Six generic application keys — the five live filed pull-all notices and the no-AEAT-history overview notice — are now authored in all four locales. English was taken verbatim from each call site's own `default=` fallback rather than re-worded, so the catalogue value and the in-code fallback state the same thing. Spanish, Catalan and Hungarian were authored against the existing catalogue's own conventions rather than a chosen register: Catalan prose already uses `model`, `casella` and `exercici`, while Hungarian keeps `modelo` and `casilla` as Spanish stems alongside `bevallás` and `időszak`, and the new strings follow each. Every interpolation token was preserved exactly.

Measured effect on the axis those keys sit on: `es` identical to `en` fell from 7 to 1, and `ca` and `hu` identical to `en` fell from 6 to 0 each. The one remaining `es`-identical-to-`en` key is a judgement rather than a gap and is recorded as such below.

**The judgement the row asked for.** `docs.casilla.chrome.page_heading` renders `Modelo {modelo}: {title}` in both English and Spanish. That is deliberate: `Modelo` is the official AEAT surface name and keeps its Spanish stem in English under the domain-naming rule, so translating it would rename the form. Recorded through `allow-identical` with that reason — the sanctioned use of the allowlist for a string identical by design, not a mute button for one nobody translated.

**What is left, and why it is not what the row scoped.** Forty modelo casilla `help` keys remain, all placeholders in all four catalogues. They are the M303 and M390 intracomunitarias block — the adquisiciones intracomunitarias de bienes bases and cuotas per rate, and the M303 autorepercutido intracomunitaria base. Their siblings ARE authored, so this is a genuine gap in a series rather than a category that carries no help, and the authored siblings establish the register.

Closing them is authoring roughly one hundred and sixty strings of AEAT casilla guidance in four languages, originating the Spanish rather than translating it.

**A semantic after-pass corrected this Step's first reading of that, and the correction narrows it to one resolution rather than two.** The first reading argued from the gate: `.help` is not among the suffixes the Spanish-authority check enforces, and an absent leaf is the sanctioned unauthored state some twenty-two thousand leaves already occupy, so removal looked as honest as authoring. The gate facts are correct and the inference from them is not. The project's own new-modelo checklist states that derived casilla labels AND help text are authored in the shared catalogues through the locales CLI, with Spanish in `es.yml` as the official Casilla source. So removal contradicts the documented authoring path; what the gate declines to enforce, the convention still requires.

**The grounding objection also weakens on measurement.** Writing help from the casilla identifier alone would indeed be invention, but it does not have to be written that way: the official Diseño de Registros for M390 is bundled in this repository and is authoritative on each casilla's segment, number and label, and the already-authored sibling help strings are descriptive restatements of what a casilla holds rather than legal interpretation. That is a groundable register, not an invented one.

So the remaining work is authoring, not a choice between authoring and deletion. It is still larger than a locale pass and still not this lane's to start unasked, but it is a scoping decision rather than an open question about which resolution is legitimate.

**Eleven new key-echoes appeared in the catalogues DURING this Step** — seven passphrase keys and four TUI restart keys from another lane's live work. The tail is refilled while it is drained, which is the mechanism by which this gate stays red for everyone regardless of who works it, and it means no single lane closes this gate on its own.

That lane went on to author ten of its eleven and left one: the Spanish passphrase confirmation label, with English, Catalan and Hungarian already written. Authored here from its own siblings — `Contraseña actual`, `Nueva contraseña` — rather than a register chosen for it. With that leaf closed, **every key-echo in the four catalogues outside the modelo casilla help block is gone**, measured directly rather than inferred from the gate's summary.

## Verification

    python -m dev.locales status        (before)
    ca key_echo=47  en key_echo=46  es key_echo=46  hu key_echo=49

    python -m dev.locales status        (after)
    ca key_echo=45  en key_echo=40  es key_echo=43  hu key_echo=50

The after-figures move less than the six keys would suggest, and `hu` rises, because the peer inflow above landed between the two readings. My six are confirmed individually: a direct scan reports zero of them echoing in any of the four catalogues, and all four locales carry an authored value at HEAD.

    pytest src/cadrumo/tests/test_locale_translation_honesty.py -n0 -q
    identical-source axis: ca-vs-en and hu-vs-en gone; es-vs-en 7 -> 0 after the allowlist entry
    key-echo axis: still red on the forty modelo help keys plus the peer inflow

**Every write was verified by re-reading the leaf rather than by the exit status, and one write needed it.** Twenty-three of twenty-four landed on the first pass; `en live.filed.pull_all.recapture_divergence` returned exit 2 and left the placeholder on disk. Re-running the identical command succeeded, so it was transient contention rather than a bad argument — the same shape as the `PermissionError` on `os.replace` another lane reported, where the verb reports failure and lands nothing. A run trusting the exit status would have reported twenty-four writes and shipped twenty-three.

## Notes

The four catalogue files were committed by a sweeper mid-Step; the strings were verified present at HEAD in all four before this record was written. The allowlist entry was committed under this Step's own explicit pathspec, one file, one line.

I did not pathspec-commit the catalogues myself. When they were ready the index carried another lane's staged deletion of roughly three thousand lines, so a bare commit would have swept it, and the working copies carried a third lane's concurrently-authored locale keys, so a pathspec commit would have swept those. Since a sweeper commits the working tree wholesale here, waiting cost nothing and absorbed no one.

What the row asked for — real Catalan and Hungarian strings — is done for every key where a source existed to translate, and the one remaining gap outside the modelo block turned out to be a missing Spanish leaf rather than a missing translation. The forty-four modelo casilla help keys are authoring work rather than a locale pass, and carry their own row.
