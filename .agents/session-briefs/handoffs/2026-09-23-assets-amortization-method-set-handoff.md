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

Run 3 was cancelled by the coordinator in favour of one final run after the
follow-ups below.

Final run 5, source `150f306c8b51ab0bf5ca27c997464d6f1ee3a340`, status proven:

- wheel sha256 `f934c5a55bb535298fb2afd89f862a8b5b502e1ef5d19f2ac48871ce3d41a669`;
  installed `__init__` sha256 `930e3f61c79bd2e3ff1f8aa11d1abd5d16bfbaab360ea739ae41f519f71b0ae7`;
- served generation `df190686044cfd783b5a597490ff0dc2ddb26c2698db7d1278dd35143ee120c2`,
  store format `cadrumo-authority-sqlite-v2`, republished from that checkout's committed
  source; the CLI forecast's generation matches;
- CLI export as in run 2 (300.00, M130 Q4 2,700.00, M100 300.00/0.00, XSD valid);
- TUI first: the lifecycle now also replaces its claim through the supersession control;
  M100/M130 540.00 count one claim;
- CLI first: after the 600.00 claim, inspect names the revision identity, a correction
  and a superseding claim leave M100 at 540.00;
- run 4 at the same build failed before any asset stage with
  `REFUSED_STORAGE_PROFILE_CUSTODY / KDF_RESOURCE_LIMIT` under host memory exhaustion;
  run 5 re-ran the journey on the unchanged wheel.

Not in wheel `f934c5a5`: the undeclared-vehicle recovery action (S10), committed after it.

## Follow-ups actioned after the first handoff

- Vehicles (`f1901758b1`, decision `2026-09-23-assets-core-vehicle-affectation-adr`): the
  transport classes charged any vehicle without an affectation test. A typed declaration
  on the revision now admits exclusive use, an RIRPF art. 22.4 listed use or accessory
  use of a non-restricted vehicle, and refuses shared, unlisted or off-book vehicles with
  their provisions. DA 18a electric-vehicle free depreciation is enrolled (2024-2025).
- LIS 103.5 is admitted at 150% of the art. 12.2 one-twentieth for reduced-size
  acquisitions, on the DGT's binding consultas and the AEAT manuals.
- Constant percentage and sum of digits are admitted for the table-listed intangibles in
  the normal modality; the simplified modality refuses them, naming the sources that
  leave the weighted table open.
- Proration stays day-count over the year's days, grounded in binding consulta
  V1978-24 (`2026-09-23-assets-core-proration-and-incentive-scope-research`); the
  manual's month fractions are illustrations.
- The undeclared-vehicle refusal names the asset and carries the catalogue action
  `operator.ledger.actividad_asset.correct_revision` to the CLI correct command and the
  TUI correction control (S10).
- CLI receipts moved to the public `actividad_asset_receipts`; acceptance oracles replace
  a hard-coded status table; brief identifiers left the harness.

## Remaining targets

- Job-creating ERD free depreciation (LIS art. 102) and renewable self-consumption free
  depreciation (LIS DA 17a, 2025 entries only): the average-workforce field
  `irpf.plantilla_media` is queued in CALENDAR's profile schema version 7; the resolver
  consumer (S11) follows its cutover, with the cross-asset investment caps (EUR 120,000 per
  unit of increase; EUR 500,000) and the DA 17a.6 documentation evidence.
- Authority republish of these registry changes after CALENDAR's v3 format cutover (S12).
- Other tax years: no Modelo 100 2026 revision exists, and `ScheduleAuthority` and claims
  are locked to tax year 2025.
- Mixed-use home facts end to end.
- Used-asset doubling in the simplified modality stays unenrolled until a source states
  whether RIRPF art. 30.1a's simplified table admits it.
- Justified amount (LIS art. 12.1.e) stays refused: no evidence contract can validate a
  caller amount. Entity regimes (LIS art. 12.3.a/d) do not apply to individuals.
- Authority currency goes stale whenever any lane edits a compiler input.
