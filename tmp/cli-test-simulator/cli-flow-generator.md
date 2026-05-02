# CLI Flow Generator System V5

Status: recovered-comment generator, not approved for implementation.

The generator converts scenario facts into granular AEAT CLI command tapes. It
must not generate emotional commands, developer-shaped commands, or terms
rejected in the approval comments.

## Vocabulary Contract

| Rule | Decision |
| --- | --- |
| Root | Generate `aeat setup` for prerequisites and `aeat app` for operational tax work. |
| Help | Generate `--help`, not bare help. |
| Setup auth | Generate provider configuration, login, status, whoami, logout. |
| Setup profile | Generate schema-backed profile key commands. |
| App domains | Generate `overview`, `ledger`, `invoice`, and `declaration`. |
| Discovery | Generate `overview --calendar` and `overview --period`. |
| Ledger import | Generate `ledger import PATH --provider PROVIDER`; add `--verify` for diagnostics. |
| Original file check | Generate `ledger import PATH --provider PROVIDER --verify --original PATH`. |
| Ledger inspection | Generate `ledger list` and `ledger show`. |
| Ledger edit | Generate `ledger edit --id ROW --set column=value --reason REASON`. |
| Skip state | Generate `ledger edit --id ROW --skip true|false --reason REASON`. |
| Split state | Generate normalized `ledger split --business SHARE --personal SHARE`; shares must add to `1.0`. |
| Invoice | Generate singular `app invoice` commands with `--kind issued|received` where importing. |
| Calculation | Generate `declaration calculate`, `review`, `status`, `edit`, and `approve`. |
| Output | Generate `validate`, `preview`, `export --output`, and `verify --format json --output`. |
| Corrective declaration | Generate the same declaration commands with `--amend --id JUSTIFICANTE_ID`. |
| State | Do not generate user-facing session/workspace save-load commands. |

## Rejected Output

The generator must never emit these canonical commands:

```text
aeat app ledger import verify ...
aeat app ledger import gaps ...
aeat app ledger import duplicates ...
aeat app ledger import exclude ...
aeat app ledger import restore ...
aeat app ledger exclude ...
aeat app ledger restore ...
aeat app declaration amendment create ...
aeat app declaration verify --export PATH
--csv-code
--amendment
```

## Input Facts

```text
profile:
  taxpayer: autonomo
  activity: design
  bank: n26
  setup_state: missing | partial | ready
  auth_provider: missing | certificate | clave_movil
  profile_keys: missing | partial | complete

scenario:
  as_of: DATE
  scope: period | year_to_date | multi_period | multi_year
  filing_history: none | partial | imported | uncertain
  deadline_state: current | due | overdue | after_period_end | unknown

ledger:
  imports: missing | invalid | partial | complete | duplicate | wrong_account
  original_files: missing | present
  record_review: none | partial | messy
  mixed_payments: true | false
  personal_imports: true | false
  document_links: missing | partial | complete

invoice:
  issued: missing | partial | complete
  received: missing | partial | complete
  metadata: missing | partial | complete
  matching: none | partial | messy
  retention_or_iva_category: required | not_required | unknown

declaration:
  modelos: unknown | discovered | explicit
  manual_edits: true | false
  review_state: not_reviewed | pending | approved | stale

recovery:
  amend_needed: true | false
  justificante_id: missing | present
  export_expected: ready | pending_review | validation_errors | unknown
```

## Compiler Phases

| Phase | Description |
| --- | --- |
| setup status | Show auth/profile readiness before work. |
| auth repair | Configure provider, log in, and confirm identity. |
| profile repair | Discover keys, set/unset values, validate readiness. |
| overview discovery | Show calendar and period state using overview. |
| ledger import | Dry-run and import transaction files. |
| import verification | Run source-file, gap, duplicate, and parser diagnostics through `--verify`. |
| ledger inspection | List rows, diagnostics, and pending work through filters. |
| ledger edit | Categorize, reference, comment, document-link, skip, unskip, split, and clear rows. |
| invoice import | Import issued and received invoice records with singular `invoice`. |
| invoice enrichment | Edit invoice base, IVA, retention, payment link, references, comments, and document paths. |
| invoice matching | Match invoice records, payments, and ledger rows. |
| declaration calculation | Calculate declarations by period/modelo and print summary output. |
| declaration review | Review values, pending decisions, assumptions, and manual edits. |
| approval | Explicitly approve reviewed calculations. |
| validation | Validate after approval or write validation report. |
| preview | Create draft PDF previews where supported. |
| export | Export AEAT-compatible local files through `--output`. |
| verification | Write verification audit output with `--format json --output`. |
| amend | Apply `--amend --id JUSTIFICANTE_ID` to declaration commands when amending prior AEAT output. |

## Primitive Command Templates

```text
aeat --help
aeat setup status
aeat setup auth providers
aeat setup auth configure --provider PROVIDER
aeat setup auth login
aeat setup auth status
aeat setup auth whoami
aeat setup profile list-keys
aeat setup profile create PROFILE
aeat setup profile use PROFILE
aeat setup profile set KEY VALUE
aeat setup profile unset KEY
aeat setup profile validate

aeat app overview --calendar --from DATE --to DATE
aeat app overview --period PERIOD --verbose

aeat app ledger import PATH --provider PROVIDER --dry-run
aeat app ledger import PATH --provider PROVIDER --verify --original PATH
aeat app ledger list --filter KEY=VALUE
aeat app ledger show --id ROW --verbose
aeat app ledger edit --id ROW --set COLUMN=VALUE --reason REASON
aeat app ledger edit --id ROW --skip true --reason REASON
aeat app ledger edit --id ROW --skip false --reason REASON
aeat app ledger split --id ROW --business SHARE --personal SHARE --reason REASON
aeat app ledger split --id ROW --clear --reason REASON

aeat app invoice import PATH --kind issued --dry-run
aeat app invoice import PATH --kind received --dry-run
aeat app invoice list --filter KEY=VALUE
aeat app invoice show --id INVOICE --verbose
aeat app invoice edit --id INVOICE --set COLUMN=VALUE --reason REASON
aeat app invoice match --period PERIOD

aeat app declaration calculate --period PERIOD --modelo MODELO
aeat app declaration review --period PERIOD --modelo MODELO --format table
aeat app declaration status --filter status=pending --period PERIOD --modelo MODELO
aeat app declaration edit --period PERIOD --modelo MODELO --set COLUMN=VALUE --reason REASON
aeat app declaration approve --period PERIOD --modelo MODELO --reason REASON
aeat app declaration validate --period PERIOD --modelo MODELO
aeat app declaration validate --period PERIOD --modelo MODELO --format json --output PATH
aeat app declaration preview --period PERIOD --modelo MODELO --format pdf
aeat app declaration export --period PERIOD --modelo MODELO --format boe --output PATH
aeat app declaration verify --period PERIOD --modelo MODELO --format json --output PATH

aeat app declaration calculate --period PERIOD --modelo MODELO --amend --id JUSTIFICANTE_ID
aeat app declaration review --period PERIOD --modelo MODELO --amend --id JUSTIFICANTE_ID --format table
aeat app declaration approve --period PERIOD --modelo MODELO --amend --id JUSTIFICANTE_ID --reason REASON
aeat app declaration validate --period PERIOD --modelo MODELO --amend --id JUSTIFICANTE_ID
aeat app declaration export --period PERIOD --modelo MODELO --amend --id JUSTIFICANTE_ID --format boe --output PATH
```

## Scoring Lenses

| Lens | Good signal | Bad signal |
| --- | --- | --- |
| User path | Commands move from setup to app work without developer vocabulary. | User guesses unsupported root commands. |
| Import | Verification is one flag on import. | Import becomes a subdomain. |
| Review | User can inspect, revise, skip, unskip, split, clear, and document rows. | User must delete data or use emotional/status commands. |
| Declaration | Calculate prints useful summary output and next action. | Calculate is silent or hides blockers. |
| Corrective work | User supplies AEAT justificante id through `--amend --id`. | CLI invents amendment nouns or CSV-code identities. |
