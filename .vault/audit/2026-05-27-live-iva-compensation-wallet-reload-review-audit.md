---
tags:
  - '#audit'
  - '#live-iva-compensation-wallet'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---

# `live-iva-compensation-wallet` Code Review

RELOAD-001 | HIGH | Rule application must not hide write failures as no-match
`apply_classification_rules` caught all exceptions from the transaction update path and reported them as `no_match`. Resolved 2026-05-27 by letting update, validation, and persistence failures propagate while preserving `no_match` only for transactions with no matching rule.

RELOAD-002 | HIGH | Wallet secure-storage tests must not use valid-looking taxpayer identifiers
The wallet backend test used a plausible taxpayer identifier literal as synthetic input. Resolved 2026-05-27 by replacing it with a non-identifier synthetic reference and preserving the privacy assertions that raw taxpayer references are not emitted by stored reports or secure SQL bytes.

RELOAD-003 | HIGH | Wallet privacy guard must cover implementation code and CIF-shaped identifiers
The initial static guard covered wallet-named test/source files but not the live application module that contains the wallet reload and capture functions, and it matched DNI/NIE-shaped identifiers without CIF-style entity identifiers. Resolved 2026-05-27 by scanning the live application module and extending the identifier detector to personal and legal-entity Spanish taxpayer shapes.

RELOAD-004 | HIGH | Filed-history-only fallback must not become filing-grade IVA wallet authority
The reconciliation path classified missing direct wallet/cartera plus AEAT filed-history recurrence as `filed_history_only` but left the decision non-blocking, allowing Modelo 303 calculation to prefill prior compensation from fallback evidence. Resolved 2026-05-27 by making `filed_history_only`, missing-wallet local recurrence, and stale-wallet local recurrence blocking decisions; the real Modelo 303 engine now requires an explicit taxpayer override before using the fallback amount.

RELOAD-005 | HIGH | Readiness coverage must name filed-history-only fallback, not only wallet divergence
Export and verification readiness already refused persisted blocked wallet decisions generically, but the focused readiness tests only covered direct wallet/local divergence. Resolved 2026-05-27 by adding real-behavior Modelo 303 verification and export tests proving a persisted `filed_history_only` fallback decision is surfaced as blocking readiness and no export file is emitted.

RELOAD-006 | MEDIUM | Residual executable AEAT route descriptors must be centralized
The W09 constants scan found NIF-IVA auth diagnostic endpoint descriptors and the manuals Biblioteca root path embedded in executable source rather than the external constants registry. Resolved 2026-05-27 by enrolling those values in `external_constants.toml`, routing the NIF-IVA and manual-fetch code through the typed registry, and expanding the executable literal guard to cover the touched NIF-IVA, GROI, and manual-fetch modules.

RELOAD-007 | HIGH | Modelo 303 wallet readiness tests must not carry valid-looking taxpayer identifiers
The Modelo export/readiness wallet tests and adjacent Renta family profile tests still used DNI/NIE-shaped synthetic identifiers in blocked-decision and descendant/ascendant paths. Resolved 2026-05-27 by replacing those literals with non-identifier synthetic taxpayer labels and re-running the focused Modelo 303 wallet export/readiness gate, profile roundtrip gates, and a privacy scan.

RELOAD-008 | MEDIUM | Renta registry drift can mask IVA readiness verification
The focused Modelo 303 verification gate exposed unrelated Modelo 100 registry drift while validating shared registry resources: missing LIRPF required-text grounding, stale Art. 84 source citations, undeclared Renta family profile selectors, and missing Modelo 130/131 relation inputs in the Art. 84 scenario harness. Resolved 2026-05-27 by validating the local official BOE/AEAT corpus anchors, aligning profile selectors with the central user-profile schema, classifying the year-specific descendant-minimum aggregate as financial profile data, and restoring the Renta Art. 84 scenario gate.

RELOAD-009 | HIGH | Historical tests and vault notes must not commit the operator's private identity
The privacy sweep found the operator's real NIE and name in sanitizer tests, Sede fixtures, user-profile/live-storage tests, and older vault research/audit notes. Resolved 2026-05-27 by replacing exact private markers with synthetic canaries or redacted prose, preserving valid-shape taxpayer canaries only where production redaction, committed justificante fixture comparison, or a production value-object boundary requires taxpayer-shaped input. Re-review removed a remaining surname-bearing email fixture and non-required reconciliation defaults. The source/vault scan now returns no matches for the leaked operator markers outside the local private env file.

RELOAD-010 | MEDIUM | Reconciliation gates expose separate Modelo 130 and Modelo 180 registry blockers
The focused reconciliation gate failed before exercising privacy-sensitive changes because Modelo 130 casilla 15 now requires previous-filing binding projection, and an earlier full-provider run also reported Modelo 180 construct legal-ref drift for Orden HFP/1284/2023 article 7. Resolved 2026-05-27 for the active reconciliation surface by routing registry-backed filing test helpers through an explicit `binding_values` channel, rejecting duplicate casilla/binding helper keys, removing input-only previous-filing casilla 15 fixtures, using valid synthetic profile identifiers at the draft boundary, and building reconciliation test providers from each draft's registry snapshot ref. Direct provider checks for Modelos 180, 200, 111, 123, and 130 pass in the current tree, so no active Modelo 180/200 registry drift remains in this slice.
