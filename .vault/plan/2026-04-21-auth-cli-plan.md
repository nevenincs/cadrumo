---
tags:
  - "#plan"
  - "#auth-cli"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-21-auth-cli-adr]]"
  - "[[2026-04-18-auth-protocol-adr]]"
  - "[[2026-04-18-auth-provider-abstraction-adr]]"
  - "[[2026-04-18-auth-protocol-research]]"
  - "[[2026-04-18-aeat-auth-providers-research]]"
---

# auth-cli plan (issue #285)

Sequenced, auditable implementation of the `aeat auth` Typer group per
`2026-04-21-auth-cli-adr.md`. Each step owns a discrete module or wire-up
and ends in a green unit-test run. No step touches the live AEAT gate,
the live-write charter, or any file outside the scope listed below.

## Phase 1 — Settings + scaffolding

1. Add `aeat_auth_provider: AuthProviderKind | None = None` to
   `src/aeat/config.py`. The field reads `AEAT_AUTH_PROVIDER` from the
   environment and is validated by the enum.
2. Add the `AEAT_AUTH_PROVIDER=` line to `.env.example` with a comment
   enumerating the valid values.
3. Create the empty module tree `src/aeat/entrypoints/cli/auth/__init__.py`,
   `_registry.py`, `_paths.py`, `_render.py`, `_session.py` plus the
   colocated `test_auth_cli.py` file. Wire the sub-app into
   `src/aeat/entrypoints/cli/__init__.py` with the help string from the ADR.

## Phase 2 — Registry + path helpers

4. `_registry.py`:
   - Frozen Pydantic model `ProviderRegistryEntry(kind, label,
     implemented)`.
   - Canonical `REGISTRY` tuple leading with `certificate` and covering
     all four `AuthProviderKind` values.
   - `get_entry(kind)` / `iter_entries()` helpers.
   - `build_provider(kind, settings)` delegates to
     :func:`aeat.adapters.outbound.aeat.auth.select_provider` for implemented kinds; raises
     `ProviderNotImplementedError` otherwise.
   - `describe(kind, settings)` returns `AuthProviderDescription`.
     For implemented kinds it delegates to the provider's
     `describe()`; for not-yet-implemented kinds it returns a
     `configured=False, available=False,
     health_summary="not yet implemented"` shape.
   - `default_kind(settings)` — env-var first, then first-configured,
     else raise `NoConfiguredProviderError(AeatError)`.
5. `_paths.py`:
   - `storage_state_paths(settings, kind)` returns a
     `StorageStatePaths(storage_state, metadata)` Pydantic model
     pointing at the authenticator's current single-file layout.
     `kind` is accepted but ignored today; a TODO comment documents
     the follow-up split.

## Phase 3 — Session + render helpers

6. `_session.py`:
   - Frozen Pydantic model `PersistedAuthSession(provider_kind,
     identity_nif, authenticated_at, idle_deadline)` derived from the
     authenticator's metadata sidecar. Unknown kinds fail-closed via
     enum validation.
   - `load(settings, kind)` returns `PersistedAuthSession | None`.
     Bad JSON or bad schema version raises
     `CorruptAuthSessionError(AeatError)`.
   - `delete(settings, kind)` removes the pair atomically and returns
     the list of paths removed; missing files are a no-op.
7. `_render.py`:
   - `render_list_providers_table(rows)` builds a Rich Table.
   - `render_list_providers_json(rows)` dumps the
     descriptions as a JSON array plus the `implemented` flag.
   - `render_status_line(session, now=None)` +
     `render_status_json(session, now=None)` produce the Kent-facing
     string or the JSON payload.
   - `render_no_session_line(settings)` is the friendly no-op message.

## Phase 4 — Commands

8. `aeat auth list-providers` in `__init__.py`:
   - Flags: `--configured`, `--all`, `--json`.
   - Iterate `_registry.iter_entries()` → `_registry.describe()` →
     filter → render. `--all` remains a no-op today per the ADR.
9. `aeat auth login`:
   - Flags: `--provider PROVIDER | -p`, `--non-interactive`,
     `--json`, default provider via `AEAT_AUTH_PROVIDER` /
     `_registry.default_kind(settings)`.
   - Reject unknown + not-yet-implemented kinds with exit code 2 and
     a pointer to EPIC #279.
   - Guard `--non-interactive` against interactive providers (Cl@ve
     Móvil / Cl@ve PIN). Today this is a pure shape check since
     neither provider exists.
   - Run the login via `asyncio.run(_do_login(settings, kind))` that
     constructs the provider via `_registry.build_provider(...)`,
     calls `authenticate()`, and returns the final `AeatSession`.
   - Render a one-line human confirmation plus the session TTL
     remaining. `--json` emits the compact dump from the ADR.
10. `aeat auth status`:
    - Flags: `--provider`, `--json`.
    - Resolve kind: explicit flag → `_session.load(settings, kind)`.
    - Human output per ADR; JSON dumps the `PersistedAuthSession`
      plus derived TTL fields.
11. `aeat auth logout`:
    - Flags: `--provider`, `--all`, `--json`.
    - Default: read the persisted session (any kind), delete its
      pair, print the removed paths. Missing session is a friendly
      no-op.
    - `--provider` narrows the delete to one kind; mismatch is a
      zero-exit no-op that leaves files in place.
    - `--all` iterates every registry kind.
    - `--json` emits `{"removed_paths": [...]}`.

## Phase 5 — Tests and verification

12. Colocated unit tests in `src/aeat/entrypoints/cli/auth/test_auth_cli.py`:
    - `pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]`.
    - Cases cover list-providers table + JSON, registry default
      resolution, login error paths, status (fresh / expired / no
      session / mismatched provider), logout (default / --all / mismatched
      provider / JSON).
13. Verify `just test-cov`, `uv run ruff check .`, `uv run ruff format
    --check .`, and `uv run ty check` all pass clean.

## Out of scope

- Real live-read execution of `aeat auth login` — that depends on the
  Cl@ve providers and the live gate; covered by follow-up `live_read`
  tests when Cl@ve lands.
- Per-provider storage-state segmentation.
- `aeat doctor` integration with the new registry.
- Translations for the runtime strings.
