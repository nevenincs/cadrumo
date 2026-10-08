# GNOME native login observation

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-198` · **Topic:** [Bundled knowledge and localization](../topics/bundled-knowledge-and-localization.md)

<!-- preserved:article -->
## Scope

This small local-runtime asset group contains two files: a 3,957-byte GNOME Shell extension and a 267-byte `metadata.json`. I read both files completely. This is static inspection only; I did not load the extension into GNOME Shell or call its D-Bus API. The extension source is the implementation evidence; metadata describes the declared target shell versions and session modes (extension (`src/cadrumo/_data/local_runtime/gnome_login/extension.js`), metadata (`src/cadrumo/_data/local_runtime/gnome_login/metadata.json`)).

## Capability and mechanism

The extension exposes a read-only view of the current GNOME screen-shield and session mode to a local process over the session D-Bus. Its well-known name and object path are both `org.cadrumo.Runtime.LoginObservation1`. The version-1 interface has a no-argument `GetState` method returning API version, random epoch ID, 32-bit sequence and lock-generation counters, locked/active booleans, and the current session-mode string. It also emits `StateChanged(sequence)` on relevant shell events. The bus interface is declared in the extension's introspection XML; metadata names the extension “Cadrumo native login observation,” version 1, with GNOME Shell targets 49 and 50 and allowed modes `user` and `unlock-dialog` (interface and metadata (`src/cadrumo/_data/local_runtime/gnome_login/extension.js`), declared shell support (`src/cadrumo/_data/local_runtime/gnome_login/metadata.json`)).

On enable, the extension generates an epoch and initializes sequence 1, then reads `Main.screenShield`. It stops if the shield is absent or its `locked`/`active` members are not booleans. Otherwise it initializes lock generation to 1 if already locked (0 otherwise), exports the D-Bus object, and subscribes to `locked-changed`, `active-changed`, and `Main.sessionMode.updated`. Lock-generation advances on transitions to locked; all three signal classes advance the general sequence. The method reads the current shield values and mode synchronously on Shell's main loop rather than returning a cached observation. It rejects calls unless the observer owns its bus name, shield fields remain valid, and the session mode is `user` or `unlock-dialog` (enable and signal setup (`src/cadrumo/_data/local_runtime/gnome_login/extension.js`), live read and mode guard (`src/cadrumo/_data/local_runtime/gnome_login/extension.js`)).

The epoch identifies a sequence-number lifetime: when the general sequence reaches `0xffffffff`, the next event rotates the UUID and resets sequence to 1. Lock-generation has a similar overflow reset that rotates the epoch before incrementing. These measures prevent a consumer that retains state from mistaking a wrapped counter for an old observation, provided it treats the epoch as part of the binding. The signal only carries the new sequence, so consumers must call `GetState` to obtain the state snapshot (counter rollover and event emission (`src/cadrumo/_data/local_runtime/gnome_login/extension.js`)).

## Security and reliability

This component observes screen lock/active state and session mode; it does not read a username, login label, password, credential, or perform lock/unlock actions. The comments' read-only claim matches the inspected method and event flow. Its D-Bus name ownership uses `DO_NOT_QUEUE`, and `_ready` remains false until name acquisition succeeds. That prevents a second extension instance from waiting invisibly and later becoming an observer; `GetState` fails closed with “Native login observation unavailable” whenever readiness, mode or shield-state checks fail (name ownership and readiness gate (`src/cadrumo/_data/local_runtime/gnome_login/extension.js`), failure guard (`src/cadrumo/_data/local_runtime/gnome_login/extension.js`)). The observer still discloses a user's locked/active state to clients able to call the session-bus service. This chunk contains no explicit caller allowlist or D-Bus policy, so effective access restrictions depend on the session-bus environment and on caller-side handling; those boundaries need cross-layer review.

`disable()` marks the service not ready, releases the owned name, disconnects tracked GNOME signals, unexports the object and clears retained state. This is a concrete lifecycle cleanup path. Two conditional availability gaps are visible: if `Main.screenShield` or its expected boolean properties are unavailable at `enable()` time, the method returns without installing a retry; if name ownership is lost or conflicts, the loss callback clears readiness but the file contains no explicit retry or diagnostic. Whether those conditions can occur under the two declared shell versions is unverified. Errors from object export or D-Bus setup are not caught in this file (cleanup (`src/cadrumo/_data/local_runtime/gnome_login/extension.js`)).

## Assessment and follow-up

The implementation has a narrow interface, validates the shell mode and state types at read time, reads state synchronously, and explicitly handles both counter rollover and extension teardown. The primary unresolved questions are whether GNOME Shell 49/50 provide these private APIs/signals exactly as assumed, how the local runtime identifies and authorizes its D-Bus caller, how it combines `epoch`, `sequence`, and `lockGeneration`, and whether it handles “unavailable” without treating it as unlocked. No tests, installation metadata beyond these two files, or runtime verification are present here. Synthesis should trace the D-Bus client and any fallback path before assessing end-to-end unlock/session safety. The observation service itself does not establish user authentication or prove that the user has entered credentials.

## Complete assigned-file coverage

- `src/cadrumo/_data/local_runtime/gnome_login/extension.js` — 3,957 bytes
- `src/cadrumo/_data/local_runtime/gnome_login/metadata.json` — 267 bytes
<!-- /preserved:article -->
