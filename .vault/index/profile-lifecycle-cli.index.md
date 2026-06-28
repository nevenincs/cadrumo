---
generated: true
tags:
  - '#index'
  - '#profile-lifecycle-cli'
date: '2026-06-15'
modified: '2026-06-15'
related:
  - '[[2026-05-16-profile-lifecycle-cli-P02-S18]]'
  - '[[2026-05-16-profile-lifecycle-cli-P02-S19]]'
  - '[[2026-05-16-profile-lifecycle-cli-P02-S20]]'
  - '[[2026-05-16-profile-lifecycle-cli-P02-S21]]'
  - '[[2026-05-16-profile-lifecycle-cli-P02-S22]]'
  - '[[2026-05-16-profile-lifecycle-cli-P02-S23]]'
  - '[[2026-05-16-profile-lifecycle-cli-P02-S24]]'
  - '[[2026-05-16-profile-lifecycle-cli-P02-S25]]'
  - '[[2026-05-16-profile-lifecycle-cli-P02-S26]]'
  - '[[2026-05-16-profile-lifecycle-cli-P03-S27]]'
  - '[[2026-05-16-profile-lifecycle-cli-P03-S28]]'
  - '[[2026-05-16-profile-lifecycle-cli-P03-S29]]'
  - '[[2026-05-16-profile-lifecycle-cli-P03-S30]]'
  - '[[2026-05-16-profile-lifecycle-cli-P03-S31]]'
  - '[[2026-05-16-profile-lifecycle-cli-P03-S32]]'
  - '[[2026-05-16-profile-lifecycle-cli-P03-S33]]'
  - '[[2026-05-16-profile-lifecycle-cli-P04-S34]]'
  - '[[2026-05-16-profile-lifecycle-cli-P04-S35]]'
  - '[[2026-05-16-profile-lifecycle-cli-P04-S36]]'
  - '[[2026-05-16-profile-lifecycle-cli-P04-S37]]'
  - '[[2026-05-16-profile-lifecycle-cli-P04-S38]]'
  - '[[2026-05-16-profile-lifecycle-cli-P04-S39]]'
  - '[[2026-05-16-profile-lifecycle-cli-P05-S40]]'
  - '[[2026-05-16-profile-lifecycle-cli-P05-S41]]'
  - '[[2026-05-16-profile-lifecycle-cli-P05-S42]]'
  - '[[2026-05-16-profile-lifecycle-cli-P05-S43]]'
  - '[[2026-05-16-profile-lifecycle-cli-P05-S44]]'
  - '[[2026-05-16-profile-lifecycle-cli-P05-S45]]'
  - '[[2026-05-16-profile-lifecycle-cli-P05-S46]]'
  - '[[2026-05-16-profile-lifecycle-cli-P06-S47]]'
  - '[[2026-05-16-profile-lifecycle-cli-P06-S48]]'
  - '[[2026-05-16-profile-lifecycle-cli-P06-S49]]'
  - '[[2026-05-16-profile-lifecycle-cli-P06-S50]]'
  - '[[2026-05-16-profile-lifecycle-cli-P06-S51]]'
  - '[[2026-05-16-profile-lifecycle-cli-P06-S52]]'
  - '[[2026-05-16-profile-lifecycle-cli-P06-S53]]'
  - '[[2026-05-16-profile-lifecycle-cli-P06-S54]]'
  - '[[2026-05-16-profile-lifecycle-cli-P06-S55]]'
  - '[[2026-05-16-profile-lifecycle-cli-P06-S56]]'
  - '[[2026-05-16-profile-lifecycle-cli-P06-S57]]'
  - '[[2026-05-16-profile-lifecycle-cli-P06-S58]]'
  - '[[2026-05-16-profile-lifecycle-cli-P07-S59]]'
  - '[[2026-05-16-profile-lifecycle-cli-P07-S60]]'
  - '[[2026-05-16-profile-lifecycle-cli-P07-S61]]'
  - '[[2026-05-16-profile-lifecycle-cli-P08-S62]]'
  - '[[2026-05-16-profile-lifecycle-cli-P08-S63]]'
  - '[[2026-05-16-profile-lifecycle-cli-P08-S64]]'
  - '[[2026-05-16-profile-lifecycle-cli-P08-S65]]'
  - '[[2026-05-16-profile-lifecycle-cli-P08-S66]]'
  - '[[2026-05-16-profile-lifecycle-cli-P08-S67]]'
  - '[[2026-05-16-profile-lifecycle-cli-P08-S68]]'
  - '[[2026-05-16-profile-lifecycle-cli-P08-S69]]'
  - '[[2026-05-16-profile-lifecycle-cli-p01-s01-exec]]'
  - '[[2026-05-16-profile-lifecycle-cli-p01-s02-exec]]'
  - '[[2026-05-16-profile-lifecycle-cli-p01-s03-exec]]'
  - '[[2026-05-16-profile-lifecycle-cli-p01-s04-exec]]'
  - '[[2026-05-16-profile-lifecycle-cli-p01-s10-exec]]'
  - '[[2026-05-16-profile-lifecycle-cli-p01-s11-exec]]'
  - '[[2026-05-16-profile-lifecycle-cli-p02-s12-exec]]'
  - '[[2026-05-16-profile-lifecycle-cli-p02-s13-exec]]'
  - '[[2026-05-16-profile-lifecycle-cli-p02-s14-exec]]'
  - '[[2026-05-16-profile-lifecycle-cli-p02-s15-exec]]'
  - '[[2026-05-16-profile-lifecycle-cli-p02-s16-exec]]'
  - '[[2026-05-16-profile-lifecycle-cli-p02-s17-exec]]'
  - '[[2026-05-16-profile-lifecycle-cli-plan]]'
  - '[[2026-06-04-profile-lifecycle-cli-adr]]'
  - '[[2026-06-04-profile-lifecycle-cli-research]]'
---

# `profile-lifecycle-cli` feature index

Auto-generated index of all documents tagged with `#profile-lifecycle-cli`.

## Documents

### adr

- `2026-06-04-profile-lifecycle-cli-adr` - `profile-lifecycle-cli` adr: `warning closeout authority alignment` | (**status:** `accepted`)  ## Problem Statement  The vault lifecycle checks reported this feature as having execution records or a plan without an explicit same-feature ADR authority record. That weakens semantic discovery because developer briefings can find work evidence without a local decision anchor.  ## Considerations  This ADR is a curation alignment record, not a new implementation mandate. It preserves historical execution context while giving the feature a stable decision node for vault health and semantic search.  ## Constraints  The pass is vault-only. No application code, tests, registry data, or runtime behavior is changed. Body wiki-links are avoided; frontmatter related fields carry the required navigation edges.  ## Implementation  Treat the linked research record as the evidence bridge for this warning closeout. Existing plans and execution records remain historical sources; this ADR exists so the feature has an explicit authority node.  ## Rationale  A same-feature ADR avoids warning-level ambiguity in the vault graph and reduces the risk that future agents brief from orphaned execution records without an authority source.  ## Consequences  Feature lifecycle checks can resolve a local ADR for this feature. Later feature-specific decisions may supersede this curation ADR if they update frontmatter links on plans, research, and indexes.  ## Codification candidates  No project rule is promoted from this warning closeout record.

### exec

- `2026-05-16-profile-lifecycle-cli-p01-s01-exec` - `profile-lifecycle-cli` `P01.S01`
- `2026-05-16-profile-lifecycle-cli-p01-s02-exec` - `profile-lifecycle-cli` `P01.S02`
- `2026-05-16-profile-lifecycle-cli-p01-s03-exec` - `profile-lifecycle-cli` `P01.S03`
- `2026-05-16-profile-lifecycle-cli-p01-s04-exec` - `profile-lifecycle-cli` `P01.S04`
- `2026-05-16-profile-lifecycle-cli-p01-s10-exec` - `profile-lifecycle-cli` `P01.S10`
- `2026-05-16-profile-lifecycle-cli-p01-s11-exec` - `profile-lifecycle-cli` `P01.S11`
- `2026-05-16-profile-lifecycle-cli-p02-s12-exec` - `profile-lifecycle-cli` `P02.S12`
- `2026-05-16-profile-lifecycle-cli-p02-s13-exec` - `profile-lifecycle-cli` `P02.S13`
- `2026-05-16-profile-lifecycle-cli-p02-s14-exec` - `profile-lifecycle-cli` `P02.S14`
- `2026-05-16-profile-lifecycle-cli-p02-s15-exec` - `profile-lifecycle-cli` `P02.S15`
- `2026-05-16-profile-lifecycle-cli-p02-s16-exec` - `profile-lifecycle-cli` `P02.S16`
- `2026-05-16-profile-lifecycle-cli-p02-s17-exec` - `profile-lifecycle-cli` `P02.S17`
- `2026-05-16-profile-lifecycle-cli-P02-S18` - delete the `"default"` literal fall-through in the wizard
- `2026-05-16-profile-lifecycle-cli-P02-S19` - call `provision_bucket_directory` and `write_manifest` from `initialize_workspace` so profile creation provisions the per-bucket directory tree atomically
- `2026-05-16-profile-lifecycle-cli-P02-S20` - thread per-bucket SQLite URL through `create_engine_from_settings` from the resolved `BucketPaths.db_dir`
- `2026-05-16-profile-lifecycle-cli-P02-S21` - wire the local blob-store factory to read its root from `BucketPaths.blobs_dir`
- `2026-05-16-profile-lifecycle-cli-P02-S22` - add the startup guard that raises `LegacyLayoutDetectedError` when `<aeat-root>/var/` exists and `<aeat-root>/buckets/` does not
- `2026-05-16-profile-lifecycle-cli-P02-S23` - precedence-chain test (flag wins over env, env wins over pointer, pointer wins over absence)
- `2026-05-16-profile-lifecycle-cli-P02-S24` - regression test asserting the pointer-file integration writes on profile create
- `2026-05-16-profile-lifecycle-cli-P02-S25` - regression test asserting `initialize_workspace` provisions the bucket directory tree and writes the manifest
- `2026-05-16-profile-lifecycle-cli-P02-S26` - legacy-layout refusal test (run startup against a synthesised legacy `var/` tree, assert `LegacyLayoutDetectedError`)
- `2026-05-16-profile-lifecycle-cli-P03-S27` - rewire `_resolve_master_key` to read from the active `BucketSession` instead of `get_master_key_provider().get_master_key()`
- `2026-05-16-profile-lifecycle-cli-P03-S28` - delete the `_lock` / `_cache` `ClassVar`s from `KeyringMasterKeyProvider`
- `2026-05-16-profile-lifecycle-cli-P03-S29` - delete the `_lock` / `_cached_passphrase` / `_cached_master_key` `ClassVar`s from `FileFallbackMasterKeyProvider`
- `2026-05-16-profile-lifecycle-cli-P03-S30` - delete the `_purge_caches_at_exit` atexit hook now that the ClassVar caches are gone
- `2026-05-16-profile-lifecycle-cli-P03-S31` - register an atexit hook that closes any open `BucketSession`
- `2026-05-16-profile-lifecycle-cli-P03-S32` - regression test asserting `_encrypted_columns` decrypt path reads through `BucketSession`
- `2026-05-16-profile-lifecycle-cli-P03-S33` - AST-guard test asserting `KeyringMasterKeyProvider` and `FileFallbackMasterKeyProvider` carry zero `ClassVar` state
- `2026-05-16-profile-lifecycle-cli-P04-S34` - remove the `dict[str, object]` union arm from `WorkflowState.invoice_reviews`
- `2026-05-16-profile-lifecycle-cli-P04-S35` - remove the `dict[str, object]` union arm from `WorkflowState.ledger_reviews`
- `2026-05-16-profile-lifecycle-cli-P04-S36` - add public `iter_records()` to the user-profile repository and replace the private `_objects` access in `_iter_profiles`
- `2026-05-16-profile-lifecycle-cli-P04-S37` - replace the private access call site
- `2026-05-16-profile-lifecycle-cli-P04-S38` - anti-tautology probe test (save profile, mutate encrypted payload, reload, assert `ValidationError` or strict inequality)
- `2026-05-16-profile-lifecycle-cli-P04-S39` - extend the existing `WorkflowState` roundtrip to populate `invoice_reviews` and `ledger_reviews` with non-default values
- `2026-05-16-profile-lifecycle-cli-P05-S40` - rename `aeat config init` to `aeat config profile create NAME`
- `2026-05-16-profile-lifecycle-cli-P05-S41` - rename `aeat config profile use` to `switch`
- `2026-05-16-profile-lifecycle-cli-P05-S42` - rename `aeat config profile remove` to `delete`
- `2026-05-16-profile-lifecycle-cli-P05-S43` - merge `view` and `status` into one `show` verb that defaults to the active profile and emits a readiness header
- `2026-05-16-profile-lifecycle-cli-P05-S44` - delete `validate` and `preflight` verbs
- `2026-05-16-profile-lifecycle-cli-P05-S45` - delete `get` / `set` / `unset` verbs from the operator CLI
- `2026-05-16-profile-lifecycle-cli-P05-S46` - rewrite the top-level `_config_help` summary to advertise every operator profile verb
- `2026-05-16-profile-lifecycle-cli-P06-S47` - add `BootstrapAlreadyCompleteError` typed error and register it
- `2026-05-16-profile-lifecycle-cli-P06-S48` - add `ProfileNameCollisionError` typed error and register it
- `2026-05-16-profile-lifecycle-cli-P06-S49` - add `ProfileLockedError` typed error and register it
- `2026-05-16-profile-lifecycle-cli-P06-S50` - add `rename(profile_id, new_name)` to the lifecycle service
- `2026-05-16-profile-lifecycle-cli-P06-S51` - add `aeat config profile rename NAME NEW` Typer verb
- `2026-05-16-profile-lifecycle-cli-P06-S52` - add `aeat config profile edit [NAME]` Typer verb that re-runs the wizard against an existing record
- `2026-05-16-profile-lifecycle-cli-P06-S53` - add `export(profile_id) -> UserProfilePortableExport` plus archive sealer to the lifecycle service
- `2026-05-16-profile-lifecycle-cli-P06-S54` - add `import_archive(path) -> ProfileId` plus archive validator to the lifecycle service
- `2026-05-16-profile-lifecycle-cli-P06-S55` - add `aeat config profile export [NAME] --to FILE` and `aeat config profile import FILE` Typer verbs
- `2026-05-16-profile-lifecycle-cli-P06-S56` - add `aeat config profile logout` Typer verb that closes the active `BucketSession`
- `2026-05-16-profile-lifecycle-cli-P06-S57` - replace `duplicate` Typer verb with `create --copy-from NAME` flag landing in the same commit as `duplicate` deletes
- `2026-05-16-profile-lifecycle-cli-P06-S58` - tests for rename / edit / export / import / logout / copy-from happy paths and refusals
- `2026-05-16-profile-lifecycle-cli-P07-S59` - remove the `profile_override` parameter from `resolve_active_profile`
- `2026-05-16-profile-lifecycle-cli-P07-S60` - remove the `--profile` flag from every `aeat config google` verb
- `2026-05-16-profile-lifecycle-cli-P07-S61` - run the locale scaffold + audit across es/en/ca/hu for every renamed string
- `2026-05-16-profile-lifecycle-cli-P08-S62` - delete the `aeat config repair list NAMESPACE` operator verb
- `2026-05-16-profile-lifecycle-cli-P08-S63` - add `python -m aeat.diagnostics` module entrypoint with `profile get / set / unset / activity` and `secure-objects list` subcommands
- `2026-05-16-profile-lifecycle-cli-P08-S64` - smoke tests for the diagnostics entrypoint
- `2026-05-16-profile-lifecycle-cli-P08-S65` - run the full pytest suite and resolve every failure
- `2026-05-16-profile-lifecycle-cli-P08-S66` - run `ruff check` and resolve every diagnostic
- `2026-05-16-profile-lifecycle-cli-P08-S67` - run `mypy` and resolve every diagnostic
- `2026-05-16-profile-lifecycle-cli-P08-S68` - run the vault audit and confirm no new errors
- `2026-05-16-profile-lifecycle-cli-P08-S69` - run a manual operator smoke against a fresh root and capture the transcript

### plan

- `2026-05-16-profile-lifecycle-cli-plan` - `profile-lifecycle-cli` plan

### research

- `2026-06-04-profile-lifecycle-cli-research` - `profile-lifecycle-cli` research: `warning closeout research grounding`  ## Question  Which vault lifecycle warning needs an explicit research grounding edge so future semantic search and developer briefings do not treat execution evidence as orphaned context?  ## Findings  This note is a vault-curation closeout record. It does not introduce new runtime behavior, change an accepted architecture, or supersede an existing feature-specific research note.  The warning pass found that this feature needed an explicit research node or a plan-to-research edge. The related frontmatter carries the navigable authority chain; body wiki-links are intentionally avoided to keep body-link hygiene clean.  Semantic vault search was used before creating this bridge. Where older plan, audit, or execution records already existed, this note makes that evidence discoverable without rewriting the historical documents.  ## Recommendation  Keep this research bridge until a deeper feature-specific research record supersedes it. Any future supersession should update the related frontmatter on the linked ADR, plan, and this research record.
