---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-W09-P41-S208]]"
---

# cross-domain-continuity Code Review

## Commit 51c99c2da -- #175 foral-regime refusal: redirect pais_vasco/navarra to Hacienda Foral

**Verdict: APPROVE+FU**

No Critical issues. Two HIGH follow-ups required before the Lourdes F1 finding can be closed fully.

---

### Critical-question answers

**Q1 -- pais_vasco AND navarra both added to CCAA enum?**
No. Correct by design. CCAA is the common-regime-only enum (15 members). Both tokens are added to _ccaa_choice_values() as a foral extension list alongside the enum values, so Click accepts them. parse_tax_region() detects them via _FORAL_ALIASES frozenset and raises ForalRegimeError. Architecture is sound.

**Q2 -- silent Madrid default eliminated?**
No. _setup_answers.py:130 retains tax_residence_ccaa: CCAA = CCAA.MADRID. Pre-existing; not changed by this commit. The foral guard fires only when the CLI flag is explicitly supplied. A operator omitting --tax-residence-ccaa silently resolves to Madrid. Out-of-scope for F1 but a standing HIGH defect.

**Q3 -- locale message cites Ley 12/2002 and foral URLs?**
Partially. es.yml, en.yml, and ca.yml all now include Ley 12/2002 citation, Concierto Economico reference, and all four foral URLs. hu.yml was not updated -- it still carries the scaffold self-reference foral_regime: profile.errors.foral_regime. The i18n render path detects rendered == translation_key and falls back to _humanise_key(), producing "Foral regime" -- stripping the legal citation, URLs, and redirect entirely for Hungarian-locale users. G3 fails for hu.

**Q4 -- guard layered at profile create AND modelo work create?**
No. Guard is in _commands.py wizard create/edit path only. No foral check exists in _modelo.py. TaxResidenceProfile.ccaa accepts only CCAA members, so the domain model itself rejects foral tokens at construction. Defence-in-depth at the AEAT filing surface (trabajo create) is absent.

**Q5 -- AEAT-only modelo work create paths reachable with a foral profile?**
No new path opened by this commit. TaxResidenceProfile pydantic model rejects foral CCAA members at the domain layer. Risk is theoretical (directly-constructed or migrated profile) but no explicit second guard means reliance on the domain model as the sole fence.

**Q6 -- anti-tautology quality of regression tests?**
Partial. The assertion any(phrase in output for phrase in ("Concierto", "Ley 12/2002", "Hacienda Foral", "foral")) is satisfied by the "foral" branch alone, which the old pre-commit message would also have triggered. Not tautological in practice since the new message is the only one containing "Ley 12/2002" and "Concierto", but the any() construct leaves the gate structurally fragile.

---

### Findings

**FORAL-001 | HIGH | hu.yml foral_regime carries scaffold self-reference -- no legal citation on Hungarian locale**

hu.yml still has foral_regime: profile.errors.foral_regime. The render path resolves this to "Foral regime" via _humanise_key(). Hungarian-locale operators receive no Ley 12/2002 citation, no Concierto Economico reference, and no foral URLs. The commit notes hu.yml pass-through ref unchanged but provides no rationale. This violates locale parity for a safety-critical redirect (G3). Remediation: translate foral_regime in hu.yml via python -m aeat.locales scaffold (G4) and add the legal citation and foral URLs to match es/en/ca content.

**FORAL-002 | HIGH | No explicit foral guard at modelo work create -- reliance on domain model fence only**

_modelo.py has no foral-CCAA check in the trabajo create path. The only fence is TaxResidenceProfile.ccaa: CCAA field validator. A foral profile inserted via persistence layer or future migration tool would not be caught at trabajo create. The audit requirement (A foral profile should not be able to file an AEAT modelo at all) is not fully satisfied at the entrypoint boundary. Remediation: add a _guard_foral_ccaa() function called from the trabajo create command that reads the active profile CCAA and raises CliRefusedBoundaryError with the foral locale message if the raw stored token resolves to a foral alias.

**FORAL-003 | MEDIUM | Test assertion uses any() across weak and strong branches -- partial anti-tautology**

Both pais_vasco and navarra regression tests assert any(phrase in output for phrase in ("Concierto", "Ley 12/2002", "Hacienda Foral", "foral")). The "foral" branch was already satisfied by the old pre-commit message. Remediation: replace any(...) with assert "Ley 12/2002" in output and for navarra also assert "hacienda.navarra.es" in output to pin the legal citation specifically.

**FORAL-004 | LOW | Silent Madrid default at _setup_answers.py:130 pre-dates this commit but remains unfixed**

tax_residence_ccaa: CCAA = CCAA.MADRID silently assigns Madrid when --tax-residence-ccaa is omitted. Pre-existing, out-of-scope for F1. A follow-up should make the field prompt-required. Tracked here for audit continuity.

---

### Gate sweep

- **G1 no naked env reads:** Pass. No os.environ or os.getenv in changed files.
- **G2 typed pydantic at boundaries:** Pass. pais_vasco/navarra enter only as CLI-layer strings immediately validated by parse_tax_region() before any pydantic model is constructed. TaxResidenceProfile.ccaa: CCAA typed field is unchanged.
- **G3 tr() for user messages:** Pass for es/en/ca. Fail for hu (FORAL-001).
- **G4 no locale yml hand-edits:** Unverifiable from diff alone; hu.yml unchanged state suggests scaffold was not run for hu.
- **G5 no shims/re-exports/duplication:** Pass. Foral list in _ccaa_choice_values() is a clean additive extension. _FORAL_ALIASES frozenset is the single canonical foral-detection surface.
- **G6 no tautological tests:** Partial (FORAL-003). The any() construct weakens the assertion but is not fully tautological in practice.
