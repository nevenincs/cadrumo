import type { Meta, StoryObj } from "@storybook/react-vite";
import { useRef } from "react";
import { userEvent, waitFor } from "storybook/test";
import { modeloFixture, type ModeloShape } from "@/dev/modeloFixture";
import type { ModeloPort } from "../../../shell/modelo";
import type { OutputLanguage } from "../../../shell/modeloContract";
import { translator, useStrings } from "../../../shell/strings";
import { DeclarationsPage, type DeclarationsMemory } from "./DeclarationsPage";

// The Declarations page over the declarations list the application read for
// a synthetic taxpayer. That taxpayer has no deadline inside the window, so
// one story lays synthetic deadline sentences over three rows to show each
// tone; it is design evidence only.

const noop = () => undefined;

/** The fixture's list with one return the AEAT holds and no local work
 * links to; its notes are synthetic, laid over the row as the read model
 * would carry them. */
function withAeatFiling(port: ModeloPort): ModeloPort {
  return {
    ...port,
    async declarations(language) {
      const list = await port.declarations(language);
      const [first, ...rest] = list.rows;
      if (!first) return list;
      const held = {
        ...first,
        key: "synthetic-aeat-filing",
        group: "aeat_unlinked" as const,
        group_words: "Filed at the AEAT",
        state: "aeat_unlinked",
        work_unit_id: null,
        state_words: "Filed with AEAT, not linked here",
        next_step: null,
        next_step_words: null,
        opens_local_work: false,
        opens_aeat_filing: true,
        help_words: "This return was filed at the AEAT.",
        aeat_submission_state: "accepted" as const,
        aeat_filing: {
          notes: [
            "The AEAT confirms this return was filed.",
            "Do not file it again from here.",
            "Linking it to local work is not available yet.",
          ],
        },
      };
      return { ...list, rows: [held, first, ...rest] };
    },
  };
}

function withDeadlines(port: ModeloPort): ModeloPort {
  const due = [
    ["Deadline passed on 20/04/2026: filing now is late", "urgent"],
    ["Deadline 30/10/2026 · days left: 6", "soon"],
    ["Deadline 30/01/2027 · days left: 98", "normal"],
  ] as const;
  return {
    ...port,
    async declarations(language) {
      const list = await port.declarations(language);
      return {
        ...list,
        rows: list.rows.map((row, i) => {
          const [words, tone] = due[i] ?? [];
          return words ? { ...row, due_words: words, due_tone: tone } : row;
        }),
      };
    },
  };
}

type Args = {
  shape?: ModeloShape;
  signedOut?: boolean;
  deadlines?: boolean;
  aeatFiling?: boolean;
  census?: boolean;
  language?: OutputLanguage;
};

function Page({
  shape = "fixture",
  signedOut,
  deadlines,
  aeatFiling,
  census,
  language = "en",
}: Args) {
  const t = useStrings();
  const page = useRef<HTMLElement>(null);
  const memory = useRef<DeclarationsMemory>({});
  const port = useRef<ModeloPort | null>(null);
  if (port.current === null) {
    const fixture = modeloFixture({
      say: noop,
      translate: translator,
      wait: async () => undefined,
      signedIn: () => !signedOut,
      shape,
    });
    port.current = deadlines
      ? withDeadlines(fixture)
      : aeatFiling
        ? withAeatFiling(fixture)
        : fixture;
  }
  return (
    <div className="flex h-full min-h-0 flex-col">
      <DeclarationsPage
        port={port.current}
        reader={signedOut ? null : "synthetic"}
        withheld={null}
        language={language}
        shown
        page={page}
        memory={memory}
        onOpen={noop}
        onCensus={census ? noop : undefined}
        pane={{
          title: t("workspace.declarations.destination.overview"),
          controls: [],
          onToggleMaximize: noop,
        }}
      />
    </div>
  );
}

const meta: Meta<typeof Page> = {
  title: "Modelo/Declarations",
  component: Page,
  render: (args, { globals }) => (
    <Page
      {...args}
      language={String(globals.locale ?? "en") as OutputLanguage}
    />
  ),
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;
type Story = StoryObj<typeof Page>;

const drawn = (canvas: HTMLElement, selector: string) =>
  waitFor(() => {
    const found = canvas.querySelector<HTMLElement>(selector);
    if (!found) throw new Error(`${selector} is not drawn yet`);
    return found;
  });

const openNew: NonNullable<Story["play"]> = async ({ canvasElement }) => {
  await userEvent.click(await drawn(canvasElement, ".declarations-new"));
};

/** Opens the dialog, takes the first modelo offered and asks to create its
 * first period. */
const create: NonNullable<Story["play"]> = async (context) => {
  await openNew(context);
  const body = context.canvasElement.ownerDocument.body;
  await userEvent.click(await drawn(body, ".new-declaration-modelo"));
  await userEvent.click(await drawn(body, ".new-declaration-submit"));
};

export const Declarations: Story = {};
export const Deadlines: Story = { args: { deadlines: true } };
export const AeatFiling: Story = {
  name: "A return only the AEAT holds",
  args: { aeatFiling: true },
  play: async ({ canvasElement }) => {
    const row = await drawn(canvasElement, "[data-kind=data]");
    await userEvent.dblClick(
      row.querySelector<HTMLElement>("[role=gridcell]") ?? row,
    );
  },
};
export const Census: Story = {
  name: "With the census entry",
  args: { census: true },
};
export const Reading: Story = { args: { shape: "slow" } };
export const Unavailable: Story = { args: { shape: "unavailable" } };
export const SignedOut: Story = { args: { signedOut: true } };
export const NewDeclaration: Story = { play: openNew };
export const CreateRefused: Story = {
  args: { shape: "refused" },
  play: create,
};
export const CreateUnknown: Story = {
  name: "Create, settlement not seen",
  args: { shape: "unknown" },
  play: create,
};
