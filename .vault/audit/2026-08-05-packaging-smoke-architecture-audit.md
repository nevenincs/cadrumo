---
tags:
  - '#audit'
  - '#packaging-smoke-architecture'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:de26013e56b272db3611deda2cc32bed876b8c97a51d50aa635940406d0d66b2'
related:
  - "[[2026-07-20-ci-speed-redesign-adr]]"
  - "[[2026-07-15-distribution-installation-readiness-research]]"
  - "[[2026-06-28-product-packaging-research]]"
---

# `packaging-smoke-architecture` audit: `smoke lane marginal proof, flake tolerance, and evidence proportionality`

## Scope

The packaging proof surface: 45 Python modules and one PowerShell script under
`dev/packaging` totalling 17,037 lines, the 10-entry lane registry `_LANES` in
`dev/packaging/campaign.py`, its three profiles `quick` / `portable` / `ci`, and the
workflows that consume them. The question asked of every lane was marginal: name the
defect class it uniquely catches, and state whether another lane already catches it.
Verdicts are grounded in what each lane's `main()` executes, never in its docstring or
its manifest `checks=` tuple — both were found to overstate.

Enumeration method, stated so its blind spots are visible. Lanes were enumerated from
the `_LANES` registry itself, which is authoritative: `campaign.py` resolves lanes only
through that dict, and `tests/test_campaign.py` asserts every profile references only
known lanes. That enumeration is complete for campaign lanes. The wider "smoke surface"
was enumerated by the `smoke_*` filename glob, and that enumeration is NOT complete for
proof surfaces: it misses `installed_tax_oracle`, `installed_mcp_oracle`,
`serving_path_benchmark`, `constraint_effect`, and `source_preflight`, each of which
executes real proofs without carrying the `smoke_` prefix. Any claim below of the form
"no other lane catches this" is scoped to the 10 registry lanes plus the serial
installed-oracles pass, and would miss a proof living in a workflow step that invokes a
module directly rather than through the registry; two such invocation paths were found
and are recorded under the acquisition-channel finding.

A structural correction to the framing. The 13 `smoke_*` surfaces are not one
population. Six modules (`smoke_core`, `smoke_pip_core`, `smoke_sdist_core`,
`smoke_extras`, `smoke_split_install`, `smoke_browser`, plus `smoke_dev` and
`smoke_docker`) are INSTALL-FORM lanes driven by the campaign registry. Five
(`smoke_homebrew`, `smoke_mcpb`, `smoke_plugin_install`, `smoke_desktop_client`,
`smoke_scoop.ps1`) are ACQUISITION-CHANNEL lanes that are not in `_LANES` at all and are
driven by separate per-channel workflows or by an operator-run recipe. They answer
orthogonal questions and cannot be compared for redundancy against each other. Treating
them as one 13-surface set is what makes the surface look larger and more repetitive
than it is.

## Findings

### split-manifest-claims-unexecuted-checks | critical | The three-wheel lane's evidence manifest asserts two checks its `main()` never runs

`dev/packaging/smoke_split_install.py` writes a smoke manifest whose `checks=` tuple
lists twelve claims, among them `root wheel sheds split-owned corpus binaries` and
`both cadrumo-data-* companion wheels remain sub-cap (< 100 MB each)`. The functions
that perform those two checks are `_build_root_wheel` (the shedding filter) and
`_build_data_wheels` (the 100 MB assertion). Neither is called by `main()`. `main()`
takes a required `--cohort-dir` and calls `load_python_cohort`, so it consumes a
prebuilt cohort and never enters the build path. A tree-wide search for callers returns
only three test modules and one MCP test — no production caller. The manifest therefore
records a proof that did not run, in the same artifact the release evidence chain reads.
The underlying properties are not unguarded: `python_cohort._validate_wheel_contract`
enforces the 100 MB per-file cap over all three wheels during cohort build, and the
build-time shedding filter runs there too. So the risk is not an unguarded cliff; the
risk is that an evidence document asserts its own coverage inaccurately, which is the
failure mode that makes every other manifest claim unreadable. This is the checking
instrument being less scrutinised than the thing it checks.

### installed-tax-oracle-runs-three-times | high | The most expensive assertion in the campaign executes three times per run

`run_installed_tax_oracle` is invoked by `smoke_core.main()`, by
`smoke_split_install.main()`, and again by `tests/test_installed_oracles.py`, all three
of which execute in a single `portable` or `ci` campaign. The prior readiness research
measured the installed oracle at 83.3 seconds and the whole split lane at 740 seconds.
The three invocations run against the same cohort bytes, from the same source commit,
proving the same grounded Modelo 200 target. The only axis that varies is the installer
and venv shape (uv for core, pip for split), which is already independently covered by
the pip lanes without an oracle. Two of the three are redundant against the defect class
"the installed CLI cannot perform grounded tax work". The oracle pass in
`test_installed_oracles.py` correctly reuses the supplied cohort rather than rebuilding
it, so the duplication is oracle execution, not wheel construction.

### conformance-pin-is-a-substring-check | high | The claim that profiles cannot drift from the just recipes is not what the test enforces

`campaign.py`'s module docstring states "The lane registry is conformance-pinned by
`tests/test_campaign.py` so the profiles cannot silently drift from the per-lane `just`
recipes." The test that carries that name,
`test_lane_commands_match_the_per_lane_just_recipes`, asserts only that each lane's
module basename appears somewhere in the justfile text. It does not compare any
aggregate recipe's lane set against the corresponding profile. The drift it claims to
prevent is present at HEAD: the `ci` profile includes `split`, while the justfile's
`packaging-smoke-linux` aggregate lists core, pip-core, sdist-core, extras, and
browser-linux, and omits split entirely. Whether that omission is deliberate or accreted
cannot be determined from the code; either way the pin did not detect it. Docstring
prose asserting a property the code lacks is a known pattern in this tree, and here it
sits on the module that is meant to be the single source of truth for what each profile
proves.

### retry-loop-collapses-the-failure-taxonomy | medium | A bare `except Exception` makes a harness defect indistinguishable from model nondeterminism

`desktop_capture.capture_with_retries` catches bare `Exception` per attempt into an
`AttemptLog` and continues. The retry itself is defensible and is not the finding: the
nondeterministic element is whether the model emits a tool call, while the observable
being tested is deterministic — `smoke_desktop_client._perform_attempt` gates on
`len(observation.successful_calls) > baseline_calls` read from Claude Desktop's own MCP
server telemetry log, requiring a NEW call that was really served AND carried no error
marker. Retrying a nondeterministic trigger for a deterministic observable is the same
shape as polling, not a coin flip. The loop is also fail-closed: exhaustion raises, and
every attempt is retained in `attempts.json` and embedded verbatim in the emitted
evidence row, so a run that needed three tries is visibly weaker than one that needed
one. The defect is narrower. Catching bare `Exception` means an `AttributeError` in the
log parser, a `KeyError` on a changed manifest, or an `OSError` on a missing profile is
logged as a retryable attempt and retried twice more, burning two further full app
launches before failing with a diagnosis that reads like model flakiness. A
deterministic harness bug and a flaky model produce the same evidence shape. Separately,
`attempts=3` is asserted nowhere and derived nowhere — it is a default in the parser and
in the function signature with no measurement behind it. Because the count is disclosed
in the evidence, an underived 3 is a weak finding rather than a masking one, but it
should be recorded as a convention rather than presented as a threshold.

### proof-cache-blind-spot-is-the-build-backend | medium | The memoization fingerprint is sound; its one real gap is unpinned build-backend resolution

The proof cache was interrogated for the false-green class and largely exonerated. The
source fingerprint hashes `git ls-files -s` over `src`, `packaging`, `dev/packaging`,
`pyproject.toml`, and `uv.lock` — so it covers the shipped data tree (which lives under
`src/cadrumo/_data`) and the prober itself, meaning a strengthened probe invalidates
every proof minted by the weaker one. `git status --porcelain` over the same scope
returns no fingerprint when the scope is dirty, and it reports untracked and staged
changes too, so a dirty or partially-staged tree is never cached against and never
served from cache. The environment fingerprint covers OS, architecture, OS release,
exact CPython version, and exact uv version, so a toolchain bump invalidates by
construction. The residual gap: the build backend's resolved version is not in either
fingerprint. `[build-system] requires` is covered through `pyproject.toml`, but the
version actually resolved at build time is fetched fresh, so a backend release that
changes wheel contents could in principle be carried across. The blast radius is bounded
— only the per-push `quick` profile memoizes, and the full campaign's promotable
evidence rows are never memoized. A second, cosmetic gap: the comment on the
`source_preflight` step claims it "runs in every profile, quick included", but the
carried-proof path returns before reaching it. That is benign because a missing tracked
data file dirties the scope and suppresses the carry, but the comment is inaccurate.

### evidence-surface-is-fragmented-across-six-modules | medium | Six evidence modules and a 1,605-line identity verifier, with no single owner

`verify_distribution_identity.py` at 1,605 lines is the largest module in the tree, and
evidence responsibilities are spread across `evidence.py`, `evidence_release.py`,
`evidence_scrub.py`, `distribution_evidence_emit.py`, `emit_real_client_evidence.py`,
and `oracle_emit_cohort.py`. This confirms rather than rediscovers the prior readiness
research finding that the evidence contract is fragmented; that finding recorded the
same shape with real 0.2.1 execution results and it has not been consolidated since.
The fragmentation is the plausible root cause of the manifest-claims defect above: when
no module owns the question "what did this lane actually prove", each lane hand-writes
its own answer as a literal tuple, and a literal tuple cannot go stale loudly.

### campaign-job-ceilings-are-wedge-guards-not-budgets | low | The 90/120-minute ceilings do not contradict the ten-minute directive

Two premises in the review brief are false at HEAD and are recorded here so they are not
re-litigated. First, the ten-minute wall is a PER-PUSH budget. The governing ADR states
the hard budgets as "the per-push pipeline wall is at most 10 minutes; no single step
exceeds 10 minutes", and it explicitly makes the full campaign dispatch-only,
projecting its Windows leg at 11–13 minutes of real work. The
`timeout-minutes: 90/120/120/60/60/90` values in the campaign workflow are ceilings far
above projected runtime, whose stated purpose is to kill a wedged run in minutes rather
than at the six-hour default. A 120-minute ceiling on a 13-minute job is a wedge guard,
not absorbed cost, and reading it as a budget overstates the campaign's weight by
roughly an order of magnitude. Second, the same ADR already performed the per-lane
marginal-proof analysis this audit was asked to perform, and states it lane by lane;
this audit's contribution is checking that statement against what the code executes, not
producing it for the first time. On that check the ADR holds for every lane except
split, whose stated proof ("the three-wheel cohort's byte-identical source
verification") is real but is now partially duplicated by core.

### core-lane-closed-the-gap-that-justified-split | high | The behavioural insufficiency that made split a separate lane no longer exists

The prior readiness research recorded the core lane as behaviourally insufficient: a
root wheel wrote an `ok: true` core-wheel manifest and its installed CLI then failed at
work creation because the registry cited a tracked official source that lived only in
the data companion. That is the defect class that justified a separate three-wheel lane.
At HEAD the gap is closed inside core: `smoke_core.main()` resolves
`cohort.manuals_wheel` and `cohort.official_wheel`, installs the complete cohort through
`_install_wheel(..., companion_wheels=companion_wheels)`, calls
`_assert_complete_wheel_cohort`, and then runs the full installed tax oracle. Further,
every lane now routes through `python_cohort.install_targets`, which returns all three
digest-pinned targets, and through `assert_installed_cohort`, which already proves the
three versions are equal, that root metadata retains both exact companion pins, and that
each member's `direct_url` origin and digest match with the origin bytes re-hashed on
disk. So four of split's twelve manifest claims — one-transaction install, matching
origins and digests, root metadata companion requirements, and single shared version —
are performed identically by every other lane. Split's genuinely unique executed
assertions reduce to two: the joined-companion-namespace corpus probe `_COHORT_PROBE`,
and `_assert_registry_verify_runs_clean`. This is a case where a lane's justification
decayed because a peer lane absorbed it, and nothing recomputed the justification.

### per-lane-verdicts | high | Eight of ten lanes carry unique marginal proof; one merges, one needs measurement

Verdicts follow, each naming the defect class uniquely caught. `core` — KEEP; the only
lane in the `quick` profile and therefore the only per-push artifact signal, and the
only lane exercising uv's install path and its `#sha256=` fragment digest channel.
`pip-core` — KEEP; pip and uv are different resolvers that record install provenance
through different channels, which is why `_verify_direct_urls` must accept both
`archive_info.hashes` and the URL fragment; a pip-specific metadata or resolution
failure is caught nowhere else. `sdist-core` — KEEP; the only lane that builds from
source through PEP 517 isolation rather than installing a prebuilt wheel, and its own
docstring records it catching a real torn-edit sdist whose import did not resolve
against its own module. `extras` — KEEP; the only lane proving the optional dependency
closure resolves and every capability-gated import loads. `split` — MERGE-INTO-core;
its two unique probes should move to a lane that already installs the cohort, and its
duplicated tax oracle should go, but see the recommendation for why this is staged
rather than immediate. `browser` and `browser-linux` — KEEP both; they are one module
distinguished by a `--with-deps` flag, so the marginal registry cost is one dict entry
while the marginal proof is system-dependency closure on Linux. `dev` — KEEP; the only
lane proving the frozen lock materialises a working developer toolchain, an entirely
different defect class from shipped-artifact installability. `docker-core` — KEEP; the
only lane proving a clean Linux image with no host contamination, which is the one
configuration where a host-leak false green is structurally impossible. `docker-browser`
— KEEP WITH MEASUREMENT; it is the weakest lane in the set, since `browser-linux`
already proves Chromium provisioning on Linux and the container adds only system-package
closure, but it has not been measured and "it looks redundant" is not evidence.

### flat-registry-lost-the-lane-form-hierarchy | critical | The design was two lanes each carrying several forms; what shipped is ten peer lanes

This is the root cause the other findings are symptoms of, and it is visible only by
diffing design intent against what shipped. The original packaging research recommended
that the ADR "decide a release/CI gate with two lanes", and then defined the Core lane as
one lane with several FORMS: it names, under a single bullet, "the local
isolated-virtualenv form", "the plain-pip form", "the source-distribution form", "the
aggregate optional-extra form", and "the Linux container form", followed by a second
bullet for the Browser lane. The intended structure was two-level — lane, then form —
with the lane owning the invariant proof and each form varying one axis. What shipped is
a flat `_LANES` dict of ten peer entries in which every form was promoted to a top-level
lane, and nothing in the structure records that core, pip-core, sdist-core, extras, and
split are five forms of one Core lane, or that browser, browser-linux, and
docker-browser are three forms of one Browser lane.

Every other finding in this audit follows from that flattening. Because no lane owns the
invariant, each form re-asserts the lane-invariant checks independently — which is why
the five wheel forms share so much preamble, why the installed tax oracle runs three
times instead of once per lane, and why `assert_installed_cohort`'s four guarantees are
re-listed as if they were per-form proofs. Because no lane owns the question "what did
this lane prove", each form hand-writes its own `checks=` tuple as a string literal, and
a string literal cannot go stale loudly — which is how the split form came to claim two
checks it does not run. The operator's assessment of accretion is therefore correct in
substance but wrong in mechanism: the surface did not accrete redundant PROOFS, it
accreted redundant STRUCTURE around proofs that are mostly individually justified. Eight
of ten lanes carry real marginal proof, and yet the registry is still the wrong shape.

This also answers the parameterisation question directly. The five wheel lanes ARE
expressible as one parameterised lane over the axes {installer: uv|pip, artifact:
wheel|sdist, extras: none|all|browser, cohort assertions: base|joined-namespace}, and
that is not a novel proposal — it is the design the research described before the
flattening. Note that the accepted CI-speed ADR already began correcting this from the
other end: the `quick` profile is a one-lane per-push gate, which is exactly the small
gate the original intent implies, with the larger set moved to dispatch cadence. The
profile mechanism it introduced is the natural home for the lane/form distinction.

### gh-retry-is-sound-but-inverts-its-retry-classes | low | The transport retry cannot mask a failure, but it retries the least-retryable class and not the most

`evidence_release.run_gh_with_retry` was checked for the masking class and cleared. It
retries on `EvidenceReleaseError`, sleeps with linear backoff, and on exhaustion raises a
message carrying the last error's stderr verbatim, so an authorization failure surfaces
with its diagnostic intact rather than being swallowed. The trust-critical calls are also
correctly excluded from retry: `list_releases` and the exactly-one-draft guard call the
bare `_run_gh`, so only asset download is retried. That split is right — retry the
transport, never the authorization or the trust check.

Two inversions are worth recording. First, `_run_gh` raises `EvidenceReleaseError` for
ANY non-zero exit, so a deterministic 401 or 403 is retried three times with escalating
sleeps before failing; the failure is not hidden, only delayed, which makes this a
cosmetic defect rather than a masking one. Second and more oddly, `_run_gh` passes a
subprocess `timeout`, and a `subprocess.TimeoutExpired` is not an `EvidenceReleaseError`,
so it propagates immediately without any retry. The most retryable failure class — a
transport timeout — is the one class this retry helper does not cover, while the least
retryable class is covered. Narrowing the retry to genuine transient conditions and
including the timeout would fix both ends at once.

## Recommendations

Fix the split manifest's false claims first, because it is the cheapest change with the
largest honesty return and it is not contentious. Either move the shedding and sub-cap
assertions onto the consumed cohort so `main()` genuinely performs them, or remove both
strings from the `checks=` tuple and let `python_cohort._validate_wheel_contract` own
them at build time. Prefer the second: the properties are already enforced there over
all three wheels, so re-performing them per lane is the duplication this campaign
exists to remove. Then sweep every other lane's `checks=` tuple against its `main()`
for the same class of overstatement; this audit verified the tuple against the executed
body only for split and for the five wheel lanes.

Remove the duplicated `run_installed_tax_oracle` call from `smoke_split_install`,
keeping the one in `smoke_core` and the one in the serial installed-oracles pass. This
is unambiguous: the same oracle, the same cohort, the same target, and the pip-installer
axis it would otherwise justify is already covered by `pip-core` without an oracle.

Replace the substring conformance pin with a real one. `test_campaign.py` should parse
the justfile's aggregate recipes and assert their lane sets equal the corresponding
profile tuples, then the `packaging-smoke-linux` / `ci` split divergence must be
resolved deliberately in one direction. Until that pin exists, the campaign docstring's
"cannot silently drift" sentence should be corrected to describe what is actually
enforced.

Narrow `capture_with_retries` to catch only the retryable class — the module's own
`DesktopCaptureError` plus transport and timeout errors — and let programming errors
propagate on the first attempt. Record `attempts=3` in the docstring as an unmeasured
convention rather than a derived threshold, and consider surfacing first-attempt success
rate in the evidence row so the model's reliability becomes a measured series instead of
a per-run anecdote.

Add the resolved build-backend version to the proof cache's environment fingerprint, and
correct the `source_preflight` comment that claims it runs in every profile.

Two recommendations are architecturally significant and must not be actioned from this
audit. Retiring `smoke_split_install` as a standalone lane is a decision a follow-on ADR
must make, because it trades a 740-second lane against relocating two probes into a lane
that currently proves a different installer path, and because the lane's justification
decayed rather than being designed away — the correct record is a decision, not a
cleanup commit. Consolidating the six evidence modules behind a single owner for "what
did this lane prove" is likewise an ADR-scale decision; the manifest-claims defect is
its symptom and should be fixed independently and immediately rather than waiting on the
consolidation.

Narrow the gh retry to genuinely transient conditions and bring the subprocess timeout
inside it, so the helper stops retrying deterministic authorization failures and starts
retrying the one class it currently drops.

The structural recommendation, and the one that should shape the follow-on ADR: restore
the lane/form hierarchy rather than delete lanes. The correct target is not a shorter
`_LANES` list but a two-level registry in which a lane owns its invariant proof and its
forms vary one axis each — Core lane over {uv-wheel, pip-wheel, pip-sdist, pip-extras,
pip-joined-cohort}, Browser lane over {host, host-with-deps, container}, with `dev` and
`docker-core` standing alone because they prove genuinely separate classes. Under that
shape the lane-invariant checks (`assert_installed_cohort`'s four guarantees, the
installed tax oracle, the wheel data payload and metadata assertions) are asserted once
per lane rather than once per form, the `checks=` tuple becomes derived from what the
lane and form actually executed rather than a hand-written literal, and the split
question dissolves — split stops being a lane to retire and becomes a form of the Core
lane contributing exactly its two unique probes. This reframes the earlier
merge-into-core verdict: the merge is right, but the reason is structural rather than
economic, and it should land as a hierarchy restoration rather than a deletion.

That ADR must decide two things this audit deliberately does not: whether the lane/form
hierarchy is worth the migration against a surface that is, proof-for-proof, mostly
justified; and whether the six evidence modules consolidate behind a single owner for
"what did this run prove", which is the same root cause seen from the evidence side. The
manifest-claims defect is a symptom of both and should be fixed immediately and
independently rather than waiting on either decision.

Nothing here should be read as unblocking distribution publication, which is held behind
separate structural blockers. Every recommendation above is scoped to the proof surface
and none of them changes what is published or when.
