const COMMAND_TREE = `aeat
|-- setup
|   |-- init
|   |-- status
|   |-- auth
|   |   |-- providers
|   |   |-- configure --provider PROVIDER
|   |   |-- login
|   |   |-- status
|   |   |-- whoami
|   |   \\-- logout
|   \\-- profile
|       |-- create NAME
|       |-- use NAME
|       |-- show
|       |-- list-keys
|       |-- get KEY
|       |-- set KEY VALUE
|       |-- unset KEY
|       |-- validate
|       \\-- edit
\\-- app
    |-- overview
    |   |-- --calendar
    |   \\-- --period PERIOD
    |-- ledger
    |   |-- import PATH --provider PROVIDER [--verify] [--original PATH]
    |   |-- list --filter KEY=VALUE
    |   |-- show --id RECORD_ID
    |   |-- edit --id RECORD_ID --set COLUMN=VALUE --skip true|false
    |   \\-- split --id RECORD_ID --business SHARE --personal SHARE
    |-- invoice
    |   |-- import PATH --kind issued|received
    |   |-- list --filter KEY=VALUE
    |   |-- show --id INVOICE_ID
    |   |-- edit --id INVOICE_ID --set COLUMN=VALUE
    |   \\-- match
    \\-- declaration
        |-- calculate
        |-- review
        |-- status --filter KEY=VALUE
        |-- edit --set COLUMN=VALUE
        |-- approve
        |-- validate
        |-- preview
        |-- export
        \\-- verify`;

const HELP = {
  root: `AEAT CLI v5 review surface.

Usage:
  aeat --help
  aeat setup --help
  aeat app --help

Commands:
  setup    Configure authentication, profile data, and local readiness.
  app      Prepare ledger and invoice records, review declarations, and export verified local files.`,
  setup: `Setup configures prerequisites for app work.

Usage:
  aeat setup status
  aeat setup init
  aeat setup auth providers
  aeat setup auth configure --provider certificate|clave_movil
  aeat setup auth login
  aeat setup profile list-keys
  aeat setup profile set KEY VALUE
  aeat setup profile validate`,
  auth: `Authentication configures and runs AEAT login flows.

Usage:
  aeat setup auth providers
  aeat setup auth configure --provider certificate --file PATH
  aeat setup auth configure --provider clave_movil
  aeat setup auth login
  aeat setup auth status
  aeat setup auth whoami
  aeat setup auth logout`,
  profile: `Profile manages taxpayer data through schema-backed keys.

Usage:
  aeat setup profile create NAME
  aeat setup profile use NAME
  aeat setup profile show
  aeat setup profile list-keys
  aeat setup profile get KEY
  aeat setup profile set KEY VALUE
  aeat setup profile unset KEY
  aeat setup profile validate
  aeat setup profile edit`,
  app: `App works from the active setup profile.

Usage:
  aeat app overview
  aeat app ledger --help
  aeat app invoice --help
  aeat app declaration --help`,
  ledger: `Ledger owns imported transaction records and tax review fields.

Usage:
  aeat app ledger import PATH --provider n26 --dry-run
  aeat app ledger import PATH --provider n26 --verify --original PATH --verbose
  aeat app ledger list --filter status=pending --filter period=2026-Q1
  aeat app ledger show --id RECORD_ID
  aeat app ledger edit --id RECORD_ID --set category=software --set business.share=1.0 --reason REASON
  aeat app ledger edit --id RECORD_ID --skip true --reason REASON
  aeat app ledger split --id RECORD_ID --business 0.45 --personal 0.55 --reason REASON`,
  invoice: `Invoice owns issued and received invoice records, enrichment, and payment linkage.

Usage:
  aeat app invoice import PATH --kind issued --dry-run
  aeat app invoice import PATH --kind received --dry-run
  aeat app invoice list --filter status=pending --filter kind=received
  aeat app invoice show --id INVOICE_ID
  aeat app invoice edit --id INVOICE_ID --set iva.rate=21 --set iva.category=general --reason REASON
  aeat app invoice match --period PERIOD`,
  declaration: `Declaration owns calculation, review, approval, validation, local export, verification, and corrective calculation flags.

Usage:
  aeat app declaration calculate --period PERIOD --modelo MODELO
  aeat app declaration review --period PERIOD --modelo MODELO --format table
  aeat app declaration status --filter status=pending
  aeat app declaration edit --period PERIOD --modelo MODELO --set casilla.71=1200.00 --reason REASON
  aeat app declaration approve --period PERIOD --modelo MODELO --reason REASON
  aeat app declaration validate --period PERIOD --modelo MODELO
  aeat app declaration export --period PERIOD --modelo MODELO --format boe --output PATH
  aeat app declaration verify --period PERIOD --modelo MODELO --format json --output PATH
  aeat app declaration calculate --period PERIOD --modelo MODELO --amend --id JUSTIFICANTE_ID`,
};

const PROFILE_KEYS = [
  ["tax.id", "required", "Tax identifier for the active taxpayer profile."],
  ["tax.name", "required", "Display name used in local review output."],
  ["activity.code", "required", "Economic activity code or controlled activity key."],
  ["activity.label", "optional", "Human label for the activity, such as design."],
  ["address.postcode", "required", "Tax address postcode used by supported modelos."],
  ["iva.regime", "backend-audit", "IVA regime key when the backend supports the relevant model."],
  ["withholding.profile", "backend-audit", "Withholding assumptions and thresholds."],
  ["usage.default_business_share", "optional", "Default business share used as an initial review hint."],
];

const SCENARIOS = {
  fresh: {
    name: "Fresh workstation",
    description: "No auth provider, no active profile, and no app records.",
    state: baseState(),
  },
  authReady: {
    name: "Auth configured",
    description: "A provider is configured and logged in, but the profile is incomplete.",
    state: { ...baseState(), authProvider: "clave_movil", authenticated: true },
  },
  profileReady: {
    name: "Profile ready",
    description: "Setup is ready; no ledger or invoice review has started.",
    state: {
      ...baseState(),
      authProvider: "clave_movil",
      authenticated: true,
      profileName: "autonomo-2026",
      profileValid: true,
      profileMissing: 0,
    },
  },
  kentN26: {
    name: "Kent with N26",
    description: "Kent uses N26 and can download invoices, but does not know the filing path.",
    state: {
      ...baseState(),
      authProvider: "clave_movil",
      authenticated: true,
      profileName: "autonomo-2026",
      profileValid: true,
      profileMissing: 0,
      bank: "n26",
    },
  },
  messyQ1: {
    name: "Messy Q1",
    description: "Rows and invoices exist, but statement verification, row review, and invoice enrichment are open.",
    state: {
      ...baseState(),
      authProvider: "clave_movil",
      authenticated: true,
      profileName: "autonomo-2026",
      profileValid: true,
      profileMissing: 0,
      bank: "n26",
      period: "2026-Q1",
      imports: 1,
      ledgerPending: 5,
      invoicePending: 3,
      invoiceMetadataGaps: 2,
      issuedInvoices: 1,
      receivedInvoices: 1,
    },
  },
  readyToApprove: {
    name: "Ready to approve",
    description: "Ledger and invoice review are complete; declaration still needs human review and approval.",
    state: {
      ...baseState(),
      authProvider: "clave_movil",
      authenticated: true,
      profileName: "autonomo-2026",
      profileValid: true,
      profileMissing: 0,
      bank: "n26",
      period: "2026-Q1",
      imports: 1,
      importVerified: true,
      ledgerPending: 0,
      invoicePending: 0,
      issuedInvoices: 2,
      receivedInvoices: 2,
      invoiceLinked: true,
      calculated: true,
    },
  },
  correctionNeeded: {
    name: "After filing, new invoice found",
    description: "A previous filing exists and new record changes may require a corrective filing workflow.",
    state: {
      ...baseState(),
      authProvider: "clave_movil",
      authenticated: true,
      profileName: "autonomo-2026",
      profileValid: true,
      profileMissing: 0,
      bank: "n26",
      period: "2026-Q1",
      imports: 1,
      importVerified: true,
      ledgerPending: 0,
      invoicePending: 1,
      issuedInvoices: 2,
      receivedInvoices: 3,
      exported: true,
      verified: true,
      stale: true,
    },
  },
};

const TAPES = {
  setupUnknown: {
    name: "Setup from unknown state",
    scenario: "fresh",
    commands: [
      "aeat --help",
      "aeat setup status",
      "aeat setup auth providers",
      "aeat setup auth configure --provider clave_movil",
      "aeat setup auth login",
      "aeat setup auth whoami",
      "aeat setup profile create autonomo-2026",
      "aeat setup profile set tax.id 12345678Z",
      "aeat setup profile set tax.name Kent",
      "aeat setup profile set activity.label design",
      "aeat setup profile set address.postcode 28013",
      "aeat setup profile validate",
      "aeat setup status",
    ],
  },
  profileRevision: {
    name: "Profile key revision",
    scenario: "authReady",
    commands: [
      "aeat setup profile list-keys",
      "aeat setup profile create autonomo-2026",
      "aeat setup profile validate",
      "aeat setup profile set tax.id 12345678Z",
      "aeat setup profile set tax.name Kent",
      "aeat setup profile set activity.code design",
      "aeat setup profile unset activity.code",
      "aeat setup profile set activity.label design",
      "aeat setup profile set address.postcode 28013",
      "aeat setup profile validate",
    ],
  },
  invalidStatements: {
    name: "Invalid and incomplete N26 imports",
    scenario: "profileReady",
    commands: [
      "aeat app ledger import ./downloads/n26-invoices.pdf --provider n26 --dry-run",
      "aeat app ledger import ./downloads/n26-jan.csv --provider n26 --dry-run",
      "aeat app ledger import ./downloads/n26-jan.csv --provider n26 --verify --original ./downloads/n26-jan.pdf --verbose",
      "aeat app ledger import ./downloads/n26-feb-mar.csv --provider n26 --dry-run",
      "aeat app ledger import ./downloads/n26-feb-mar.csv --provider n26 --verify --original ./downloads/n26-feb-mar.pdf",
      "aeat app ledger list --filter issue=gap --filter period=2026-Q1",
    ],
  },
  duplicateWrongAccount: {
    name: "Duplicate and wrong account import",
    scenario: "profileReady",
    commands: [
      "aeat app ledger import ./downloads/n26-business-q1.csv --provider n26 --verify",
      "aeat app ledger import ./downloads/n26-business-q1-copy.csv --provider n26 --verify --verbose",
      "aeat app ledger list --filter issue=duplicate --filter period=2026-Q1",
      "aeat app ledger edit --id row_dup_002 --skip true --reason duplicate-file",
      "aeat app ledger import ./downloads/n26-personal-q1.csv --provider n26 --verify --original ./downloads/n26-personal-q1.pdf",
      "aeat app ledger list --filter import=import_003 --filter period=2026-Q1",
      "aeat app ledger edit --id row_personal_001 --skip true --reason personal-account",
      "aeat app ledger edit --id row_personal_001 --skip false --reason user-corrected-account",
      "aeat app ledger edit --id row_personal_001 --skip true --reason personal-account-confirmed",
    ],
  },
  manualRows: {
    name: "Manual ledger record decisions",
    scenario: "messyQ1",
    commands: [
      "aeat app ledger list --filter status=pending --filter period=2026-Q1",
      "aeat app ledger show --id row_1042",
      "aeat app ledger edit --id row_1042 --set category=software --set business.share=1.0 --set reference=invoice-901 --set comments=invoice-reviewed --reason invoice",
      "aeat app ledger edit --id row_1043 --set category=design-services --set business.share=1.0 --set comments=client-payment --reason client-payment",
      "aeat app ledger split --id row_1050 --business 0.45 --personal 0.55 --reason mixed-card-payment",
      "aeat app ledger split --id row_1050 --clear --reason corrected-single-use",
      "aeat app ledger split --id row_1050 --business 0.45 --personal 0.55 --reason mixed-card-payment-confirmed",
      "aeat app ledger edit --id row_1051 --skip true --reason private-expense",
      "aeat app ledger edit --id row_1051 --skip false --reason invoice-found",
      "aeat app ledger edit --id row_1051 --set category=supplies --set business.share=1.0 --set document.path=./receipts/receipt-901.pdf --reason invoice-found",
      "aeat app ledger list --filter status=pending --filter period=2026-Q1",
    ],
  },
  invoiceEnrichment: {
    name: "Invoice enrichment and matching",
    scenario: "messyQ1",
    commands: [
      "aeat app invoice import ./invoices/issued-q1.csv --kind issued --dry-run",
      "aeat app invoice import ./invoices/received-q1.csv --kind received --dry-run",
      "aeat app invoice import ./invoices/issued-q1.csv --kind issued",
      "aeat app invoice import ./invoices/received-q1.csv --kind received",
      "aeat app invoice list --filter status=pending --filter kind=received",
      "aeat app invoice show --id inv_2041",
      "aeat app invoice edit --id inv_2041 --set base=120.00 --set iva.rate=21 --set iva.amount=25.20 --set iva.category=general --set retention.rate=15 --set payment.id=row_1042 --set comments=metadata-completed --reason invoice-review",
      "aeat app invoice match --period 2026-Q1",
      "aeat app invoice list --filter status=pending --filter period=2026-Q1",
    ],
  },
  blockedExport: {
    name: "Export refused until review completes",
    scenario: "messyQ1",
    commands: [
      "aeat app declaration calculate --period 2026-Q1 --modelo 303",
      "aeat app declaration status --filter status=pending --period 2026-Q1 --modelo 303",
      "aeat app declaration validate --period 2026-Q1 --modelo 303",
      "aeat app declaration export --period 2026-Q1 --modelo 303 --format boe --output ./exports/2026-q1",
      "aeat app ledger list --filter status=pending --filter period=2026-Q1",
      "aeat app invoice list --filter status=pending --filter period=2026-Q1",
      "aeat app declaration validate --period 2026-Q1 --modelo 303 --format json --output ./exports/2026-q1-validation.json",
    ],
  },
  normalExport: {
    name: "Normal Modelo 303 local export path",
    scenario: "readyToApprove",
    commands: [
      "aeat app overview --calendar --from 2026-01-01 --to 2026-04-20",
      "aeat app overview --period 2026-Q1",
      "aeat app declaration calculate --period 2026-Q1 --modelo 303",
      "aeat app declaration review --period 2026-Q1 --modelo 303 --format table",
      "aeat app declaration edit --period 2026-Q1 --modelo 303 --set casilla.71=1200.00 --reason manual-check",
      "aeat app declaration review --period 2026-Q1 --modelo 303 --format table",
      "aeat app declaration approve --period 2026-Q1 --modelo 303 --reason reviewed-against-ledger",
      "aeat app declaration validate --period 2026-Q1 --modelo 303",
      "aeat app declaration preview --period 2026-Q1 --modelo 303 --format pdf",
      "aeat app declaration export --period 2026-Q1 --modelo 303 --format boe --output ./exports/2026-q1",
      "aeat app declaration verify --period 2026-Q1 --modelo 303 --format json --output ./exports/2026-q1-verify.json",
    ],
  },
  behindHistory: {
    name: "Behind with partial filing history",
    scenario: "kentN26",
    commands: [
      "aeat app overview --calendar --from 2025-10-01 --to 2026-05-03",
      "aeat app overview --period 2025-Q4",
      "aeat app ledger import ./downloads/n26-2025-q4.csv --provider n26 --dry-run",
      "aeat app ledger import ./downloads/n26-2025-q4.csv --provider n26 --verify",
      "aeat app ledger import ./downloads/n26-2026-jan-may.csv --provider n26 --verify --verbose",
      "aeat app ledger list --filter issue=gap --filter period=2025-Q4",
      "aeat app ledger list --filter status=pending --filter period=2025-Q4",
      "aeat app ledger edit --id row_2201 --set category=aeat-tax-payment --set business.share=1.0 --set comments=prior-modelo-payment --reason prior-modelo-payment",
      "aeat app ledger edit --id row_2207 --skip true --reason not-business",
      "aeat app declaration calculate --period 2025-Q4 --modelo 303",
      "aeat app declaration status --filter status=pending --period 2025-Q4 --modelo 303",
      "aeat app declaration validate --period 2025-Q4 --modelo 303 --format json --output ./exports/2025-q4-validation.json",
    ],
  },
  multiPeriod: {
    name: "Multi-period forgetfulness",
    scenario: "kentN26",
    commands: [
      "aeat app overview --calendar --from 2025-10-01 --to 2026-07-20",
      "aeat app overview --period 2025-Q4",
      "aeat app overview --period 2026-Q1",
      "aeat app overview --period 2026-Q2",
      "aeat app ledger import ./downloads/n26-2025-q4.csv --provider n26 --verify",
      "aeat app ledger import ./downloads/n26-2026-q1.csv --provider n26 --verify",
      "aeat app ledger import ./downloads/n26-2026-q2.csv --provider n26 --verify",
      "aeat app ledger list --filter issue=gap --filter period=2026-Q1",
      "aeat app ledger list --filter issue=gap --filter period=2026-Q2",
      "aeat app ledger edit --id row_3104 --set category=design-services --set business.share=1.0 --reason client-payment",
      "aeat app ledger split --id row_3110 --business 0.60 --personal 0.40 --reason shared-subscription",
      "aeat app invoice match --period 2026-Q1",
      "aeat app declaration calculate --period 2025-Q4 --modelo 303",
      "aeat app declaration calculate --period 2026-Q1 --modelo 303",
      "aeat app declaration calculate --period 2026-Q2 --modelo 303",
      "aeat app declaration review --period 2025-Q4 --modelo 303 --format table",
      "aeat app declaration review --period 2026-Q1 --modelo 303 --format table",
      "aeat app declaration review --period 2026-Q2 --modelo 303 --format table",
    ],
  },
  correctiveFlow: {
    name: "Corrective filing after new data",
    scenario: "correctionNeeded",
    commands: [
      "aeat app overview --period 2026-Q1",
      "aeat app invoice import ./late-file/invoice-2026-041.pdf --kind received --dry-run",
      "aeat app invoice import ./late-file/invoice-2026-041.pdf --kind received",
      "aeat app invoice edit --id inv_2041 --set base=320.00 --set iva.rate=21 --set iva.amount=67.20 --set payment.id=row_1141 --reason late-invoice",
      "aeat app ledger edit --id row_1141 --set category=supplies --set business.share=1.0 --set reference=inv_2041 --reason found-after-export",
      "aeat app invoice match --period 2026-Q1",
      "aeat app declaration calculate --period 2026-Q1 --modelo 303 --amend --id 3031234567890",
      "aeat app declaration review --period 2026-Q1 --modelo 303 --amend --id 3031234567890 --format table",
      "aeat app declaration approve --period 2026-Q1 --modelo 303 --amend --id 3031234567890 --reason amend-reviewed",
      "aeat app declaration validate --period 2026-Q1 --modelo 303 --amend --id 3031234567890",
      "aeat app declaration export --period 2026-Q1 --modelo 303 --amend --id 3031234567890 --format boe --output ./exports/2026-q1-amend",
      "aeat app declaration verify --period 2026-Q1 --modelo 303 --format json --output ./exports/2026-q1-amend-verify.json",
    ],
  },
};

const ui = {};
let activeScenario = "fresh";
let activeTape = "setupUnknown";
let tapeIndex = 0;
let state = cloneState(SCENARIOS[activeScenario].state);
let lastAudit = null;

function baseState() {
  return {
    authProvider: "",
    authenticated: false,
    profileName: "",
    profileValid: false,
    profileMissing: 4,
    bank: "",
    period: "",
    imports: 0,
    importVerified: false,
    importGaps: false,
    importDuplicates: false,
    ledgerPending: 0,
    ledgerExcluded: 0,
    documents: 0,
    issuedInvoices: 0,
    receivedInvoices: 0,
    invoicePending: 0,
    invoiceMetadataGaps: 0,
    invoiceLinked: false,
    overviewReady: false,
    calculated: false,
    reviewed: false,
    approved: false,
    edited: false,
    validationReport: false,
    validated: false,
    previewed: false,
    exported: false,
    verified: false,
    amend: false,
    amendId: "",
    skippedRows: 0,
    splitRows: 0,
    stale: false,
  };
}

function cloneState(value) {
  return JSON.parse(JSON.stringify(value));
}

function setupReady() {
  return Boolean(state.authenticated && state.profileName && state.profileValid);
}

function tokenize(command) {
  const tokens = [];
  let current = "";
  let quote = "";
  for (const char of command.trim()) {
    if (quote) {
      if (char === quote) {
        quote = "";
      } else {
        current += char;
      }
      continue;
    }
    if (char === '"' || char === "'") {
      quote = char;
      continue;
    }
    if (/\s/.test(char)) {
      if (current) {
        tokens.push(current);
        current = "";
      }
      continue;
    }
    current += char;
  }
  if (current) tokens.push(current);
  return tokens;
}

function parseFlags(tokens) {
  const flags = {};
  for (let index = 0; index < tokens.length; index += 1) {
    const token = tokens[index];
    if (!token.startsWith("--")) continue;
    const name = token.slice(2);
    const next = tokens[index + 1];
    const value = next && !next.startsWith("--") ? next : true;
    if (next && !next.startsWith("--")) index += 1;
    if (flags[name] === undefined) {
      flags[name] = value;
    } else if (Array.isArray(flags[name])) {
      flags[name].push(value);
    } else {
      flags[name] = [flags[name], value];
    }
  }
  return flags;
}

function valuesOf(flags, name) {
  const value = flags[name];
  if (value === undefined) return [];
  return Array.isArray(value) ? value : [value];
}

function execute(command) {
  const trimmed = command.trim();
  if (!trimmed) return null;
  const tokens = tokenize(trimmed);
  const flags = parseFlags(tokens);

  if (trimmed === "aeat" || trimmed === "aeat --help") return ok(HELP.root);
  if (trimmed === "aeat help") return warn("Bare `help` is not canonical. Use `aeat --help`.");
  if (trimmed === "aeat setup" || trimmed === "aeat setup --help") return ok(HELP.setup);
  if (trimmed === "aeat setup auth" || trimmed === "aeat setup auth --help") return ok(HELP.auth);
  if (trimmed === "aeat setup profile" || trimmed === "aeat setup profile --help") return ok(HELP.profile);
  if (trimmed === "aeat app" || trimmed === "aeat app --help") return ok(HELP.app);
  if (trimmed === "aeat app ledger" || trimmed === "aeat app ledger --help") return ok(HELP.ledger);
  if (trimmed === "aeat app invoice" || trimmed === "aeat app invoice --help") return ok(HELP.invoice);
  if (trimmed === "aeat app declaration" || trimmed === "aeat app declaration --help") return ok(HELP.declaration);

  if (tokens[0] !== "aeat") return error("Commands must start with `aeat`.");
  if (tokens[1] === "setup") return runSetup(tokens, flags);
  if (tokens[1] === "app") return runApp(tokens, flags);
  return error("Unknown root command. Run `aeat --help`.");
}

function runSetup(tokens, flags) {
  const area = tokens[2];
  if (area === "status") return runSetupStatus();
  if (area === "init") {
    return ok(`Setup initialized.
Local state: ready

Next:
  aeat setup auth configure --provider certificate|clave_movil
  aeat setup auth login
  aeat setup profile validate`);
  }
  if (area === "verify") {
    return warn("`aeat setup verify` is not part of the v5 review surface. Use `aeat setup status` and `aeat setup profile validate`.");
  }
  if (area === "account") {
    return warn("`account` is rejected in v5. Identity is shown through `aeat setup auth whoami` and `aeat setup profile show`.");
  }
  if (area === "auth") return runAuth(tokens, flags);
  if (area === "profile") return runProfile(tokens, flags);
  return error("Unknown setup command. Run `aeat setup --help`.");
}

function runSetupStatus() {
  const ready = setupReady();
  return (ready ? ok : warn)(`Setup status
Auth provider: ${state.authProvider || "not configured"}
Authenticated: ${yesNo(state.authenticated)}
Profile: ${state.profileName || "missing"}
Profile valid: ${yesNo(state.profileValid)}
Missing profile keys: ${state.profileMissing}

Next:
  ${ready ? "aeat app overview" : "aeat setup auth status && aeat setup profile validate"}`);
}

function runAuth(tokens, flags) {
  const action = tokens[3];
  if (action === "providers" || action === "list") {
    return ok(`Supported providers
certificate: implemented
clave_movil: implemented
clave_permanente: research only, not implemented in this simulator`);
  }
  if (action === "configure") {
    const provider = flags.provider;
    if (!provider) return error("Missing --provider certificate|clave_movil.");
    if (!["certificate", "clave_movil"].includes(provider)) {
      return warn(`Provider not available in v5 simulator: ${provider}
Implemented providers: certificate, clave_movil
Research only: clave_permanente`);
    }
    state.authProvider = provider;
    state.authenticated = false;
    return ok(`Authentication provider configured.
Provider: ${provider}
Login state: not logged in
File: ${flags.file || "not provided"}

Next:
  aeat setup auth login`);
  }
  if (action === "import") {
    return warn("This auth subcommand is rejected. Authentication is a provider configuration and login process. Use `aeat setup auth configure` and `aeat setup auth login`.");
  }
  if (action === "login") {
    if (!state.authProvider) return warn("Configure an auth provider before login.");
    state.authenticated = true;
    return ok(`AEAT login complete.
Provider: ${state.authProvider}
Authenticated: yes`);
  }
  if (action === "status") {
    return (state.authenticated ? ok : warn)(`Authentication status
Provider: ${state.authProvider || "not configured"}
Authenticated: ${yesNo(state.authenticated)}`);
  }
  if (action === "whoami") {
    if (!state.authenticated) return warn("Not authenticated. Run `aeat setup auth login`.");
    return ok(`Authenticated identity
Provider: ${state.authProvider}
Profile: ${state.profileName || "not selected"}
Tax id: ${state.profileValid ? "configured" : "unknown until profile validates"}`);
  }
  if (action === "logout") {
    state.authenticated = false;
    return ok("Authentication state cleared.");
  }
  return error("Unknown auth command. Run `aeat setup auth --help`.");
}

function runProfile(tokens, flags) {
  const action = tokens[3];
  if (action === "create" || action === "use") {
    const name = tokens[4];
    if (!name) return error(`Usage: aeat setup profile ${action} NAME`);
    state.profileName = name;
    state.profileValid = state.profileMissing === 0;
    return ok(`${action === "create" ? "Profile created" : "Active profile selected"}.
Name: ${name}
Valid: ${yesNo(state.profileValid)}`);
  }
  if (action === "show") {
    return ok(`Profile
Name: ${state.profileName || "missing"}
Valid: ${yesNo(state.profileValid)}
Missing keys: ${state.profileMissing}
Editable keys: run aeat setup profile list-keys`);
  }
  if (action === "list-keys") {
    return ok(PROFILE_KEYS.map(([key, stateLabel, description]) => `${key.padEnd(30)} ${stateLabel.padEnd(13)} ${description}`).join("\n"));
  }
  if (action === "get") {
    const key = tokens[4];
    if (!key) return error("Usage: aeat setup profile get KEY");
    return ok(`${key}: ${state.profileValid ? "configured" : "not set or not validated"}`);
  }
  if (action === "set") {
    const key = tokens[4];
    const value = tokens[5];
    if (!key || value === undefined) return error("Usage: aeat setup profile set KEY VALUE");
    state.profileMissing = Math.max(0, state.profileMissing - 1);
    state.profileValid = state.profileMissing === 0 && Boolean(state.profileName);
    return ok(`Profile value set.
Key: ${key}
Value: ${value}
Missing keys: ${state.profileMissing}`);
  }
  if (action === "unset") {
    const key = tokens[4];
    if (!key) return error("Usage: aeat setup profile unset KEY");
    state.profileMissing += 1;
    state.profileValid = false;
    return ok(`Profile value cleared.
Key: ${key}
Missing keys: ${state.profileMissing}`);
  }
  if (action === "validate") {
    state.profileValid = Boolean(state.profileName && state.profileMissing === 0);
    return (state.profileValid ? ok : warn)(`Profile validation
Name: ${state.profileName || "missing"}
Missing required keys: ${state.profileMissing}
Valid: ${yesNo(state.profileValid)}`);
  }
  if (action === "edit") {
    return ok(`Interactive profile editor
Mode: schema-backed
Keys: run aeat setup profile list-keys
Simulator note: edit is represented here without opening an external editor.`);
  }
  return error("Unknown profile command. Run `aeat setup profile --help`.");
}

function runApp(tokens, flags) {
  const domain = tokens[2];
  if (["status", "next", "obligations", "calendar", "receipts", "sessions", "workspaces"].includes(domain)) {
    return warn(`\`aeat app ${domain}\` is not part of the v5 design.

Use:
  aeat app overview --calendar --from DATE --to DATE
  aeat app overview --period PERIOD`);
  }
  if (domain === "invoices") return warn("Use singular `aeat app invoice`.");
  if (!setupReady()) {
    return warn(`Setup is incomplete.

Next:
  aeat setup status
  aeat setup auth configure --provider certificate|clave_movil
  aeat setup profile validate`);
  }
  if (domain === "overview") return runOverview(flags);
  if (domain === "ledger") return runLedger(tokens, flags);
  if (domain === "invoice") return runInvoice(tokens, flags);
  if (domain === "declaration") return runDeclaration(tokens, flags);
  return error("Unknown app domain. Run `aeat app --help`.");
}

function runOverview(flags) {
  if (flags.calendar) {
    state.overviewReady = true;
    return ok(`Overview calendar
From: ${flags.from || "not provided"}
To: ${flags.to || "not provided"}
Profile: ${state.profileName}
Known periods: 2025-Q4, 2026-Q1, 2026-Q2
Period states: filed, missing, late, due, or unknown depending on local and AEAT history`);
  }
  if (flags.period) {
    state.period = flags.period;
    return ok(`Period overview
Period: ${flags.period}
Profile: ${state.profileName}
State: derived from profile-scoped records, declaration state, and imported AEAT history where available.
Pending ledger records: ${state.ledgerPending}
Pending invoices: ${state.invoicePending}`);
  }
  state.overviewReady = true;
  return ok(`App overview
Profile: ${state.profileName}
Imports: ${state.imports}
Ledger pending: ${state.ledgerPending}
Invoice pending: ${state.invoicePending}
Declaration approved: ${yesNo(state.approved)}
Declaration stale: ${yesNo(state.stale)}`);
}

function runLedger(tokens, flags) {
  const action = tokens[3];
  if (["statements", "transactions", "evidence", "source", "receipt"].includes(action)) {
    return warn(`\`aeat app ledger ${action}\` is not canonical in v5.

Use schema-backed record commands:
  aeat app ledger list --filter status=pending
  aeat app ledger show --id RECORD_ID
  aeat app ledger edit --id RECORD_ID --set reference=VALUE --set comments=VALUE --reason REASON`);
  }
  if (action === "import") return runLedgerImport(tokens, flags);
  if (action === "list" || action === "search") return runLedgerList(action, flags);
  if (action === "show") return runLedgerShow(flags);
  if (action === "edit") return runLedgerEdit(flags);
  if (action === "split") return runLedgerSplit(flags);
  if (action === "exclude" || action === "restore") {
    return warn(`\`aeat app ledger ${action}\` is not canonical in v5.

Use:
  aeat app ledger edit --id RECORD_ID --skip true|false --reason REASON`);
  }
  return error("Unknown ledger command. Run `aeat app ledger --help`.");
}

function runLedgerImport(tokens, flags) {
  const subcommand = tokens[4];
  if (["list", "verify", "gaps", "duplicates", "exclude", "restore"].includes(subcommand)) {
    return warn(`\`aeat app ledger import ${subcommand}\` is not canonical in v5.

Use import as the action:
  aeat app ledger import PATH --provider PROVIDER --verify

Use ledger edit for record decisions:
  aeat app ledger edit --id RECORD_ID --skip true|false --reason REASON`);
  }

  const filePath = tokens[4];
  if (!filePath) return error("Usage: aeat app ledger import PATH --provider PROVIDER");
  if (flags.statement) return warn("`--statement` is not canonical in v5. Use `--provider PROVIDER`.");
  if (!flags.provider) return error("Missing --provider PROVIDER.");
  if (/\.pdf$/i.test(filePath)) {
    return warn(`Statement import rejected before state change.
Path: ${filePath}
Reason: ledger import expects transaction data, not an invoice or PDF-only file.`);
  }
  if (flags["dry-run"]) {
    return ok(`Ledger import dry run passed.
Path: ${filePath}
Provider: ${flags.provider}
State changed: no`);
  }
  state.imports += 1;
  state.bank = flags.provider;
  state.period = inferPeriod(filePath);
  state.ledgerPending += 3;
  const duplicate = /copy|duplicate/i.test(filePath) || state.imports > 1;
  const coverageGap = /jan|jan-may|2025-q4/i.test(filePath);
  if (flags.verify) {
    state.importVerified = Boolean(flags.original || state.imports > 0);
    state.importDuplicates = duplicate;
    state.importGaps = coverageGap;
  }
  resetDeclarationAfterInputChange();
  const message = `Ledger import saved.
Path: ${filePath}
Provider: ${flags.provider}
Imported batches: ${state.imports}
Ledger records pending: ${state.ledgerPending}
Verification: ${flags.verify ? "run" : "not requested"}
Original file: ${flags.original || "not provided"}
Gap diagnostics: ${flags.verify ? (coverageGap ? "possible missing coverage" : "no immediate gap signal") : "not run"}
Duplicate diagnostics: ${flags.verify ? (duplicate ? "possible duplicate rows" : "no immediate duplicate signal") : "not run"}
Verbose: ${yesNo(Boolean(flags.verbose))}`;
  return flags.verify && (duplicate || coverageGap) ? warn(message) : ok(message);
}

function runLedgerList(action, flags) {
  if (flags["needs-review"]) {
    return warn("This review shortcut is rejected in v5. Use `--filter status=pending`.");
  }
  const filters = valuesOf(flags, "filter");
  const pending = filters.includes("status=pending") || state.ledgerPending > 0;
  return (pending ? warn : ok)(`Ledger ${action}
Filters: ${filters.length ? filters.join(", ") : "none"}
Period: ${flags.period || state.period || "unknown"}
Pending records: ${state.ledgerPending}
Excluded records: ${state.ledgerExcluded}`);
}

function runLedgerShow(flags) {
  if (!flags.id) return error("Missing --id RECORD_ID.");
  return ok(`Ledger record
Id: ${flags.id}
Status: ${state.ledgerPending > 0 ? "pending" : "approved"}
Editable columns: category, business.share, reference, comments, period, modelo, invoice.id, document.path, skip
Use: aeat app ledger edit --id ${flags.id} --set column=value --reason REASON`);
}

function runLedgerEdit(flags) {
  if (!flags.id) return error("Missing --id RECORD_ID.");
  const sets = valuesOf(flags, "set");
  const skip = parseSkipFlag(flags.skip);
  if (sets.length === 0 && skip === null) return error("Use one or more `--set column=value` edits or `--skip true|false`.");
  if (skip !== null && !flags.reason) return error("Skipping or unskipping requires --reason REASON.");
  state.ledgerPending = Math.max(0, state.ledgerPending - 1);
  if (sets.some((item) => /^document\.path=|^receipt\.path=/.test(item))) state.documents += 1;
  if (skip === true) {
    state.skippedRows += 1;
    state.ledgerExcluded = state.skippedRows;
  }
  if (skip === false) {
    state.skippedRows = Math.max(0, state.skippedRows - 1);
    state.ledgerExcluded = state.skippedRows;
    state.ledgerPending += 1;
  }
  resetDeclarationAfterInputChange();
  return ok(`Ledger record edited.
Id: ${flags.id}
Columns: ${sets.length ? sets.join(", ") : "none"}
Skip: ${skip === null ? "unchanged" : String(skip)}
Reason: ${flags.reason || "not provided"}
Remaining pending records: ${state.ledgerPending}
Declaration state reset: yes`);
}

function runLedgerSplit(flags) {
  if (!flags.id) return error("Missing --id RECORD_ID.");
  if (flags.clear) {
    state.splitRows = Math.max(0, state.splitRows - 1);
    resetDeclarationAfterInputChange();
    return ok(`Ledger split cleared.
Id: ${flags.id}
Source transaction preserved: yes
Reason: ${flags.reason || "not provided"}`);
  }
  const business = Number(flags.business);
  const personal = Number(flags.personal);
  if (!Number.isFinite(business) || !Number.isFinite(personal)) return error("Split requires --business SHARE and --personal SHARE.");
  const total = business + personal;
  if (Math.abs(total - 1) > 0.0001) return error("Split shares must add up to 1.0.");
  state.ledgerPending = Math.max(0, state.ledgerPending - 1);
  state.splitRows += 1;
  resetDeclarationAfterInputChange();
  return ok(`Ledger record split.
Id: ${flags.id}
Business share: ${business.toFixed(2)}
Personal share: ${personal.toFixed(2)}
Total share: ${total.toFixed(2)}
Source transaction preserved: yes
Split metadata tracked: backend requirement
Reason: ${flags.reason || "not provided"}`);
}

function runInvoice(tokens, flags) {
  const action = tokens[3];
  if (action === "import") return runInvoiceImport(tokens, flags);
  if (action === "list" || action === "search") return runInvoiceList(action, flags);
  if (action === "show") return runInvoiceShow(flags);
  if (action === "edit") return runInvoiceEdit(flags);
  if (action === "match") return runInvoiceMatch(flags);
  return error("Unknown invoice command. Run `aeat app invoice --help`.");
}

function runInvoiceImport(tokens, flags) {
  const filePath = tokens[4];
  if (!filePath) return error("Usage: aeat app invoice import PATH --kind issued|received");
  if (!["issued", "received"].includes(flags.kind)) return error("Missing --kind issued|received.");
  if (flags["dry-run"]) {
    return ok(`Invoice import dry run passed.
Kind: ${flags.kind}
Path: ${filePath}
State changed: no`);
  }
  if (flags.kind === "issued") state.issuedInvoices += 1;
  if (flags.kind === "received") state.receivedInvoices += 1;
  state.invoicePending = Math.max(state.invoicePending, 2);
  state.invoiceMetadataGaps = Math.max(state.invoiceMetadataGaps, 1);
  resetDeclarationAfterInputChange();
  return ok(`Invoice import saved.
Kind: ${flags.kind}
Path: ${filePath}
Pending invoices: ${state.invoicePending}`);
}

function runInvoiceList(action, flags) {
  const filters = valuesOf(flags, "filter");
  const pending = filters.includes("status=pending") || state.invoicePending > 0;
  return (pending ? warn : ok)(`Invoice ${action}
Filters: ${filters.length ? filters.join(", ") : "none"}
Issued batches: ${state.issuedInvoices}
Received batches: ${state.receivedInvoices}
Pending invoices: ${state.invoicePending}
Metadata gaps: ${state.invoiceMetadataGaps}`);
}

function runInvoiceShow(flags) {
  if (!flags.id) return error("Missing --id INVOICE_ID.");
  return ok(`Invoice record
Id: ${flags.id}
Editable columns: kind, base, iva.rate, iva.amount, iva.category, retention.rate, payment.id, reference, comments
Backend audit: retention and IVA category integration are CLI requirements, not fully proven backend capabilities.`);
}

function runInvoiceEdit(flags) {
  if (!flags.id) return error("Missing --id INVOICE_ID.");
  const sets = valuesOf(flags, "set");
  if (sets.length === 0) return error("Use one or more `--set column=value` edits.");
  const backendGap = sets.some((item) => item.startsWith("retention.") || item.startsWith("iva.category="));
  state.invoicePending = Math.max(0, state.invoicePending - 1);
  state.invoiceMetadataGaps = Math.max(0, state.invoiceMetadataGaps - 1);
  resetDeclarationAfterInputChange();
  return (backendGap ? warn : ok)(`Invoice record edited.
Id: ${flags.id}
Columns: ${sets.join(", ")}
Reason: ${flags.reason || "not provided"}
Remaining pending invoices: ${state.invoicePending}
Backend audit: ${backendGap ? "retention or IVA category support must be implemented" : "no backend gap triggered"}`);
}

function runInvoiceMatch(flags) {
  if (state.ledgerPending > 0) {
    return warn(`Invoice matching has open ledger review.
Period: ${flags.period || state.period || "unknown"}
Ledger pending: ${state.ledgerPending}`);
  }
  state.invoiceLinked = true;
  state.invoicePending = 0;
  resetDeclarationAfterInputChange();
  return ok(`Invoices matched.
Period: ${flags.period || state.period || "unknown"}
Pending invoices: 0`);
}

function runDeclaration(tokens, flags) {
  const action = tokens[3];
  if (["blockers", "evidence", "package", "correct", "amendment", "correction"].includes(action)) {
    return warn(`\`aeat app declaration ${action}\` is rejected in v5.

Use:
  aeat app declaration status --filter status=pending
  aeat app declaration calculate --period PERIOD --modelo MODELO --amend --id JUSTIFICANTE_ID`);
  }
  if (action === "calculate") return runDeclarationCalculate(flags);
  if (action === "review") return runDeclarationReview(flags);
  if (action === "status") return runDeclarationStatus(flags);
  if (action === "edit") return runDeclarationEdit(flags);
  if (action === "approve") return runDeclarationApprove(flags);
  if (action === "validate") return runDeclarationValidate(flags);
  if (action === "preview") return runDeclarationPreview(flags);
  if (action === "export") return runDeclarationExport(flags);
  if (action === "verify") return runDeclarationVerify(flags);
  return error("Unknown declaration command. Run `aeat app declaration --help`.");
}

function runDeclarationCalculate(flags) {
  const amend = amendContext(flags);
  state.period = flags.period || state.period || "2026-Q1";
  state.calculated = true;
  state.reviewed = false;
  state.approved = false;
  state.validated = false;
  state.previewed = false;
  state.exported = false;
  state.verified = false;
  state.stale = false;
  if (amend.enabled) {
    state.amend = true;
    state.amendId = amend.id;
  }
  return ok(`Declaration calculated.
Period: ${state.period}
Modelo: ${flags.modelo || "not provided"}
Amends prior declaration: ${amend.enabled ? "yes" : "no"}
Justificante id: ${amend.enabled ? amend.id : "not used"}
Pending ledger records: ${state.ledgerPending}
Pending invoices: ${state.invoicePending}
Summary:
  base taxable: simulated
  iva output: simulated
  iva input: simulated
  result: simulated

Next:
  aeat app declaration review --period ${state.period} --modelo ${flags.modelo || "303"}${amend.enabled ? ` --amend --id ${amend.id}` : ""} --format table`);
}

function runDeclarationReview(flags) {
  if (!state.calculated) return warn("No current calculation. Run `aeat app declaration calculate --period PERIOD --modelo MODELO`.");
  state.reviewed = true;
  const pending = state.ledgerPending > 0 || state.invoicePending > 0 || state.invoiceMetadataGaps > 0;
  return (pending ? warn : ok)(`Declaration review
Period: ${flags.period || state.period}
Modelo: ${flags.modelo || "not provided"}
Format: ${flags.format || "table"}
Ledger pending: ${state.ledgerPending}
Invoice pending: ${state.invoicePending}
Invoice metadata gaps: ${state.invoiceMetadataGaps}
Manual edits recorded: ${yesNo(state.edited)}
Approved: ${yesNo(state.approved)}`);
}

function runDeclarationStatus(flags) {
  const filters = valuesOf(flags, "filter");
  const pending = filters.includes("status=pending") || state.ledgerPending > 0 || state.invoicePending > 0 || state.invoiceMetadataGaps > 0;
  return (pending ? warn : ok)(`Declaration status
Filters: ${filters.length ? filters.join(", ") : "none"}
Period: ${flags.period || state.period || "unknown"}
Modelo: ${flags.modelo || "not provided"}
Calculated: ${yesNo(state.calculated)}
Reviewed: ${yesNo(state.reviewed)}
Approved: ${yesNo(state.approved)}
Validated: ${yesNo(state.validated)}
Stale: ${yesNo(state.stale)}
Pending ledger records: ${state.ledgerPending}
Pending invoices: ${state.invoicePending}
Invoice metadata gaps: ${state.invoiceMetadataGaps}`);
}

function runDeclarationEdit(flags) {
  if (!state.calculated) return warn("No current calculation. Run calculate first.");
  const sets = valuesOf(flags, "set");
  if (sets.length === 0) return error("Use one or more `--set column=value` edits.");
  state.edited = true;
  state.reviewed = false;
  state.approved = false;
  state.validated = false;
  state.exported = false;
  return ok(`Declaration values edited.
Columns: ${sets.join(", ")}
Reason: ${flags.reason || "not provided"}
Approval reset: yes`);
}

function runDeclarationApprove(flags) {
  const amend = amendContext(flags);
  if (!state.reviewed) return warn("Review is required before approval.");
  if (state.ledgerPending > 0 || state.invoicePending > 0 || state.invoiceMetadataGaps > 0) {
    return warn(`Approval refused.
Ledger pending: ${state.ledgerPending}
Invoice pending: ${state.invoicePending}
Invoice metadata gaps: ${state.invoiceMetadataGaps}`);
  }
  state.approved = true;
  state.stale = false;
  return ok(`Declaration approved by human.
Period: ${flags.period || state.period}
Modelo: ${flags.modelo || "not provided"}
Amends prior declaration: ${amend.enabled || state.amend ? "yes" : "no"}
Justificante id: ${amend.id || state.amendId || "not used"}
Reason: ${flags.reason || "not provided"}`);
}

function runDeclarationValidate(flags) {
  const amend = amendContext(flags);
  if (!state.approved) {
    if (flags.format === "json" && flags.output) {
      state.validationReport = true;
      return warn(`Validation report saved, but declaration is not exportable.
Output: ${flags.output}
Reason: human approval is missing or unresolved work remains.`);
    }
    return warn("Validation refused. Human approval is required first.");
  }
  if (state.stale) return warn("Validation refused. Declaration is stale after record changes.");
  state.validated = true;
  return ok(`Declaration validated.
Period: ${flags.period || state.period}
Modelo: ${flags.modelo || "not provided"}
Amends prior declaration: ${amend.enabled || state.amend ? "yes" : "no"}
Justificante id: ${amend.id || state.amendId || "not used"}`);
}

function runDeclarationPreview(flags) {
  if (!state.validated) return warn("Preview is available after validation.");
  state.previewed = true;
  return ok(`Preview generated.
Format: ${flags.format || "pdf"}
Filing artifact: no`);
}

function runDeclarationExport(flags) {
  const amend = amendContext(flags);
  if (!state.validated) return warn("Export refused. Validate an approved current declaration first.");
  if (state.stale) return warn("Export refused. Declaration is stale after record changes.");
  if (flags.format !== "boe") return warn("Use `--format boe` only where a modelo supports an AEAT-compatible local artifact.");
  if (!flags.output) return error("Export requires --output PATH.");
  state.exported = true;
  return ok(`Declaration exported.
Period: ${flags.period || state.period}
Modelo: ${flags.modelo || "not provided"}
Format: boe
Output: ${flags.output}
Amends prior declaration: ${amend.enabled || state.amend ? "yes" : "no"}
Justificante id: ${amend.id || state.amendId || "not used"}
Live submission: no`);
}

function runDeclarationVerify(flags) {
  if (flags.export) return warn("`--export` is not valid on verify. Use declaration export --output PATH, then declaration verify --period PERIOD --modelo MODELO --format json --output PATH.");
  if (!state.exported) return warn("No current exported declaration state. Run export first, or use validate --format json --output PATH for repair data.");
  state.verified = true;
  return ok(`Declaration verified.
Period: ${flags.period || state.period || "unknown"}
Modelo: ${flags.modelo || "not provided"}
Format: ${flags.format || "table"}
Output: ${flags.output || "not written"}
Manual AEAT upload remains outside this CLI design.`);
}

function parseSkipFlag(value) {
  if (value === undefined) return null;
  if (value === true) return true;
  if (["true", "1"].includes(String(value).toLowerCase())) return true;
  if (["false", "0"].includes(String(value).toLowerCase())) return false;
  return null;
}

function amendContext(flags) {
  if (!flags.amend) return { enabled: false, id: "" };
  return { enabled: true, id: flags.id || "missing" };
}

function resetDeclarationAfterInputChange() {
  state.calculated = false;
  state.reviewed = false;
  state.approved = false;
  state.validated = false;
  state.previewed = false;
  state.exported = false;
  state.verified = false;
  state.validationReport = false;
  state.stale = true;
}

function inferPeriod(filePath) {
  if (/2025.*q4|q4/i.test(filePath)) return "2025-Q4";
  if (/q2/i.test(filePath)) return "2026-Q2";
  return "2026-Q1";
}

function ok(message) {
  return { kind: "ok", message };
}

function warn(message) {
  return { kind: "warn", message };
}

function error(message) {
  return { kind: "error", message };
}

function nextAction() {
  if (!state.authProvider) return "aeat setup auth configure --provider certificate|clave_movil";
  if (!state.authenticated) return "aeat setup auth login";
  if (!state.profileName) return "aeat setup profile create NAME";
  if (!state.profileValid) return "aeat setup profile validate";
  if (!state.overviewReady) return "aeat app overview --calendar --from DATE --to DATE";
  if (state.imports === 0) return "aeat app ledger import PATH --provider n26 --dry-run";
  if (!state.importVerified) return "aeat app ledger import PATH --provider n26 --verify --original PATH";
  if (state.ledgerPending > 0) return "aeat app ledger list --filter status=pending";
  if (state.invoicePending > 0 || state.invoiceMetadataGaps > 0) return "aeat app invoice list --filter status=pending";
  if (!state.calculated || state.stale) return "aeat app declaration calculate --period PERIOD --modelo MODELO";
  if (!state.reviewed) return "aeat app declaration review --period PERIOD --modelo MODELO --format table";
  if (!state.approved) return "aeat app declaration approve --period PERIOD --modelo MODELO --reason REASON";
  if (!state.validated) return "aeat app declaration validate --period PERIOD --modelo MODELO";
  if (!state.exported) return "aeat app declaration export --period PERIOD --modelo MODELO --format boe --output PATH";
  if (!state.verified) return "aeat app declaration verify --period PERIOD --modelo MODELO --format json --output PATH";
  return "aeat app overview --period PERIOD";
}

function init() {
  bindUi();
  populateScenarios();
  populateTapes();
  setScenario(activeScenario);
  render();
  print("aeat --help", ok(HELP.root));
}

function bindUi() {
  [
    "scenarioSelect",
    "scenarioDescription",
    "tapeSelect",
    "runTapeBtn",
    "stepTapeBtn",
    "tapeCommands",
    "commandTree",
    "terminalOutput",
    "commandForm",
    "commandInput",
    "clearBtn",
    "stateList",
    "nextAction",
    "randomizeBtn",
    "resetBtn",
    "auditRuns",
    "auditSeed",
    "runAuditBtn",
    "playAuditTapeBtn",
    "exportAuditBtn",
    "auditSummary",
  ].forEach((id) => {
    ui[id] = document.getElementById(id);
  });

  ui.commandTree.textContent = COMMAND_TREE;
  ui.commandForm.addEventListener("submit", (event) => {
    event.preventDefault();
    runCommand(ui.commandInput.value);
    ui.commandInput.value = "";
  });
  ui.scenarioSelect.addEventListener("change", () => setScenario(ui.scenarioSelect.value));
  ui.tapeSelect.addEventListener("change", () => {
    activeTape = ui.tapeSelect.value;
    tapeIndex = 0;
    renderTape();
  });
  ui.runTapeBtn.addEventListener("click", runActiveTape);
  ui.stepTapeBtn.addEventListener("click", stepActiveTape);
  ui.clearBtn.addEventListener("click", () => (ui.terminalOutput.innerHTML = ""));
  ui.randomizeBtn.addEventListener("click", randomScenario);
  ui.resetBtn.addEventListener("click", () => setScenario(activeScenario));
  ui.runAuditBtn.addEventListener("click", runAudit);
  ui.playAuditTapeBtn.addEventListener("click", playAuditTape);
  ui.exportAuditBtn.addEventListener("click", exportAudit);
  document.querySelectorAll(".tab").forEach((button) => {
    button.addEventListener("click", () => switchTab(button.dataset.tab));
  });
}

function populateScenarios() {
  ui.scenarioSelect.innerHTML = "";
  Object.entries(SCENARIOS).forEach(([id, scenario]) => {
    const option = document.createElement("option");
    option.value = id;
    option.textContent = scenario.name;
    ui.scenarioSelect.appendChild(option);
  });
}

function populateTapes() {
  ui.tapeSelect.innerHTML = "";
  Object.entries(TAPES).forEach(([id, tape]) => {
    const option = document.createElement("option");
    option.value = id;
    option.textContent = tape.name;
    ui.tapeSelect.appendChild(option);
  });
}

function setScenario(id) {
  activeScenario = id;
  ui.scenarioSelect.value = id;
  state = cloneState(SCENARIOS[id].state);
  tapeIndex = 0;
  ui.scenarioDescription.textContent = SCENARIOS[id].description;
  render();
}

function render() {
  renderState();
  renderTape();
  ui.nextAction.textContent = nextAction();
}

function renderState() {
  const rows = [
    ["Auth provider", state.authProvider || "none"],
    ["Authenticated", yesNo(state.authenticated)],
    ["Profile", state.profileName || "none"],
    ["Profile valid", yesNo(state.profileValid)],
    ["Bank", state.bank || "unknown"],
    ["Period", state.period || "none"],
    ["Imports", String(state.imports)],
    ["Import verified", yesNo(state.importVerified)],
    ["Ledger pending", String(state.ledgerPending)],
    ["Ledger skipped", String(state.skippedRows || state.ledgerExcluded)],
    ["Ledger split rows", String(state.splitRows || 0)],
    ["Document links", String(state.documents)],
    ["Issued invoices", String(state.issuedInvoices)],
    ["Received invoices", String(state.receivedInvoices)],
    ["Invoice pending", String(state.invoicePending)],
    ["Metadata gaps", String(state.invoiceMetadataGaps)],
    ["Calculated", yesNo(state.calculated)],
    ["Reviewed", yesNo(state.reviewed)],
    ["Approved", yesNo(state.approved)],
    ["Validated", yesNo(state.validated)],
    ["Stale", yesNo(state.stale)],
    ["Exported", yesNo(state.exported)],
    ["Verified", yesNo(state.verified)],
    ["Amend flag", state.amendId || yesNo(state.amend)],
  ];
  ui.stateList.innerHTML = "";
  rows.forEach(([term, value]) => {
    const wrapper = document.createElement("div");
    const dt = document.createElement("dt");
    const dd = document.createElement("dd");
    dt.textContent = term;
    dd.textContent = value;
    wrapper.append(dt, dd);
    ui.stateList.appendChild(wrapper);
  });
}

function renderTape() {
  const tape = TAPES[activeTape];
  ui.tapeCommands.innerHTML = "";
  tape.commands.forEach((command, index) => {
    const item = document.createElement("li");
    item.textContent = command;
    if (index < tapeIndex) item.classList.add("done");
    if (index === tapeIndex) item.classList.add("active");
    ui.tapeCommands.appendChild(item);
  });
}

function runCommand(command) {
  const result = execute(command);
  if (!result) return;
  print(command, result);
  render();
}

function print(command, result) {
  const entry = document.createElement("div");
  entry.className = `terminal-entry ${result.kind}`;
  const prompt = document.createElement("div");
  prompt.className = "terminal-command";
  prompt.textContent = `$ ${command}`;
  const output = document.createElement("pre");
  output.textContent = result.message;
  entry.append(prompt, output);
  ui.terminalOutput.appendChild(entry);
  ui.terminalOutput.scrollTop = ui.terminalOutput.scrollHeight;
}

function runActiveTape() {
  const tape = TAPES[activeTape];
  setScenario(tape.scenario);
  activeTape = ui.tapeSelect.value;
  tape.commands.forEach((command) => {
    tapeIndex += 1;
    runCommand(command);
  });
  renderTape();
}

function stepActiveTape() {
  const tape = TAPES[activeTape];
  if (tapeIndex === 0 && activeScenario !== tape.scenario) setScenario(tape.scenario);
  const command = tape.commands[tapeIndex];
  if (!command) return;
  tapeIndex += 1;
  runCommand(command);
  renderTape();
}

function randomScenario() {
  const ids = Object.keys(SCENARIOS);
  const id = ids[Math.floor(Math.random() * ids.length)];
  setScenario(id);
}

function runAudit() {
  if (!window.AeatAuditEngine) return;
  lastAudit = window.AeatAuditEngine.runAudit({
    runs: Number(ui.auditRuns.value) || 250,
    seed: ui.auditSeed.value || "kent-n26-v5",
  });
  renderAudit(lastAudit);
  ui.playAuditTapeBtn.disabled = false;
  ui.exportAuditBtn.disabled = false;
}

function renderAudit(audit) {
  const lines = [
    `Seed: ${audit.seed}`,
    `Runs: ${audit.runs}`,
    ...audit.metrics.map((entry) => `${entry.label}: ${entry.value}`),
    "",
    "Top findings:",
  ];
  audit.findings.slice(0, 5).forEach((section) => {
    const item = section.items[0];
    if (item) lines.push(`${section.title}: ${item.label} (${item.count})`);
  });
  ui.auditSummary.textContent = lines.join("\n");
}

function playAuditTape() {
  if (!lastAudit || !lastAudit.sampleTape) return;
  setScenario("kentN26");
  lastAudit.sampleTape.commands.forEach(runCommand);
}

function exportAudit() {
  if (!lastAudit) return;
  const markdown = [
    "# AEAT CLI v5 audit findings",
    "",
    `Seed: \`${lastAudit.seed}\``,
    `Runs: \`${lastAudit.runs}\``,
    `Generated: \`${lastAudit.generatedAt}\``,
    "",
    "## Metrics",
    "",
    "| Metric | Value |",
    "| --- | --- |",
    ...lastAudit.metrics.map((entry) => `| ${entry.label} | ${entry.value} |`),
    "",
    "## Sample Tape",
    "",
    ...lastAudit.sampleTape.commands.map((command) => `- \`${command}\``),
    "",
  ].join("\n");
  const blob = new Blob([markdown], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "aeat-cli-v5-audit-findings.md";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function switchTab(tab) {
  document.querySelectorAll(".tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === tab);
  });
  document.querySelectorAll(".tab-body").forEach((body) => {
    body.classList.toggle("active", body.id === `${tab}Tab`);
  });
}

function yesNo(value) {
  return value ? "yes" : "no";
}

document.addEventListener("DOMContentLoaded", init);
