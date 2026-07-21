---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S39'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Update the Docker clean-install probe to Cadrumo names

## Scope

- `dev/packaging/smoke_docker.py`

## Description

- Retarget the Docker core and browser probes to the `cadrumo` distribution, import package, console script, version banner, extras requirements, and install remedy.
- Preserve `registry/aeat`, `corpus/aeat_official`, the AEAT browser adapter namespace, and its authority-specific browser settings.
- Strip inherited `CADRUMO_*` settings before every product runtime command and provide container-local storage and database routes where valid.
- Generate and inspect both embedded probe programs, then attempt the real WSL Docker core lane under bounded timeouts.

## Outcome

The Docker probes now exercise only the canonical Cadrumo product identity. Both
runtime lanes discard inherited Cadrumo settings. The default core check and
browser lane use container-local SQLite routes; profile creation uses an isolated
local storage root and lets Cadrumo derive the profile bucket database after
activation, as required by the storage integrity guard.

## Notes

- Native Docker Desktop was unavailable, but the configured WSL Ubuntu Docker daemon responded as version 29.6.1.
- The one bounded real core run built the wheel and started the clean container, then failed during profile creation because the first implementation supplied `CADRUMO_DATABASE_URL` before a profile bucket was active. The implementation was corrected by removing that premature override; Docker was not retried.
- Post-fix embedded-probe generation assertions, Python compilation, Ruff, formatting, focused former-identity residue, plan, and diff checks passed.
- Independent review confirmed no remaining HIGH findings after the browser process environment was rebuilt from the cleaned mapping and the core version and attachment subprocesses were given cleaned environments.
- `registry/aeat`, `corpus/aeat_official`, `cadrumo.adapters.outbound.aeat`, `AEAT_BROWSER_CHANNEL`, and `AEAT_BROWSER_HEADLESS` remain intentionally because they identify Spanish tax-authority data and integration behavior.
