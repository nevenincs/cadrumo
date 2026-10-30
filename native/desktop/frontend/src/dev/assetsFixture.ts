// The scenario ledger's answers to the Assets tab's provisional operations:
// a register that spans decades, with every state of a plan, a timeline and
// a write the tab shows. Its elements are synthetic. Its figures are fixed
// text; only a baja re-adds the claims it leaves. Elements made through the
// admitted create and correct operations appear beside the seeded ones, with
// the history those operations kept.

import type {
  AcquisitionCandidate,
  Amount,
  AssetBaja,
  AssetCounts,
  AssetListRow,
  Descriptor,
  DescriptorField,
  DraftedOperationId,
  FormField,
  FormKind,
  FormOptions,
  PlanClaim,
  PlanElection,
  PlanRow,
  ProvisionalOperationId,
  TimelineEvent,
} from "@/components/ledger/assets/assetsContract";
import type { JsonObject, JsonValue } from "../shell/ledger";

type Handler = (request: JsonObject) => JsonObject;

type Tools = {
  now: () => string;
  hex64: (text: string) => string;
  /** Throws the refusal of a request its contract would not decode. */
  invalid: () => never;
  /** Throws a refusal the ledger settles with its own result as detail. */
  stop: (reason: string, detail: JsonObject) => never;
};

/** What the admitted create and correct operations hold of an element. */
type AdmittedAsset = {
  revisions: { revision: JsonObject; revision_id: string }[];
};

type Held = {
  id: string;
  name: string | null;
  serial: string | null;
  fields: DescriptorField[];
  kind_key: string;
  method_key: string;
  in_service_date: string;
  revision_number: number;
  baja: AssetBaja | null;
  plan: PlanRow[];
  /** Gives a plan its pending figures, as the backend states them. */
  pending: (rows: PlanRow[]) => PlanRow[];
  events: TimelineEvent[];
  /** How many admitted revisions are already in `events`. */
  admitted: number;
  /** What an element made through the add form was made from. */
  made?: {
    basis: string;
    non_deductible_iva: string;
    acquisition: string;
  };
  /** The facts a correction last stated. */
  stated?: { basis?: string; non_deductible_iva?: string };
};

type Draft = Omit<TimelineEvent, "sequence" | "replaces_sequence"> & {
  key?: string;
  replaces?: string;
};

/** An answer as the relay carries it: a copy, so a reader never holds the
 * register's own records. */
const json = <T>(value: T): JsonObject =>
  JSON.parse(JSON.stringify(value)) as JsonObject;
const dec = (value: string): Amount => ({ decimal: value });
const yearOf = (date: string) => Number(date.slice(0, 4));
const span = (from: number, to: number) =>
  Array.from({ length: to - from + 1 }, (_, at) => from + at);
const daysIn = (year: number) =>
  (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0 ? 366 : 365;
const cents = (amount: Amount) =>
  amount === null ? 0 : Math.round(Number(amount.decimal) * 100);
const total = (claims: readonly PlanClaim[]): Amount =>
  claims.length === 0
    ? null
    : dec(
        (
          claims.reduce((sum, claim) => sum + cents(claim.amount), 0) / 100
        ).toFixed(2),
      );

/**
 * Stands in for the backend's pending figures, which the views only draw: the
 * basis less what the schedule allows by each year's end, or for a free
 * method less what is claimed. A year with no figure to go on has none, and
 * every year after it is unknown too.
 */
const pendingBy =
  (basis: string, by: "schedule" | "claims") =>
  (rows: PlanRow[]): PlanRow[] => {
    let left: number | null = cents(dec(basis));
    return rows.map((planned) => {
      const step = by === "schedule" ? planned.planned : planned.claimed;
      if (left === null || step === null) {
        left = null;
        return { ...planned, pending_end: null };
      }
      left -= cents(step);
      return { ...planned, pending_end: dec((left / 100).toFixed(2)) };
    });
  };
const unchanged = (rows: PlanRow[]) => rows;

/** The tokens each choice offers and the label key that words each. */
const REASONS = {
  sale: "desktop.ledger.assets.option.reason.sale",
  scrapping: "desktop.ledger.assets.option.reason.scrapping",
  theft: "desktop.ledger.assets.option.reason.theft",
  withdrawal: "desktop.ledger.assets.option.reason.withdrawal",
};
const KINDS = {
  tangible: "desktop.ledger.assets.option.kind.tangible",
  intangible: "desktop.ledger.assets.option.kind.intangible",
  vehicle: "desktop.ledger.assets.option.kind.vehicle",
};
const METHODS = {
  linear_table: "desktop.ledger.assets.option.method.linear_table",
  constant_percentage:
    "desktop.ledger.assets.option.method.constant_percentage",
  free_300: "desktop.ledger.assets.option.method.free_300",
};

/** The purchases an element can be made from. One states every figure, one
 * does not know its non-deductible IVA, one states neither. */
const CANDIDATES: AcquisitionCandidate[] = [
  {
    candidate_id: "purchase-3d-printer",
    description: "Suministros Técnicos SL · impresora 3D",
    date: "2026-03-02",
    amount: dec("1815.00"),
    values: { basis_amount: "1500.00", non_deductible_iva: "0.00" },
  },
  {
    candidate_id: "purchase-cutting-table",
    description: "Carpintería Ruiz · mesa de despiece",
    date: "2026-05-19",
    amount: dec("2420.00"),
    values: { basis_amount: "2000.00", non_deductible_iva: null },
  },
  {
    candidate_id: "purchase-without-invoice",
    description: "Pago sin factura enlazada",
    date: "2026-06-11",
    amount: dec("640.00"),
    values: { basis_amount: null, non_deductible_iva: null },
  },
];

const choices = (labels: Record<string, string>) =>
  Object.entries(labels).map(([token, label_key]) => ({ token, label_key }));

const field = (
  key: string,
  control: FormField["control"],
  required: boolean,
  extra: Partial<FormField> & { label_key: string },
): FormField => ({
  key,
  control,
  required,
  choices: [],
  bounds: null,
  ...extra,
});

/** The scenario's operations for the Assets tab, over `admitted`, which the
 * admitted create and correct operations write to. */
export function assetOperations(
  tools: Tools,
  admitted: () => ReadonlyMap<string, AdmittedAsset>,
  /** The admitted operations' answers in their admitted shapes, where a
   * request still comes in one. */
  legacy?: { reads: Record<string, Handler>; writes: Record<string, Handler> },
) {
  const { now, hex64, invalid, stop } = tools;

  const election = (
    id: string,
    method: string,
    revision: number,
  ): PlanElection => ({
    fingerprint: hex64(`election:${id}:${method}:${revision}`),
    method_key: method,
    revision_number: revision,
  });
  const claimOf = (
    id: string,
    tag: string,
    amount: string,
    from: string,
    until: string,
    extra: Partial<PlanClaim> = {},
  ): PlanClaim => ({
    claim_id: hex64(`claim:${id}:${tag}`),
    amount: dec(amount),
    from,
    until,
    effective: true,
    superseded_by: null,
    revision_number: 1,
    matches_current_schedule: true,
    used_by: [],
    ...extra,
  });
  const wholeYear = (
    id: string,
    year: number,
    amount: string,
    extra: Partial<PlanClaim> = {},
  ) =>
    claimOf(id, String(year), amount, `${year}-01-01`, `${year}-12-31`, extra);

  /** A year of a plan: claimed in full unless `over` says otherwise. */
  const row = (
    id: string,
    year: number,
    standing: PlanElection,
    over: Partial<PlanRow> & { amount?: string; edition?: string } = {},
  ): PlanRow => {
    const { amount, edition = "2015", ...rest } = over;
    const claims = rest.claims ?? (amount ? [wholeYear(id, year, amount)] : []);
    const effective = claims.filter((claim) => claim.effective);
    return {
      tax_year: year,
      state_key: "claimed",
      finding_keys: [],
      authority: { edition, projected: false },
      election: standing,
      service_days: daysIn(year),
      calendar_days: daysIn(year),
      planned: amount ? dec(amount) : null,
      planned_absent_key: null,
      claimed: total(effective),
      pending_end: null,
      claimable: null,
      ...rest,
      claims,
    };
  };

  // ---- Timelines ---------------------------------------------------------

  const numbered = (drafts: readonly Draft[]): TimelineEvent[] => {
    const sequence = new Map<string, number>();
    drafts.forEach((draft, at) => {
      if (draft.key) sequence.set(draft.key, at + 1);
    });
    return drafts.map((draft, at) => ({
      sequence: at + 1,
      recorded_at: draft.recorded_at,
      type_key: draft.type_key,
      origin_key: draft.origin_key,
      effect_date: draft.effect_date,
      replaces_sequence: draft.replaces
        ? (sequence.get(draft.replaces) ?? null)
        : null,
      changes: draft.changes,
      affects_calculation: draft.affects_calculation,
    }));
  };
  const claimDrafts = (
    rows: readonly PlanRow[],
    recorded: (year: number) => string | null,
  ): Draft[] =>
    rows.flatMap((planned) =>
      planned.claims.map((claim): Draft => {
        const replaced = rows
          .flatMap((other) => other.claims)
          .find((other) => other.superseded_by === claim.claim_id);
        return {
          key: claim.claim_id,
          replaces: replaced?.claim_id,
          recorded_at: recorded(planned.tax_year),
          type_key: "claim_recorded",
          origin_key: "person",
          effect_date: claim.until,
          changes: [
            {
              field_key: "amount",
              before: null,
              after: claim.amount?.decimal ?? null,
            },
          ],
          affects_calculation: true,
        };
      }),
    );
  const added = (
    date: string,
    at: string | null,
    origin = "person",
  ): Draft => ({
    recorded_at: at,
    type_key: "element_added",
    origin_key: origin,
    effect_date: date,
    changes: [],
    affects_calculation: true,
  });
  const described = (
    at: string | null,
    name: string,
    serial: string | null,
  ): Draft => ({
    recorded_at: at,
    type_key: "description_added",
    origin_key: "person",
    effect_date: null,
    changes: [
      { field_key: "name", before: null, after: name },
      ...(serial ? [{ field_key: "serial", before: null, after: serial }] : []),
    ],
    affects_calculation: false,
  });

  // ---- The seeded register ----------------------------------------------

  const seeds = (): Held[] => {
    const held: Held[] = [];

    // Decades old and fully amortized; claims from before time was kept.
    {
      const id = "plotter";
      const linear = election(id, "linear_table", 1);
      const rows = [
        row(id, 1999, linear, {
          amount: "1170.41",
          service_days: 292,
          edition: "1998",
        }),
        ...span(2000, 2007).map((year) =>
          row(id, year, linear, { amount: "1600.00", edition: "1998" }),
        ),
        row(id, 2008, linear, { amount: "430.00", edition: "1998" }),
      ];
      held.push({
        id,
        name: "Plotter de gran formato",
        serial: "PLT-4410-A",
        fields: [],
        kind_key: "tangible",
        method_key: "linear_table",
        in_service_date: "1999-03-15",
        revision_number: 1,
        baja: null,
        pending: pendingBy("14400.41", "schedule"),
        plan: pendingBy("14400.41", "schedule")(rows),
        events: numbered([
          added("1999-03-15", null),
          described(null, "Plotter de gran formato", "PLT-4410-A"),
          ...claimDrafts(rows, (year) =>
            year < 2005 ? null : `${year + 1}-02-08T10:15:00Z`,
          ),
        ]),
        admitted: 0,
      });
    }

    // A correction changed the method from 2014; one claim predates it and a
    // later one no longer matches the schedule.
    {
      const id = "servidor";
      const first = election(id, "linear_table", 1);
      const second = election(id, "constant_percentage", 2);
      const replacement = claimOf(
        id,
        "2014:replacement",
        "1510.00",
        "2014-01-01",
        "2014-12-31",
        { revision_number: 2 },
      );
      const original = wholeYear(id, 2014, "1480.00", {
        effective: false,
        superseded_by: replacement.claim_id,
      });
      const rows = [
        ...span(2009, 2013).map((year) =>
          row(id, year, first, {
            amount: "1480.00",
            ...(year === 2009 ? { service_days: 214 } : {}),
          }),
        ),
        row(id, 2014, second, {
          amount: "1510.00",
          claims: [original, replacement],
        }),
        row(id, 2015, second, {
          amount: "1360.00",
          finding_keys: ["claim_stale"],
          claims: [
            wholeYear(id, 2015, "1480.00", { matches_current_schedule: false }),
          ],
        }),
        ...span(2016, 2019).map((year) =>
          row(id, year, second, {
            amount: "1190.00",
            claims: [wholeYear(id, year, "1190.00", { revision_number: 2 })],
          }),
        ),
      ];
      held.push({
        id,
        name: "Servidor de archivos",
        serial: "SRV-2009-117",
        fields: [{ key: "libro_registro", value: "R-0031" }],
        kind_key: "tangible",
        method_key: "constant_percentage",
        in_service_date: "2009-06-01",
        revision_number: 2,
        baja: null,
        pending: pendingBy("18000.00", "schedule"),
        plan: pendingBy("18000.00", "schedule")(rows),
        events: numbered([
          added("2009-06-01", null),
          described(null, "Servidor de archivos", "SRV-2009-117"),
          ...claimDrafts(
            rows.filter((r) => r.tax_year < 2014),
            () => null,
          ),
          {
            recorded_at: "2014-02-03T09:00:00Z",
            type_key: "correction_added",
            origin_key: "person",
            effect_date: "2014-01-01",
            changes: [
              {
                field_key: "method",
                before: "linear_table",
                after: "constant_percentage",
              },
            ],
            affects_calculation: true,
          },
          ...claimDrafts(
            rows.filter((r) => r.tax_year >= 2014),
            (year) => `${year + 1}-01-20T08:30:00Z`,
          ),
        ]),
        admitted: 0,
      });
    }

    // A vehicle: a missing year, a year claimed in part, an overlap, and
    // years on projected rates.
    {
      const id = "furgoneta";
      const linear = election(id, "linear_table", 1);
      const overlapA = wholeYear(id, 2023, "2100.00");
      const overlapB = claimOf(
        id,
        "2023:b",
        "1050.00",
        "2023-07-01",
        "2023-12-31",
      );
      const half = claimOf(
        id,
        "2026:h1",
        "1050.00",
        "2026-01-01",
        "2026-06-30",
      );
      const rows = [
        ...span(2021, 2022).map((year) =>
          row(id, year, linear, {
            amount: "2100.00",
            ...(year === 2021 ? { service_days: 325 } : {}),
          }),
        ),
        row(id, 2023, linear, {
          amount: "2100.00",
          finding_keys: ["claim_conflict"],
          claims: [overlapA, overlapB],
        }),
        row(id, 2024, linear, {
          amount: "2100.00",
          service_days: 366,
          claims: [
            wholeYear(id, 2024, "2100.00", {
              used_by: ["M130 2024 1T", "M130 2024 2T", "M100 2024"],
            }),
          ],
        }),
        row(id, 2025, linear, {
          amount: "2100.00",
          state_key: "missing",
          claims: [],
          claimed: null,
          claimable: { from: "2025-01-01", until: "2025-12-31" },
        }),
        row(id, 2026, linear, {
          amount: "2100.00",
          state_key: "partial",
          claims: [half],
          claimable: { from: "2026-07-01", until: "2026-12-31" },
        }),
        ...span(2027, 2028).map((year) =>
          row(id, year, linear, {
            amount: "2100.00",
            state_key: "forecast",
            claims: [],
            authority: { edition: "2026", projected: true },
          }),
        ),
      ];
      held.push({
        id,
        name: "Furgoneta de reparto",
        serial: "VIN-ZZ99120",
        fields: [],
        kind_key: "vehicle",
        method_key: "linear_table",
        in_service_date: "2021-02-10",
        revision_number: 1,
        baja: null,
        pending: pendingBy("21000.00", "schedule"),
        plan: pendingBy("21000.00", "schedule")(rows),
        events: numbered([
          added("2021-02-10", "2021-02-12T11:00:00Z"),
          described(
            "2021-02-12T11:02:00Z",
            "Furgoneta de reparto",
            "VIN-ZZ99120",
          ),
          ...claimDrafts(rows, (year) => `${year + 1}-01-15T09:00:00Z`),
        ]),
        admitted: 0,
      });
    }

    // An intangible without a serial: a recorded zero beside a missing year.
    {
      const id = "licencia";
      const linear = election(id, "linear_table", 1);
      const rows = [
        row(id, 2020, linear, { amount: "300.00", service_days: 122 }),
        row(id, 2021, linear, { amount: "900.00" }),
        row(id, 2022, linear, {
          amount: "900.00",
          claims: [wholeYear(id, 2022, "0.00")],
        }),
        row(id, 2023, linear, {
          amount: "900.00",
          state_key: "missing",
          claims: [],
          claimed: null,
          claimable: { from: "2023-01-01", until: "2023-12-31" },
        }),
        row(id, 2024, linear, { amount: "900.00" }),
      ];
      held.push({
        id,
        name: "Licencia de software de diseño",
        serial: null,
        fields: [],
        kind_key: "intangible",
        method_key: "linear_table",
        in_service_date: "2020-09-01",
        revision_number: 1,
        baja: null,
        pending: pendingBy("4500.00", "schedule"),
        plan: pendingBy("4500.00", "schedule")(rows),
        events: numbered([
          added("2020-09-01", "2020-09-03T16:20:00Z", "import"),
          described(
            "2020-09-03T16:25:00Z",
            "Licencia de software de diseño",
            null,
          ),
          ...claimDrafts(rows, (year) => `${year + 1}-02-02T12:00:00Z`),
        ]),
        admitted: 0,
      });
    }

    // Free depreciation: no planned figure, the elected amount once claimed.
    {
      const id = "prensa";
      const free = election(id, "free_300", 1);
      const rows = [
        row(id, 2023, free, {
          planned: null,
          planned_absent_key: "free_method",
          claims: [wholeYear(id, 2023, "280.00")],
          service_days: 241,
        }),
        row(id, 2024, free, {
          planned: null,
          planned_absent_key: "free_method",
          state_key: "missing",
          claims: [],
          claimed: null,
          claimable: { from: "2024-01-01", until: "2024-12-31" },
        }),
      ];
      held.push({
        id,
        name: "Prensa de taller",
        serial: "PT-2023-009",
        fields: [],
        kind_key: "tangible",
        method_key: "free_300",
        in_service_date: "2023-05-04",
        revision_number: 1,
        baja: null,
        pending: pendingBy("3000.00", "claims"),
        plan: pendingBy("3000.00", "claims")(rows),
        events: numbered([
          added("2023-05-04", "2023-05-05T10:00:00Z"),
          described("2023-05-05T10:03:00Z", "Prensa de taller", "PT-2023-009"),
          ...claimDrafts(rows, (year) => `${year + 1}-01-10T10:00:00Z`),
        ]),
        admitted: 0,
      });
    }

    // Opening history never stated: nothing can be worked out, and nothing
    // is read as zero.
    {
      const id = "escaner";
      const linear = election(id, "linear_table", 1);
      const rows = span(2019, 2026).map((year) =>
        row(id, year, linear, {
          state_key: "incomplete",
          finding_keys: ["opening_history_missing"],
          planned: null,
          planned_absent_key: "opening_history_unknown",
          claimed: null,
          service_days: year === 2019 ? 42 : daysIn(year),
        }),
      );
      held.push({
        id,
        name: null,
        serial: null,
        fields: [],
        kind_key: "tangible",
        method_key: "linear_table",
        in_service_date: "2019-11-20",
        revision_number: 1,
        baja: null,
        pending: unchanged,
        plan: rows,
        events: numbered([added("2019-11-20", null, "import")]),
        admitted: 0,
      });
    }

    // Given a baja: the claim that crossed the last day of service was
    // replaced in the same write, and no year follows.
    {
      const id = "camara";
      const first = election(id, "linear_table", 1);
      const second = election(id, "linear_table", 2);
      const shortened = claimOf(
        id,
        "2024:end",
        "750.00",
        "2024-01-01",
        "2024-06-30",
        {
          revision_number: 3,
        },
      );
      const crossing = wholeYear(id, 2024, "1500.00", {
        effective: false,
        superseded_by: shortened.claim_id,
        revision_number: 2,
      });
      const rows = [
        ...span(2011, 2018).map((year) =>
          row(id, year, first, {
            amount: "1350.00",
            ...(year === 2011 ? { service_days: 272 } : {}),
          }),
        ),
        ...span(2019, 2023).map((year) =>
          row(id, year, second, {
            amount: "1500.00",
            claims: [wholeYear(id, year, "1500.00", { revision_number: 2 })],
          }),
        ),
        row(id, 2024, second, {
          amount: "750.00",
          service_days: 182,
          claims: [crossing, shortened],
        }),
      ];
      const [crossingDraft, shortenedDraft] = claimDrafts(
        [rows[rows.length - 1]!],
        () => "2024-07-02T08:10:00Z",
      ) as [Draft, Draft];
      held.push({
        id,
        name: "Cámara de revelado",
        serial: "CR-2011-44",
        fields: [],
        kind_key: "tangible",
        method_key: "linear_table",
        in_service_date: "2011-04-04",
        revision_number: 3,
        baja: { date: "2024-06-30", reason_key: "sale" },
        pending: pendingBy("19500.00", "schedule"),
        plan: pendingBy("19500.00", "schedule")(rows),
        events: numbered([
          added("2011-04-04", null),
          described(null, "Cámara de revelado", "CR-2011-44"),
          ...claimDrafts(
            rows.filter((r) => r.tax_year < 2019),
            () => null,
          ),
          {
            recorded_at: "2019-01-14T09:40:00Z",
            type_key: "correction_added",
            origin_key: "person",
            effect_date: "2019-01-01",
            changes: [
              { field_key: "basis", before: "13500.00", after: "19500.00" },
            ],
            affects_calculation: true,
          },
          ...claimDrafts(
            rows.filter((r) => r.tax_year >= 2019 && r.tax_year < 2024),
            (year) => `${year + 1}-01-18T09:00:00Z`,
          ),
          { ...crossingDraft, recorded_at: "2024-01-20T09:00:00Z" },
          {
            recorded_at: "2024-07-02T08:10:00Z",
            type_key: "baja_recorded",
            origin_key: "person",
            effect_date: "2024-06-30",
            changes: [
              { field_key: "baja_date", before: null, after: "2024-06-30" },
              { field_key: "baja_reason", before: null, after: "sale" },
            ],
            affects_calculation: true,
          },
          shortenedDraft,
        ]),
        admitted: 0,
      });
    }

    // An industrial building at 2.53%, inside the table's 3% and 68 years: decades of settled
    // years, one missing year and a run of years on projected rates.
    {
      const id = "taller";
      const linear = election(id, "linear_table", 1);
      const rows = [
        row(id, 1994, linear, {
          amount: "1200.00",
          service_days: 243,
          edition: "1992",
        }),
        ...span(1995, 2025).map((year) =>
          row(id, year, linear, {
            amount: "2400.00",
            edition: year < 2015 ? "1992" : "2015",
          }),
        ),
        row(id, 2026, linear, {
          amount: "2400.00",
          state_key: "missing",
          claims: [],
          claimed: null,
          claimable: { from: "2026-01-01", until: "2026-12-31" },
        }),
        ...span(2027, 2033).map((year) =>
          row(id, year, linear, {
            amount: "2400.00",
            state_key: "forecast",
            claims: [],
            claimed: null,
            authority: { edition: "2026", projected: true },
          }),
        ),
      ];
      held.push({
        id,
        name: "Nave industrial del taller",
        serial: null,
        fields: [],
        kind_key: "tangible",
        method_key: "linear_table",
        in_service_date: "1994-05-02",
        revision_number: 1,
        baja: null,
        pending: pendingBy("94800.00", "schedule"),
        plan: pendingBy("94800.00", "schedule")(rows),
        events: numbered([
          added("1994-05-02", null),
          described(null, "Nave industrial del taller", null),
          ...claimDrafts(rows, (year) =>
            year < 2005 ? null : `${year + 1}-01-12T09:00:00Z`,
          ),
        ]),
        admitted: 0,
      });
    }

    return held;
  };

  const elements = new Map(seeds().map((held) => [held.id, held]));

  /** Brings in the elements the admitted operations made, and the
   * revisions they added to elements already held. */
  const sync = () => {
    for (const [id, source] of admitted()) {
      const latest = source.revisions[source.revisions.length - 1]?.revision;
      if (!latest) continue;
      const text = (value: JsonValue | undefined, fallback: string) =>
        typeof value === "string" && value !== "" ? value : fallback;
      const method = text(
        (latest.amortization as JsonObject | null)?.method,
        "linear_table",
      );
      const kind = text(latest.asset_kind, "tangible");
      const service = text(latest.in_service_date, "");
      const held = elements.get(id) ?? {
        id,
        name: null,
        serial: null,
        fields: [],
        kind_key: kind,
        method_key: method,
        in_service_date: service,
        revision_number: 0,
        baja: null,
        plan: [],
        pending: unchanged,
        events: [],
        admitted: 0,
      };
      for (const revision of source.revisions.slice(held.admitted)) {
        held.events.push({
          sequence: held.events.length + 1,
          recorded_at: null,
          type_key: held.admitted === 0 ? "element_added" : "correction_added",
          origin_key: "person",
          effect_date: service || null,
          replaces_sequence: null,
          changes: [],
          affects_calculation: true,
        });
        held.admitted += 1;
        held.revision_number =
          Number(revision.revision.revision_number) || held.admitted;
      }
      held.kind_key = kind;
      held.method_key = method;
      held.in_service_date = service;
      elements.set(id, held);
    }
  };

  // ---- Refusals and reading a request ------------------------------------

  const refuse = (
    code: string,
    shape: JsonObject,
    verdict: JsonObject | null = null,
    reasonKey: string | null = null,
  ): never =>
    stop(code, {
      outcome: "refused",
      refusal: {
        code,
        precondition_verdict: verdict,
        accelerated_da18: null,
        reason_key: reasonKey,
      },
      ...shape,
    });
  const only = (request: JsonObject, allowed: readonly string[]) => {
    if (Object.keys(request).some((key) => !allowed.includes(key))) invalid();
  };
  const textOf = (value: JsonValue | undefined) =>
    typeof value === "string" && value.trim() !== "" ? value.trim() : null;
  const need = (value: JsonValue | undefined) => textOf(value) ?? invalid();
  const heldFor = (request: JsonObject, shape: JsonObject): Held => {
    sync();
    const id = need(request.asset_id);
    return (
      elements.get(id) ??
      refuse(
        "REFUSED_ACTIVIDAD_ASSET_VALIDATION",
        shape,
        null,
        "asset_not_found",
      )
    );
  };

  const countsOf = (plan: readonly PlanRow[]): AssetCounts => {
    const count = (test: (planned: PlanRow) => boolean) =>
      plan.filter(test).length;
    return {
      missing: count((planned) => planned.state_key === "missing"),
      incomplete: count((planned) => planned.state_key === "incomplete"),
      conflict: count((planned) =>
        planned.finding_keys.includes("claim_conflict"),
      ),
      stale: count((planned) => planned.finding_keys.includes("claim_stale")),
    };
  };
  const rowOf = (held: Held): AssetListRow => ({
    asset_id: held.id,
    name: held.name,
    serial: held.serial,
    kind_key: held.kind_key,
    method_key: held.method_key,
    in_service_date: held.in_service_date,
    revision_number: held.revision_number,
    ...(held.baja ? { baja: held.baja } : {}),
    counts: countsOf(held.plan),
  });

  /** The tax years the stepper offers: each year an element has a plan
   * row or entered service in. */
  const yearsOffered = () =>
    [
      ...new Set(
        [...elements.values()].flatMap((held) => [
          ...held.plan.map((planned) => planned.tax_year),
          ...(held.in_service_date ? [yearOf(held.in_service_date)] : []),
        ]),
      ),
    ].sort((a, b) => a - b);

  const LABELS = {
    acquisition: "desktop.ledger.assets.field.acquisition",
    baja_date: "desktop.ledger.assets.field.baja_date",
    baja_reason: "desktop.ledger.assets.field.baja_reason",
    basis: "desktop.ledger.assets.field.basis",
    in_service_date: "desktop.ledger.assets.field.in_service_date",
    kind: "desktop.ledger.assets.field.kind",
    libro_registro: "desktop.ledger.assets.field.libro_registro",
    method: "desktop.ledger.assets.field.method",
    method_year: "desktop.ledger.assets.field.method_year",
    name: "desktop.ledger.assets.field.name",
    non_deductible_iva: "desktop.ledger.assets.field.non_deductible_iva",
    serial: "desktop.ledger.assets.field.serial",
  } as const;
  const DATE_HINT = "desktop.ledger.form.date_hint";
  const AMOUNT_HINT = "desktop.ledger.form.amount_hint";
  const IVA_HINT = "desktop.ledger.assets.field.non_deductible_iva_hint";

  /** The year of a plan an act is about, and the claim it replaces. */
  const claimTerms = (
    held: Held,
    year: number | null,
    replaces: string | null,
  ) => {
    const planned = held.plan.find((entry) => entry.tax_year === year);
    const replaced =
      planned?.claims.find((claim) => claim.claim_id === replaces) ?? null;
    return { planned, replaced };
  };

  const optionsFor = (
    kind: FormKind,
    held: Held | null,
    year: number | null = null,
    replaces: string | null = null,
  ): FormOptions => {
    const descriptor = (key: string) =>
      held?.fields.find((entry) => entry.key === key)?.value ?? null;
    const terms = held ? claimTerms(held, year, replaces) : null;
    const span = terms?.replaced ?? terms?.planned?.claimable ?? null;
    const fields: Record<FormKind, FormField[]> = {
      element: [
        field("name", "text", true, { label_key: LABELS.name }),
        field("serial", "text", false, { label_key: LABELS.serial }),
        field("kind_key", "choice", true, {
          label_key: LABELS.kind,
          choices: choices(KINDS),
        }),
        field("method_key", "choice", true, {
          label_key: LABELS.method,
          choices: choices(METHODS),
        }),
        field("in_service_date", "date", true, {
          label_key: LABELS.in_service_date,
          hint_key: DATE_HINT,
        }),
        field("acquisition", "candidate", true, {
          label_key: LABELS.acquisition,
        }),
        field("basis_amount", "amount", true, {
          label_key: LABELS.basis,
          hint_key: AMOUNT_HINT,
        }),
        field("non_deductible_iva", "amount", true, {
          label_key: LABELS.non_deductible_iva,
          hint_key: IVA_HINT,
        }),
      ],
      descriptor: [
        field("name", "text", true, {
          label_key: LABELS.name,
          current: held?.name ?? null,
        }),
        field("serial", "text", false, {
          label_key: LABELS.serial,
          current: held?.serial ?? null,
        }),
        field("libro_registro", "text", false, {
          label_key: LABELS.libro_registro,
          current: descriptor("libro_registro"),
        }),
      ],
      correction: [
        field("method_key", "choice", false, {
          label_key: LABELS.method,
          choices: choices(METHODS),
          current: held?.method_key ?? null,
        }),
        field("method_year", "whole", false, {
          label_key: LABELS.method_year,
          hint_key: "desktop.ledger.form.year_hint",
        }),
        field("basis_amount", "amount", false, {
          label_key: LABELS.basis,
          hint_key: AMOUNT_HINT,
          current: held?.stated?.basis ?? null,
        }),
        field("non_deductible_iva", "amount", false, {
          label_key: LABELS.non_deductible_iva,
          hint_key: IVA_HINT,
          current: held?.stated?.non_deductible_iva ?? null,
        }),
      ],
      claim: [
        field("from", "date", true, {
          label_key: "desktop.ledger.assets.from",
          hint_key: DATE_HINT,
          current: span?.from ?? null,
        }),
        field("until", "date", true, {
          label_key: "desktop.ledger.assets.until",
          hint_key: DATE_HINT,
          current: span?.until ?? null,
        }),
        ...(terms?.planned?.planned_absent_key === "free_method"
          ? [
              field("free_amount", "amount", true, {
                label_key: "desktop.ledger.assets.free",
                hint_key: "desktop.ledger.assets.free_hint",
              }),
            ]
          : []),
      ],
      baja: [
        field("date", "date", true, {
          label_key: LABELS.baja_date,
          hint_key: DATE_HINT,
          bounds: { min: held?.in_service_date ?? null, max: null },
        }),
        field("reason_key", "choice", true, {
          label_key: LABELS.baja_reason,
          choices: choices(REASONS),
        }),
      ],
    };
    return {
      kind,
      tax_year: kind === "claim" ? year : null,
      fields: fields[kind],
      next_sequence:
        kind === "descriptor" && held
          ? held.events.filter(
              (event) => event.type_key === "description_added",
            ).length + 1
          : kind === "correction" && held
            ? held.revision_number + 1
            : null,
    };
  };

  // ---- Reads -------------------------------------------------------------

  const ok = { outcome: "succeeded", refusal: null };

  const reads: Partial<Record<ProvisionalOperationId, Handler>> = {
    "ledger.actividad-asset.list": (request) => {
      only(request, []);
      sync();
      return json({
        ...ok,
        rows: [...elements.values()].map(rowOf),
        years: yearsOffered(),
      });
    },
    "ledger.actividad-asset.plan": (request) => {
      only(request, ["asset_id"]);
      const held = heldFor(request, { asset_id: null, rows: [] });
      return json({ ...ok, asset_id: held.id, rows: held.plan });
    },
    "ledger.actividad-asset.timeline": (request) => {
      only(request, ["asset_id"]);
      const held = heldFor(request, { asset_id: null, events: [] });
      return json({ ...ok, asset_id: held.id, events: held.events });
    },
    "ledger.actividad-asset.form-options": (request) => {
      only(request, ["kind", "asset_id", "tax_year", "supersedes_claim_id"]);
      const kind = need(request.kind) as FormKind;
      if (
        !["element", "descriptor", "correction", "claim", "baja"].includes(kind)
      )
        invalid();
      sync();
      const id = textOf(request.asset_id);
      const held = id === null ? null : (elements.get(id) ?? null);
      if (kind !== "element" && held === null)
        return refuse(
          "REFUSED_ACTIVIDAD_ASSET_VALIDATION",
          { options: null },
          null,
          "asset_not_found",
        );
      const year =
        typeof request.tax_year === "number" ? request.tax_year : null;
      if (kind === "claim" && year === null) invalid();
      return json({
        ...ok,
        options: optionsFor(
          kind,
          held,
          year,
          textOf(request.supersedes_claim_id),
        ),
      });
    },
    "ledger.actividad-asset.acquisition-candidates": (request) => {
      only(request, []);
      sync();
      const taken = new Set(
        [...elements.values()].map((held) => held.made?.acquisition),
      );
      return json({
        ...ok,
        candidates: CANDIDATES.filter(
          (candidate) => !taken.has(candidate.candidate_id),
        ),
      });
    },
  };

  // ---- Writes ------------------------------------------------------------

  const incomplete = (missing: string[], shape: JsonObject): never =>
    refuse("REFUSED_ACTIVIDAD_ASSET_INCOMPLETE", shape, {
      missing_field_keys: missing,
    });

  const writes: Partial<Record<ProvisionalOperationId, Handler>> = {
    "ledger.actividad-asset.describe": (request) => {
      only(request, ["asset_id", "name", "serial", "fields"]);
      const shape = { descriptor: null };
      const held = heldFor(request, shape);
      const name = textOf(request.name);
      const serial = textOf(request.serial);
      const extra = request.fields;
      if (!Array.isArray(extra)) invalid();
      if (name === null) return incomplete(["name"], shape);
      const fields = (extra as JsonValue[]).map((entry): DescriptorField => {
        const found = entry as JsonObject | null;
        if (!found || typeof found.key !== "string") return invalid();
        return { key: found.key, value: textOf(found.value) };
      });
      held.events.push({
        sequence: held.events.length + 1,
        recorded_at: now(),
        type_key: "description_added",
        origin_key: "person",
        effect_date: null,
        replaces_sequence: null,
        changes: [
          ...(held.name !== name
            ? [{ field_key: "name", before: held.name, after: name }]
            : []),
          ...(held.serial !== serial
            ? [{ field_key: "serial", before: held.serial, after: serial }]
            : []),
        ],
        affects_calculation: false,
      });
      held.name = name;
      held.serial = serial;
      held.fields = fields;
      const descriptor: Descriptor = {
        asset_id: held.id,
        sequence: held.events.filter(
          (event) => event.type_key === "description_added",
        ).length,
        name,
        serial,
        fields,
      };
      return json({ ...ok, descriptor });
    },
    "ledger.actividad-asset.dispose": (request) => {
      only(request, ["asset_id", "date", "reason_key"]);
      const shape = { baja: null, superseded_claim_ids: [] };
      const held = heldFor(request, shape);
      const date = textOf(request.date);
      const reason = textOf(request.reason_key);
      const missing = [
        ...(date === null ? ["date"] : []),
        ...(reason === null ? ["reason_key"] : []),
      ];
      if (missing.length > 0) return incomplete(missing, shape);
      if (!/^\d{4}-\d{2}-\d{2}$/.test(date!)) invalid();
      if (!Object.hasOwn(REASONS, reason!))
        return refuse(
          "REFUSED_ACTIVIDAD_ASSET_VALIDATION",
          shape,
          null,
          "reason_not_offered",
        );
      if (held.baja)
        return refuse(
          "REFUSED_ACTIVIDAD_ASSET_VALIDATION",
          shape,
          null,
          "already_disposed",
        );
      if (date! < held.in_service_date)
        return refuse(
          "REFUSED_ACTIVIDAD_ASSET_VALIDATION",
          shape,
          null,
          "baja_before_service",
        );
      const last = yearOf(date!);
      const crossing: string[] = [];
      held.plan = held.plan.filter((planned) => planned.tax_year <= last);
      for (const planned of held.plan.filter(
        (entry) => entry.tax_year === last,
      )) {
        for (const claim of planned.claims)
          if (claim.effective && claim.until > date!) {
            claim.effective = false;
            crossing.push(claim.claim_id);
          }
        const effective = planned.claims.filter((claim) => claim.effective);
        planned.claimed = total(effective);
        if (effective.length === 0) planned.state_key = "missing";
      }
      held.plan = held.pending(held.plan);
      held.revision_number += 1;
      held.baja = { date: date!, reason_key: reason! };
      held.events.push({
        sequence: held.events.length + 1,
        recorded_at: now(),
        type_key: "baja_recorded",
        origin_key: "person",
        effect_date: date!,
        replaces_sequence: null,
        changes: [
          { field_key: "baja_date", before: null, after: date! },
          { field_key: "baja_reason", before: null, after: reason! },
        ],
        affects_calculation: true,
      });
      return json({ ...ok, baja: held.baja, superseded_claim_ids: crossing });
    },
  };

  // ---- The admitted operations, in their drafted shapes ---------------------

  const DATE = /^\d{4}-\d{2}-\d{2}$/;
  const DAY = 86_400_000;
  const day = (date: string) => Date.parse(`${date}T00:00:00Z`);
  const addDays = (date: string, by: number) =>
    new Date(day(date) + by * DAY).toISOString().slice(0, 10);
  const daysBetween = (from: string, until: string) =>
    Math.round((day(until) - day(from)) / DAY) + 1;

  const objectOf = (value: JsonValue | undefined): JsonObject =>
    value !== null && typeof value === "object" && !Array.isArray(value)
      ? value
      : invalid();
  /** What a form stated for one field, as text; null where it stated none. */
  const stated = (value: JsonValue | undefined): string | null => {
    if (typeof value === "string") return textOf(value);
    if (typeof value === "number") return String(value);
    if (value !== null && typeof value === "object" && !Array.isArray(value))
      return typeof value.decimal === "string" ? value.decimal : null;
    return null;
  };
  const record = (
    held: Held,
    event: Omit<TimelineEvent, "sequence" | "replaces_sequence"> & {
      replaces_sequence?: number | null;
    },
  ) =>
    held.events.push({
      sequence: held.events.length + 1,
      replaces_sequence: null,
      ...event,
    });
  /** The event that recorded a claim, for the one that replaces it. */
  const recording = (held: Held, claim: PlanClaim) =>
    [...held.events]
      .reverse()
      .find(
        (event) =>
          event.type_key === "claim_recorded" &&
          event.effect_date === claim.until &&
          event.changes[0]?.after === (claim.amount?.decimal ?? null),
      )?.sequence ?? null;

  /** A year of a plan worked out again from the claims it now holds. */
  const restate = (held: Held, planned: PlanRow) => {
    const effective = planned.claims
      .filter((claim) => claim.effective)
      .sort((a, b) => (a.from < b.from ? -1 : a.from > b.from ? 1 : 0));
    planned.claimed = total(effective);
    const stale = effective.some((claim) => !claim.matches_current_schedule);
    const overlapping = effective.some((claim, at) =>
      effective.slice(at + 1).some((other) => other.from <= claim.until),
    );
    planned.finding_keys = [
      ...planned.finding_keys.filter(
        (key) => key !== "claim_stale" && key !== "claim_conflict",
      ),
      ...(stale ? ["claim_stale"] : []),
      ...(overlapping ? ["claim_conflict"] : []),
    ];
    if (planned.state_key === "forecast" || planned.state_key === "incomplete")
      return;
    const first = `${planned.tax_year}-01-01`;
    const start = held.in_service_date > first ? held.in_service_date : first;
    const last = `${planned.tax_year}-12-31`;
    const end = held.baja && held.baja.date < last ? held.baja.date : last;
    let cursor = start;
    let gap: { from: string; until: string } | null = null;
    for (const claim of effective) {
      if (claim.from > cursor && gap === null)
        gap = { from: cursor, until: addDays(claim.from, -1) };
      if (claim.until >= cursor) cursor = addDays(claim.until, 1);
    }
    if (gap === null && cursor <= end) gap = { from: cursor, until: end };
    planned.claimable = gap;
    planned.state_key =
      effective.length === 0 ? "missing" : gap ? "partial" : "claimed";
  };

  const unsupported = "REFUSED_ACTIVIDAD_ASSET_UNSUPPORTED";
  const validation = "REFUSED_ACTIVIDAD_ASSET_VALIDATION";

  const draftedReads: Partial<Record<DraftedOperationId, Handler>> = {
    "ledger.actividad-asset.forecast": (request) => {
      const forecast = legacy?.reads["ledger.actividad-asset.forecast"];
      if (forecast && admitted().has(textOf(request.asset_id) ?? ""))
        return forecast(request);
      only(request, [
        "asset_id",
        "covered_from",
        "covered_until",
        "requested_free_amount",
        "supersedes_claim_id",
      ]);
      const shape = { forecast: null };
      const held = heldFor(request, shape);
      const from = need(request.covered_from);
      const until = need(request.covered_until);
      if (!DATE.test(from) || !DATE.test(until) || until < from) invalid();
      if (yearOf(from) !== yearOf(until))
        return refuse(validation, shape, null, "span_crosses_years");
      const year = yearOf(from);
      const planned = held.plan.find((entry) => entry.tax_year === year);
      if (!planned) return refuse(validation, shape, null, "year_not_in_plan");
      if (planned.authority.projected)
        return refuse(unsupported, shape, null, "projected_authority");
      if (planned.state_key === "incomplete")
        return refuse(validation, shape, null, "opening_history_unknown");
      const days = daysBetween(from, until);
      let amount: string;
      if (planned.planned_absent_key === "free_method") {
        const asked = stated(request.requested_free_amount);
        if (asked === null) return incomplete(["free_amount"], shape);
        amount = asked;
      } else {
        const basis = planned.service_days ?? daysIn(year);
        amount = (
          Math.round((cents(planned.planned) * Math.min(days, basis)) / basis) /
          100
        ).toFixed(2);
      }
      return json({
        ...ok,
        forecast: {
          asset_id: held.id,
          asset_revision_id: hex64(
            `revision:${held.id}:${held.revision_number}`,
          ),
          tax_year: year,
          covered_from: from,
          covered_until: until,
          service_days: days,
          calendar_days: daysIn(year),
          amount: dec(amount),
          schedule_fingerprint: hex64(`schedule:${held.id}:${from}:${until}`),
        },
      });
    },
  };

  const draftedWrites: Partial<Record<DraftedOperationId, Handler>> = {
    "ledger.actividad-asset.create": (request) => {
      const create = legacy?.writes["ledger.actividad-asset.create"];
      if (create && "revision" in request) return create(request);
      only(request, ["asset_id", "values"]);
      const shape = { asset_id: null, reused_existing_element: false };
      const id = need(request.asset_id);
      const values = objectOf(request.values);
      const missing = optionsFor("element", null)
        .fields.filter((entry) => entry.required)
        .map((entry) => entry.key)
        .filter((key) => stated(values[key]) === null);
      if (missing.length > 0) return incomplete(missing, shape);
      const kind = stated(values.kind_key)!;
      const method = stated(values.method_key)!;
      const service = stated(values.in_service_date)!;
      if (!Object.hasOwn(KINDS, kind) || !Object.hasOwn(METHODS, method))
        return refuse(validation, shape, null, "option_not_offered");
      if (!DATE.test(service)) invalid();
      sync();
      const name = stated(values.name)!;
      const serial = stated(values.serial);
      const made = {
        basis: stated(values.basis_amount)!,
        non_deductible_iva: stated(values.non_deductible_iva)!,
        acquisition: stated(values.acquisition)!,
      };
      const held = elements.get(id);
      if (held) {
        const same =
          held.made !== undefined &&
          JSON.stringify(held.made) === JSON.stringify(made) &&
          held.name === name &&
          held.serial === serial &&
          held.kind_key === kind &&
          held.method_key === method &&
          held.in_service_date === service;
        if (!same) return refuse(validation, shape, null, "asset_exists");
        return json({ ...ok, asset_id: id, reused_existing_element: true });
      }
      const purchase = CANDIDATES.find(
        (candidate) => candidate.candidate_id === made.acquisition,
      );
      if (
        !purchase ||
        [...elements.values()].some(
          (other) => other.made?.acquisition === made.acquisition,
        )
      )
        return refuse(validation, shape, null, "acquisition_not_found");
      elements.set(id, {
        id,
        name,
        serial,
        fields: [],
        kind_key: kind,
        method_key: method,
        in_service_date: service,
        revision_number: 1,
        baja: null,
        plan: [],
        pending: unchanged,
        events: numbered([
          added(service, now()),
          described(now(), name, serial),
        ]),
        admitted: 0,
        made,
      });
      return json({ ...ok, asset_id: id, reused_existing_element: false });
    },
    "ledger.actividad-asset.correct": (request) => {
      const correct = legacy?.writes["ledger.actividad-asset.correct"];
      if (correct && "revision" in request) return correct(request);
      only(request, [
        "asset_id",
        "revision_number",
        "values",
        "supersede_claim_ids",
      ]);
      const shape = { revision_number: null, superseded_claim_ids: [] };
      const held = heldFor(request, shape);
      const values = objectOf(request.values);
      const named = request.supersede_claim_ids;
      if (!Array.isArray(named)) return invalid();
      if (request.revision_number !== held.revision_number)
        return refuse(validation, shape, null, "revision_stale");
      const method = stated(values.method_key);
      const basis = stated(values.basis_amount);
      const iva = stated(values.non_deductible_iva);
      if (method === null && basis === null && iva === null)
        return refuse(validation, shape, null, "nothing_changed");
      if (method !== null && !Object.hasOwn(METHODS, method))
        return refuse(validation, shape, null, "option_not_offered");
      const changesMethod = method !== null && method !== held.method_key;
      const fromYear = stated(values.method_year);
      if (changesMethod && fromYear === null)
        return incomplete(["method_year"], shape);
      const from = fromYear === null ? null : Number(fromYear);
      if (from !== null && !Number.isInteger(from)) invalid();
      const targets = named.map((claimId) => {
        const found = held.plan
          .flatMap((planned) =>
            planned.claims.map((claim) => ({ planned, claim })),
          )
          .find((entry) => entry.claim.claim_id === claimId);
        if (!found) return refuse(validation, shape, null, "claim_not_found");
        if (!found.claim.effective)
          return refuse(validation, shape, null, "claim_not_effective");
        return found;
      });
      const before = held.stated ?? {};
      held.revision_number += 1;
      held.stated = {
        ...(basis !== null
          ? { basis }
          : before.basis
            ? { basis: before.basis }
            : {}),
        ...(iva !== null
          ? { non_deductible_iva: iva }
          : before.non_deductible_iva
            ? { non_deductible_iva: before.non_deductible_iva }
            : {}),
      };
      const prior = held.method_key;
      if (changesMethod) held.method_key = method;
      record(held, {
        recorded_at: now(),
        type_key: "correction_added",
        origin_key: "person",
        effect_date: from === null ? null : `${from}-01-01`,
        changes: [
          ...(changesMethod
            ? [{ field_key: "method", before: prior, after: method }]
            : []),
          ...(basis !== null && basis !== (before.basis ?? null)
            ? [
                {
                  field_key: "basis",
                  before: before.basis ?? null,
                  after: basis,
                },
              ]
            : []),
          ...(iva !== null && iva !== (before.non_deductible_iva ?? null)
            ? [
                {
                  field_key: "non_deductible_iva",
                  before: before.non_deductible_iva ?? null,
                  after: iva,
                },
              ]
            : []),
        ],
        affects_calculation: true,
      });
      const replaced = new Set(targets.map((entry) => entry.claim.claim_id));
      for (const planned of held.plan) {
        if (from !== null && planned.tax_year < from) continue;
        if (changesMethod)
          planned.election = election(
            held.id,
            held.method_key,
            held.revision_number,
          );
        for (const claim of planned.claims)
          if (claim.effective && !replaced.has(claim.claim_id))
            claim.matches_current_schedule = false;
      }
      for (const { planned, claim } of targets) {
        const next: PlanClaim = {
          ...claim,
          claim_id: hex64(
            `claim:${held.id}:${claim.from}:${claim.until}:${planned.claims.length}`,
          ),
          effective: true,
          superseded_by: null,
          revision_number: held.revision_number,
          matches_current_schedule: true,
          used_by: [],
        };
        const replacing = recording(held, claim);
        claim.effective = false;
        claim.superseded_by = next.claim_id;
        planned.claims.push(next);
        record(held, {
          recorded_at: now(),
          type_key: "claim_recorded",
          origin_key: "person",
          effect_date: next.until,
          replaces_sequence: replacing,
          changes: [
            {
              field_key: "amount",
              before: null,
              after: next.amount?.decimal ?? null,
            },
          ],
          affects_calculation: true,
        });
      }
      for (const planned of held.plan)
        if (from === null || planned.tax_year >= from) restate(held, planned);
      held.plan = held.pending(held.plan);
      return json({
        ...ok,
        revision_number: held.revision_number,
        superseded_claim_ids: targets.map((entry) => entry.claim.claim_id),
      });
    },
    "ledger.actividad-asset.claim": (request) => {
      const claim = legacy?.writes["ledger.actividad-asset.claim"];
      if (claim && "creating_operation" in request) return claim(request);
      only(request, ["forecast", "supersedes_claim_id"]);
      const shape = {
        claim_id: null,
        reused_existing_claim: false,
        superseded_claim_id: null,
        conflicting_claim: null,
      };
      const forecast = objectOf(request.forecast);
      const held = heldFor({ asset_id: need(forecast.asset_id) }, shape);
      const from = need(forecast.covered_from);
      const until = need(forecast.covered_until);
      const amount = stated(forecast.amount) ?? invalid();
      const planned = held.plan.find(
        (entry) => entry.tax_year === yearOf(from),
      );
      if (!planned) return refuse(validation, shape, null, "year_not_in_plan");
      const replacesId = textOf(request.supersedes_claim_id);
      const replaced = replacesId
        ? (planned.claims.find((entry) => entry.claim_id === replacesId) ??
          null)
        : null;
      if (replacesId && !replaced)
        return refuse(validation, shape, null, "claim_not_found");
      if (replaced && !replaced.effective)
        return refuse(validation, shape, null, "claim_not_effective");
      const same = planned.claims.find(
        (entry) =>
          entry.effective &&
          entry.from === from &&
          entry.until === until &&
          entry.amount?.decimal === amount,
      );
      if (same)
        return json({
          ...ok,
          claim_id: same.claim_id,
          reused_existing_claim: true,
          superseded_claim_id: null,
          conflicting_claim: null,
        });
      const clash = planned.claims.find(
        (entry) =>
          entry.effective &&
          entry !== replaced &&
          entry.from <= until &&
          from <= entry.until,
      );
      if (clash)
        return refuse(
          "REFUSED_ACTIVIDAD_ASSET_CLAIM_CONFLICT",
          {
            ...shape,
            conflicting_claim: {
              claim_id: clash.claim_id,
              from: clash.from,
              until: clash.until,
              amount: clash.amount,
            },
          },
          null,
          "overlapping_claim",
        );
      const next = claimOf(
        held.id,
        `${from}:${until}:${planned.claims.length}`,
        amount,
        from,
        until,
        { revision_number: held.revision_number },
      );
      const replacing = replaced ? recording(held, replaced) : null;
      if (replaced) {
        replaced.effective = false;
        replaced.superseded_by = next.claim_id;
      }
      planned.claims.push(next);
      record(held, {
        recorded_at: now(),
        type_key: "claim_recorded",
        origin_key: "person",
        effect_date: until,
        replaces_sequence: replacing,
        changes: [{ field_key: "amount", before: null, after: amount }],
        affects_calculation: true,
      });
      restate(held, planned);
      held.plan = held.pending(held.plan);
      return json({
        ...ok,
        claim_id: next.claim_id,
        reused_existing_claim: false,
        superseded_claim_id: replaced?.claim_id ?? null,
        conflicting_claim: null,
      });
    },
  };

  return {
    reads: { ...reads, ...draftedReads },
    writes: { ...writes, ...draftedWrites },
  };
}

/** The years the seeded register offers, for stories that show the stepper
 * on a list that spans decades. */
export function assetFixtureYears(): number[] {
  const never = (): never => {
    throw new Error("The seeded register is read without a request.");
  };
  const { reads } = assetOperations(
    { now: () => "", hex64: (text) => text, invalid: never, stop: never },
    () => new Map(),
  );
  const answer = reads["ledger.actividad-asset.list"]!({});
  return answer.years as number[];
}
