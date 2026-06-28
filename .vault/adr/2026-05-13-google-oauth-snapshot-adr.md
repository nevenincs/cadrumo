---
tags:
  - '#adr'
  - '#google-oauth'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-13-google-oauth-adr]]"
  - "[[2026-05-12-google-oauth-adr]]"
  - "[[2026-05-08-google-oauth-adr]]"
  - "[[2026-05-06-google-oauth-research]]"
  - "[[2026-05-06-secure-persistence-enforcement-adr]]"
---

# `google-oauth` adr: `Snapshot, backup, and restore with encryption boundary` | (**status:** `accepted`)

## Problem Statement

ADR-2 fixed the per-record mirror layout. ADR-3 closes the encryption-boundary question that R8 flagged as the single architectural decision the ADR series must close before any implementation: does the sync coordinator move ciphertext or plaintext across the provider boundary? And the symmetric set of decisions for snapshot semantics, manifest integrity, key-escrow strategy, and the restore flows that follow from those choices.

## Considerations

- ADR-1 / ADR-2 placed sync beside `SecureObjectRepository`; per-row mirror at ciphertext layer is the substrate's existing record shape.
- Research stream R2 surveyed SQLite backup APIs, Litestream, restic, borg, kopia, rclone crypt encryption strategies, key escrow patterns.
- Research stream R8 flagged the ciphertext-vs-plaintext layer choice as the load-bearing security decision; recommended ciphertext-layer.
- The substrate already uses envelope encryption with KEK in OS keychain via `MasterKeyProvider`.

## Constraints

- **Pydantic v2 strict** for every record (manifest entry, escrow envelope, restore plan).
- **No partial implementations.** Snapshot, restore (full / selective / cross-machine), and integrity verification all land complete.
- **No backwards-compat surfaces.** No legacy snapshot format readers; no migration from any prior backup shape.
- **Drive never sees plaintext.** Operator's encryption material stays under operator control on a workstation with the OS keychain (or passphrase escrow).
- **Cross-machine restore must work without access to the source workstation's OS keychain.** Defines the escrow requirement.

## Implementation

### 1. Ciphertext-layer sync — the load-bearing choice

The sync coordinator writes substrate ciphertext to Drive verbatim. Drive never receives plaintext. The local KEK (from `MasterKeyProvider`) is never transmitted. Trust boundary: Google sees encrypted bytes only.

Substrate row format on disk:

```
SecureObjectRow.payload = envelope-encrypted ciphertext under operational KEK
```

What goes to Drive:

```
<aeat-vault>/<namespace>/<hmac_prefix>--<label>.bin
  body  = SecureObjectRow.payload verbatim
  appProperties = DriveAppProperties (per ADR-2)
```

What does NOT go to Drive: the master key, the DEKs, the operator's NIF, any plaintext payload, any keychain material.

### 2. Snapshot semantics — per-row continuous mirror, not point-in-time blob

There is no "snapshot" as a single bundled artefact in v1. The Drive mirror IS the snapshot, maintained continuously by per-record sync. Restore reads from the same per-record mirror. This is structurally simpler than a periodic-bundle approach (no manifest assembly, no snapshot-versioning, no cleanup policy) and matches the user-stated mirror requirement literally.

A future ADR amendment may add periodic point-in-time bundles (operator might want a quarterly archive); v1 does not.

### 3. Cross-machine restore — KEK escrow via passphrase

The local KEK is OS-keychain-bound. To restore on a new workstation, the operator needs the KEK. Solution: a one-time export of the KEK wrapped under a passphrase-derived key, stored in Drive alongside the mirror.

```python
class KekEscrowEnvelope(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    profile_id: str
    kdf: Literal["argon2id"]
    kdf_params: Argon2idParams              # salt, time_cost, memory_cost, parallelism
    wrap_alg: Literal["aes-256-gcm"]
    wrap_nonce: bytes
    wrapped_kek: bytes                       # KEK encrypted under passphrase-derived wrap key
    created_at: datetime
    schema_version: int = 1
```

Stored at `/aeat-vault/_sync-state/kek-escrow-<profile_id>.json`. The operator's passphrase is the only thing not in Drive; possession of the passphrase + Drive + a fresh workstation is sufficient to restore.

CLI:

```
aeat config google escrow create --profile <id>          # prompts for passphrase, uploads envelope
aeat config google escrow status --profile <id> [--format json|text] # shows envelope presence + last-rotated
aeat config google escrow rotate --profile <id>          # re-wraps with a new passphrase
aeat config google escrow delete --profile <id>          # removes; disables cross-machine restore
```

The escrow is opt-in. An operator who only ever uses one workstation can decline; they retain backup via Drive but lose the cross-machine restore path.

### 4. Manifest integrity — per-namespace HMAC manifest

The Drive mirror is the source of truth, but operators (and future auditors) need a tamper-evidence layer. Per-namespace HMAC manifest:

```python
class NamespaceManifest(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    profile_id: str
    namespace: str
    generated_at: datetime
    entries: tuple[ManifestEntry, ...]      # sorted by object_key_hmac
    manifest_hmac: bytes                     # HMAC-SHA256 of canonical-JSON(entries) under HMAC key

class ManifestEntry(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    object_key_hmac: bytes
    drive_file_id: str
    drive_revision: str
    content_sha256: bytes
    classification: SensitivityClass
    schema_version: int
    written_at: datetime
```

Stored at `/aeat-vault/_sync-state/manifest-<profile_id>-<namespace>.json`. Regenerated on every `push`/`pull` invocation that affected the namespace.

The HMAC key is derived from the master KEK + a manifest-specific HKDF context. An attacker with Drive write access but no KEK cannot forge a manifest.

### 5. Restore flows

**Full restore (cross-machine bootstrap):**

```
1. Fresh workstation: `aeat config google register --client-json <path> --profile <id>` (per ADR-0).
2. `aeat config google login --profile <id>` runs loopback OAuth flow.
3. `aeat config google restore --profile <id> --from-drive`
   a. Operator enters passphrase.
   b. Coordinator pulls /aeat-vault/_sync-state/kek-escrow-<profile_id>.json
   c. Derives wrap key (Argon2id over passphrase + kdf_params.salt).
   d. Decrypts KekEscrowEnvelope.wrapped_kek → recovered KEK.
   e. Stores recovered KEK in OS keychain via MasterKeyProvider.
   f. For each namespace on Drive: pulls every record, verifies content_sha256 against manifest, decrypts, writes into local SecureObjectRepository.
   g. Verifies manifest HMAC at end.
4. Substrate is now restored; `aeat config google sync status` reports parity.
```

**Selective restore (one namespace or one record):**

```
aeat config google restore --profile <id> --namespace <ns>
aeat config google restore --profile <id> --keys <hmac_prefix_list>
```

Same algorithm, scoped.

**Restore without escrow (passphrase lost):**

Refused. The KEK material is not recoverable from Drive content alone (ciphertext layer is the whole point). Operator must regenerate substrate state from upstream sources (re-ingest financial transactions, etc.). The ADR records this explicitly so the limitation is not surprising.

### 6. Refresh + rotation interactions

ADR-0's refresh model (lazy + clock-skew buffer + `invalid_grant` → reauth-required) handles OAuth-token lifecycle. The KEK escrow envelope has its own lifecycle:

- `escrow rotate` decrypts under old passphrase, re-wraps under new passphrase, re-uploads.
- An operator who has lost their passphrase cannot rotate; they must `escrow delete` + `escrow create` (which generates a fresh wrap; existing escrow is invalidated).

The master KEK itself can be rotated via the substrate's existing `_rotation.py` machinery; after rotation, escrow MUST be regenerated (`escrow create` again with passphrase) because the wrapped KEK in the old envelope no longer matches the substrate's operational KEK.

### 7. CLI surface — additions for ADR-3

In addition to the sync commands from ADR-2:

```
aeat config google escrow {create|status|rotate|delete} --profile <id>
aeat config google restore --profile <id> [--from-drive] [--namespace <ns>] [--keys <hmac_prefix_list>]
aeat config google manifest verify --profile <id> [--namespace <ns>]
```

`manifest verify` re-computes the per-namespace HMAC and reports tampering / drift. Read-only; no side effects.

### 8. Out of scope (deferred)

- Periodic point-in-time snapshot bundles (single archive blob per quarter, etc.) — future amendment.
- Cross-provider restore (Drive → S3 or similar) — covered when a second provider lands.
- Snapshot pruning / retention policy (none in v1; mirror is continuous and complete).

## Rationale

**Ciphertext-layer sync over plaintext-layer.** Trust boundary stays inside the operator's workstation. Google sees encrypted bytes; even a compromised OAuth token can only exfiltrate ciphertext, not plaintext data. Plaintext-layer sync would require either trusting Drive's at-rest encryption (operator-uncontrolled) or re-encrypting at the boundary with a separate snapshot KEK (extra complexity). Ciphertext-layer is the project's defence-in-depth stance.

**Continuous per-row mirror over periodic bundled snapshots.** The user-stated requirement is 100% mirror of database hierarchy and structure. Bundled snapshots are opaque to the operator and require manifest assembly + version management + cleanup. Continuous per-row mirror falls out of ADR-1/ADR-2's design directly with no extra machinery.

**KEK escrow via passphrase, opt-in.** Cross-machine restore is a real operator need (workstation replacement, dev↔prod profile separation across machines) but the master KEK is OS-keychain-bound. Wrapping the KEK under a passphrase-derived key and storing the envelope in Drive bridges that gap. Opt-in respects the operator who chooses single-workstation simplicity. The passphrase is the only piece of recovery material not in Drive; possession of (passphrase + Drive access + a workstation) is necessary and sufficient.

**Per-namespace HMAC manifest over per-snapshot global manifest.** Per-namespace scoping aligns with ADR-2's bucket layout (one mirror namespace per Drive folder). Operators who share specific namespaces with accountants can give a partial manifest. Global manifest would require regeneration on every cross-namespace change — cost scales poorly.

**Refuse-restore-without-escrow over best-effort recovery.** Encryption is meaningful only when key compromise is hard. Allowing partial recovery without KEK would weaken the security stance. Documented limitation; surfaced in `escrow status` warnings; operator chooses their resilience level explicitly via `escrow create`.

## Consequences

**Positive.**

- Drive sees only ciphertext; trust boundary is tight.
- Cross-machine restore works end-to-end with operator-controlled material (passphrase + Drive + workstation).
- Manifest HMAC gives tamper evidence at the namespace level.
- Continuous mirror eliminates "what's in the latest snapshot?" cognitive load — Drive is the snapshot.
- Substrate's existing `_rotation.py` composes cleanly: KEK rotation invalidates escrow; operator regenerates explicitly.

**Negative.**

- Cross-machine restore requires the operator remember a passphrase. Forgotten passphrase = no restore from Drive alone.
- The `_sync-state/kek-escrow-<id>.json` file in Drive is a high-value target; an attacker who compromises both the operator's Google account AND their passphrase recovers the KEK. Standard threat-model trade-off; passphrase strength is the operator's responsibility.
- Manifest regeneration on every push/pull adds one small write per affected namespace per sync run. Cost trivial; complexity bounded.

**Neutral.**

- Operator who declines escrow loses cross-machine restore but otherwise gets full mirror + tamper evidence. Reasonable position for a single-workstation operator.
- A future periodic-bundle ADR amendment can layer on top of the continuous mirror without changing ADR-3's encryption boundary or escrow design.

## References

External:
- restic encryption + integrity model — `https://restic.readthedocs.io/en/stable/100_references.html`
- Argon2id KDF parameters — `https://datatracker.ietf.org/doc/html/rfc9106`
- OWASP Key Management Cheat Sheet — `https://cheatsheetseries.owasp.org/cheatsheets/Key_Management_Cheat_Sheet.html`

Internal:
- `[[2026-05-13-google-oauth-adr]]` — bucket hierarchy + sync-state.
- `[[2026-05-12-google-oauth-adr]]` — provider abstraction.
- `[[2026-05-08-google-oauth-adr]]` — OAuth + per-profile session.
- `[[2026-05-06-google-oauth-research]]` — R2/R8 grounding.
- `[[2026-05-06-secure-persistence-enforcement-adr]]` — substrate envelope encryption.
