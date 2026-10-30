// The scenario ledger's answers to the Assets tab's provisional operations:
// a register that spans decades, with every state of a plan, a timeline and
// a write the tab shows. Its elements are synthetic. Its figures are fixed
// text; only a baja re-adds the claims it leaves. Elements made through the
// admitted create and correct operations appear beside the seeded ones, with
// the history those operations kept.

import type {
  Amount,
  AssetBaja,
  AssetCounts,
  AssetListRow,
  Descriptor,
  DescriptorField,
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
  events: TimelineEvent[];
  /** How many admitted revisions are already in `events`. */
  admitted: number;
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
        plan: rows,
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
        plan: rows,
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
        row(id, 2024, linear, { amount: "2100.00", service_days: 366 }),
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
        plan: rows,
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
        plan: rows,
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
        plan: rows,
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
        "1000.00",
        "2024-01-01",
        "2024-06-30",
        {
          revision_number: 3,
        },
      );
      const crossing = wholeYear(id, 2024, "1950.00", {
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
            amount: "1950.00",
            claims: [wholeYear(id, year, "1950.00", { revision_number: 2 })],
          }),
        ),
        row(id, 2024, second, {
          amount: "1950.00",
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
        plan: rows,
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

  const optionsFor = (kind: FormKind, held: Held | null): FormOptions => {
    const fields: Record<FormKind, FormField[]> = {
      element: [
        field("name", "text", true, {
          label_key: "desktop.ledger.assets.field.name",
        }),
        field("serial", "text", false, {
          label_key: "desktop.ledger.assets.field.serial",
        }),
        field("kind_key", "choice", true, {
          label_key: "desktop.ledger.assets.field.kind",
          choices: choices(KINDS),
        }),
        field("method_key", "choice", true, {
          label_key: "desktop.ledger.assets.field.method",
          choices: choices(METHODS),
        }),
        field("in_service_date", "date", true, {
          label_key: "desktop.ledger.assets.field.in_service_date",
        }),
        field("basis", "amount", true, {
          label_key: "desktop.ledger.assets.field.basis",
        }),
      ],
      descriptor: [
        field("name", "text", true, {
          label_key: "desktop.ledger.assets.field.name",
        }),
        field("serial", "text", false, {
          label_key: "desktop.ledger.assets.field.serial",
        }),
      ],
      correction: [
        field("method_key", "choice", true, {
          label_key: "desktop.ledger.assets.field.method",
          choices: choices(METHODS),
        }),
        field("basis", "amount", true, {
          label_key: "desktop.ledger.assets.field.basis",
        }),
      ],
      claim: [
        field("from", "date", true, {
          label_key: "desktop.ledger.assets.from",
        }),
        field("until", "date", true, {
          label_key: "desktop.ledger.assets.until",
        }),
        field("free_amount", "amount", false, {
          label_key: "desktop.ledger.assets.free",
        }),
      ],
      baja: [
        field("date", "date", true, {
          label_key: "desktop.ledger.assets.field.baja_date",
          bounds: { min: held?.in_service_date ?? null, max: null },
        }),
        field("reason_key", "choice", true, {
          label_key: "desktop.ledger.assets.field.baja_reason",
          choices: choices(REASONS),
        }),
      ],
    };
    return { kind, tax_year: null, fields: fields[kind] };
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
      only(request, ["kind", "asset_id", "tax_year"]);
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
      return json({ ...ok, options: optionsFor(kind, held) });
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

  return { reads, writes };
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
