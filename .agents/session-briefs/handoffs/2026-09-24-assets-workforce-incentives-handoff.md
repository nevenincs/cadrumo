# ASSETS-01: workforce-conditioned incentives and final installed proof, handoff

Date: 2026-09-24. Worktree `Y:/code/cadrumo-worktrees/tui-modelo`, branch `tui/modelo`.
Governing decisions: `2026-09-23-assets-core-amortization-method-set-adr`,
`2026-09-23-assets-core-vehicle-affectation-adr` and
`2026-09-24-assets-core-average-workforce-write-path-adr` (accepted); plan
`2026-09-23-assets-core-plan` (S01-S13 closed with this handoff). Follows
`2026-09-23-assets-amortization-method-set-handoff.md`.

## Outcome

- The average workforce is a profile fact: `irpf.plantilla_media` holds one instance
  per calendar year (`year`, `average_workforce`, `state` observed or committed),
  written through `aeat config profile plantilla-media set|list|remove` and the
  profile manager's average-workforce dialog, in en/es/ca/hu.
- Job-creating ERD free depreciation (LIS art. 102.1) and renewable self-consumption
  free depreciation (LIS DA 17a) are admitted for 2025, resolved against that fact:
  - art. 102: new material elements made available in a LIS art. 101 period; the
    24-month average after the entry year's start must exceed the prior 12 months and
    the increase must hold for 24 more months; the benefiting investment is capped at
    EUR 120,000 per unit of increase, the increase truncated to two decimals;
  - DA 17a: electricity self-consumption or thermal own-use installations made
    available from 20 October 2022 and entering service in 2025, charged only in that
    period, with the workforce kept; buildings excluded; the DA 17a.6 document is typed
    and must match the installation's purpose; investment capped at EUR 500,000.
- Every declared year a workforce test used travels in the charge's source reference
  with its observed or committed state, since a committed year must be regularised if
  it is not met (LIS art. 102.4, DA 17a.7).
- Assets of the same incentive and entry year share one investment cap. An asset that
  would cross it is refused whole, and so is an installation the building code makes
  mandatory (DA 17a.5): charging part of one asset freely is not supported.
- Grounding of the 2025 DA 17a window: the consolidated LIS text, RDL 16/2025 art. 17
  (captured from BOE's article endpoint), its derogation by the Congreso
  (BOE-A-2026-2024; window closed on 27 January 2026), the AEAT note of 1 April 2026 on
  the RDL's 2025 effects, and the Renta 2025 manual. The note's list of 2025 IRPF
  measures does not name art. 17; the manual is the source that applies the principle
  to this incentive.

## Changed surfaces (commits)

Workforce fact and write path: `3fc9d65ebb`, `c2b579b053`, `3188a48a65`, `8189379517`,
`2d6038cd82`, `24828a68aa`, `3625371c48`, `60e57871e1`, `43fe343ca7`. Vehicle recovery
action: `453487ca6f`, `72935c5fc6`. Incentives (S11): `4dcbfbaed9`. Grounding: `10de093cff`,
`62364b2e73`, `495d111248`. Legal-kind vocabulary (`resolucion`, `acuerdo_parlamentario`;
`instruction` retired after the republish cleared it): `af8e4ed114`, `6d7d32e960`.

TUI fixes taken on the way: `d428e566b0` (appearance toggle and manager field door
typing), `3985855371` (Declarations heading and form edge), `2aa93b107d` and
`d16cc91852` (typed `self.app` on the account chrome), `499fef2423` (theme parity test
compares frames after scrolls land), `c169f47436` (installed-session boundary test asks
a fresh child).

## Checks

| Check | Result |
|---|---|
| Asset population: resolver, application, domain, CLI commands, TUI parity | 107 passed |
| Modelo 100 drift and parameter gates with the resolver | 65 passed |
| `inspect_authoring_candidate` at each registry change | 0 findings |
| Legal kinds: normatives, verifiers, applicability, domain legal and vocabulary tests | 236 passed |
| Ruff, `ruff format --check`, ty, basedpyright, pyrefly on every changed file | clean |
| Locale audit (`python -m dev.locales audit`) | ca, en, es, hu ok |

The orphan-parameter gate now counts the asset resolver's declared read set
(`ACTIVITY_ASSET_PARAMETER_IDS`), which the resolver enforces on every read.

## Installed proof (S12)

Source `6d7d32e960077639d50d0eb9350e81be0a9f0cd7`, isolated detached worktree, status proven
(09:16-09:35):

- wheel `cadrumo-0.5.1` sha256 `0f2f1990bd913d7919c881861ed95e22e27a38448b8959c200623ff1080dcdae`;
  installed `__init__` sha256 `930e3f61c79bd2e3ff1f8aa11d1abd5d16bfbaab360ea739ae41f519f71b0ae7`,
  from site-packages;
- served authority generation `9a430d4b324429caa97fd1b7628049da21ec4d83fedc399307987b34d34d4c7a`
  (database `2fbdfadc…`), published from that checkout's committed source; the CLI
  forecast's generation matches;
- CLI export: constant-percentage forecast 300.00, M130 Q4 expenses 2,700.00, M100
  material 300.00 and intangible 0.00, XML valid against the pinned 2025 XSD;
- CLI first: forecast 600.00 and claim; a correction and a superseding claim leave M100
  at 540.00; a fresh TUI reads it back;
- TUI first: lifecycle proven; the CLI continuation reads two revisions and M100/M130
  material 540.00; a fresh TUI reads it back;
- credential channel `--profile-secrets-stdin` on every installed CLI command.

## Remaining targets

- LIS art. 102.2, 102.3 and 102.5 (elements ordered under a works contract, self-built
  elements, leased elements with the purchase option exercised) are not modelled; the
  resolver admits only new elements made available in the reduced-size period.
- The regularisation a committed year owes when it is not met (LIS art. 102.4, DA 17a.7)
  is reported in the charge's provenance, not computed.
- DA 17a.5's proportional share above the building code's mandatory power, and splitting
  an asset across an investment cap, stay refused.
- Other tax years: no Modelo 100 2026 revision exists.
- Mixed-use home facts end to end; used-asset doubling in the simplified modality stays
  unenrolled; justified amount (LIS art. 12.1.e) stays refused; entity regimes (LIS art.
  12.3.a/d) do not apply to individuals.
- The citation blocklist still admits an `instruction` source category that no legal
  kind maps to any more.
