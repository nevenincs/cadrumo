import type { Meta, StoryObj } from "@storybook/react-vite";
import { useMemo } from "react";
import { userEvent, within } from "storybook/test";
import type { DocsSearchResult } from "../ipc/docsBridge";
import type { Action } from "../shell/actions";
import { useStrings, type Translate } from "../shell/strings";
import { CommandPalette, type DocsSearch } from "./CommandPalette";

// The palette over a fixed action list and a fixed search provider. A story
// that shows results types its query the way a person would.
const DOCS = "https://docs.invalid";

// What the documentation serves is in the documentation's language, and the
// category line is the controller's, so each language has its own results.
// A match is the first "IVA" of the excerpt.
type Page = {
  title: string;
  excerpt: string;
};
type Words = {
  guides: string;
  glossary: string;
  pages: readonly [Page, Page, Page, Page];
};

const WORDS: Record<string, Words> = {
  en: {
    guides: "Guides",
    glossary: "Glossary",
    pages: [
      {
        title: "Declaring quarterly IVA",
        excerpt: "The quarterly IVA return gathers output and input tax.",
      },
      {
        title: "IVA devengado",
        excerpt: "Output IVA charged on the operations of the period.",
      },
      {
        title: "Total cuota devengada",
        excerpt: "Sum of the IVA quotas accrued in the period.",
      },
      {
        title: "cadrumo app modelo calculate",
        excerpt: "Calculates a draft revision, IVA carry included.",
      },
    ],
  },
  es: {
    guides: "Guías",
    glossary: "Glosario",
    pages: [
      {
        title: "Declarar el IVA trimestral",
        excerpt:
          "La declaración trimestral de IVA reúne el IVA repercutido y el soportado.",
      },
      {
        title: "IVA devengado",
        excerpt: "IVA repercutido en las operaciones del periodo.",
      },
      {
        title: "Total cuota devengada",
        excerpt: "Suma de las cuotas de IVA devengadas en el periodo.",
      },
      {
        title: "cadrumo app modelo calculate",
        excerpt:
          "Calcula una revisión en borrador, con el arrastre de IVA incluido.",
      },
    ],
  },
  ca: {
    guides: "Guies",
    glossary: "Glossari",
    pages: [
      {
        title: "Declarar l'IVA trimestral",
        excerpt:
          "La declaració trimestral de l'IVA recull l'IVA repercutit i el suportat.",
      },
      {
        title: "IVA devengado",
        excerpt: "IVA repercutit en les operacions del període.",
      },
      {
        title: "Total cuota devengada",
        excerpt: "Suma de les quotes d'IVA meritades en el període.",
      },
      {
        title: "cadrumo app modelo calculate",
        excerpt:
          "Calcula una revisió en esborrany, amb l'arrossegament d'IVA inclòs.",
      },
    ],
  },
  hu: {
    guides: "Útmutatók",
    glossary: "Szójegyzék",
    pages: [
      {
        title: "A negyedéves IVA bevallása",
        excerpt:
          "A negyedéves IVA-bevallás összegyűjti a fizetendő és a levonható IVA-t.",
      },
      {
        title: "IVA devengado",
        excerpt: "Az időszak műveletei után felszámított fizetendő IVA.",
      },
      {
        title: "Total cuota devengada",
        excerpt: "Az időszakban esedékessé vált IVA-tételek összege.",
      },
      {
        title: "cadrumo app modelo calculate",
        excerpt: "Kiszámít egy vázlatverziót, az IVA-átvitellel együtt.",
      },
    ],
  },
};

const IVA = "IVA";

function resultsIn(t: Translate): DocsSearchResult[] {
  const words = WORDS[t.locale ?? "en"] ?? WORDS.en!;
  const hit = (excerpt: string) => {
    const at = excerpt.indexOf(IVA);
    return [[at, at + IVA.length]] as const;
  };
  const [page, concept, casilla, command] = words.pages;
  return [
    {
      kind: "page",
      ...page,
      url: `${DOCS}/guides/iva.html`,
      ranges: [...hit(page.excerpt)],
      crumb: `${words.guides} · IVA`,
    },
    {
      kind: "concept",
      ...concept,
      url: `${DOCS}/glossary.html#iva-devengado`,
      ranges: [...hit(concept.excerpt)],
      crumb: words.glossary,
    },
    {
      kind: "casilla",
      ...casilla,
      url: `${DOCS}/modelos/303.html#casilla-27`,
      ranges: [...hit(casilla.excerpt)],
      crumb: `${t("desktop.palette.kind_casilla")} · Modelo 303 · 27`,
    },
    {
      kind: "cli",
      ...command,
      url: `${DOCS}/cli.html#modelo-calculate`,
      ranges: [...hit(command.excerpt)],
      crumb: t("desktop.palette.kind_cli"),
    },
  ];
}

const noop = () => undefined;
// What the documentation's search does in a story.
type Mode = "answers" | "pending" | "empty" | "failing" | "absent";
const searchOf = (mode: Mode, t: Translate): DocsSearch =>
  ({
    answers: async () => resultsIn(t),
    pending: () => new Promise<DocsSearchResult[]>(noop),
    empty: async () => [],
    failing: () => Promise.reject(new Error("fixture")),
    absent: null,
  })[mode];

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
      searchDocs={searchOf(mode, t)}
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
