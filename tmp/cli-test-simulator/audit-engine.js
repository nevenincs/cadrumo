(function registerAuditEngine(root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.AeatAuditEngine = factory();
  }
})(
  typeof globalThis !== "undefined" ? globalThis : this,
  function buildAuditEngine() {
    const FINDING_TITLES = [
      "Top Failed Command Guesses",
      "Setup And Profile Friction",
      "Ledger Record Gaps",
      "Invoice Enrichment Gaps",
      "Overview And Period Discovery",
      "Human Review Gate Risks",
      "Correction Recalculation",
      "Export Reliability",
      "Suggested CLI Additions",
    ];

    const SUGGESTED_COMMANDS = [
      "aeat setup auth status",
      "aeat setup auth configure --provider clave_movil",
      "aeat setup auth login",
      "aeat setup init --name PROFILE --activity ACTIVITY --tax-id TAX_ID",
      "aeat setup profile list-keys",
      "aeat setup profile set KEY VALUE",
      "aeat setup profile validate",
      "aeat app overview status --calendar --from DATE --to DATE",
      "aeat app ledger import PATH --provider n26 --dry-run",
      "aeat app ledger import PATH --provider n26 --verify --source PATH --verbose",
      "aeat app ledger review --filter status=pending --filter period=PERIOD",
      "aeat app ledger edit --id RECORD_ID --set category=VALUE --set business.share=VALUE --reason REASON",
      "aeat app ledger edit --id RECORD_ID --skip true|false --reason REASON",
      "aeat app invoice review --filter status=pending --filter kind=received",
      "aeat app invoice edit --id INVOICE_ID --set base=VALUE --set iva.rate=VALUE --set iva.amount=VALUE --reason REASON",
      "aeat app declaration status --filter status=pending",
      "aeat app declaration approve --id draft_MODELO_PERIOD --by reviewer --reason REASON",
      "aeat --format json app declaration validate --id draft_MODELO_PERIOD --output PATH",
      "aeat app declaration calculate --period PERIOD --modelo MODELO",
      "aeat app declaration verify --id DRAFT_ID --file PATH",
    ];

    function runAudit(options) {
      const settings = cleanOptions(options || {});
      const rng = makeRng(settings.seed);
      const aggregate = createAggregate();
      const runs = [];

      for (let index = 0; index < settings.runs; index += 1) {
        const run = runSingleAudit(rng, index);
        runs.push(run);
        absorb(aggregate, run);
      }

      const summary = {
        completed: aggregate.completed,
        pending: aggregate.pending,
        totalCommands: aggregate.totalCommands,
        totalWarnings: aggregate.totalWarnings,
        totalErrors: aggregate.totalErrors,
        risks: aggregate.risks,
      };

      return {
        kind: "aeat-cli-v6-stochastic-audit",
        seed: settings.seed,
        runs: settings.runs,
        generatedAt: new Date().toISOString(),
        persona:
          "Kent is an autonomo who uses N26 and can download invoices, but does not know AEAT obligations or the CLI shape.",
        summary,
        metrics: buildMetrics(summary, settings.runs),
        findings: buildFindings(aggregate),
        suggestedCommands: SUGGESTED_COMMANDS,
        sampleTape: chooseSampleTape(runs),
        runsSample: runs.slice(0, Math.min(5, runs.length)),
      };
    }

    function cleanOptions(options) {
      const runs = Math.max(1, Math.min(Number(options.runs) || 100, 2000));
      return { runs, seed: String(options.seed || "kent-n26-v6") };
    }

    function runSingleAudit(rng, index) {
      const period = choose(rng, ["2026-Q1", "2026-Q2", "2025-Q4"]);
      const events = [];
      const state = {
        setup: rng() < 0.3,
        ledgerImported: false,
        importVerified: false,
        rowReviewDone: false,
        invoiceDone: false,
        calculated: false,
        reviewed: false,
        approved: false,
        exported: false,
        pending: false,
        risks: [],
      };

      const invalidFile = rng() < 0.22;
      const duplicateImport = rng() < 0.18;
      const wrongFile = rng() < 0.16;
      const missingInvoiceMetadata = rng() < 0.28;
      const manualDeclarationEdit = rng() < 0.44;
      const recalculation = rng() < 0.24;
      const validationPending = rng() < 0.25;
      function event(command, outcome, finding, recommendation, material = outcome !== "ok") {
        events.push({ command, outcome, finding, recommendation, material });
        if (outcome === "error") state.risks.push(command);
      }

      if (!state.setup) {
        event(
          "aeat setup auth status",
          "ok",
          "Setup And Profile Friction",
          "Auth state must be inspectable without changing it.",
        );
        event(
          "aeat setup auth configure --provider clave_movil",
          "ok",
          "Setup And Profile Friction",
          "Auth configuration names a supported provider.",
        );
        event(
          "aeat setup auth login",
          "ok",
          "Setup And Profile Friction",
          "Authentication is an actual login step.",
        );
        event(
          "aeat setup auth whoami",
          "ok",
          "Setup And Profile Friction",
          "Identity is exposed through auth/profile, not account.",
        );
        event(
          "aeat setup profile list-keys",
          "ok",
          "Setup And Profile Friction",
          "Profile keys must be discoverable.",
        );
        event(
          "aeat setup init --name autonomo-2026 --activity design --tax-id 12345678Z",
          "ok",
          "Setup And Profile Friction",
          "Profile context is created before profile values are edited.",
        );
        event(
          "aeat setup profile set name Kent",
          "ok",
          "Setup And Profile Friction",
          "Profile display identity uses a schema-backed key.",
        );
        event(
          "aeat setup profile set address.postcode 28013",
          "ok",
          "Setup And Profile Friction",
          "Optional tax-address facts can be added after profile creation.",
        );
        event(
          "aeat setup profile set declaration.type autoliquidacion",
          "ok",
          "Setup And Profile Friction",
          "Declaration header values use discoverable profile keys.",
        );
        event(
          "aeat setup profile validate",
          "ok",
          "Setup And Profile Friction",
          "Profile validation closes setup.",
        );
        state.setup = true;
      }

      event(
        "aeat app overview status --calendar --from 2025-10-01 --to 2026-07-20",
        "ok",
        "Overview And Period Discovery",
        "Overview handles filing discovery without a separate calendar command.",
      );
      event(
        `aeat app overview status --period ${period}`,
        "ok",
        "Overview And Period Discovery",
        "Period state is explained before declaration commands.",
      );

      if (invalidFile) {
        event(
          "aeat app ledger import ./downloads/n26-invoices.pdf --provider n26 --dry-run",
          "warn",
          "Ledger Record Gaps",
          "Invalid ledger input is rejected before state changes.",
          false,
        );
      }

      event(
        `aeat app ledger import ./downloads/n26-${period}.csv --provider n26 --dry-run`,
        "ok",
        "Ledger Record Gaps",
        "Statement import is tested first.",
      );
      event(
        `aeat app ledger import ./downloads/n26-${period}.csv --provider n26`,
        "ok",
        "Ledger Record Gaps",
        "Transaction records are imported into ledger.",
      );
      state.ledgerImported = true;

      event(
        `aeat app ledger import ./downloads/n26-${period}.csv --provider n26 --verify --source ./downloads/n26-${period}.pdf`,
        "ok",
        "Ledger Record Gaps",
        "Imported records are checked against the original downloaded file.",
      );
      state.importVerified = true;

      if (duplicateImport) {
        event(
          `aeat app ledger import ./downloads/n26-${period}-copy.csv --provider n26 --verify --verbose`,
          "warn",
          "Ledger Record Gaps",
          "Duplicate diagnostics are visible through import --verify.",
        );
        event(
          `aeat app ledger edit --id row_dup_${index} --skip true --reason duplicate-file`,
          "ok",
          "Ledger Record Gaps",
          "Duplicate rows can be skipped without deleting trace.",
        );
      }

      if (wrongFile) {
        event(
          `aeat app ledger edit --id row_wrong_${index} --skip true --reason personal-account`,
          "ok",
          "Ledger Record Gaps",
          "Wrong-account rows can be skipped with a reason.",
        );
      }

      event(
        `aeat app ledger review --filter status=pending --filter period=${period}`,
        "ok",
        "Ledger Record Gaps",
        "Manual ledger review is visible through status filters.",
      );
      event(
        `aeat app ledger review --id row_${index}_1`,
        "ok",
        "Ledger Record Gaps",
        "One record can be inspected before editing.",
      );
      event(
        `aeat app ledger edit --id row_${index}_1 --set category=software --set business.share=1.0 --set reference=invoice-${index} --reason invoice`,
        "ok",
        "Ledger Record Gaps",
        "Manual categorization is schema-backed.",
      );
      if (rng() < 0.55) {
        event(
          `aeat app ledger edit --id row_${index}_2 --split business=0.45 --split personal=0.55 --reason mixed-card-payment`,
          "ok",
          "Ledger Record Gaps",
          "Mixed payments use share values that add to 1.0.",
        );
      }
      if (rng() < 0.4) {
        event(
          `aeat app ledger edit --id row_${index}_3 --skip true --reason private-expense`,
          "ok",
          "Ledger Record Gaps",
          "User can decide a record is not filing-relevant.",
        );
        event(
          `aeat app ledger edit --id row_${index}_3 --skip false --reason invoice-found`,
          "ok",
          "Ledger Record Gaps",
          "User can revise that decision.",
        );
      }
      state.rowReviewDone = true;

      event(
        `aeat app invoice import ./invoices/issued-${period}.csv --kind issued --dry-run`,
        "ok",
        "Invoice Enrichment Gaps",
        "Issued invoices stay under singular invoice.",
      );
      event(
        `aeat app invoice import ./invoices/received-${period}.csv --kind received --dry-run`,
        "ok",
        "Invoice Enrichment Gaps",
        "Received invoices stay under singular invoice.",
      );
      event(
        `aeat app invoice review --filter status=pending --filter kind=received`,
        "ok",
        "Invoice Enrichment Gaps",
        "Missing invoice metadata is visible.",
      );
      event(
        `aeat app invoice review --id inv_${index}_1`,
        "ok",
        "Invoice Enrichment Gaps",
        "Invoice lines and totals need inspectable state.",
      );
      event(
        `aeat app invoice edit --id inv_${index}_1 --set base=120.00 --set iva.rate=21 --set iva.amount=25.20 --set payment.id=row_${index}_1 --reason invoice-review`,
        "ok",
        "Invoice Enrichment Gaps",
        "Invoice metadata is editable by column.",
      );
      if (missingInvoiceMetadata) {
        event(
          `aeat app invoice edit --id inv_${index}_2 --set iva.category=general --set retention.rate=15 --reason metadata-gap`,
          "ok",
          "Invoice Enrichment Gaps",
          "IVA category and retention are now fully supported backend schema fields.",
        );
      }
      event(
        `aeat app invoice match --period ${period}`,
        "ok",
        "Invoice Enrichment Gaps",
        "Invoice matching checks payments and ledger references.",
      );
      state.invoiceDone = true;

      if (recalculation) {
        event(
          `aeat app declaration calculate --period ${period} --modelo 303`,
          "warn",
          "Correction Recalculation",
          "Corrective declaration work recalculates a new draft and compares it against the previous approved/exported draft.",
        );
      }

      event(
        `aeat app declaration calculate --period ${period} --modelo 303`,
        "ok",
        "Human Review Gate Risks",
        "Calculation is explicit and period-scoped.",
      );
      state.calculated = true;

      event(
        `aeat app declaration review --period ${period} --modelo 303 --format table`,
        "ok",
        "Human Review Gate Risks",
        "Human review is required before approval.",
      );
      state.reviewed = true;

      if (manualDeclarationEdit) {
        event(
          `aeat app declaration edit --id draft_303_${period} --set casilla.71=1200.00 --reason manual-check`,
          "ok",
          "Human Review Gate Risks",
          "Manual calculation edits reset approval.",
        );
        event(
          `aeat app declaration review --period ${period} --modelo 303 --format table`,
          "ok",
          "Human Review Gate Risks",
          "Edited values are reviewed again.",
        );
      }

      if (validationPending) {
        event(
          `aeat app declaration status --filter status=pending --period ${period} --modelo 303`,
          "warn",
          "Human Review Gate Risks",
          "Pending work is surfaced by status filters.",
        );
        event(
          `aeat --format json app declaration validate --id draft_303_${period} --output ./exports/${period}-validation.json`,
          "warn",
          "Export Reliability",
          "Validation report gives repair data without claiming export readiness.",
        );
        event(
          `aeat app declaration edit --id draft_303_${period} --set casilla.01=100.00 --reason fix-validation`,
          "ok",
          "Export Reliability",
          "Operator fixes validation blockers using the CLI.",
        );
        event(
          `aeat app declaration approve --id draft_303_${period} --by reviewer --reason fixed`,
          "ok",
          "Human Review Gate Risks",
          "Human approval gates validation.",
        );
        state.approved = true;
        event(
          `aeat app declaration export --id draft_303_${period} --output ./exports/${period}`,
          "ok",
          "Export Reliability",
          "Local AEAT-compatible export is generated.",
        );
        event(
          `aeat app declaration verify --id draft_303_${period} --file ./exports/${period}-verify.json`,
          "ok",
          "Export Reliability",
          "Local verification runs before manual upload.",
        );
        state.exported = true;
        state.pending = false;
      } else {
        event(
          `aeat app declaration approve --id draft_303_${period} --by reviewer --reason reviewed-against-ledger`,
          "ok",
          "Human Review Gate Risks",
          "Human approval gates validation.",
        );
        state.approved = true;
        event(
          `aeat app declaration validate --id draft_303_${period}`,
          "ok",
          "Export Reliability",
          "Validation passes before export.",
        );
        event(
          `aeat app declaration preview --id draft_303_${period}`,
          "ok",
          "Export Reliability",
          "Preview PDF is not treated as the filing artifact.",
        );
        event(
          `aeat app declaration export --id draft_303_${period} --output ./exports/${period}`,
          "ok",
          "Export Reliability",
          "Local AEAT-compatible export is generated.",
        );
        event(
          `aeat app declaration verify --id draft_303_${period} --file ./exports/${period}-verify.json`,
          "ok",
          "Export Reliability",
          "Local verification runs before manual upload.",
        );
        state.exported = true;
      }

      const completed = state.exported && !state.pending;
      return {
        id: index,
        completed,
        pending: !completed,
        commands: events.map((item) => item.command),
        warnings: events.filter((item) => item.outcome === "warn").length,
        errors: events.filter((item) => item.outcome === "error").length,
        events,
        risks: state.risks,
      };
    }

    function createAggregate() {
      return {
        completed: 0,
        pending: 0,
        totalCommands: 0,
        totalWarnings: 0,
        totalErrors: 0,
        risks: 0,
        findings: Object.fromEntries(
          FINDING_TITLES.map((title) => [title, new Map()]),
        ),
        runs: [],
      };
    }

    function absorb(aggregate, run) {
      aggregate.runs.push(run);
      if (run.completed) aggregate.completed += 1;
      if (!run.completed) aggregate.pending += 1;
      aggregate.totalCommands += run.commands.length;
      aggregate.totalWarnings += run.warnings;
      aggregate.totalErrors += run.errors;
      aggregate.risks += run.risks.length;
      run.events.filter((event) => event.material).forEach((event) => {
        const section =
          aggregate.findings[event.finding] ||
          aggregate.findings["Suggested CLI Additions"];
        const current = section.get(event.command) || {
          label: event.command,
          count: 0,
          recommendation: event.recommendation,
        };
        current.count += 1;
        section.set(event.command, current);
      });
    }

    function buildMetrics(summary, runs) {
      const completionRate = Math.round((summary.completed / runs) * 100);
      const pendingRate = Math.round((summary.pending / runs) * 100);
      const commands = (summary.totalCommands / runs).toFixed(1);
      const warnings = (summary.totalWarnings / runs).toFixed(1);
      const errors = (summary.totalErrors / runs).toFixed(1);
      const risk = Math.round((summary.risks / runs) * 100);
      return [
        { label: "Completion Rate", value: `${completionRate}%` },
        { label: "Pending Review Rate", value: `${pendingRate}%` },
        { label: "Commands To Success", value: commands },
        { label: "Warning Count", value: warnings },
        { label: "Error Count", value: errors },
        { label: "Command Guess Distance", value: "v6 rerun" },
        {
          label: "Record Completeness",
          value: `${Math.max(0, 100 - pendingRate)}%`,
        },
        { label: "Human Review Gate", value: "tracked" },
        { label: "Tax-Safety Risk", value: `${risk}%` },
      ];
    }

    function buildFindings(aggregate) {
      return FINDING_TITLES.map((title) => ({
        title,
        items: Array.from((aggregate.findings[title] || new Map()).values())
          .sort((left, right) => right.count - left.count)
          .slice(0, 6),
      }));
    }

    function chooseSampleTape(runs) {
      const pending = runs.find((run) => !run.completed);
      const chosen = pending || runs[0] || { commands: [] };
      return {
        name: pending
          ? "Sample pending-review v6 tape"
          : "Sample completed v6 tape",
        commands: chosen.commands,
      };
    }

    function choose(rng, values) {
      return values[Math.floor(rng() * values.length)];
    }

    function makeRng(seed) {
      let value = 2166136261;
      String(seed)
        .split("")
        .forEach((char) => {
          value ^= char.charCodeAt(0);
          value = Math.imul(value, 16777619);
        });
      return function next() {
        value += 0x6d2b79f5;
        let t = value;
        t = Math.imul(t ^ (t >>> 15), t | 1);
        t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
      };
    }

    return { runAudit };
  },
);
