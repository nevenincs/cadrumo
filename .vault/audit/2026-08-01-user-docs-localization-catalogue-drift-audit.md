---
tags:
  - '#audit'
  - '#user-docs-localization'
date: '2026-08-01'
modified: '2026-08-01'
body_schema: 'body-v1'
body_hash: 'sha256:a1c8bc7b493b5bae9adb0c818ef3e2ca2350a00f1b5800529a15992aa59f83eb'
related:
  - "[[2026-07-18-user-docs-localization-adr]]"
  - "[[2026-08-01-user-docs-search-consolidation-adr]]"
---

# `user-docs-localization` audit: `translation catalogues were complete against stale source: the masked drift, the tracked backlog, and the gate lesson`

## Scope

Records the 2026-08-01 operator ruling on the documentation translation catalogues, the measured drift state a resync surfaced, the named human-translation backlog that ruling commits the project to track, and the gate-design finding behind the masking. Authored by the architecture-remediation ruling agent; the per-page numbers below were independently recomputed from the committed `docs/locales/es/LC_MESSAGES` catalogues with babel and match the catalogue agent's report exactly. The three languages (es, ca, hu) are identical in shape; es figures stand for all three.

## Findings

### completeness-was-measured-against-the-catalogue-not-the-source | high | the gate stayed green while readers were served confident translations of rewritten English

Before the resync every catalogue reported 3062 of 3062 translated, zero fuzzy, zero untranslated - 100 percent complete - while the English source had been rewritten under it since 2026-07-25: genuine drift across 22 of 58 pages. The completeness gate measured the catalogue against ITSELF (every msgid carries a msgstr) rather than against CURRENT source, so completeness and correctness diverged invisibly and the live site kept serving confidently wrong translations of text that no longer existed. Verified against a pre-change backup: the resync SURFACED drift, it did not introduce it, and zero translations were lost (3022 translated + 40 fuzzy retaining their text verbatim = exactly the prior 3062).

The gate-design lesson, recorded as this audit's durable finding: **a completeness gate must observe the surface that matters, not the artefact's self-consistency.** This is the third instance of the same false-green shape found on 2026-08-01 alone, after the three blind localization/deployment gates recorded in the `2026-08-01-user-docs-search-consolidation-adr` Update 3 addendum (injector-decision-level assertions, English-only fixtures, non-emptiness checks) and the pages-mode deployment env. In every instance the observed surface was a proxy the defect did not pass through. The localization gate `test_docs_localization.py` now measures against current source and is honestly red - which is the fix working.

### the-tracked-backlog | high | 101 strings per language need human translation; 303 total; agents must not invent them

Post-resync state per language (es shown; ca and hu identical): 3123 total, 3022 translated, 40 fuzzy, 61 untranslated. The operator ruled: PUBLISH NOW with honest English fallback, TRACK the 303 - fallback is strictly better than confidently wrong translations of rewritten source. The 6 red `test_docs_localization.py` failures (3 untranslated-delta, 3 punctuation-stale `download.md` entries) are the backlog's enforcement teeth: the gate stays red until the strings are humanly translated, so this backlog cannot silently rot.

**Agents MUST NOT invent these translations.** A fabricated Catalan or Hungarian string is a defect shipped to users in a language none of the project's agents can verify; the honesty disciplines of the locale catalogues apply with full force. The backlog is HUMAN translation work. The one exception: the five `download.md` entries per language are a mechanical punctuation alignment (the English changed an em-dash to a colon; the retained translations carry the old punctuation) and are trivially clearable without translation judgement.

Per-page backlog (fuzzy + untranslated, es; identical across languages), so a translator can pick pages up in impact order:

- `how-to/censo-update` - 26 (2 fuzzy, 24 untranslated)
- `how-to/profile-setup` - 21 (2 fuzzy, 19 untranslated)
- `reference/environment-overrides` - 11 (6 fuzzy, 5 untranslated)
- `how-to/irpf-lifecycle` - 6 (4 fuzzy, 2 untranslated)
- `download` - 5 (5 fuzzy: the mechanical punctuation set)
- `how-to/iva-lifecycle` - 5 (1 fuzzy, 4 untranslated)
- `how-to/modelo-130` - 3; `how-to/quickstart` - 3
- 2 each: `explanation/how-renta-is-assembled`, `how-to/index`, `how-to/ledger-evidence` (1+1), `how-to/modelo-390`, `how-to/protect-data-access` (1+1), `how-to/review-calculation-values`, `how-to/verification-reports`
- 1 each: `how-to/classify-transactions`, `how-to/classify-with-llm`, `how-to/filing-spine`, `how-to/first-quarterly-filing`, `how-to/modelo-100`, `how-to/modelo-349`, `how-to/prorrata`

Ownership: the `user-docs-localization` feature line and its catalogue tooling (`dev/docs/i18n.py`, the `.po` catalogues under `docs/locales/`); the work routes through the gettext catalogues, never hand-invented prose. The publish-evidence annotation requirement for the interim red gate is ruled in `2026-08-01-user-docs-search-consolidation-adr` Update 5.

## Recommendations

- Translate in the impact order above; clear the five mechanical `download.md` punctuation entries per language first (no translation judgement needed).
- Keep `test_docs_localization.py` measuring against current source; never restore a catalogue-self-consistency check as the completeness signal.
- When the next gate of this family is authored, apply the observed-surface lesson: assert against the artefact or source the defect actually passes through, per the Update 3 addendum's gate contract pattern.
