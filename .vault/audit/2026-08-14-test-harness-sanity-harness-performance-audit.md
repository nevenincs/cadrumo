---
tags:
  - '#audit'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-10-14'
body_schema: 'body-v1'
body_hash: 'sha256:b95d13970ca84910e752d6dc16a3f9ae4fa772e74b6e99aecf7f6bd594c44653'
related: []
---
# `test-harness-sanity` audit: harness performance

## Scope and status

This historical review measured harness runtime: collection, per-worker fixed cost, and setup. It
does not certify suite correctness. Figures depend on tree, input corpus, execution mode, and
machine load; later same-day or cross-day re-measurements supersede point estimates where stated.
The audit preserves false leads and rejected optimizations so a green or faster run is not read
beyond the evidence.

## Findings

### import-time-side-effect | fixed | One eager registry load cost 3.2x on collection and 21 modules

A shared test-support module resolved a registry revision at module import, loading and validating
the registry even for importers that never needed it. Four additional test modules inherited the
cost after fixture consolidation. Deferring resolution to first use reduced collection errors from
21 to 2 and full collection from 310s to 98s. An AST sweep of 5,580 first-party modules now finds
two module-level calls, both in one already-flagged module. The import-time side-effect finding is
closed.

### per-worker-fixed-cost | open, and not this campaign's | Registry validation is recomputed by every worker

A cold authority load measured about 22s/process: roughly 5s compilation and 17s validation.
Bundled-tree compilation has a fingerprint-keyed cross-process disk cache; validation is still per
process, potentially seven CPU-minutes across 24 workers. A validation cache is safety-sensitive and
belongs to the registry owner. Later measurements distinguish cached compile work, fingerprint
walks, validation, and whole-object reconstruction; do not merge these costs into one claim.

### disproved | The bundled-tree disk cache is NOT disabled under pytest

The first probe passed the wrong directory level to `is_bundled_registry_root`. With the actual
`aeat` root, the cache is active in production and pytest as documented. The probe, not the
predicate, was wrong.

### disproved | Widening expensive fixture scope would not help

Of 342 function-scoped fixtures, 163 perform expensive setup. Registry snapshots are cached
in-process, so widening scope does not save measured work. Fresh encrypted stores are an isolation
guarantee and must remain per-test.

## Registry-load investigation

The first campaign described 66 eager calls “across the test suite”; its census had only included
`test_*.py`. Corrected population: 13 test-layer files for that part of the migration, plus 19
production direct calls that still paid the path fingerprint walk. Do not reuse the 66→2 claim as a
whole-tree count.

A warm registry load still walked path components before reaching the cache. String-prefix
normalization reduced the test-side cache-hit path, but production sites retained the walk. A later
shared prime costs about 67.9s and 1,216 MB for 4,906 modules; six workers imply roughly 7.3 GB.
Lazy priming was blocked by three gates that need a complete mapping, and putting 47 consumers on
one worker worsened the binding wall-clock measure. Neither was adopted.

The compiled registry loader is process-local; subprocesses do not share Python state. A git-archive
probe separated tree churn from loader behavior: after one cache compilation, two processes loaded
in 9.94s and 8.36s. The registry disk cache is real standalone, but later measurements show
whole-authority reconstruction, not pickle I/O, dominates warm CLI load. A compiled artifact alone
is insufficient; random access is the architectural lever.

AST-based import surgery followed three failed text anchors. Frozen before/after snapshots showed
the same failing node sets; one direct loader call remains deliberately in the disk-cache
fingerprint oracle. The migration also removed a private-import violation. Payload identity and the
cache oracle were separately checked; no production behavior change was claimed.

## Scan and gate work

### `src/cadrumo/tests` and package scans

- The shadowing dimension was scanned three times; it was reduced to one shared result. A five-pass
  drift census was similarly consolidated after proving the result was identical. - The proposed AST
  cache for all 4,903 IVA modules was rejected: retaining the trees cost 1,247 MB per worker. Fusing
  three analyses while each tree is live reduced their combined time from 76.16/63.00s to
  48.92/49.48s; each gate keeps its own assertion. Failure sets were compared, not only counts. -
  Import-hygiene work reused one package scan across 43 gates. A valid isolated memo removed the
  second 18.12s `get_codebase_keys` scan; instrumented invocation counts proved it was exercised.
  Frozen A/B runs had identical sets (5 failed, 27 passed). Earlier wall-clock samples were
  contaminated by peer load and are not the result. - Several remaining long-duration tests were
  already shared or intentionally independent. `test_tax_id_respelling_gate` reruns the census to
  test determinism; `test_tui_migration_manifest` independently checks the generated manifest.
  Caching either would compare a value to itself. Git-blob gates cannot borrow a working-tree AST
  cache. Record these as measured rule-outs.

### Locale and IVA gates

Locale honesty originally measured 125.14/126.13s because five gates parsed four catalogues
repeatedly. Per-locale memoization and `yaml.CSafeLoader` reduced same-session samples to 6.86/6.04s
after equality of all four parsed documents was checked against the pure-Python loader. This gate
deliberately parses files independently of the production renderer.

The result later decayed with input growth: `es.yml` increased from 78,096 to 86,073 lines (+10.2%)
in about 24 hours and over 40 locale commits. Re-measurements were 10.48/12.19s. The durable result
is about 125s to 11s on the then-current four-catalogue corpus, not a stable 6.04s point.

Three IVA stem gates each parsed roughly 4,903 files (15.56/18.70/22.40s). They now analyze each
tree while it is live and discard it, avoiding a 1,247 MB retained AST. Combined samples were
48.92/49.48s; this is less than a 3x reduction because analysis itself is substantial.

### Import-hygiene measurements and declined levers

One package scan now serves 43 gates, down from 248.81/262.89s to 116.04/100.93s in paired runs,
with the same seven failures by name. The first purported baseline was invalid: peer work had
already landed the helper in HEAD. The baseline was corrected to the commit parent (`a295ac3032`)
after checking file history.

Other expensive candidates were inspected before declining: the tax-id gate’s second scan is a
determinism check; the migration-manifest test independently walks/AST-parses; the
storage-provenance gate already shares state. Reuse is not justified where it removes independent
evidence.

## Fail-closed execution and measurement hazards

### xdist worker loss — critical, policy landed

Profiling twice wedged for 30 minutes; another run raised an xdist scheduler `KeyError` for `gw6`
despite the project hook resolving six workers. A five-test file once reported one failure and two
passes after a worker died, silently omitting two tests. A one-node `-n2` run produced three
failures over 892s; the golden sequence case had a 344s idle interval. Worker restart can drop or
duplicate work, not recover it safely.

The standing policy is `--max-worker-restart=0`, asserted by a gate. Worker death is terminal;
timeouts bound the two 8-wide subprocess pools and real double-build. Verify collected and executed
node counts. Later dev runs completed but exposed another case; the policy is fail-closed, not a
guarantee that the machine is healthy.

### Shared temp root and resource findings

A completed run was damaged at teardown because pytest shared a temp root; 38 third-party files were
corrupted during parallel installs. Missing files were restored and bad measurements repeated. The
shared-temp-root hazard was not fixed in this campaign.

A full resource sweep found no thread or handle leaks. Peak RSS was 4.0–5.7 GB per worker. Session
state is about 1.7 GB, around three quarters from the AST prime; another 2.3–4 GB accumulates during
testing and is not released. This is not evidence of Python-object retention. The suite is CPU-bound
rather than tail-bound; six workers matter because more workers multiply memory and contention.

The invocation counter initially mishandled positional arguments. After correction it showed why
repeats are not cost: fewer calls can still cost the same, and documentation build outputs must not
be cached. Profiling slices were contaminated by peer load; cProfile also attributed ~30s to a
string helper that measured about 1.4%. The full-suite resource conclusions come from the later
clean sweep.

A separate parallel install hit the shared pytest temp root; `dev` profiling also ran while many
peer Python processes competed. Treat wall clocks as bands. Preserve machine load,
collection/execution counts, tree snapshot, and execution mode with each result.

## Changes landed and measured

- Fail-closed xdist policy (`--max-worker-restart=0`) plus a gate; bounded subprocess-pool timeouts.
  - Profile KDF calibration once per registration: 17.44s to 2.20s, without weakening the KDF.
  Session defaults cannot cross spawn boundaries; cold CLI children were measured and do not
  calibrate. - Locale honesty gate: cache plus C YAML loader; historical 125s→6s, now about 11s as
  catalogues grew. - Import-hygiene package scan: about 249s→108s in the campaign summary; paired
  samples and identical failure membership are recorded above. - `dev/locales` C loader: 282s→137s;
  MCP tool-descriptor memo: harness slice 143s→93s; packaging wheel cohort once per module:
  204s→153s. - Ledger list-filter: refuse corpus seeding and seed once per file; 91.30s to 53.9s
  initial median. Re-measurement was 54.91, 46.22, 55.88s (median 54.91; range 46–56s). -
  Asesor/year-end/multicurrency personas: seed once and copy per test; 10/9/7 seedings per module to
  one each. - Header-cell fold uses one `translate` pass and memo; 2.50x with byte-identical output
  over 5,527 inputs. Registry directory validators return classified entries, removing 115 listings
  per compile. - Batch ingest caches endpoint availability once per URL/TTL rather than once per
  document. Connections fell 76→12 or 13 and connect time 71.5s→8.2/9.2s. Wall-clock claim was
  corrected below.

## Batch-ingest fix and final timing correction

The initial flakiness diagnosis blamed a leaked loopback endpoint; later evidence refuted it. The
cost was a failed local-LLM connection repeated for each document. Endpoint availability is now
cached per URL for 10 seconds, only after a failure; successful calls remain live. Existing URL
handling and retry semantics remain. Four loopback suites were green, including five runs of 21
tests.

Campaign close first claimed 98s→35s (-65%). Closure review remeasured 43.85/38.87/42.86s (median
42.86; -56%) and then added same-day runs 34.69/44.38s. Full sample: 34.69, 38.87, 42.86, 43.85,
44.38s. The honest claim is roughly 98s→35–44s (about -55% to -64%), with machine/session
variability. The earlier 34.30–35.79s came from one session. Structural metrics are more
reproducible: connections 76→12/13; connect time 71.5s→8.2/9.2s. Do not report a point estimate as a
stable result.

## Open decisions and measured rule-outs

### Registry architecture and worker count

The bundled registry tree can be compiled at build time and served from a plain, inspectable
artifact, but the warm load is dominated by hydration. A 23 MB compiled artifact read in 0.007s;
fingerprinting is about 0.93s and reconstructing the complete object graph about 2.9s. `aeat app
modelo list` needs roughly 60 headers but hydrates 17,526 source fragments. The architectural
proposal is a version-stable indexed database (SQLite is a candidate) with random access. Shipping a
pickle is not sufficient and has unsafe/version-fragile load semantics. This remains an
ADR/registry-owner decision.

`DEFAULT_WORKER_COUNT` remains a resource tradeoff: roughly 1.7 GB session state per worker plus
test allocations, peaking 4.0–5.7 GB. Re-measure only on a healthy tree and fixed machine
conditions. Registry validation also fails on the current tree; durations rankings are incomplete
because fast failures crowd out slow passes, though each observed slow test remains evidence.

### Combined-period gate

The gate measured 25.21s in a `-n auto` lane: 403.1 MB over 26,824 files, with regex work about
14.5–15s (roughly 70%). Merging two patterns into one alternation was equivalent over all files
(zero mismatches; 530 findings) but slower: 20.974s versus 15.078s. The corpus-enumeration memo had
no demonstrated win and was reverted; a later honesty review corrected its comparison: 26.62s
isolated was compared to the 25.21s parallel-lane figure. Proper isolated baseline median was
27.10s; the ~0.5s difference was within 1.7s run-to-run spread. Revert stands for “no measurable
benefit,” not because the memo was slower.

About 74% of the scan’s bytes are bundled third-party BOE/AEAT/manual text. Excluding it could
reduce about 25s to about 7s but narrows the gate’s subject; no unilateral exclusion was made. The
gate’s intent is to prevent repository code from writing combined periods.

Measured rule-outs retained: TOML hand-reading was slower (0.87x/0.83x across 3,000 files and five
repeats); the section-directory fold reduced listings but was slower (1.49s vs 1.29s in matched
runs); directory-scan deduplication is capped near 0.26s. Login-screen backoff is deliberate
real-time behavior; per-test KDF cost remains security work. The ECB “47% of a test” claim was
corrected to about 1–2% of the lane, but its tests still call the live ECB endpoint without the
written live-network marker. Enforcement remains open.

## Closure honesty review

A fresh-context review corrected two closure claims. First, batch-ingest wall clock is a 35–44s band
after a roughly 98s before-state, not a stable 35s/-65% point; connection counts and connect time
are the durable metrics. Second, the combined-period memo’s comparison used mismatched
parallel/isolated modes. Its reversion remains justified only as “no measurable win against a
matched baseline.”

Other campaign claims were checked. `test_ledger_list_filter` remeasurement supports a 46–56s range
with median 54.91s against 91.30s. Locale parsing remeasured 10.48/12.19s after the catalogue grew
10.2%; about 125s→11s remains the useful current comparison. Performance numbers should include
input size and execution mode; deterministic work removed (calls, connections, files, listings) is a
stronger headline than one wall-clock point.

The closure review verified the landed changes are present and supports structural completeness for
that landed work only. Open items remain decisions, not silently closed: random-access registry
architecture; worker count; combined-period scan scope; shared temp-root isolation; live ECB marker
enforcement; registry validation state; and the misplaced `cadrumo_llm_ollama_chat_url`
configuration field.
