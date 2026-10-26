import type { Meta, StoryObj } from "@storybook/react-vite";
import { useMemo } from "react";
import { userEvent, within } from "storybook/test";
import type { DocsSearchResult } from "../ipc/contract";
import type { Action } from "../shell/actions";
import { useStrings } from "../shell/strings";
import { CommandPalette, type DocsSearch } from "./CommandPalette";

// The palette over a fixed action list and a fixed search provider. A story
// that shows results types its query the way a person would.
const DOCS = "https://docs.invalid";

const RESULTS: DocsSearchResult[] = [
  {
    kind: "page",
    title: "Declaring quarterly IVA",
    url: `${DOCS}/guides/iva.html`,
    excerpt: "The quarterly IVA return gathers output and input tax.",
    ranges: [[14, 17]],
    crumb: "Guides · IVA",
  },
  {
    kind: "concept",
    title: "IVA devengado",
    url: `${DOCS}/glossary.html#iva-devengado`,
    excerpt: "Output IVA charged on the operations of the period.",
    ranges: [[7, 10]],
    crumb: "Glossary",
  },
  {
    kind: "casilla",
    title: "Total cuota devengada",
    url: `${DOCS}/modelos/303.html#casilla-27`,
    excerpt: "Sum of the IVA quotas accrued in the period.",
    ranges: [[11, 14]],
    crumb: "Casilla · Modelo 303 · 27",
  },
  {
    kind: "cli",
    title: "cadrumo app modelo calculate",
    url: `${DOCS}/cli.html#modelo-calculate`,
    excerpt: "Calculates a draft revision, IVA carry included.",
    ranges: [[28, 31]],
    crumb: "Command",
  },
];

const noop = () => undefined;
// What the documentation's search does in a story.
type Mode = "answers" | "pending" | "empty" | "failing" | "absent";
const SEARCH: Record<Mode, DocsSearch> = {
  answers: async () => RESULTS,
  pending: () => new Promise<DocsSearchResult[]>(noop),
  empty: async () => [],
  failing: () => Promise.reject(new Error("fixture")),
  absent: null,
};

function Palette({ mode }: { mode: Mode }) {
  const t = useStrings();
  const actions = useMemo<Action[]>(
    () => [
      {
        id: "docs.home",
        label: t("desktop.rail.docs_home"),
        group: "docs",
        icon: "book",
        chords: [{ alt: true, code: "Home", key: "Home", scope: "docs" }],
        run: noop,
      },
      {
        id: "tui.toggle",
        label: t("desktop.rail.tui"),
        group: "view",
        icon: "tui",
        chords: [
          { mod: true, shift: true, code: "KeyT", key: "T", scope: "global" },
        ],
        run: noop,
      },
      {
        id: "panel.console",
        label: t("desktop.rail.console"),
        group: "view",
        icon: "console",
        chords: [
          {
            mod: true,
            shift: true,
            code: "Digit1",
            key: "1",
            scope: "global",
          },
        ],
        run: noop,
      },
      {
        id: "panel.python",
        label: t("desktop.rail.python"),
        group: "view",
        icon: "python",
        chords: [
          {
            mod: true,
            shift: true,
            code: "Digit2",
            key: "2",
            scope: "global",
          },
        ],
        run: noop,
      },
      {
        id: "panel.logs",
        label: t("desktop.rail.logs"),
        group: "view",
        icon: "logs",
        chords: [
          {
            mod: true,
            shift: true,
            code: "Digit3",
            key: "3",
            scope: "global",
          },
        ],
        run: noop,
      },
      {
        id: "split.swap",
        label: t("desktop.split.swap"),
        group: "view",
        icon: "swap",
        run: noop,
      },
      {
        id: "docs.zoomIn",
        label: t("desktop.action.zoom_in"),
        group: "docs",
        icon: "zoomIn",
        chords: [{ mod: true, code: "Equal", key: "=", scope: "docs" }],
        run: noop,
      },
      {
        id: "settings.open",
        label: t("desktop.rail.settings"),
        group: "view",
        icon: "settings",
        chords: [{ mod: true, code: "Comma", key: ",", scope: "app" }],
        run: noop,
      },
    ],
    [t],
  );
  return (
    <CommandPalette
      actions={actions}
      searchDocs={SEARCH[mode]}
      openDoc={noop}
      close={noop}
    />
  );
}

const meta = {
  title: "Shell/Command palette",
  parameters: { fill: true },
  args: { mode: "answers" },
  render: (args: { mode: Mode }) => <Palette {...args} />,
} satisfies Meta<{ mode: Mode }>;
export default meta;
type Story = StoryObj<typeof meta>;

const typed =
  (query: string): NonNullable<Story["play"]> =>
  async ({ canvasElement }) => {
    // The palette is drawn in a portal, outside the story's own element.
    const page = within(canvasElement.ownerDocument.body);
    await userEvent.type(await page.findByRole("combobox"), query);
  };

export const Actions: Story = {};

export const DocumentationResults: Story = { play: typed("iva") };

export const ChosenRow: Story = {
  play: async (context) => {
    await typed("iva")(context);
    // The choice can only move once there are results to move through.
    await within(context.canvasElement.ownerDocument.body).findByText(
      "IVA devengado",
    );
    await userEvent.keyboard("{ArrowDown}{ArrowDown}");
  },
};

export const Searching: Story = {
  args: { mode: "pending" },
  play: typed("iva"),
};

export const NothingFound: Story = {
  args: { mode: "empty" },
  play: typed("zzz"),
};

export const SearchUnavailable: Story = {
  args: { mode: "failing" },
  play: typed("iva"),
};

export const ActionsOnly: Story = {
  name: "Before the documentation answers",
  args: { mode: "absent" },
  play: typed("zzz"),
};
