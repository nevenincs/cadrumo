import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, userEvent, within } from "storybook/test";
import type { ModeloFormIssueLine } from "../../../shell/modeloContract/modeloWorkForm";
import type { OpenableSurface as SourceSurface } from "../details/Details";
import { translator } from "../../../shell/strings";
import { CheckView } from "./CheckView";

// A finding that compares the form's figure with other declarations leads to
// two places: the records behind the figure and the declarations it was
// compared with. Each door is worded by the catalogue's own words for the
// area it opens. Synthetic findings stand in for what the backend serves.

const line = (
  message: string,
  surface: SourceSurface | null,
  compared_surface: SourceSurface | null,
): ModeloFormIssueLine => ({
  level: "check",
  box: null,
  where: null,
  message,
  action: "",
  detail: null,
  technical: "synthetic",
  address: null,
  in_records: false,
  surface,
  compared_surface,
  from_calculation: false,
  recalculates: false,
  finding_id: null,
  resolution_answer: null,
  answer_lead_words: null,
  answer_lead_words_language: null,
  invoice_id: null,
});

const BOTH = "Synthetic finding with two doors.";
const ONE = "Synthetic finding with one door.";

function Doors({
  lines,
  opened,
}: {
  lines: ModeloFormIssueLine[];
  opened: SourceSurface[];
}) {
  return (
    <CheckView
      verdict={{
        status: null,
        words: "Synthetic verdict.",
        unapplied_words: null,
        checked_words: null,
        checked_resolves: false,
      }}
      lines={lines}
      stagedCount={0}
      onGo={() => undefined}
      onOpenSurface={(surface) => {
        opened.push(surface);
      }}
      canOpenSurface={() => true}
      onRecalculate={null}
    />
  );
}

const meta: Meta = {
  title: "Modelo/Finding doors",
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

const doorsOf = (canvasElement: HTMLElement, message: string) => {
  const item = within(canvasElement).getByText(message).closest("li");
  if (!item) throw new Error("finding not drawn");
  return item;
};

export const TwoDoors: Story = {
  name: "Check · a finding with both doors opens each area",
  render: () => {
    const opened: SourceSurface[] = [];
    (window as unknown as { __opened: SourceSurface[] }).__opened = opened;
    return (
      <Doors
        lines={[line(BOTH, "withholding", "declarations")]}
        opened={opened}
      />
    );
  },
  play: async ({ canvasElement, globals }) => {
    const t = translator(String(globals.locale ?? "en"));
    const opened = (window as unknown as { __opened: SourceSurface[] })
      .__opened;
    const item = doorsOf(canvasElement, BOTH);
    const first = item.querySelector<HTMLElement>('[data-line-door="surface"]');
    const second = item.querySelector<HTMLElement>(
      '[data-line-door="compared_surface"]',
    );
    await expect(first).not.toBeNull();
    await expect(second).not.toBeNull();
    await expect(first?.textContent).toBe(
      t("workspace.modelo.surface.open.withholding"),
    );
    await expect(second?.textContent).toBe(
      t("workspace.modelo.surface.open.declarations"),
    );
    await userEvent.click(first as HTMLElement);
    await userEvent.click(second as HTMLElement);
    await expect(opened).toEqual(["withholding", "declarations"]);
  },
};

export const OneDoor: Story = {
  name: "Check · a finding with one door draws no second",
  render: () => {
    const opened: SourceSurface[] = [];
    (window as unknown as { __opened: SourceSurface[] }).__opened = opened;
    return <Doors lines={[line(ONE, "withholding", null)]} opened={opened} />;
  },
  play: async ({ canvasElement, globals }) => {
    const t = translator(String(globals.locale ?? "en"));
    const opened = (window as unknown as { __opened: SourceSurface[] })
      .__opened;
    const item = doorsOf(canvasElement, ONE);
    const first = item.querySelector<HTMLElement>('[data-line-door="surface"]');
    await expect(first?.textContent).toBe(
      t("workspace.modelo.surface.open.withholding"),
    );
    await expect(
      item.querySelector('[data-line-door="compared_surface"]'),
    ).toBeNull();
    await userEvent.click(first as HTMLElement);
    await expect(opened).toEqual(["withholding"]);
  },
};
