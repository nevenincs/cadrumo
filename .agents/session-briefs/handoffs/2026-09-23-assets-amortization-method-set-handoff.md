# ASSETS-01: 2025 amortization method set, handoff

Date: 2026-09-23. Worktree `Y:/code/cadrumo-worktrees/tui-modelo`, branch `tui/modelo`.
Governing decision: `2026-09-23-assets-core-amortization-method-set-adr` (accepted);
plan `2026-09-23-assets-core-plan` (S01-S07 closed, S08 is this handoff).

## Outcome

- The asset lane is green on the current tree. The namespace-sequence tripwire
  passes at its cause (`withholding_workflow` enrolled, `faf9b18bc7`), and the TUI
  parity test drives the shared operations instead of the CLI adapter (`a2e62cdb55`).
- Every IRPF-permitted 2025 method is typed registry authority from cited
  provisions (RIS arts. 4-7, LIS arts. 12 and 103, RIRPF art. 30), carried as an
  election on the immutable asset revision:
  - linear with elected coefficient, used-asset doubling (keyed `normal:material`)
    and multi-shift (keyed by modality);
  - reduced-size acceleration (LIS 103, both modalities);
  - constant percentage, sum of digits (both orders) and an approved plan;
  - definite-life intangibles, indefinite-life intangibles and goodwill;
  - low-value free depreciation (EUR 300 unit, EUR 25,000 period cap);
  - R&D free depreciation and R&D buildings over 10 years;
  - charging infrastructure in service in 2024-2025.
- Typed, cited refusals: justified amount (LIS 12.1.e), small-enterprise
  employment free depreciation (LIS 102), renewable self-consumption (DA 17a),
  electric vehicles (DA 18a.1), entity-regime free depreciation (LIS 12.3.a/d),
  and reduced-size acceleration of indefinite-life intangibles and goodwill
  (LIS 103.5 conflicts with the AEAT manual).
- Method continuity, the from-start rule (an opening amount must attest the same
  method), the profile modality and the remaining basis are enforced at forecast,
  recomputed at record time and rechecked inside the encrypted compare-and-swap
  write. A superseding claim is forecast without the claim it replaces (CLI
  `--supersedes-claim-id`, TUI `#asset-supersedes-claim-id`), and a new claim under
  a superseded revision refuses.
- Asset errors derive from the registered `CadrumoError` hierarchy with codes and
  messages in en/es/ca/hu.

## Changed surfaces (commits)

`faf9b18bc7`, `a2e62cdb55`, `2b7fc51a78` (research, ADR, plan), `231bee9648` (election,
schedules, resolver, registry parameters, legal entries), `393da09995` (CLI help,
four locales), `5f701e6c58`, `8a373bf390` (import load targets), `d30450a7cd`
(installed method proof), `33129301ba` and `b630c0e93e` (first review fixes),
`58523f3fa7` (error hierarchy), `0d34b1534a` and `30d35de000` (receipt polling on
Windows), `f92721ce93`, `2f97378e51` and `a33f4abd40` (re-review fixes and supersession
proof), `7149baa17d` (IVA source-mesh fixture states the claimed IVA axes),
`a26691666f` (audit, ledger, plan).

## Checks

| Check | Result |
|---|---|
| Asset suites: registry resolver, domain, application, encrypted history, acceptance, TUI parity, CLI commands | 105 passed, exit 0 |
| `core/errors/tests/test_exception_base_hygiene.py` (`-m "unit or integration"`) | 10 passed, exit 0 |
| IVA profile cutover scan + investment-goods source mesh (`-m integration`) | 1 + 2 passed, exit 0 |
| Ruff, `ruff format --check`, `ty`, basedpyright strict, pyrefly on every changed file | clean |
| Global import gate (`dev.quality.import_gate`) | exit 7, globally red; zero findings sourced from asset modules. The one hard finding is `dev/acceptance/income_tax/authority.py:19`. |
| Private-module imports in asset tests and acceptance | one: the CLI's own test imports `_actividad_asset_cli` helpers from its package (the gate permits it; the CLI tests use this pattern throughout) |

## Installed proof

Run 2, source `0d34b1534a9c58efb934f3e2f02dbd3ee1e5518b`, status proven (20:29-21:07):

- wheel `cadrumo-0.5.1` sha256 `16d5e13e4c42b39e75ed3f2ca05558f238db9b863c744157ff9fe6f7b14c3d1f`;
  installed `__init__` sha256 `930e3f61c79bd2e3ff1f8aa11d1abd5d16bfbaab360ea739ae41f519f71b0ae7`, from site-packages;
- served authority generation `cadc37df7010f94a9c9690b8d5de94a12d284c4c22a8d474fdc8960fa5cf1144`,
  store format `cadrumo-authority-sqlite-v2`, republished from that checkout's committed
  source; it differs from the shared tree's `09b89639` only in compiler input. The CLI
  forecast's `authority_generation` equals the installed descriptor's;
- CLI export: constant-percentage machine forecast 300.00, M130 Q4 expenses 2,700.00,
  M100 material 300.00 and intangible 0.00, XML valid against the pinned 2025 XSD;
- TUI first: create, correct, forecast, claim, replay and hand off; a fresh TUI reads it
  back; the CLI continuation reads two revisions and M100/M130 material 540.00;
- CLI first: forecast 600.00 and claim; a fresh TUI reads it back;
- credential channel `--profile-secrets-stdin` on every installed CLI command.

Not in wheel `16d5e13e`: the superseding-claim forecast and the revision-currency
recheck (`f92721ce93`), CLI inspect `revision_id` and the installed superseding-claim
step (`2f97378e51`), and the child's receipt replace retry (`30d35de000`). Run 3 at
`2f97378e51` (wheel `6b21f168`, generation `d77f0117`) covers them; its result is
appended below.

## Remaining targets

- Other tax years: the method set is enrolled for 2025 only. No Modelo 100 2026
  revision exists to carry the parameters, and `ScheduleAuthority` and claims are
  locked to tax year 2025.
- Mixed-use home facts end to end.
- Day-count versus month proration: the accepted lifecycle ADR prorates by days/365,
  while AEAT worked examples prorate by months (EUR 733.81 against EUR 720 for the
  LIS art. 103 example). This needs a lifecycle-ADR amendment.
- Refused incentives, each with its named blocker:
  - small-enterprise employment: workforce-average facts are absent;
  - electric vehicles: vehicle scope facts are absent;
  - reduced-size acceleration of indefinite-life intangibles and goodwill: LIS 103.5
    conflicts with the AEAT manual;
  - justified amount: needs a proof-of-depreciation evidence contract.
- Ambiguous admissions left unsupported: constant percentage and sum of digits for
  intangibles, and used doubling in the simplified modality.
- Authority currency goes stale whenever any lane edits a compiler input, because
  the compiler identity hashes every non-test module under core, domain,
  application and the registry compiler and pipeline.
- The installed TUI journey proves supersession only through the screen test, not
  the installed child; the installed CLI journey carries the step.
