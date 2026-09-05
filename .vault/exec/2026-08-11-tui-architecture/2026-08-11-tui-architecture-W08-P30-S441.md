---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:a495fe10fe1e94b36a2461fd29f57ab7cff52d6caad3cf9271d6acfa8cd53451'
step_id: 'S441'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Close the locale translation honesty gate, and correct the Modelo 232 related-party labels it led to. The gate's offenders split into values that are legitimately identical across languages -- AEAT acronyms, templates made of placeholders and AEAT terms, and genuine cognates -- which take per-key allowlist justifications, and one real defect the gate does not itself police: the Spanish catalogue carried English label text for the 45 related-party fields while their help text was Spanish, and every locale described the one-character F/J/O flag as a foreign identification. Ground those labels in the official record design.

## Scope

- `src/cadrumo/locales/_intentional_identical.json`
- `src/cadrumo/locales/*/modelo/schema/232.yml`

## Changes

The honesty gate passes. Its offenders were not one problem but two, and only
one of them was the gate's.

WHAT THE GATE WAS ACTUALLY REPORTING was values legitimately identical across
languages, and they take per-key allowlist justifications rather than invented
differences: AEAT acronyms and identifiers (NIF, AEAT, IBAN, SOCIMI, Modelo),
templates whose only words are placeholders and AEAT terms
("Modelo %{modelo} · %{filing_year} · %{period}"), and genuine cognates --
Catalan really does spell "Local", "Formal", "Absent", "Present" and "Total" as
English does, and "prorrata" is the IVA term the English catalogue itself
carries verbatim. Each entry says which word is shared and why.

A REAL DEFECT SURFACED THAT THE GATE DOES NOT POLICE. The Spanish catalogue
carried ENGLISH label text for all 45 Modelo 232 related-party fields --
"Related party 1: Amount" -- while the help text beside it was correct Spanish.
The gate skips modelo.schema.* for Spanish deliberately, because Spanish IS the
schema's source language there, so it never looked.

Translating that English into Spanish would have baked in a second error.
`vinculada-1-fjo` is one character wide at position 159, and a one-character
field cannot be a "Foreign national identification". The official design names
it: "3.Informacion operaciones con personas o entidades vinculadas 1 - F/J/O",
the fisica/juridica/otra flag. All four locales carried the wrong meaning, so
all four were corrected, and the 45 Spanish labels were written from the
official field names rather than from the English.

Teeth needed a second attempt, and the first one is the useful record. Reverting
a Spanish Modelo 232 label to English did NOT fail the gate -- correctly, since
Spanish is that subtree's source and an es value equal to en there is the
source, not an untranslated string. The valid defect is an in-scope key: ca
tui.aeat_sync.column.availability set to "Availability" failed with the key
named. Restored by copy; 11 passed.

## Notes

21 allowlist entries were added and then REMOVED. They covered es
modelo.schema.* keys, which the gate skips, so each was a justification nothing
consults -- noise in a governance file. Discovering why the injected defect
passed is what exposed them.

The Modelo 232 label fix is a correctness improvement outside this gate's
scope. No gate asserts it: the pinned-label authorities cover Modelo 200 only,
and there is no Modelo 232 adjudication cohort. The grounding is the bundled
design (orden HFP/816/2017) read directly, recorded here rather than asserted.
