import type { Meta, StoryObj } from "@storybook/react-vite";
import { useMemo } from "react";
import { userEvent, waitFor, within } from "storybook/test";
import { STORY_READER, useLedgerPort } from "@/dev/LedgerStage";
import type { LedgerShape } from "@/dev/ledgerFixture";
import type { LedgerPort } from "../../../shell/ledger";
import { translator, useStrings } from "../../../shell/strings";
import { AssetsSection } from "./AssetsSection";
import { ASSET_KEYS } from "./assetsWords";

// The Assets tab over the scenario's ledger: its list, the detail of one
// element with its plan and timeline, the forms, the filing handoff, and the
// states a read can end in. Stock is another part's view and stays a stand-in
// that names its place.

type Answer = "register" | "empty" | "refused" | "loading";

type Args = {
  shape?: LedgerShape;
  /** What the list read answers; the register's own unless said. */
  answer?: Answer;
  signedOut?: boolean;
  parts?: boolean;
  /** The handoff leaves elements out of its Modelo 130 amounts. */
  partial?: boolean;
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
            { unavailable_asset_ids?: string[] }
          > | null;
        };
        for (const [target, found] of Object.entries(
          result.filing_handoff ?? {},
        ))
          if (target.endsWith("_m130"))
            found.unavailable_asset_ids = ["first", "second"];
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
  locale,
}: Args) {
  const base = useLedgerPort(shape);
  const port = useMemo(
    () => withListAnswer(partial ? withPartialHandoff(base) : base, answer),
    [base, answer, partial],
  );
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

export const ElementWithoutAName: Story = {
  name: "An element with no name",
  play: (context) =>
    press(context, "button", wordsOf(context)(ASSET_KEYS.list.no_name)),
};

export const FormAsked: Story = {
  name: "A form asked for",
  play: (context) =>
    press(context, "button", wordsOf(context)(ASSET_KEYS.action.add)),
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
    await userEvent.selectOptions(quarter, "4T");
  },
};

export const FilingHandoffPartialAmount: Story = {
  name: "Filing handoff, an amount that leaves elements out",
  args: { partial: true },
  play: FilingHandoff.play,
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
