import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, within } from "storybook/test";
import type {
  ModeloFormAttentionCount,
  ModeloFormIssueLine,
} from "../../../shell/modeloContract/modeloWorkForm";
import { translator } from "../../../shell/strings";
import { CheckView } from "./CheckView";
import { AttentionMark } from "./Marks";

// A limit the calculation states, as the read model serves it: counted in the
// header by a chip in the served words, and listed in the check under its own
// level, apart from what blocks filing and what is worth checking. Synthetic
// placeholder words stand in for what the backend serves.

const COUNTS: ModeloFormAttentionCount[] = [
  { level: "check", count: 2, words: "Synthetic chip: 2 to check" },
  { level: "limitation", count: 1, words: "Synthetic chip: 1 limit stated" },
];

const line = (
  level: ModeloFormIssueLine["level"],
  message: string,
): ModeloFormIssueLine => ({
  level,
  box: null,
  where: null,
  message,
  action: "",
  detail: null,
  technical: "synthetic",
  address: null,
  in_records: false,
  surface: null,
  compared_surface: null,
  from_calculation: true,
  recalculates: false,
  finding_id: null,
  resolution_answer: null,
  answer_lead_words: null,
  answer_lead_words_language: null,
  invoice_id: null,
});

const LIMIT = "Synthetic limit: one figure rests on a value you stated.";
const CHECK = "Synthetic finding worth a look.";

const meta: Meta = {
  title: "Modelo/Stated limits",
  decorators: [
    (Story) => (
      <div className="flex max-w-3xl flex-col gap-3 p-6">
        <Story />
      </div>
    ),
  ],
};
export default meta;
type Story = StoryObj;

export const LimitationChip: Story = {
  name: "Header chip · limits stated, in the served words",
  render: () => (
    <div className="flex items-center gap-2">
      {COUNTS.map((entry) => (
        <AttentionMark key={entry.level} entry={entry} />
      ))}
    </div>
  ),
  play: async ({ canvasElement }) => {
    const page = within(canvasElement);
    // Each chip is named by the words the read model served for it.
    for (const entry of COUNTS) {
      const chip = page.getByRole("img", { name: entry.words });
      await expect(chip.textContent).toBe(String(entry.count));
      await expect(chip.querySelector("svg")).not.toBeNull();
    }
  },
};

export const LimitationInCheck: Story = {
  name: "Check · a stated limit under its own level",
  render: () => (
    <CheckView
      verdict={{
        status: null,
        words: "Synthetic verdict.",
        unapplied_words: null,
      }}
      lines={[line("check", CHECK), line("limitation", LIMIT)]}
      stagedCount={0}
      onGo={() => undefined}
      onOpenSurface={() => undefined}
      canOpenSurface={() => false}
      onRecalculate={null}
    />
  ),
  play: async ({ canvasElement, globals }) => {
    const t = translator(String(globals.locale ?? "en"));
    const sections = [
      ...canvasElement.querySelectorAll<HTMLElement>("[data-attention-level]"),
    ];
    await expect(
      sections.map((section) => section.dataset.attentionLevel),
    ).toEqual(["check", "limitation"]);
    const limits = sections[1] as HTMLElement;
    // The level is named by its catalogue word, and its line in the served
    // sentence.
    const level = limits.dataset.attentionLevel ?? "";
    await expect(limits.getAttribute("aria-label")).toBe(
      t(`workspace.modelo.level.${level}`),
    );
    await expect(within(limits).getByText(LIMIT)).toBeVisible();
    await expect(within(limits).queryByText(CHECK)).toBeNull();
  },
};
