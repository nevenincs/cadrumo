---
tags:
  - '#plan'
  - '#portal-catalogue'
date: '2026-04-17'
modified: '2026-04-17'
related:
  - '[[2026-04-17-portal-catalogue-adr]]'
  - '[[2026-04-17-portal-catalogue-research]]'
  - '[[2026-04-13-modelo-inventory-adr]]'
---

# portal-catalogue implementation plan

Implements the `aeat.domain.portals` subpackage per the portal-catalogue ADR:
closed `Portal` enum, strict pydantic v2 `PortalMetadata` registry, 41
portal entries, CLI mirror, and typed `submission_portal` cross-
reference on `ModeloMetadata`. The #108 modelo registry migrates from
the free-form `submission_portal_hint: str` to a typed
`submission_portal: Portal | None`.

## Proposed Changes

- New subpackage `src/aeat/domain/portals/` with: `_codes.py`, `_categories.py`,
  `_metadata.py`, `_registry.py`, `_errors.py`, `_cli.py`,
  `_entries/` (41 files), colocated tests, and a thin public API
  re-exported from `src/aeat/domain/portals/__init__.py`.
- Migration of `src/aeat/domain/modelos/_metadata.py` to replace
  `submission_portal_hint: str` with `submission_portal: Portal | None`
  and add a registry-level cross-reference invariant.
- Update of all 20 modelo entries under `src/aeat/domain/modelos/_entries/` to
  bind their new `submission_portal` to the matching `Portal` member.
- New test `src/aeat/domain/modelos/test_portal_cross_reference.py` closing
  the round-trip.
- Wiring of the new Typer subcommand into `src/aeat/entrypoints/cli/__init__.py`.
- Conventional-commit messages throughout.

## Tasks

- `Phase 1 — Scaffolding`
  1. Create `_errors.py` with `PortalRegistryError`,
     `UnknownPortalError`, `PortalIntegrityError` (all subclass
     `AeatError`).
  2. Create `_categories.py` with `PortalCategory`, `AuthMethod`,
     `UrlStability`, `Subdomain` `StrEnum`s (exact members per ADR §3).
  3. Create `_codes.py` with the `Portal` `StrEnum` (41 members, values
     = member name lowercased).
  4. Create `_metadata.py` with the strict `PortalMetadata` pydantic
     model and every validator required by ADR §4.
- `Phase 2 — Registry + entries`
  1. Create `_entries/__init__.py` (empty).
  2. Add per-portal files under `_entries/`, one file per Portal member,
     each exposing `ENTRY: PortalMetadata`. 41 files.
  3. Create `_registry.py` with `_finalise_registry`, all import-time
     invariants (closure over `Portal`, unique keys, `replaced_by`
     resolves, `related_modelo` round-trip, modelo closure with M037
     carve-out), and the three helpers (`get_portal`,
     `portals_for_modelo`, `portals_by_category`).
  4. Wire `src/aeat/domain/portals/__init__.py` public API: re-export the
     enums, the model, the errors, the registry, and the helpers.
- `Phase 3 — CLI`
  1. Create `_cli.py` with `aeat portals list`, `show`, `for-modelo`
     subcommands emitting deterministic JSON (sorted by `Portal`
     value).
  2. Wire the subcommand into `src/aeat/entrypoints/cli/__init__.py`.
- `Phase 4 — Unit tests`
  1. `test_codes.py` — `Portal` has exactly 41 members; values match
     member names lowercased; no duplicates.
  2. `test_categories.py` — pin the exact member count and values:
     `PortalCategory` has 7 members, `AuthMethod` has 7,
     `UrlStability` has 4, `Subdomain` has 7 (with the exact host
     strings from ADR §3).
  3. `test_metadata.py` — strict-validation invariants: HTTPS only,
     host matches subdomain, G-code path regex for FILING/CENSUS
     active entries, trilingual label check, `AuthMethod.ANONYMOUS`
     exclusivity, `replaced_by` rules including the
     retired-without-replacement fallback (when
     `active is False and replaced_by is None`, `notes_es` MUST be
     non-empty), `related_modelo` category gating.
  4. `test_registry.py` — registry is frozen `MappingProxyType`,
     closure over `Portal`, every `ModeloCode` covered (M037 carve-out
     flagged explicitly), duplicate-entry rejection, `replaced_by`
     resolves, `related_modelo` round-trip, `portals_for_modelo`
     scope is FILING+BORRADOR only (matches ADR §6), `portals_by_category`
     returns deterministic sort order, and `_finalise_registry` emits
     exactly one `info` log line on success with no `print` calls in
     the module.
  5. `test_modelo_cross_reference.py` — every FILING/CENSUS/BORRADOR
     portal's `related_modelo` is in `ModeloCode`; every `ModeloCode`
     has ≥1 such portal.
  6. `test_cli.py` — `aeat portals list` / `show` / `for-modelo` emit
     deterministic JSON; explicit coverage for the three `list` filter
     flags (`--category`, `--modelo`, `--active-only`) in isolation
     and combined; invalid inputs raise `UnknownPortalError` /
     `UnknownModeloError`.
  7. `test_smoke.py` — keep the existing stub; harden it to import
     every public name from `aeat.domain.portals`.
- `Phase 5 — ModeloMetadata migration`
  1. Change `src/aeat/domain/modelos/_metadata.py`:
     replace `submission_portal_hint: str` with
     `submission_portal: Portal | None`. Remove the `submission_portal_hint`
     validator bullet. Update the docstring.
  2. Update all 20 `src/aeat/domain/modelos/_entries/modelo_*.py` files:
     replace `submission_portal_hint="..."` with
     `submission_portal=Portal.PORTAL_M<code>_<SHORT>`.
  3. Extend `src/aeat/domain/modelos/_registry.py` with a new
     `_check_submission_portal` invariant called from
     `_finalise_registry` — asserts every `submission_portal` (when
     non-None) resolves in `PORTAL_REGISTRY` and that
     `metadata.submission_portal.related_modelo == metadata.code`.
  4. Create `src/aeat/domain/modelos/test_portal_cross_reference.py` pinning
     the round-trip for every `ModeloCode` member.
  5. Update `src/aeat/domain/modelos/__init__.py` if any public surface
     shifted (no shift expected — the field rename is internal to the
     record).
- `Phase 6 — Verification`
  1. `uv run pytest -m unit src/aeat/portals src/aeat/models` — expect
     all tests to pass.
  2. `uv run pytest -m unit` — full unit suite; catches any ripple in
     deadline/filing consumers.
  3. `uv run pre-commit run --all-files` — ruff/mypy/style pass.
  4. `uv run aeat portals list --modelo 303` — sanity check the CLI
     output is deterministic JSON.
  5. `uv run aeat modelos show 303` — confirm the ModeloMetadata CLI
     still renders with the new `submission_portal` field visible.

## Parallelization

Phases 1–3 are sequential (later phases import earlier modules).
Phase 4 test files can be authored in parallel once Phases 1–3 land
because they only depend on each other at the public-API level. Phase
5 must land AFTER Phase 2's registry boots cleanly — otherwise the
registry cross-reference check has nothing to round-trip against.
Phase 6 is serial at the end.

For a single executor this is an 11-step linear sequence; there is no
meaningful win from sub-agent dispatch because Phase 2 alone (41 entry
files + registry) dominates wall time and must be serialised.

## Verification

Mission success criteria, anchored to the ADR acceptance items:

- **Portal enum + extensible pydantic metadata.** Covered by Phases
  1.3, 1.4, and `test_codes.py` + `test_metadata.py`.
- **Every modelo cross-references a Portal by enum member.** Covered
  by Phase 5 and `test_portal_cross_reference.py`, which asserts the
  round-trip for every member of `ModeloCode` (including M037's
  retired carve-out).
- **URL well-formedness.** Covered by `test_metadata.py` (HTTPS only,
  host matches subdomain, G-code path regex for FILING/CENSUS active
  entries). Every registry URL is exercised because each entry is
  constructed at import time and `_finalise_registry` fails fast on
  any violation.
- **Registry closure + frozen API.** Covered by `test_registry.py` —
  `set(PORTAL_REGISTRY.keys()) == set(Portal)`, attempts to mutate the
  proxy raise `TypeError`, duplicate insertion raises
  `PortalIntegrityError`.
- **CLI deterministic JSON.** Covered by `test_cli.py` with snapshot
  assertions on the subcommand outputs.
- **Pydantic mandate.** All records (`PortalMetadata`) use
  `ConfigDict(strict=True, frozen=True, extra="forbid")`. No bare
  dataclasses or TypedDicts introduced — `Translatable` is the only
  TypedDict and it's the pre-existing trilingual primitive, not a
  record.
- **No new env vars.** `tests/test_config.py` continues to pass
  unchanged.
- **No live-write surface.** Portal metadata is read-only; no
  `aeat.adapters.outbound.aeat.export`, `aeat.application.filing`, or `aeat.adapters.outbound.aeat.browser` touched.

Honest caveats: the G-code and per-modelo URLs are curated from public
AEAT Sede pages as of 2026-04-17. Unit tests cannot detect AEAT-side
URL rotation; that is the self-healing sync's job (#83). The
`VOLATILE_APP_PATH` stability tier exists precisely to flag entries
that need external probing. Verification of URL liveness is NOT in
scope for this plan.
