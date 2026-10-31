import type { Meta, StoryObj } from "@storybook/react-vite";
import { useMemo } from "react";
import { userEvent, waitFor, within } from "storybook/test";
import { STORY_READER, useLedgerPort } from "@/dev/LedgerStage";
import type { LedgerShape } from "@/dev/ledgerFixture";
import type { LedgerPort } from "../../../shell/ledger";
import { translator, useStrings } from "../../../shell/strings";
import { AssetsSection } from "./AssetsSection";
import { amountText, dateText } from "../movements/movementWords";
import { listOf } from "../../../shared/lists";
import { ASSET_KEYS } from "./assetsWords";

// The Assets tab over the scenario's ledger: its list, the detail of one
// element with its plan and timeline, the forms, the filing handoff, and the
// states a read can end in. Stock is another part's view and stays a stand-in
// that names its place.

type LeftOut =
  | "named"
  | "unnamed"
  | "unknown"
  | "unavailable_named"
  | "unavailable_unnamed"
  | "singular";

type Answer = "register" | "empty" | "refused" | "loading";

type Args = {
  shape?: LedgerShape;
  /** What the list read answers; the register's own unless said. */
  answer?: Answer;
  signedOut?: boolean;
  parts?: boolean;
  /** The handoff leaves elements out of its Modelo 130 amounts. */
  partial?: boolean;
  /** The year the list says the register opens on, whatever the clock says. */
  servedYear?: number;
  /** Every kind of count stated on the first element. */
  allCounts?: boolean;
  /** What the handoff leaves out of its amounts, named by the made-up list,
   * by an element the list holds no name for, or with an accrual not worked out. */
  leftOut?: LeftOut;
  locale: string;
};

function ViewStandIn({ word }: { word: string }) {
  const t = useStrings();
  return <p className="p-3 text-sm text-muted-foreground">{t(word)}</p>;
}

/** The scenario's port, with the list read answered as the story asks. */
function withListAnswer(port: LedgerPort, answer: Answer): LedgerPort {
  if (answer === "register") return port;
  const settled = (result: object) =>
    Promise.resolve({
      kind: "settled",
      operation_id: "story",
      revision: 1,
      result,
    });
  return {
    ...port,
    submit: ((definition: string, payload: never) => {
      if (definition !== "ledger.actividad-asset.list")
        return port.submit(definition as never, payload);
      if (answer === "loading") return new Promise(() => undefined);
      if (answer === "empty")
        return settled({
          outcome: "succeeded",
          refusal: null,
          rows: [],
          years: [],
          default_year: null,
        });
      return settled({
        outcome: "refused",
        refusal: {
          code: "REFUSED_ACTIVIDAD_ASSET_VALIDATION",
          precondition_verdict: null,
          accelerated_da18: null,
          reason_key: "ledger.actividad_asset.errors.modality_not_declared",
          reason_facts: [],
        },
        rows: null,
        years: [],
        default_year: null,
      });
    }) as LedgerPort["submit"],
  };
}

/** The scenario's port, with the filing handoff made partial: two elements
 * are left out of each Modelo 130 amount, as when their year cannot be
 * worked out. */
function withPartialHandoff(port: LedgerPort): LedgerPort {
  return {
    ...port,
    submit: ((definition: string, payload: never) => {
      const sent = port.submit(definition as never, payload) as Promise<{
        kind: string;
        result?: unknown;
      }>;
      if (definition !== "ledger.actividad-asset.filing-handoff") return sent;
      return sent.then((answer) => {
        if (answer.kind !== "settled") return answer;
        const result = structuredClone(answer.result) as {
          filing_handoff: Record<
            string,
            { unavailable_asset_ids?: string[] } | null
          > | null;
        };
        for (const [target, found] of Object.entries(
          result.filing_handoff ?? {},
        ))
          if (found !== null && target.endsWith("_m130"))
            found.unavailable_asset_ids = ["first", "second"];
        return { ...answer, result };
      });
    }) as LedgerPort["submit"],
  };
}

type ListShape = {
  default_year: number | null;
  rows: { findings: Record<string, number> }[];
};

/** The scenario's port, with the list changed as the story asks. */
function withList(
  port: LedgerPort,
  change: (list: ListShape) => void,
): LedgerPort {
  return {
    ...port,
    submit: ((definition: string, payload: never) => {
      const sent = port.submit(definition as never, payload) as Promise<{
        kind: string;
        result?: unknown;
      }>;
      if (definition !== "ledger.actividad-asset.list") return sent;
      return sent.then((answer) => {
        if (answer.kind !== "settled") return answer;
        const result = structuredClone(answer.result) as ListShape;
        change(result);
        return { ...answer, result };
      });
    }) as LedgerPort["submit"],
  };
}

const SPAN = { covered_from: "2026-07-01", covered_until: "2027-01-01" };

/** The scenario's port, with what the filing handoff leaves out stated as the
 * story asks, whatever the seeded register leaves out of its own. */
function withLeftOut(port: LedgerPort, leftOut: LeftOut): LedgerPort {
  return {
    ...port,
    submit: ((definition: string, payload: never) => {
      const sent = port.submit(definition as never, payload) as Promise<{
        kind: string;
        result?: unknown;
      }>;
      if (definition !== "ledger.actividad-asset.filing-handoff") return sent;
      return sent.then((answer) => {
        if (answer.kind !== "settled") return answer;
        const result = structuredClone(answer.result) as {
          filing_handoff: {
            m100_gaps: object[];
            material_m130: Record<string, string[]> | null;
            intangible_m130: Record<string, string[]> | null;
          } | null;
        };
        const handoff = result.filing_handoff;
        if (handoff === null) return answer;
        const gap = (
          asset_id: string,
          kind: string,
          accrued: string | null,
        ) => ({
          asset_id,
          kind,
          ...SPAN,
          accrued: accrued === null ? null : { decimal: accrued },
        });
        const quarter = (
          free: string[],
          agrarian: string[],
          unavailable?: string[],
        ) => {
          for (const found of [handoff.material_m130, handoff.intangible_m130])
            if (found !== null) {
              found.free_gap_asset_ids = free;
              found.agrarian_excluded_asset_ids = agrarian;
              if (unavailable !== undefined)
                found.unavailable_asset_ids = unavailable;
            }
        };
        if (leftOut === "named") {
          handoff.m100_gaps = [
            gap("furgoneta", "accrued", "1451.84"),
            gap("impresora", "free_method", null),
            gap("servidor", "unavailable", null),
          ];
          quarter(["impresora"], []);
        } else if (leftOut === "unnamed") {
          handoff.m100_gaps = [
            gap("no-list-name-a", "free_method", null),
            gap("no-list-name-b", "accrued", "310.00"),
          ];
          quarter(["no-list-name-a", "impresora"], ["no-list-name-b"]);
        } else if (leftOut === "unavailable_named") {
          handoff.m100_gaps = [];
          quarter([], [], ["furgoneta", "impresora"]);
        } else if (leftOut === "unavailable_unnamed") {
          handoff.m100_gaps = [];
          quarter([], [], ["no-list-name-a", "no-list-name-b"]);
        } else if (leftOut === "singular") {
          handoff.m100_gaps = [gap("no-list-name-a", "free_method", null)];
          quarter(["no-list-name-a"], ["no-list-name-b"], ["no-list-name-c"]);
        } else {
          handoff.m100_gaps = [gap("furgoneta", "accrued", null)];
          quarter([], []);
        }
        return { ...answer, result };
      });
    }) as LedgerPort["submit"],
  };
}

function Stage({
  shape,
  answer = "register",
  signedOut,
  parts,
  partial,
  leftOut,
  servedYear,
  allCounts,
  locale,
}: Args) {
  const base = useLedgerPort(shape);
  const port = useMemo(() => {
    let served = leftOut
      ? withLeftOut(base, leftOut)
      : partial
        ? withPartialHandoff(base)
        : base;
    if (servedYear !== undefined)
      served = withList(served, (list) => {
        list.default_year = servedYear;
      });
    if (allCounts)
      served = withList(served, (list) => {
        const first = list.rows[0];
        if (first)
          first.findings = {
            missing: 1,
            incomplete: 2,
            conflict: 3,
            unsupported: 4,
            without_tables: 5,
            stale: 6,
          };
      });
    return withListAnswer(served, answer);
  }, [base, answer, partial, leftOut, servedYear, allCounts]);
  return (
    <div className="flex h-full min-h-0 flex-col">
      <AssetsSection
        port={port}
        reader={signedOut ? null : STORY_READER}
        locale={locale}
        onOpenLink={() => undefined}
        {...(parts === false
          ? {}
          : { stock: <ViewStandIn word={ASSET_KEYS.area.stock} /> })}
      />
    </div>
  );
}

const meta: Meta<Args> = {
  title: "Ledger/Assets/Section",
  render: (args, { globals }) => (
    <Stage {...args} locale={String(globals.locale ?? "en")} />
  ),
  args: { locale: "en" },
  argTypes: { locale: { table: { disable: true } } },
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;
type Story = StoryObj<Args>;

type PlayContext = Parameters<NonNullable<Story["play"]>>[0];
const wordsOf = (context: PlayContext) =>
  translator(String(context.globals.locale ?? "en"));

/** Waits for a control the story's own words name, then presses it. */
async function press(
  context: PlayContext,
  role: "button" | "tab",
  name: string,
) {
  const found = await waitFor(() => {
    const control = within(context.canvasElement).queryByRole(role, { name });
    if (!control) throw new Error(`${name} is not drawn yet`);
    return control;
  });
  await userEvent.click(found);
}

export const Register: Story = { name: "Register spanning decades" };

export const RegisterOpensOnTheServedYear: Story = {
  name: "Register opens on the year the list serves, whatever the clock says",
  args: { servedYear: 2024 },
  play: async (context) => {
    const t = wordsOf(context);
    const year = await within(context.canvasElement).findByLabelText(
      t(ASSET_KEYS.year),
    );
    await waitFor(() => {
      if ((year as HTMLSelectElement).value !== "2024")
        throw new Error("the register did not open on the served year");
    });
  },
};

export const CountsOfEveryKind: Story = {
  name: "Counts of every kind, each with a glyph of its own",
  args: { allCounts: true },
};

export const OneElement: Story = {
  name: "An element chosen",
  play: (context) => press(context, "button", "Furgoneta de reparto"),
};

export const ElementOutOfService: Story = {
  name: "An element out of service, its record",
  play: async (context) => {
    await press(context, "button", "Cámara de revelado");
    await press(context, "tab", wordsOf(context)(ASSET_KEYS.detail.record));
  },
};

export const ElementOutOfServiceInTheList: Story = {
  name: "An element out of service: nothing left to amortize, said as not applying",
  play: async (context) => {
    const t = wordsOf(context);
    const mark = await waitFor(() => {
      const found = within(context.canvasElement).queryAllByRole("img", {
        name: new RegExp(
          t(ASSET_KEYS.mark.not_applicable).replace(
            /[.*+?^${}()|[\]\\]/g,
            "\\$&",
          ),
        ),
      })[0];
      if (!found) throw new Error("the mark is not drawn yet");
      return found;
    });
    await userEvent.hover(mark);
  },
};

export const ElementWithoutAName: Story = {
  name: "An element with no name",
  play: (context) =>
    press(context, "button", wordsOf(context)(ASSET_KEYS.list.no_name)),
};

export const ElementWithoutASerialNumber: Story = {
  name: "An element with no serial number: nothing recorded, not Not known",
  play: async (context) => {
    const t = wordsOf(context);
    const mark = await waitFor(() => {
      const found = within(context.canvasElement).queryAllByRole("img", {
        name: new RegExp(
          t(ASSET_KEYS.list.serial_missing).replace(
            /[.*+?^${}()|[\]\\]/g,
            "\\$&",
          ),
        ),
      })[0];
      if (!found) throw new Error("the serial number mark is not drawn yet");
      return found;
    });
    await userEvent.hover(mark);
  },
};

export const FormAsked: Story = {
  name: "A form asked for",
  play: (context) =>
    press(context, "button", wordsOf(context)(ASSET_KEYS.action.add)),
};

export const FilingHandoffYearAlone: Story = {
  name: "Filing handoff for the year alone: the Modelo 100 boxes",
  play: (context) =>
    press(context, "button", wordsOf(context)("desktop.ledger.assets.handoff")),
};

export const FilingHandoff: Story = {
  name: "Filing handoff for a quarter",
  play: async (context) => {
    const t = wordsOf(context);
    await press(context, "button", t("desktop.ledger.assets.handoff"));
    const quarter = await waitFor(() => {
      const control = within(context.canvasElement).queryByLabelText(
        t("desktop.ledger.assets.quarter"),
      );
      if (!control) throw new Error("the quarter is not drawn yet");
      return control;
    });
    // The quarters are the ones the registry serves for the year.
    await waitFor(
      () => {
        if (!quarter.querySelector('option[value="4T"]'))
          throw new Error("the quarters are not offered yet");
      },
      { timeout: 5000 },
    );
    await userEvent.selectOptions(quarter, "4T");
  },
};

export const FilingHandoffPartialAmount: Story = {
  name: "Filing handoff, an amount that leaves elements out",
  args: { partial: true },
  play: FilingHandoff.play,
};

/** Waits until the handoff's left-out words say `text`. */
const saysLeftOut = (context: PlayContext, text: string) =>
  waitFor(
    () => {
      if (!context.canvasElement.textContent?.includes(text))
        throw new Error(`"${text}" is not drawn yet`);
    },
    { timeout: 5000 },
  );

/** Opens the handoff with a quarter, which is where Modelo 130 is left out. */
async function openQuarter(context: PlayContext) {
  await FilingHandoff.play?.(context);
}

export const FilingHandoffLeftOutNamed: Story = {
  name: "Filing handoff, left-out intervals and elements named",
  args: { leftOut: "named" },
  play: async (context) => {
    const t = wordsOf(context);
    await openQuarter(context);
    const span = {
      start: dateText(t.locale ?? "en", SPAN.covered_from, true),
      end: dateText(t.locale ?? "en", SPAN.covered_until, true),
    };
    await saysLeftOut(
      context,
      t("desktop.ledger.assets.handoff_gap_accrued", {
        name: "Furgoneta de reparto",
        ...span,
        amount: amountText(t.locale ?? "en", "1451.84"),
      }),
    );
    await saysLeftOut(
      context,
      t("desktop.ledger.assets.handoff_free_named", {
        names: "Impresora 3D",
      }),
    );
  },
};

export const FilingHandoffLeftOutUnnamed: Story = {
  name: "Filing handoff, left out elements the list holds no name for: a count",
  args: { leftOut: "unnamed" },
  play: async (context) => {
    const t = wordsOf(context);
    await openQuarter(context);
    await saysLeftOut(
      context,
      t("desktop.ledger.assets.handoff_gap_unnamed", { count: 2 }),
    );
    await saysLeftOut(
      context,
      t("desktop.ledger.assets.handoff_free_count", { count: 2 }),
    );
  },
};

export const FilingHandoffLeftOutCouldNotBeWorkedOutNamed: Story = {
  name: "Filing handoff, elements that could not be worked out are named",
  args: { leftOut: "unavailable_named" },
  play: async (context) => {
    const t = wordsOf(context);
    await openQuarter(context);
    await saysLeftOut(
      context,
      t("desktop.ledger.assets.handoff_unavailable_named", {
        names: listOf(t.locale ?? "en", [
          "Furgoneta de reparto",
          "Impresora 3D",
        ]),
      }),
    );
  },
};

export const FilingHandoffLeftOutCouldNotBeWorkedOutCount: Story = {
  name: "Filing handoff, elements that could not be worked out and have no name: a count",
  args: { leftOut: "unavailable_unnamed" },
  play: async (context) => {
    const t = wordsOf(context);
    await openQuarter(context);
    await saysLeftOut(
      context,
      t("desktop.ledger.assets.handoff_unavailable_count", { count: 2 }),
    );
  },
};

export const FilingHandoffSingularCounts: Story = {
  name: "Filing handoff, one element of each kind is said in the singular",
  args: { leftOut: "singular" },
  play: async (context) => {
    const t = wordsOf(context);
    await openQuarter(context);
    for (const key of [
      "desktop.ledger.assets.handoff_gap_unnamed_one",
      "desktop.ledger.assets.handoff_free_count_one",
      "desktop.ledger.assets.handoff_agrarian_count_one",
      "desktop.ledger.assets.handoff_unavailable_count_one",
    ])
      await saysLeftOut(context, t(key));
    await within(context.canvasElement).findAllByRole("img", {
      name: t("desktop.ledger.assets.handoff_partial_one"),
    });
  },
};

export const FilingHandoffAccrualUnknown: Story = {
  name: "Filing handoff, an accrual not worked out: never drawn as zero",
  args: { leftOut: "unknown" },
  play: async (context) => {
    const t = wordsOf(context);
    await openQuarter(context);
    const locale = t.locale ?? "en";
    await saysLeftOut(
      context,
      t("desktop.ledger.assets.handoff_gap_unavailable", {
        name: "Furgoneta de reparto",
        start: dateText(locale, SPAN.covered_from, true),
        end: dateText(locale, SPAN.covered_until, true),
      }),
    );
    if (
      context.canvasElement.textContent?.includes(
        t("desktop.ledger.assets.handoff_gap_accrued", {
          name: "Furgoneta de reparto",
          start: dateText(locale, SPAN.covered_from, true),
          end: dateText(locale, SPAN.covered_until, true),
          amount: amountText(locale, "0"),
        }),
      )
    )
      throw new Error("an accrual not worked out was drawn as zero");
  },
};

export const WithoutStock: Story = {
  name: "Without the Stock area",
  args: { parts: false },
  play: (context) => press(context, "button", "Furgoneta de reparto"),
};

export const Empty: Story = {
  name: "Register with no elements",
  args: { answer: "empty" },
};
export const Loading: Story = {
  name: "Register being read",
  args: { answer: "loading" },
};
export const Refused: Story = {
  name: "Register read refused",
  args: { answer: "refused" },
};
export const Unavailable: Story = {
  name: "Ledger not answering",
  args: { shape: "unavailable" },
};
export const SignedOut: Story = {
  name: "Account withholds the ledger",
  args: { signedOut: true },
};
