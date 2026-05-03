# contributing

This project ships through a Kent-first delivery model. Before opening an issue or a PR, read this document end-to-end.

## the rule that overrides every other rule

**Every issue answers one question: what can Kent do at the end of this issue that he could not do at the start?** If an issue is pure infrastructure, it must cite the Kent capability it ultimately unblocks. If a PR does not move any Kent capability forward (directly or transitively), pause and re-examine.

"Kent" is our target user — a Spanish autónomo who needs to file his tax returns. See [`.vault/audit/2026-04-17-kent-ux-journey-audit.md`](.vault/audit/2026-04-17-kent-ux-journey-audit.md) for who Kent is.

## Definition of Ready (DoR)

An issue gets the `ready` label when:

- Title leads with a Kent capability or cites the capability it unblocks
- Acceptance criteria are **Kent-observable** (at least one criterion a non-developer could verify)
- Dependencies are explicit (`blocks` / `depends on` issue refs)
- `priority:P0–P3` label set
- `effort:XS–XL` label set
- `parallel-safe` or `parallel-risky` label set
- No `needs-design` flag remaining (an ADR must exist if the change is non-trivial)

## Definition of Done (DoD)

A PR closing an issue must satisfy all of:

- Every DoR criterion still holds
- Tests exercise the Kent-observable acceptance criterion
- Charter [#197](https://github.com/wgergely/aeat/issues/197) and [#432](https://github.com/wgergely/aeat/issues/432) compliance (no executable AEAT write path)
- No regression against Kent's journey (add a `regression-prevention` test if the PR closes a Kent wall)
- README / getting-started / ROADMAP.md updated when user-facing
- Coverage matrices under `docs/coverage/` updated when relevant
- Conventional commit on every commit; release-please note if user-facing

## priority and effort

| Label | Meaning |
|---|---|
| `priority:P0-blocker` | Blocks a Kent success moment; worked before lower priorities |
| `priority:P1-high` | Significant Kent capability; works in the current milestone |
| `priority:P2-medium` | Enhances a capability; current or next milestone |
| `priority:P3-low` | Nice-to-have |
| `effort:XS` | <1 hour |
| `effort:S` | 1–4 hours |
| `effort:M` | 1 day |
| `effort:L` | 2–3 days |
| `effort:XL` | 1 week or more |

Issues `effort:XL` should usually be EPICs with child sub-issues.

## parallel safety

| Label | Meaning |
|---|---|
| `parallel-safe` | Can be worked concurrently with any other `parallel-safe` issue |
| `parallel-risky` | Touches shared modules — coordinate with any overlapping `parallel-risky` issue |

## audit cadence

| Frequency | Scope | Umbrella |
|---|---|---|
| Monthly | Feature + modelo coverage | [#241](https://github.com/wgergely/aeat/issues/241) |
| Monthly | Code duplication sweep | [#242](https://github.com/wgergely/aeat/issues/242) |
| Monthly | Code health (complexity, coverage, deps, dead code) | [#243](https://github.com/wgergely/aeat/issues/243) |
| Monthly | Kent-journey regression | [#244](https://github.com/wgergely/aeat/issues/244) |
| Quarterly | Charter compliance | [#245](https://github.com/wgergely/aeat/issues/245) |
| Quarterly | Architectural + ADR review | [#246](https://github.com/wgergely/aeat/issues/246) |

Per-milestone gate: see [#109](https://github.com/wgergely/aeat/issues/109) methodology and [#110](https://github.com/wgergely/aeat/issues/110)–[#113](https://github.com/wgergely/aeat/issues/113) per-milestone instances.

## delegation

The repository runs on up to six parallel agent slots across Claude, Codex, Gemini.

- Any agent may pick up any `ready` + `parallel-safe` issue without owner assignment.
- `parallel-risky` issues must be serialised — coordinate before starting.
- `needs-design` means an ADR (`.vault/adr/`) must land before implementation.
- Handover prompts follow the canonical template (see project memory).

## fetching the AEAT certificate (live tests)

The `live_read` test surface needs a real PKCS#12 client certificate
issued by FNMT (or another AEAT-recognised CA). When the certificate
lives in your Google Drive, fetch it through the project's just chain:

Supported Google auth paths in this repo are:

- Desktop OAuth local-dev (default)
- Service-account automation

This contributor flow uses the Desktop OAuth local-dev path because the
certificate fetch reads from Drive. `aeat auth init --path
desktop-oauth-local-dev --json <path>` is what writes
`GOOGLE_AUTH_PATH`, completes the Google Workspace MCP contract, and
prepares the repo-local MCP cache directory. `just gcloud-auth` is now
only the optional ADC-backed compatibility step for legacy wrapper
flows. The legacy
`just gsuite-oauth-client` recipe remains a wrapper around
`uv run aeat auth init`.

```bash
just env-setup                              # creates env/.env from .env.example
# Edit env/.env and set GOOGLE_CLOUD_PROJECT to your GCP project id
uv run aeat auth init --path desktop-oauth-local-dev
uv run aeat auth init --path desktop-oauth-local-dev --json <path>
uv run aeat doctor                          # verifies the Desktop OAuth path
just gcloud-auth                            # optional ADC compatibility step for legacy wrappers
just aeat-cert-fetch <DRIVE_FILENAME.p12>   # fetches into credentials/
```

If `aeat doctor` later reports a required `Drive round-trip` failure,
the Desktop OAuth token on disk is stale for Drive-backed work. Repair
it with:

```bash
uv run aeat auth init --path desktop-oauth-local-dev --reset-cli-token
```

The recipe writes `credentials/<DRIVE_FILENAME.p12>` (gitignored) and
prints the absolute path. Then complete `env/.env` with:

```
AEAT_LIVE_TESTS_ENABLED=1
AEAT_CERTIFICATE_PATH=<absolute path printed by aeat-cert-fetch>
AEAT_CERTIFICATE_PASSWORD_SECRET=<your cert passphrase>
```

The password is a secret — `env/.env` is gitignored; never commit it.
Verify the live-read path with `just test-live-read`.

`aeat-cert-fetch` is a thin wrapper over `aeat drive fetch <name>`,
which fails fast if the Drive name has zero or multiple matches and
refuses to overwrite an existing file without `--overwrite`.

## releases

Releases run **locally**, never in CI. Run `just release` for a dry-run preview, `just release-apply` to bump + tag. Conventional commits drive the CHANGELOG. See `RELEASING.md` and [`.vault/adr/2026-04-12-release-please-adr.md`](.vault/adr/2026-04-12-release-please-adr.md).

## the supreme authorities

- Product direction: charter [#197](https://github.com/wgergely/aeat/issues/197) — produce, verify, export; Kent uploads via the AEAT portal himself
- Safety: charter [#116](https://github.com/wgergely/aeat/issues/116) — live AEAT submission is permanently forbidden
- Delivery process: PM charter [#240](https://github.com/wgergely/aeat/issues/240)

If an issue's scope conflicts with a charter, the charter wins.
