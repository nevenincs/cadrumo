---
tags:
  - '#adr'
  - '#google-app-identity'
date: '2026-10-19'
modified: '2026-10-30'
body_schema: 'body-v2'
body_hash: 'sha256:cb1f5e373bf494929c890015f32af42bc3cf77b362d53a214ae88548666272f1'
related:
  - "[[2026-10-04-google-app-identity-adr]]"
  - "[[2026-10-04-canonical-environment-adr]]"
  - "[[2026-10-13-provider-settings-adr]]"
  - "[[2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr]]"
  - "[[2026-10-04-application-sign-in-adr]]"
  - "[[2026-08-13-profile-password-custody-rollup-adr]]"
  - "[[2026-09-26-mcp-purpose-authentication-profile-access-adr]]"
  - "[[2026-10-04-desktop-shell-adr]]"
  - '[[2026-10-04-google-app-identity-reference]]'
  - '[[2026-10-04-canonical-environment-reference]]'
---
# `google-app-identity` adr: `A profile's Google sign-in and its environment stay inside that profile's folder` | (**status:** `accepted`)

## Problem Statement

On 2026-10-19 the operator ruled that Google sign-in belongs to the current profile while software provisioning stays application-wide. Google OAuth tokens must be saved in the profile's own folder on disk and never anywhere another profile can reach; the operator called any cross-profile reach "a scope and critical provisioning issue". The app's environment variables must always point to that profile folder, and the Google OAuth client must be readable by every session and every profile. An audit of the code against that ruling found two ways token material could leave or cross the profile folder, and no environment variable naming the folder at all. `2026-10-04-google-app-identity-adr` had left the remote-mirror policy of the token namespace open.

## Considerations

- The refresh token, its sign-in record and the Drive root are encrypted secure objects in the bucket database, `<storage root>/buckets/<profile id>/db/cadrumo.db` (`src/cadrumo/core/storage_taxonomy_locations.py:690`, `src/cadrumo/adapters/persistence/storage/runtime.py:89`). The database is per profile, not a root-level store; the root-level `cadrumo.db` serves only cold bootstrap with no profile selected, and the session store never reaches it.
- Payloads are AES-GCM under the active session's profile DEK, with namespace, key digest and schema bound into the associated data (`src/cadrumo/adapters/persistence/storage/crypto/encrypted_columns.py:44`, `:78`). Each profile has its own wrapped DEK, so profile B's key fails the tag on A's ciphertext even if B holds the bytes.
- The session store keyed rows by the record's profile but opened whichever profile was selected at write time. A consent outlasting a profile switch could write A's token into B's database (`src/cadrumo/adapters/outbound/google/session_store.py`, before this record).
- The token and metadata namespaces kept the default `CIPHERTEXT_WITH_METADATA` mirror policy, so a full profile archive push copied their ciphertext to Drive (`src/cadrumo/adapters/outbound/storage/mirror_push.py:316`). Both were already `PROCESS_LOCAL`, so neither portable export nor restorative backup carries them.
- Access tokens are memory-only (`src/cadrumo/adapters/outbound/google/records.py:70`); the OAuth flow writes no file, temporary file, keyring entry or log line with token text; the TUI and CLI hold no Google store of their own; the agent and its tools reach Google only through registered operations.
- The token directory is a location beneath the storage root, `<storage root>/tokens`, with no override variable. Its only writer is the AEAT acquisition-lock path (`src/cadrumo/application/auth/acquisition_lock.py:138`), whose files hold no Google material.
- `CADRUMO_ACTIVE_PROFILE` stays severed from every environment source (`src/cadrumo/core/config.py:82`, rule 13): selection belongs to the pointer and the in-process override.
- `2026-10-13-provider-settings-adr` constraint 8 said the agent receives no profile identity. A folder path under `buckets/` names the profile's identifier.
- The client is publisher installation data in the package's own `cadrumo/_data/google/oauth_client.json` (`src/cadrumo/core/config_google.py:17`), embedded at build time and pinned as a package fact, never under the storage root.

## Considered options

- **Route by the record's own profile, make the sign-in local-only, and derive a read-only folder variable from the profile a launcher serves.** Chosen.
- **Restore an environment selector (`CADRUMO_ACTIVE_PROFILE`) so processes follow the selection.** Rejected: it reverses rule 13 and the reason it was severed, a shell variable outranking the pointer.
- **A pointer-derived variable that every process reads at start.** Rejected for children: a long-lived parent would hand a stale folder down after a switch, and the CLI and TUI must ask the runtime, not read the pointer (`2026-10-18-runtime-authority-boundary-adr`).
- **Encrypt the token under a second per-profile key in a root-level store.** Rejected: the bucket database already gives per-profile placement and keys; a second store adds a reach across profiles the ruling forbids.
- **Remove the token directory.** Rejected: it is a declared location with a live reader.

## Constraints

1. A profile's Google sign-in rows live only in that profile's bucket database. The session store opens the database of the profile named by the record key, and the storage runtime refuses when the unlocked session serves another profile. No code path writes Google token material outside `<storage root>/buckets/<profile id>/`.
2. `GOOGLE_OAUTH_TOKEN_NAMESPACE` and `GOOGLE_OAUTH_METADATA_NAMESPACE` are `LOCAL_ONLY` for remote mirroring and stay `PROCESS_LOCAL` for custody carry. The Drive root locator keeps its mirror policy. Existing encryption, namespaces, keys, schema and associated data are unchanged.
3. `CADRUMO_PROFILE_ROOT` names `<storage root>/buckets/<profile id>` of the one profile a process is started for. Its launcher derives it from that exact profile; a received value is never relayed; nothing in Cadrumo reads it back to select a profile. `CADRUMO_ACTIVE_PROFILE` stays severed.
4. Launchers that know their profile set it: the runtime for each profile worker (its bound profile) and the agent service for the agent gateway (the lease's profile), which forwards it with the storage root to the tool servers and programs the agent starts. The package contract declares it as an optional slot of the `python`, `aeat`, `cadrumo-mcp`, `agent-gateway` and `agent-worker` profiles. A profile switch starts new workers and a new agent session, so the folder follows the switch without a long-lived value.
5. The Google OAuth client stays a single installation-wide package fact readable by every profile and session. No profile folder holds a copy, and no per-profile client exists.
6. The token directory stays as declared. It never receives Google token material.

Affected prior rulings, amended in place on 2026-10-19 with a note of what they said before: `2026-10-04-google-app-identity-adr` (the open mirror-policy question is settled), `2026-10-04-canonical-environment-adr` (the reserved-names bullet gains the derived variable), and `2026-10-13-provider-settings-adr` constraint 8 (the agent now receives its profile's folder path, and still no password, receipt, session policy or settings store).

## Implementation

We will keep every Google sign-in record inside its own profile's folder and tell each process the folder of the profile it works for.

- Storage: `src/cadrumo/adapters/outbound/google/session_store.py` routes through `secure_object_repository_for_bucket(profile)`; the two namespaces in `src/cadrumo/adapters/persistence/storage/secure_object_namespaces.py` are local-only.
- Environment: `src/cadrumo/core/profile_root_environment.py` defines the variable and its derivation; `child_environment(..., profile_id=...)` in `src/cadrumo/core/storage_environment.py` sets it; `src/cadrumo_runtime/adapters/profile_worker.py` and `src/cadrumo_agent_service/host/launch_environment.py` pass their profile; `native/application-environment.toml` admits the slot.
- Not yet built, named for the owning sessions: the desktop host sets the variable for the processes it starts itself (terminal, service and manager launches, today outside this change's write scope), and the CLI and TUI publish it into their own environment from the runtime's active-profile answer once that client path lands. Hypothesis: the desktop reads the profile from its existing sign-in status observation.

## Rationale

The ruling is about reach, and the bucket already is the reach boundary: one folder, one database, one DEK per profile. Making the store open the record's own bucket closes the one write path that could cross it, and local-only mirroring closes the one copy that left it. A derived variable satisfies "the environment points to the profile folder" without reopening environment selection, and deriving it per launch from the exact profile keeps it correct across switches where an inherited value would not.

## Consequences

- A sign-in can be read and decrypted only under its own profile's session; a switch mid-consent refuses the save instead of misplacing it.
- A full archive push reports the two sign-in namespaces as withheld, as it already does for provider keys; restoring Drive mirror state does not restore a Google sign-in, so the person signs in again on another machine.
- Tools started by the agent learn the profile's folder, and with it the profile identifier. The agent still holds no password, receipt, session or settings.
- Reconsider if a process must serve several profiles at once, or if the desktop must expose the folder to software it does not launch.

Accepted 2026-10-19 on operator directive 2026-10-19.
