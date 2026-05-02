(function () {
  const STORAGE_KEY = "aeat-cli-approval-session-v5";
  const DRAFT_STORAGE_KEY = "aeat-cli-approval-session-v5-drafts";

  const sections = [
    {
      id: "root",
      title: "Root Boundary",
      status: "accepted anchor",
      question: "Approve the root boundary for v5?",
      context:
        "The CLI has two root domains. Setup contains prerequisites. App contains operational tax work. No developer command family belongs in this user surface.",
      shape: `aeat setup
  Configure authentication, profile data, and local readiness.

aeat app
  Work through overview, ledger, invoice, and declaration workflows.`,
      options: [
        option("approve-root-v5", "Approve root", "Keep setup/app with this wording.", true),
        option("revise-root-v5", "Revise wording", "Keep the boundary but change the descriptions."),
        option("block-root-v5", "Needs redesign", "Do not carry this root framing forward."),
      ],
    },
    {
      id: "setup-auth",
      title: "Setup Auth",
      status: "accepted anchor",
      question: "Approve authentication as provider configuration plus login?",
      context:
        "Authentication remains setup work. Provider support must reflect implemented backend behavior; unsupported providers stay research-only.",
      shape: `aeat setup auth providers
  Show implemented and research-only authentication providers.

aeat setup auth configure --provider certificate --file PATH
  Configure certificate authentication.

aeat setup auth configure --provider clave_movil
  Configure Clave Movil authentication.

aeat setup auth login
  Start the configured AEAT login flow.

aeat setup auth status
  Show provider and login state.

aeat setup auth whoami
  Show the authenticated identity when available.

aeat setup auth logout
  Clear active authentication state.`,
      options: [
        option("approve-auth-v5", "Approve auth", "Use provider configure/login/status/whoami/logout.", true),
        option("revise-auth-v5", "Revise auth", "Change provider wording or login commands."),
        option("block-auth-v5", "Needs redesign", "Authentication still does not model user login correctly."),
      ],
    },
    {
      id: "setup-profile",
      title: "Setup Profile",
      status: "accepted anchor",
      question: "Approve a schema-backed profile editor?",
      context:
        "Profile stores taxpayer facts used by app workflows. Keys must be discoverable and validated before filing work starts.",
      shape: `aeat setup profile create NAME
  Create a taxpayer profile.

aeat setup profile use NAME
  Select the active profile.

aeat setup profile show
  Show current profile facts and validation state.

aeat setup profile list-keys
  List editable keys, types, requiredness, and descriptions.

aeat setup profile get KEY
  Read one profile value.

aeat setup profile set KEY VALUE
  Set one schema-backed value.

aeat setup profile unset KEY
  Clear one optional value.

aeat setup profile validate
  Validate completeness and consistency.

aeat setup profile edit
  Open an interactive schema-backed editor.`,
      options: [
        option("approve-profile-v5", "Approve profile", "Use dictionary-backed keys and validation.", true),
        option("revise-profile-v5", "Revise profile", "Keep schema editing but change commands or keys."),
        option("block-profile-v5", "Needs redesign", "Profile is still too weak or unclear."),
      ],
    },
    {
      id: "app-domains",
      title: "App Domains",
      status: "accepted anchor",
      question: "Approve the singular app domain map?",
      context:
        "The app surface stays singular and user-operational. Calendar discovery remains inside overview. Supporting files are fields on records.",
      shape: `aeat app overview
  Show profile-scoped readiness, unresolved work, declaration status, and next actions.

aeat app ledger
  Import, inspect, and edit transaction records.

aeat app invoice
  Import, inspect, enrich, and match issued and received invoice records.

aeat app declaration
  Calculate, review, approve, validate, export, verify, and amend declarations.`,
      options: [
        option("approve-domains-v5", "Approve domains", "Use overview, ledger, invoice, declaration.", true),
        option("revise-domains-v5", "Revise domains", "Keep singular nouns but change the map."),
        option("block-domains-v5", "Needs redesign", "The domain structure still is not usable."),
      ],
    },
    {
      id: "ledger-backend",
      title: "Ledger Backend Contract",
      status: "backend audit",
      question: "Approve ledger fields only as a backend-audit contract?",
      context:
        "This is not a manual approval of a schema. The CLI must be driven by backend library behavior and migrations, then expose only auditable user actions.",
      shape: `Backend-owned ledger facts:
  stable row id
  source import identity
  source transaction identity
  period
  date
  description
  amount
  direction
  status
  category
  business.share
  skip
  reference
  comments
  invoice.id
  document.path
  modelo
  review.history
  split.metadata

Required audit:
  confirm existing fields
  define missing migrations
  define edit history
  define skip state
  define split and clear behavior`,
      options: [
        option("accept-ledger-audit-v5", "Accept audit gate", "Treat fields as backend-driven requirements, not manual approval.", true),
        option("revise-ledger-contract-v5", "Revise contract", "Change field names or audit requirements."),
        option("block-ledger-contract-v5", "Needs redesign", "Ledger remains too ambiguous."),
      ],
    },
    {
      id: "ledger-import",
      title: "Ledger Import Action",
      status: "reworked",
      question: "Approve import as an action with verification flags?",
      context:
        "Import is not a command domain. Gap checks, duplicate checks, and original-file checks are one verification behavior on the import action.",
      shape: `aeat app ledger import PATH --provider n26 --dry-run
  Validate a transaction file before saving records.

aeat app ledger import PATH --provider n26 --verify --original ./downloads/n26-jan.pdf --verbose
  Import records and run backend verification, including source-file, gap, duplicate, and parser diagnostics.

Rejected:
  aeat app ledger import verify ...
  aeat app ledger import gaps ...
  aeat app ledger import duplicates ...
  aeat app ledger import exclude ...
  aeat app ledger import restore ...`,
      options: [
        option("approve-ledger-import-v5", "Approve import", "Use import PATH with --provider and --verify.", true),
        option("revise-ledger-import-v5", "Revise import", "Change verification or original-file wording."),
        option("block-ledger-import-v5", "Needs redesign", "Import grammar is still not concrete enough."),
      ],
    },
    {
      id: "ledger-inspection",
      title: "Ledger Inspection",
      status: "reworked",
      question: "Approve list and show as the read-only ledger surface?",
      context:
        "A user needs to inspect imported records before editing. List and show must expose stable row identities, review status, provenance, and filterable work queues.",
      shape: `aeat app ledger list --filter status=pending --filter period=2026-Q1
  List records using cohesive filters.

aeat app ledger list --filter issue=duplicate --filter period=2026-Q1
  Inspect duplicate diagnostics produced by import verification.

aeat app ledger show --id row_1042 --verbose
  Show one record, provenance, classification history, linked invoice/category data, notes, document path, and skip state.`,
      options: [
        option("approve-ledger-inspection-v5", "Approve inspection", "Use list/show with filters and stable ids.", true),
        option("revise-ledger-inspection-v5", "Revise inspection", "Change filter syntax or displayed fields."),
        option("block-ledger-inspection-v5", "Needs redesign", "Read-only ledger work is still unclear."),
      ],
    },
    {
      id: "ledger-edit",
      title: "Ledger Edit, Skip, Split",
      status: "reworked",
      question: "Approve edit, skip, and normalized split behavior?",
      context:
        "Exclude and restore are removed. Skipping is an auditable edit. Splits use normalized shares that must add to 1.0 and require backend support for source identity, split metadata, and clearing a split.",
      shape: `aeat app ledger edit --id row_1042 --set category=software --set business.share=1.0 --set reference=inv_901 --reason invoice
  Edit schema-backed ledger fields.

aeat app ledger edit --id row_1051 --skip true --reason private-expense
  Mark a record skipped without deleting it.

aeat app ledger edit --id row_1051 --skip false --reason invoice-found
  Return a skipped record to review.

aeat app ledger split --id row_1050 --business 0.45 --personal 0.55 --reason mixed-card-payment
  Split one source transaction into normalized shares.

aeat app ledger split --id row_1050 --clear --reason corrected-single-use
  Clear split metadata and return to the source transaction.`,
      options: [
        option("approve-ledger-edit-v5", "Approve edit model", "Use edit --skip and normalized split/clear.", true),
        option("revise-ledger-edit-v5", "Revise edit model", "Change edit, skip, split, or clear syntax."),
        option("block-ledger-edit-v5", "Needs redesign", "Ledger row work still does not model real review."),
      ],
    },
    {
      id: "record-files",
      title: "Record Files",
      status: "accepted anchor",
      question: "Approve supporting files as record fields?",
      context:
        "No standalone file domain is approved. Evidence that affects tax eligibility is attached to the relevant ledger or invoice record.",
      shape: `aeat app ledger edit --id row_1042 --set document.path=./receipts/receipt-901.pdf --set reference=inv_901 --reason invoice-found
  Link a supporting file through ledger columns.

aeat app invoice edit --id inv_2041 --set document.path=./invoices/inv-2041.pdf --set payment.id=row_1042 --reason invoice-review
  Link an invoice file through invoice columns.`,
      options: [
        option("approve-record-files-v5", "Approve fields", "Use record fields for supporting files and references.", true),
        option("revise-record-files-v5", "Revise fields", "Change file/reference/comment field names."),
        option("block-record-files-v5", "Needs redesign", "Supporting files still need a different model."),
      ],
    },
    {
      id: "invoice-backend",
      title: "Invoice Backend Contract",
      status: "backend audit",
      question: "Approve invoice fields only as a backend-audit contract?",
      context:
        "Invoice must be separated from ledger transaction evidence. Issued and received invoice records are tax documents with their own review and matching state.",
      shape: `Backend-owned invoice facts:
  id
  kind
  status
  issue_date
  counterparty
  base
  iva.rate
  iva.amount
  iva.category
  retention.rate
  retention.amount
  payment.id
  document.path
  reference
  comments
  lines
  review.history

Required audit:
  confirm retention fields
  confirm IVA category mapping
  confirm payment linkage
  confirm import/edit history`,
      options: [
        option("accept-invoice-audit-v5", "Accept audit gate", "Treat fields as backend-driven requirements.", true),
        option("revise-invoice-contract-v5", "Revise contract", "Change invoice fields or audit requirements."),
        option("block-invoice-contract-v5", "Needs redesign", "Invoice design is still too thin."),
      ],
    },
    {
      id: "invoice-review",
      title: "Invoice Review",
      status: "reworked",
      question: "Approve invoice import, list, show, edit, and match?",
      context:
        "Issued and received invoice records stay under singular invoice. Review uses the same filter and schema-backed edit pattern as ledger.",
      shape: `aeat app invoice import PATH --kind issued --dry-run
  Validate issued invoice records.

aeat app invoice import PATH --kind received --dry-run
  Validate received invoice records.

aeat app invoice list --filter status=pending --filter kind=received
  List invoice records that need metadata review.

aeat app invoice show --id inv_2041 --verbose
  Show invoice lines, totals, payment linkage, references, comments, and backend audit gaps.

aeat app invoice edit --id inv_2041 --set base=120.00 --set iva.rate=21 --set iva.amount=25.20 --set iva.category=general --set retention.rate=15 --set payment.id=row_1042 --reason invoice-review
  Enrich invoice metadata.

aeat app invoice match --period 2026-Q1
  Match invoice records to payments and ledger records.`,
      options: [
        option("approve-invoice-review-v5", "Approve review", "Use singular invoice with filters and schema-backed edits.", true),
        option("revise-invoice-review-v5", "Revise review", "Change invoice kind, edit, or matching grammar."),
        option("block-invoice-review-v5", "Needs redesign", "Invoice workflow still is not granular enough."),
      ],
    },
    {
      id: "overview-resume",
      title: "Overview And Resume",
      status: "accepted anchor",
      question: "Approve overview as the period and resume surface?",
      context:
        "Interrupted work resumes from profile-scoped state. No user-facing session or workspace command is required for normal continuation.",
      shape: `aeat app overview
  Show profile readiness, pending record counts, declaration state, and next action.

aeat app overview --calendar --from 2025-10-01 --to 2026-07-20
  Show period states across a date range.

aeat app overview --period 2026-Q1 --verbose
  Explain local state, imported AEAT state where available, unresolved work, and next commands.`,
      options: [
        option("approve-overview-v5", "Approve overview", "Use overview for discovery and resume.", true),
        option("revise-overview-v5", "Revise overview", "Change calendar, period, or resume wording."),
        option("block-overview-v5", "Needs redesign", "Period discovery still is not usable."),
      ],
    },
    {
      id: "declaration-calculate",
      title: "Declaration Calculate",
      status: "reworked",
      question: "Approve calculate output as a visible summary, not a silent operation?",
      context:
        "Bare calculate must return a compact human-readable calculation summary and next action. If inputs are unresolved, it returns blockers and repair commands instead of pretending the draft is ready.",
      shape: `aeat app declaration calculate --period 2026-Q1 --modelo 303
  Calculate from current profile, ledger, invoice, and supported backend data.
  Print a compact table of calculated values, warnings, blocker counts, and next action.

aeat app declaration calculate --period 2026-Q1 --modelo 303 --verbose
  Include backend fingerprints, source counts, and diagnostic detail.

Invalid operation behavior:
  show unresolved ledger rows
  show unresolved invoice records
  show missing profile facts
  show the command needed to repair the first blocker`,
      options: [
        option("approve-calculate-v5", "Approve output", "Bare calculate prints summary and next action.", true),
        option("revise-calculate-v5", "Revise output", "Change calculate summary or invalid-operation behavior."),
        option("block-calculate-v5", "Needs redesign", "Calculate behavior is still ambiguous."),
      ],
    },
    {
      id: "declaration-review",
      title: "Declaration Review Gates",
      status: "accepted anchor",
      question: "Approve review, status, edit, and approve gates?",
      context:
        "Declaration work is human-gated. Manual edits reset approval. Approval is required before validation and export.",
      shape: `aeat app declaration review --period 2026-Q1 --modelo 303 --format table
  Review calculated values, assumptions, warnings, and changed inputs.

aeat app declaration status --filter status=pending --period 2026-Q1 --modelo 303
  Show unresolved work through cohesive filters.

aeat app declaration edit --period 2026-Q1 --modelo 303 --set casilla.71=1200.00 --reason manual-check
  Record an auditable manual change and reset approval.

aeat app declaration approve --period 2026-Q1 --modelo 303 --reason reviewed-against-ledger
  Approve the reviewed declaration state.`,
      options: [
        option("approve-declaration-review-v5", "Approve gates", "Use review/status/edit/approve.", true),
        option("revise-declaration-review-v5", "Revise gates", "Change review, status, edit, or approval syntax."),
        option("block-declaration-review-v5", "Needs redesign", "Declaration review still is unsafe or unclear."),
      ],
    },
    {
      id: "declaration-export",
      title: "Declaration Export And Verify",
      status: "reworked",
      question: "Approve export and verify separation?",
      context:
        "Export writes a local artifact with an explicit output path. Verify does not take an export flag; it verifies declaration state and may write a JSON audit report.",
      shape: `aeat app declaration validate --period 2026-Q1 --modelo 303
  Validate only after human approval.

aeat app declaration validate --period 2026-Q1 --modelo 303 --format json --output ./exports/2026-q1-validation.json
  Write a validation report when unresolved work remains.

aeat app declaration preview --period 2026-Q1 --modelo 303 --format pdf
  Create a non-filing preview where supported.

aeat app declaration export --period 2026-Q1 --modelo 303 --format boe --output ./exports/2026-q1
  Export a local AEAT-compatible file where supported.

aeat app declaration verify --period 2026-Q1 --modelo 303 --format json --output ./exports/2026-q1-verify.json
  Verify declaration state and write machine-readable audit output.

Rejected:
  aeat app declaration verify --export PATH`,
      options: [
        option("approve-declaration-export-v5", "Approve outputs", "Use explicit export --output and verify --format json --output.", true),
        option("revise-declaration-export-v5", "Revise outputs", "Change output names or gating wording."),
        option("block-declaration-export-v5", "Needs redesign", "Export behavior still is not safe enough."),
      ],
    },
    {
      id: "amend-flag",
      title: "Amend Flag",
      status: "reworked",
      question: "Approve corrective declaration work through --amend --id?",
      context:
        "There is no corrective-filing noun or subcommand. The declaration command itself states that it amends a prior AEAT declaration. The id is the prior AEAT justificante id; do not add a separate CSV code concept.",
      shape: `aeat app declaration calculate --period 2026-Q1 --modelo 303 --amend --id 3031234567890
  Calculate a declaration that amends the prior declaration identified by AEAT justificante id.

aeat app declaration review --period 2026-Q1 --modelo 303 --amend --id 3031234567890 --format table
  Review changed values and blocker state.

aeat app declaration approve --period 2026-Q1 --modelo 303 --amend --id 3031234567890 --reason amend-reviewed
  Approve the amended declaration state.

aeat app declaration export --period 2026-Q1 --modelo 303 --amend --id 3031234567890 --format boe --output ./exports/2026-q1-amend
  Export the amended declaration artifact.

Research rule:
  where AEAT requires latest prior rectification identity, --id must refer to that justificante id.`,
      options: [
        option("approve-amend-flag-v5", "Approve flag", "Use --amend --id on declaration commands.", true),
        option("revise-amend-flag-v5", "Revise flag", "Change id wording or command coverage."),
        option("block-amend-flag-v5", "Needs redesign", "Corrective declaration modeling is still wrong."),
      ],
    },
    {
      id: "safety-status",
      title: "Safety And Status",
      status: "in progress",
      question: "Approve v5 as the next review candidate, not implementation approval?",
      context:
        "This approval session is design review only. Production CLI implementation still requires backend audit, tests, and a separate implementation plan.",
      shape: `Global rules:
  --help is required at every group.
  --verbose is required on diagnostic and state-sensitive workflows.
  --dry-run is required where practical on import, edit, approve, validate, and export commands.
  --format table|json controls CLI response format.
  --format boe is only for supported AEAT-compatible local declaration artifacts.
  --format pdf is only for previews.
  No live submission command is approved.

V5 status:
  review candidate
  not approved for production implementation

Required before implementation:
  backend audit for profile schema
  backend audit for ledger fields, skip state, and split metadata
  backend audit for invoice retention, IVA category, and payment linkage
  declaration calculation output contract
  export and verify output contract
  corrective declaration behavior against AEAT justificante rules`,
      options: [
        option("approve-status-v5", "Approve candidate", "Accept v5 as the next review candidate.", true),
        option("revise-status-v5", "Revise status", "More comments must be incorporated before review."),
        option("block-status-v5", "Needs redesign", "Do not proceed from this candidate."),
      ],
    },
  ];

  const els = {
    sectionNav: document.getElementById("sectionNav"),
    progressLabel: document.getElementById("progressLabel"),
    progressBar: document.getElementById("progressBar"),
    sectionTitle: document.getElementById("sectionTitle"),
    sectionQuestion: document.getElementById("sectionQuestion"),
    sectionContext: document.getElementById("sectionContext"),
    sectionShape: document.getElementById("sectionShape"),
    decisionOptions: document.getElementById("decisionOptions"),
    decisionNote: document.getElementById("decisionNote"),
    decisionBadge: document.getElementById("decisionBadge"),
    previousBtn: document.getElementById("previousBtn"),
    saveBtn: document.getElementById("saveBtn"),
    nextBtn: document.getElementById("nextBtn"),
    decisionLog: document.getElementById("decisionLog"),
    jsonOutput: document.getElementById("jsonOutput"),
    copyJsonBtn: document.getElementById("copyJsonBtn"),
    downloadJsonBtn: document.getElementById("downloadJsonBtn"),
    resetSessionBtn: document.getElementById("resetSessionBtn"),
  };

  let currentIndex = 0;
  let decisions = loadJson(STORAGE_KEY);
  let draftState = loadJson(DRAFT_STORAGE_KEY);
  const pendingOptions = {};
  const noteDrafts = {};
  let selectedOption = null;

  Object.entries(draftState).forEach(([id, draft]) => {
    if (!draft) return;
    if (draft.optionId) pendingOptions[id] = draft.optionId;
    if (draft.note !== undefined) noteDrafts[id] = draft.note;
  });

  function option(id, label, detail, recommended) {
    return { id, label, detail, recommended: Boolean(recommended) };
  }

  function loadJson(key) {
    try {
      return JSON.parse(localStorage.getItem(key) || "{}");
    } catch {
      return {};
    }
  }

  function persist() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(decisions, null, 2));
  }

  function persistDrafts() {
    localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(draftState, null, 2));
  }

  function currentSection() {
    return sections[currentIndex];
  }

  function captureDraft() {
    const section = currentSection();
    if (!section) return;
    noteDrafts[section.id] = els.decisionNote.value;
    draftState[section.id] = {
      optionId: selectedOption || null,
      optionLabel: selectedOption ? (section.options.find((item) => item.id === selectedOption) || {}).label || "" : "",
      note: els.decisionNote.value,
      updatedAt: new Date().toISOString(),
    };
    persistDrafts();
  }

  function renderNav() {
    els.sectionNav.innerHTML = "";
    sections.forEach((section, index) => {
      const item = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.className = index === currentIndex ? "active" : "";
      button.innerHTML = `<span>${index + 1}. ${escapeHtml(section.title)}</span><small>${escapeHtml(decisions[section.id] ? decisions[section.id].optionLabel : section.status)}</small>`;
      button.addEventListener("click", () => {
        captureDraft();
        currentIndex = index;
        render();
      });
      item.appendChild(button);
      els.sectionNav.appendChild(item);
    });
  }

  function renderSection() {
    const section = currentSection();
    const decision = decisions[section.id];
    selectedOption = pendingOptions[section.id] || (decision ? decision.optionId : null);

    els.progressLabel.textContent = `Section ${currentIndex + 1} of ${sections.length} - ${section.status}`;
    els.progressBar.style.width = `${((currentIndex + 1) / sections.length) * 100}%`;
    els.sectionTitle.textContent = section.title;
    els.sectionQuestion.textContent = section.question;
    els.sectionContext.textContent = section.context;
    els.sectionShape.textContent = section.shape;
    els.decisionNote.value =
      noteDrafts[section.id] !== undefined ? noteDrafts[section.id] : decision ? decision.note || "" : "";

    const savedOption = decision ? section.options.find((item) => item.id === decision.optionId) : null;
    els.decisionBadge.textContent = decision ? decision.optionLabel : section.status;
    els.decisionBadge.className = `badge ${decision ? (savedOption && savedOption.recommended ? "ok" : "warn") : badgeForStatus(section.status)}`;

    els.decisionOptions.innerHTML = "";
    section.options.forEach((item) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `decision-option ${selectedOption === item.id ? "selected" : ""}`;
      button.innerHTML = `
        <span>
          ${escapeHtml(item.label)}
          ${item.recommended ? "<em>recommended</em>" : ""}
        </span>
        <small>${escapeHtml(item.detail)}</small>
      `;
      button.addEventListener("click", () => {
        captureDraft();
        selectedOption = item.id;
        pendingOptions[section.id] = item.id;
        persistDrafts();
        renderSection();
      });
      els.decisionOptions.appendChild(button);
    });

    els.previousBtn.disabled = currentIndex === 0;
    els.nextBtn.textContent = currentIndex === sections.length - 1 ? "Stay here" : "Skip for now";
    els.saveBtn.textContent = currentIndex === sections.length - 1 ? "Save decision" : "Save and continue";
  }

  function renderLog() {
    els.decisionLog.innerHTML = "";
    sections.forEach((section) => {
      const row = document.createElement("div");
      const term = document.createElement("dt");
      const description = document.createElement("dd");
      const decision = decisions[section.id];
      term.textContent = section.title;
      description.innerHTML = decision
        ? `<span class="badge ok">${escapeHtml(decision.optionLabel)}</span>`
        : `<span class="badge ${badgeForStatus(section.status)}">${escapeHtml(section.status)}</span>`;
      row.append(term, description);
      els.decisionLog.appendChild(row);
    });
    els.jsonOutput.value = JSON.stringify(buildExport(), null, 2);
  }

  function buildExport() {
    return {
      artifact: "aeat-cli-redesign-approval-session-v5",
      generatedAt: new Date().toISOString(),
      adr: ".vault/adr/2026-05-02-aeat-cli-redesign-adr.md",
      reference: ".vault/reference/2026-05-02-aeat-cli-redesign-reference.md",
      recoveredInput: "browser localStorage aeat-cli-approval-session-v4",
      drafts: sections.map((section) => ({
        id: section.id,
        title: section.title,
        status: section.status,
        draft: draftState[section.id] || null,
      })),
      sections: sections.map((section) => ({
        id: section.id,
        title: section.title,
        status: section.status,
        question: section.question,
        decision: decisions[section.id] || null,
      })),
    };
  }

  function saveCurrentDecision(advance) {
    captureDraft();
    const section = currentSection();
    const selected = section.options.find((item) => item.id === selectedOption);
    if (!selected) {
      els.decisionOptions.classList.add("needs-choice");
      window.setTimeout(() => els.decisionOptions.classList.remove("needs-choice"), 450);
      return;
    }

    decisions[section.id] = {
      optionId: selected.id,
      optionLabel: selected.label,
      note: (noteDrafts[section.id] || "").trim(),
      savedAt: new Date().toISOString(),
    };
    delete pendingOptions[section.id];
    delete draftState[section.id];
    persistDrafts();
    persist();

    if (advance && currentIndex < sections.length - 1) currentIndex += 1;
    render();
  }

  function badgeForStatus(status) {
    if (status.includes("accepted")) return "ok";
    if (status.includes("progress") || status.includes("audit")) return "warn";
    return "blocked";
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function render() {
    renderNav();
    renderSection();
    renderLog();
  }

  els.previousBtn.addEventListener("click", () => {
    captureDraft();
    currentIndex = Math.max(0, currentIndex - 1);
    render();
  });

  els.nextBtn.addEventListener("click", () => {
    captureDraft();
    currentIndex = Math.min(sections.length - 1, currentIndex + 1);
    render();
  });

  els.saveBtn.addEventListener("click", () => saveCurrentDecision(true));
  els.decisionNote.addEventListener("input", captureDraft);

  els.resetSessionBtn.addEventListener("click", () => {
    if (!window.confirm("Reset all approval decisions?")) return;
    decisions = {};
    draftState = {};
    Object.keys(pendingOptions).forEach((key) => delete pendingOptions[key]);
    Object.keys(noteDrafts).forEach((key) => delete noteDrafts[key]);
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(DRAFT_STORAGE_KEY);
    currentIndex = 0;
    render();
  });

  els.copyJsonBtn.addEventListener("click", async () => {
    els.jsonOutput.value = JSON.stringify(buildExport(), null, 2);
    els.jsonOutput.select();
    try {
      await navigator.clipboard.writeText(els.jsonOutput.value);
      els.copyJsonBtn.textContent = "Copied";
      window.setTimeout(() => (els.copyJsonBtn.textContent = "Copy JSON"), 1200);
    } catch {
      document.execCommand("copy");
    }
  });

  els.downloadJsonBtn.addEventListener("click", () => {
    const blob = new Blob([JSON.stringify(buildExport(), null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "aeat-cli-approval-session-v5.json";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  });

  render();
})();
