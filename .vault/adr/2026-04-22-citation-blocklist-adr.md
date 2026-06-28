---
tags:
  - "#adr"
  - "#real-pdf-import"
date: 2026-04-22
modified: '2026-04-22'
related:
  - "[[2026-04-22-ruleset-architecture-adr]]"
  - "[[2026-04-22-real-pdf-import-wave-64-exhaustive-audit]]"
  - "[[2026-04-22-real-pdf-import-wave-66-exhaustive-audit]]"
  - "[[2026-04-22-real-pdf-import-wave-68-exhaustive-audit]]"
  - "[[2026-04-21-real-pdf-import-umbrella-research]]"
---
# citation-blocklist-adr

## status

Accepted — 2026-04-22. Ships in wave 69 of EPIC #305 as
`src/aeat/domain/modelos/_citation_registry.py` + a `LegalCitation` model
validator.

## context

Six consecutive audit waves (59c, 61a, 63a, 65a, 67a, 68 stream 3)
surfaced Spanish-tax citation errors where a `(source, article)`
pair was attributed the wrong role. Examples:

- LIRPF art. **103** cited for "cuota diferencial" — art. 103 is
  actually "Liquidaciones provisionales" (AEAT administrative
  power). Correct source: art. 79 (cuota diferencial) + art. 99
  (pagos a cuenta).
- LIRPF art. **67** cited for "cuota íntegra estatal" — art. 67 is
  "Cuota líquida estatal" (post-deduction). Correct: art. 62.
- LIRPF art. **77** cited for "cuota íntegra autonómica" — art. 77
  is "Cuota líquida autonómica total". Correct: art. 73 / 74.
- LIRPF art. **79** cited for "cuota líquida total" — art. 79 is
  "Cuota diferencial". Cuota líquida total splits across arts. 67
  (estatal) + 77 (autonómica).
- LIS art. **125** cited for "cuota líquida" arithmetic — art. 125
  is procedural ("Autoliquidación e ingreso"). Correct: art. 30.
- RIRPF art. **100.3.a** cited for "19% arrendamientos urbanos" —
  art. 100 has no sub-letter structure in the BOE consolidated
  text. Correct: art. 100.1.
- RIRPF art. **100.3.c** cited for "ganancias patrimoniales" —
  same issue, no sub-letters.
- RIRPF art. **105.1** cited for "premios en metálico" — art. 105
  covers IIC transmisiones. Correct: LIRPF 101.7 via RIRPF 99.
- RIRPF art. **110.2** cited for "2% agrarias" — art. 110.2 is the
  60% Ceuta/Melilla reduction (or the analogous reduction clause).
  Correct: art. 110.1.c.
- RIRPF art. **110.4** cited for "2% módulos" — art. 110.4 is the
  minoración clause. Correct: art. 110.1.b.

Each miscite shipped through code review because the surrounding
`quoted_text_es` was internally self-consistent with the wrong
article number; review caught the error only on a later external
verification pass (WebSearch against BOE / iberley / supercontable).

Wave 65c introduced a 6-point author checklist (ADR §External-
anchoring convention) requiring WebSearch verification before
landing any new citation. Waves 65a, 67a, and 68 still surfaced
new citation errors afterwards — a process-only rule does not
prevent what the author didn't think to double-check.

## decision

### 1. Known-bad blocklist (this ADR)

Ship `src/aeat/domain/modelos/_citation_registry.py` with a frozen
`_KNOWN_BAD_CITATIONS` tuple of `(source, article, role_substring)`
triples. Every triple corresponds to a documented prior miscite.
`LegalCitation`'s model validator refuses construction when the
triple matches, with an error message naming the closing wave +
correct article.

The `role_substring` match is narrow enough (case-folded substring
of `quoted_text_es`) that legitimate historical references (e.g. a
citation that quotes the prior miscite as a correction note) don't
false-positive — the author just adapts the `quoted_text_es` to
avoid echoing the wrong role verbatim.

### 2. NOT implemented this wave: positive registry

The wave-68 stream-3 recommendation included a complementary
`CITATION_TITLES: dict[(source, article), str]` positive registry
that would require EVERY citation to resolve to a known BOE plain-
text title. Deferred to a future wave because:

- Populating it requires pinning a title for every existing
  citation, which is itself subject to the same error mode we're
  trying to prevent. A well-intended backfill could entrench new
  errors.
- The blocklist closes the specific known failure modes; the
  positive registry is a larger step-change in the contract.

If a seventh miscite pattern surfaces in a wave >= 70, revisit
this decision and ship the positive registry with a carefully-
WebSearch-verified backfill.

### 3. Extension contract

When a future audit surfaces a new citation error:

1. Land the citation fix in the affected ruleset + test files.
2. Add a new `KnownBadCitation(...)` tuple entry to
   `_KNOWN_BAD_CITATIONS` in the same commit.
3. Add the test coverage that would have caught the miscite, in
   `test_citation_registry.py`.
4. Reference the audit wave that surfaced it via the
   `audit_wave` field for provenance.

## implications

### Short-term (wave 69+)

- `LegalCitation` construction fails on the 10 currently-blocklisted
  miscites. None of them ship in the current codebase (wave 67g
  closed the last of them), so the rule is enforcement-only.
- A future author who introduces a NEW citation that happens to
  echo one of the known-bad role phrases will fail at import time
  with a pointer to the correct article.

### Long-term

- If the positive-registry option is later adopted, this blocklist
  stays as a defence-in-depth: positive registry catches unknown-
  pair miscites (wrong article for role); blocklist catches
  specifically-known-wrong pairs (defence for corrected miscites).

### Non-goals

- Stopping every possible citation error. An author who cites a
  never-before-flagged wrong `(source, article)` pair with a
  non-matching role phrase will still ship the error. Catching
  those requires the positive-registry option.
- Machine-readable Spanish-tax knowledge base. This is a
  defensive string-match blocklist, not a semantic model of BOE.

## alternatives considered

- **Process-only author checklist** (wave 65c bullets). Rejected as
  standalone: waves 65a, 67a, 68 shipped new citation errors
  despite the checklist existing. Kept as complement to the
  blocklist — the checklist is a pre-flight; the blocklist is a
  post-flight.
- **Docstring grep CI gate** (wave 68 stream 3 option C). Rejected:
  an author who miscites the number will also miscite the title,
  so a string-match on docstrings is circular.
- **Positive `(source, article) → title` registry** (wave 68 stream 3
  option B). Deferred as §2 above.
- **Per-wave exec-record catch-up** (tracked separately under issue
  #313). Orthogonal — exec records are an audit-trail artefact,
  not a citation-correctness mechanism.

## references

- `src/aeat/domain/modelos/_citation_registry.py` — blocklist
- `src/aeat/domain/modelos/_citations.py` — `LegalCitation` validator
- `src/aeat/domain/modelos/test_citation_registry.py` — coverage
- Wave 64, 66, 68 audit docs — surfacing miscites
- `[[2026-04-22-ruleset-architecture-adr]]` §External-anchoring
  convention — the author checklist that complements this blocklist
