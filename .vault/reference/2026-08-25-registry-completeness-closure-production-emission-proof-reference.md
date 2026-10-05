---
tags:
  - '#reference'
  - '#registry-completeness-closure'
date: '2026-08-25'
modified: '2026-10-03'
body_schema: 'body-v1'
body_hash: 'sha256:7e46f5f45e803fdc28bd0dcc61b1ef43f4fd3bf86b59af90c378aecb1eb5330f'
related:
  - "[[2026-08-24-registry-completeness-closure-adr]]"
---

# `registry-completeness-closure` reference: `production emission proof evidence boundary`

The canonical filing-export proof chain is structurally complete, but the repository does not contain authoritative filing-instance inputs from which a successful production-emission claim can be made. This audit followed the law-selected registry snapshot through generator verification, `export_draft`, and emitted-byte acceptance, and compared every apparent positive fixture with the source-ownership requirements.

## Summary

The filing denominator contains 66 filing-grade revisions. Twenty-five revisions have a canonical `_generation.provenance.json` manifest and at least one positioned literal in the first required non-repeating record, so their generator inputs and candidate official byte positions are structurally verifiable. The remaining 41 revisions, including Modelo 130, cannot pass canonical generation verification because no generated provenance manifest exists.

No revision has a repository-owned production `ModeloDraft` and `FilingProducerSnapshot` together with independently accepted payload digest and extent. Therefore zero of the 66 revisions can honestly be enrolled in `CANONICAL_LIVE_FILING_EXPORT_PROOF_ENTRIES`.

The empty canonical entry tuple is consequently an honest refusal, not missing implementation plumbing.

Resolving all cited producer keys through the shared snapshot proves only that a runtime resolver exists; it does not provide authoritative taxpayer values for a proof case.

That secure, operator-specific state cannot be turned into deterministic source-tree release evidence, and sensitive taxpayer or financial values cannot be persisted as a new plaintext proof fixture.

The apparent positive fixtures are not authority. The Modelo 151 closure test invents NIFs, names, refund-account data, casilla values, product identity, digest, and extent. Modelo 111 and 200 live-proof tests deliberately use invented or zero hashes to prove refusal. The shared filing export fixtures use synthetic taxpayer and calculation values. The Modelo 130 golden scenario explicitly declares no numeric worked-example oracle, and its historical export fixture was likewise synthetic. These tests demonstrate mechanism or failure behavior; none authorizes canonical success.

The current authorable boundary is therefore: derive the full filing-grade denominator and law-selection coordinates; verify loaded layout and source identity for all revisions; verify generator provenance and derive distinct literal-probe candidates for the 25 ready revisions; retain explicit refusal for everything without production filing-instance evidence. It is not authorable to derive draft values from schema defaults or allowed values, to choose zeros as a supposedly neutral filing, to derive the expected digest or extent from the payload under test, or to treat dynamically selected literal offsets as independent acceptance of taxpayer-bearing output.

Full production-emission enrollment requires new accepted authority above the current implementation: either provenance-stamped, non-sensitive official specimen filing inputs with independently accepted output bytes for each revision, or an ADR amendment that separates value-independent renderer conformance from operator-specific production replay and changes the release predicate accordingly. The accepted registry-completeness ADR currently requires successful emitted-byte proof, so the second option cannot be substituted silently. S33 must remain open.
