---
tags:
  - "#exec"
  - "#restructure-execution"
date: 2025-05-22
modified: '2025-05-22'
related:
---

# Audit and Fix locales/es.yml

## Changes

1.  **Command Casing**: Updated all instances of `AEAT` to `aeat` when inside backticks or referring to a CLI command execution (e.g., `aeat setup`).
2.  **Accent Fixes**: Corrected `está` to `esta` for demonstratives (e.g., `esta instalación`, `esta URL`).
3.  **Acronym Capitalization**: Verified and ensured `IVA`, `NIF`, `NIE`, `CIF`, `NRC`, `IRPF` are capitalized in user-facing text.
4.  **Tax Jargon**: Capitalized `Modelo` and `Casilla` in labels and when referring to specific form elements.
5.  **Phrase Refinement**:
    *   `no hay perfil activo` -> `No hay ningún perfil activo`.
    *   `falló la autenticación` -> `La autenticación ha fallado`.

## Verification Results

- Manual audit of `src/aeat/locales/es.yml`.
- Typecheck and lint (planned).
