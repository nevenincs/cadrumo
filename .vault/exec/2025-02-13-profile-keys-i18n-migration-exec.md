---
tags:
  - '#exec'
  - '#profile-keys-i18n-migration'
date: '2025-02-13'
modified: '2025-02-13'
related: []
---

# Execution Record - Profile Keys i18n Migration

Migration of profile key descriptions from hardcoded values in `_keys.py` to the i18n system.

## 1. Extract and Migrate Descriptions

### `es.yml`
Add to `profile.key`:
- `tax.id`: "Identificador fiscal usado en los borradores locales de declaración."
- `name`: "Nombre visible usado en la salida de revisión local."
- `activity`: "Etiqueta de actividad económica o clave de actividad controlada."
- `address.postcode`: "Código postal del domicilio fiscal cuando un Modelo soportado lo requiere."
- `declaration.type`: "Tipo de declaración para las cabeceras de exportación; por defecto I."

### `en.yml`
Add to `profile.key`:
- `tax.id`: "Tax identifier used for local declaration drafts."
- `name`: "Display name used in local review output."
- `activity`: "Business activity label or controlled activity key."
- `address.postcode`: "Tax address postcode when a supported Modelo needs it."
- `declaration.type`: "Declaration type for export headers; defaults to I."

### `ca.yml`
Add to `profile.key`:
- `tax.id`: "Identificador fiscal utilitzat en els esborranys locals de declaració."
- `name`: "Nom visible utilitzat a la sortida de revisió local."
- `activity`: "Etiqueta d'activitat econòmica o clau d'activitat controlada."
- `address.postcode`: "Codi postal del domicili fiscal quan un Modelo suportat el necessita."
- `declaration.type`: "Tipus de declaració per a les capçaleres d'exportació; per defecte I."

### `hu.yml`
Add to `profile.key`:
- `tax.id`: "Helyi bevallás-tervezetekhez használt adóazonosító."
- `name`: "A helyi áttekintés kimeneten megjelenő név."
- `activity`: "Gazdasági tevékenység címke vagy ellenőrzött tevékenységkulcs."
- `address.postcode`: "Adózási cím irányítószáma, ha valamely támogatott Modelo igényli."
- `declaration.type`: "Bevallás-típus az exportfejlécekhez; alapértelmezett: I."

## 2. Refactor `src/aeat/domain/profile/_keys.py`

- Update `_key` function signature to remove `es`, `en`, `ca`, `hu`.
- Update `PROFILE_KEYS` calls.

## 3. Update `src/aeat/domain/profile/test_keys.py`

- Fix tests.
