---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - "[[2026-05-27-yara-cli-testimonial-audit]]"
  - "[[2026-05-27-lourdes-cli-testimonial-audit]]"
---

# `cli-testimonial` audit: `round-23 Inés Fernández-Aragüete single-mother adopción internacional`

## Scope

Twenty-third testimonial round, Inés Fernández-Aragüete — Madrid
empleada bancaria 37, single mother by international adoption.
Adopted Laia (8 months) finalised Spanish-court resolution
2024-05-12 (China origin). €42k salary. Exercises adopción
axis, Art. 58.1 + 58.3 LIRPF (mínimo descendiente + incremento
menor de 3), Art. 81 LIRPF monoparental, Madrid autonomic
adoption deducción €600.

## Findings

### CRITICAL — Descendant axis (adoption date + birth date) entirely absent

Profile has `--family-minor-children-in-unit` boolean but no
structured descendant data. No `--descendiente-adopcion-fecha`,
no `--descendiente-fecha-nacimiento`, no per-descendant attributes.
The motor cannot apply:
- Art. 58.1 LIRPF mínimo descendiente €2,400 (Laia first child).
- Art. 58.3 LIRPF +€2,800 incremento menor de 3 años (Laia at 8 months).
- Art. 58 prorrata por fecha resolución (if pre-1-July → full year).

Total mínimo Laia entitled: €5,200. Currently silently zero.
Affects every adopting parent + every parent with descendants
generally — universal gap.

### HIGH — `--situacion-familiar monoparental` absent (CONFIRMS Yara #188)

Inés is empleada single + sole tutor. Art. 81 LIRPF €2,150
reducción applies. Profile has `--taxpayer-marital-status 1`
(soltera) but no `--situacion-familiar monoparental` axis.
Tracked under #188 (Yara) and #176 (Lourdes pareja-de-hecho
shape). Re-confirmed.

### HIGH — Madrid autonomic adoción deducción €600 not triggered

Madrid CCAA has €600 deducción por nacimiento o adopción for
first descendant. Inés's profile carries CCAA Madrid but no
trigger event (adoption date) → deducción cannot fire. Even if
the deducción exists in the registry, without adopción data
the motor cannot activate it.

### CRITICAL — CLI import regression `UnmatchedPlaceholderError`

Same finding as Diego H1. After multiple commands, CLI fails to
import with:
```
ValueError: AeatError subclass aeat.core.i18n._render.UnmatchedPlaceholderError
is missing a declared ErrorCode registry entry
```

Investigation: the class IS registered in `_core.py:117`. Likely a
race condition in class-init order — `_render.py` asserts the
registry entry before the registry list is fully loaded. Stale
`__pycache__` from concurrent agent activity may trigger.

CLI was operational at HEAD when independently verified by team-
lead (`aeat --version` returned cleanly). Persona-session may
have hit a transient import-order interleaving.

Tracked as #217.

### MEDIUM — Casilla 0001 text-type rejection good UX, but no auto-suggest

Post-#174 guard correctly rejects `--casilla "0001=42000"` and
points to `--binding` or `aeat app modelo casillas` for the
correct numeric casilla. But no auto-suggest of casilla 0003
for the trabajo income case. User must navigate manually.

### INFO — M100 bindings missing field for trabajo income

`bindings list --modelo 100` returns 6 bindings: estimación
modalidad + CCAA + 4 retención previous_filing entries. No
binding for trabajo rendimientos themselves — these go via
`--casilla` directly. Unclear flow for non-technical user.

## Recommendations

Priority order:

1. **Descendant axis (CRITICAL, #221)** — add structured
   descendant data: per-descendant `birth_date`, `adoption_date`,
   `tipo_filiacion`, `discapacidad_grado`. Auto-derive mínimo
   descendiente from the list. Apply Art. 58.3 menor-de-3
   automatically. Same pattern as marriage_date axis (#213).

2. **`--situacion-familiar monoparental` (#188 elevated)** —
   already tracked. Triple-confirmed (Yara + Lourdes + Inés).

3. **Madrid autonomic deducción auto-trigger** — once descendant
   axis lands, surface CCAA-specific deducciones derived from
   adopción / nacimiento events.

4. **`UnmatchedPlaceholderError` race (#217)** — same task as
   Diego.

For an adopting parent like Inés, the €5,200 mínimo + €2,150
reducción + €600 autonomic = **€7,950 of legitimate adjustments**
the CLI cannot apply in current state.
