import type { Meta, StoryObj } from "@storybook/react-vite";
import { useMemo } from "react";
import { userEvent, waitFor, within } from "storybook/test";
import { Button } from "@/components/ui/button";
import { STORY_READER, useLedgerPort } from "@/dev/LedgerStage";
import type { LedgerShape } from "@/dev/ledgerFixture";
import type { LedgerPort } from "../../../shell/ledger";
import { translator, useStrings } from "../../../shell/strings";
import { Panel } from "../setup/SetupParts";
import { AssetsSection } from "./AssetsSection";
import type { AssetFormArgs, AssetSlots } from "./FixedAssetsPane";
import { ASSET_KEYS } from "./assetsWords";

// The Assets tab over the scenario's ledger: a register that spans decades,
// its list, the detail of one element, the filing handoff, and the states a
// read can end in. The plan, the timeline, the forms and the Stock area are
// other parts' views; here each is a stand-in that names its place.

type Answer = "register" | "empty" | "refused" | "loading";

type Args = {
  shape?: LedgerShape;
  /** What the list read answers; the register's own unless said. */
  answer?: Answer;
  signedOut?: boolean;
  parts?: boolean;
  locale: string;
};

const ACT_WORD = {
  element: "add",
  descriptor: "describe",
  correction: "correct",
  claim: "claim",
  baja: "dispose",
} as const;

function FormStandIn({ request, onClose }: AssetFormArgs) {
  const t = useStrings();
  return (
    <Panel
      title={t(ASSET_KEYS.action[ACT_WORD[request.kind]])}
      className="ledger-assets-form-stand-in"
      actions={
        <Button variant="ghost" size="sm" onClick={onClose}>
          {t("desktop.ledger.form.cancel")}
        </Button>
      }
    >
      {null}
    </Panel>
  );
}

function ViewStandIn({ word }: { word: string }) {
  const t = useStrings();
  return <p className="p-3 text-sm text-muted-foreground">{t(word)}</p>;
}

const SLOTS: AssetSlots = {
  planView: () => <ViewStandIn word={ASSET_KEYS.detail.plan} />,
  timelineView: () => <ViewStandIn word={ASSET_KEYS.detail.timeline} />,
  forms: (args) => <FormStandIn {...args} />,
};

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
        },
        rows: [],
        years: [],
      });
    }) as LedgerPort["submit"],
  };
}

function Stage({ shape, answer = "register", signedOut, parts, locale }: Args) {
  const base = useLedgerPort(shape);
  const port = useMemo(() => withListAnswer(base, answer), [base, answer]);
  return (
    <div className="flex h-full min-h-0 flex-col">
      <AssetsSection
        port={port}
        reader={signedOut ? null : STORY_READER}
        locale={locale}
        {...(parts === false ? {} : { slots: SLOTS })}
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

export const ElementWithABaja: Story = {
  name: "An element given a baja, its record",
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

export const WithoutParts: Story = {
  name: "Without the other parts",
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
