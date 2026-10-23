import type { Meta, StoryObj } from "@storybook/react-vite";
import { DeclarationsHub } from "./DeclarationsHub";
import {
  checked130,
  DECLARATIONS,
  envelope,
  exported130,
  fieldsOf,
  filled130,
  issues130,
  recorded130,
} from "./fixtures";
import { editKey, heldValue, intentFor, type Staged } from "./FormView";
import type { FormEnvelope } from "./types";
import { ModeloWorkspace } from "./Workspace";

// Design prototypes for the Modelo workspace, round by round. Every form is
// an envelope of the registered read `modelo.work.form` for a synthetic
// taxpayer; see `fixtures.ts` for what each scenario changed. The AEAT side
// is the calendar read's, passed on its own.

const meta: Meta = {
  title: "Prototypes/Modelo",
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;

type Story = StoryObj<{ locale: string }>;

const lang = (globals: Record<string, unknown>) =>
  String(globals.locale ?? "en");

/** Edits as the workspace keeps them, typed into boxes by number. */
function typed(e: FormEnvelope, locale: string, by: [string, string][]) {
  const all = fieldsOf(e.form.form);
  const out: Staged = {};
  for (const [box, text] of by) {
    const f = all.find((x) => x.box === box);
    const intent = f && intentFor(f, text);
    if (f && intent && !("refused" in intent))
      out[editKey(f)] = { intent, was: heldValue(f, locale) };
  }
  return out;
}

export const Declarations: Story = {
  render: (_, { globals }) => (
    <DeclarationsHub rows={DECLARATIONS} locale={lang(globals)} />
  ),
};

export const NewDeclaration: Story = {
  render: (_, { globals }) => (
    <DeclarationsHub rows={DECLARATIONS} locale={lang(globals)} creating />
  ),
};

export const OneBoxToDo: Story = {
  name: "130 · one box needs you",
  render: (_, { globals }) => (
    <ModeloWorkspace
      envelope={filled130(lang(globals))}
      locale={lang(globals)}
      initialSelected="c:18"
    />
  ),
};

export const ReviewEdits: Story = {
  name: "130 · reviewing edits, one replaces an earlier declaration",
  render: (_, { globals }) => {
    const e = filled130(lang(globals));
    return (
      <ModeloWorkspace
        envelope={e}
        locale={lang(globals)}
        initialSelected="c:05"
        initialReviewing
        initialStaged={typed(e, lang(globals), [
          ["05", "1.250,00"],
          ["18", "0"],
        ])}
      />
    );
  },
};

export const CouldNotWorkOut: Story = {
  name: "130 · calculated, result could not be worked out",
  render: (_, { globals }) => (
    <ModeloWorkspace
      envelope={envelope("130", lang(globals))}
      locale={lang(globals)}
      initialSelected="c:13"
    />
  ),
};

export const CheckFindings: Story = {
  name: "130 · check found things",
  render: (_, { globals }) => (
    <ModeloWorkspace
      envelope={issues130(lang(globals))}
      locale={lang(globals)}
      initialView="check"
    />
  ),
};

export const ReadyToExport: Story = {
  name: "130 · checked, ready to export",
  render: (_, { globals }) => (
    <ModeloWorkspace
      envelope={checked130(lang(globals))}
      locale={lang(globals)}
      initialView="file"
    />
  ),
};

export const StaleExport: Story = {
  name: "130 · exported file out of date",
  render: (_, { globals }) => (
    <ModeloWorkspace
      envelope={exported130(lang(globals), false)}
      locale={lang(globals)}
      initialView="file"
    />
  ),
};

export const Recorded: Story = {
  name: "130 · recorded as filed, receipt not added",
  render: (_, { globals }) => (
    <ModeloWorkspace
      envelope={recorded130(lang(globals))}
      locale={lang(globals)}
      aeat={{ state: "not_observed", on: null }}
      initialView="file"
    />
  ),
};

export const RecordedHistory: Story = {
  name: "130 · receipt verified, preparing a correction",
  render: (_, { globals }) => (
    <ModeloWorkspace
      envelope={recorded130(lang(globals))}
      locale={lang(globals)}
      aeat={{ state: "justificante_verified", on: "2026-10-15T09:40:00" }}
      initialView="history"
      initialCorrecting
    />
  ),
};

export const Sources: Story = {
  name: "130 · where values come from",
  render: (_, { globals }) => (
    <ModeloWorkspace
      envelope={filled130(lang(globals))}
      locale={lang(globals)}
      initialView="sources"
    />
  ),
};

export const Grids303: Story = {
  name: "303 · official grids, before calculating",
  render: (_, { globals }) => (
    <ModeloWorkspace
      envelope={envelope("303", lang(globals))}
      locale={lang(globals)}
      initialSelected="c:150"
    />
  ),
};

export const Records347: Story = {
  name: "347 · repeated records",
  render: (_, { globals }) => (
    <ModeloWorkspace
      envelope={envelope("347", lang(globals))}
      locale={lang(globals)}
    />
  ),
};

export const ReadOnly390: Story = {
  name: "390 · cannot be edited",
  render: (_, { globals }) => (
    <ModeloWorkspace
      envelope={envelope("390", lang(globals))}
      locale={lang(globals)}
    />
  ),
};

export const Narrow130: Story = {
  name: "130 · narrow window, details over the form",
  render: (_, { globals }) => (
    <ModeloWorkspace
      envelope={filled130(lang(globals))}
      locale={lang(globals)}
      initialSelected="c:05"
    />
  ),
};
