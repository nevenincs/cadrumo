import { seededUnit } from "@/dev/seededUnits";
import { RENTA_UNIT } from "@/dev/rentaUnit";
import type { Meta, StoryObj } from "@storybook/react-vite";
import { useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { expect, userEvent, waitFor, within } from "storybook/test";
import rulesIncomplete from "@fixtures/modelo/scenario-rules-incomplete.json" with { type: "json" };
import { modeloFixture, type ModeloShape } from "@/dev/modeloFixture";
import { translator } from "../../../shell/strings";
import type { ModeloPort } from "../../../shell/modelo";
import type { OutputLanguage } from "../../../shell/modeloContract/modelo";
import {
  readPanePreference,
  writePanePreference,
  type PanePreference,
} from "../../../shell/panePreference";
import { PRIOR_VALUES_PANE } from "../form/PriorValuesOffer";
import type { WorkspaceView } from "./Workspace";
import { WorkspaceScreen } from "./WorkspaceScreen";
import { WORKSPACE_PANE_IDS } from "./WorkspacePanes";

// One declaration's workspace over the envelopes the application read for a
// synthetic taxpayer, through the scenario's modelo port.

const noop = () => undefined;

/** The synthetic taxpayer's declarations, by the work unit the list read. */
const UNITS = {
  "130": seededUnit("130"),
  "303": seededUnit("303"),
  "347": seededUnit("347"),
  "rules-incomplete": rulesIncomplete.work_unit_id,
  "100": RENTA_UNIT,
} as const;

const language = (globals: Record<string, unknown>) =>
  String(globals.locale ?? "en") as OutputLanguage;

function Screen({
  modelo,
  shape = "fixture",
  locale,
  view,
}: {
  modelo: keyof typeof UNITS;
  shape?: ModeloShape;
  locale: OutputLanguage;
  view?: WorkspaceView;
}) {
  const port = useRef<ModeloPort | null>(null);
  port.current ??= modeloFixture({
    say: noop,
    translate: translator,
    wait: async () => undefined,
    signedIn: () => true,
    shape,
  });
  return (
    <div className="flex h-full min-h-0 flex-col">
      <WorkspaceScreen
        port={port.current}
        workUnitId={UNITS[modelo]}
        language={locale}
        locale={locale}
        onBack={noop}
        onOpenSurface={noop}
        canOpenSurface={() => true}
        openLink={noop}
        initialView={view}
      />
    </div>
  );
}

/** Draws its children with the panes kept as `kept`, by pane name, and gives
 * the viewer's own preferences back when the story is left. */
function KeptPanes({
  kept,
  children,
}: {
  kept: Record<string, PanePreference>;
  children: ReactNode;
}) {
  const [held] = useState(() => {
    const before = Object.keys(kept).map(
      (id) => [id, readPanePreference(id)] as const,
    );
    for (const [id, preference] of Object.entries(kept))
      writePanePreference(id, preference);
    return before;
  });
  useLayoutEffect(
    () => () => {
      for (const [id, preference] of held) writePanePreference(id, preference);
    },
    [held],
  );
  return children;
}

const ALL_PANES = (preference: PanePreference) =>
  Object.fromEntries(
    Object.values(WORKSPACE_PANE_IDS).map((id) => [id, preference]),
  );

const meta: Meta = {
  title: "Modelo/Workspace",
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;
type Story = StoryObj;

export const Modelo130: Story = {
  name: "130 · something blocks filing",
  render: (_, { globals }) => (
    <Screen modelo="130" locale={language(globals)} />
  ),
};

export const Modelo303: Story = {
  name: "303 · not calculated yet",
  render: (_, { globals }) => (
    <Screen modelo="303" locale={language(globals)} />
  ),
};

export const Modelo347: Story = {
  name: "347 · to check",
  render: (_, { globals }) => (
    <Screen modelo="347" locale={language(globals)} />
  ),
};

export const RulesIncomplete: Story = {
  name: "Rules not complete",
  render: (_, { globals }) => (
    <Screen modelo="rules-incomplete" locale={language(globals)} />
  ),
};

export const Unavailable: Story = {
  name: "The form cannot be read",
  render: (_, { globals }) => (
    <Screen modelo="130" shape="unavailable" locale={language(globals)} />
  ),
};

export const Checked: Story = {
  name: "130 · after its check",
  render: (_, { globals }) => (
    <Screen modelo="130" shape="checked" locale={language(globals)} />
  ),
};

export const CheckedFindings: Story = {
  name: "130 · Check view after its check",
  render: (_, { globals }) => (
    <Screen
      modelo="130"
      shape="checked"
      view="check"
      locale={language(globals)}
    />
  ),
};

export const CheckNotYet: Story = {
  name: "130 · Check view before any check",
  render: (_, { globals }) => (
    <Screen modelo="130" view="check" locale={language(globals)} />
  ),
};

export const Filed: Story = {
  name: "130 · recorded as filed",
  render: (_, { globals }) => (
    <Screen modelo="130" shape="filed" locale={language(globals)} />
  ),
};

export const Sources: Story = {
  name: "130 · Sources view",
  render: (_, { globals }) => (
    <Screen modelo="130" view="sources" locale={language(globals)} />
  ),
};

export const History: Story = {
  name: "130 · History view, read unavailable in the scenario",
  render: (_, { globals }) => (
    <Screen modelo="130" view="history" locale={language(globals)} />
  ),
};

export const Modelo100Unresolved: Story = {
  name: "100 · salaried, withholding credits unresolved",
  render: (_, { globals }) => (
    <Screen modelo="100" shape="renta" locale={language(globals)} />
  ),
};

/** Opens the outline beside the form, once the workspace has read it. */
const showOutline = async ({
  canvasElement,
}: {
  canvasElement: HTMLElement;
}) => {
  const tabs = await waitFor(
    () => {
      const found = canvasElement.querySelectorAll<HTMLElement>(
        "aside [role=tablist] [role=tab]",
      );
      if (found.length < 2) throw new Error("the rail is not drawn yet");
      return found;
    },
    { timeout: 15_000 },
  );
  await userEvent.click(tabs[1]!);
};

export const Modelo100Outline: Story = {
  name: "100 · salaried, the outline beside the form",
  render: (_, { globals }) => (
    <Screen modelo="100" shape="renta" locale={language(globals)} />
  ),
  play: showOutline,
};

export const Modelo100ActivityOutline: Story = {
  name: "100 · self-employed, the outline with what needs you",
  render: (_, { globals }) => (
    <Screen modelo="100" shape="renta-activity" locale={language(globals)} />
  ),
  play: showOutline,
};

export const Modelo303Outline: Story = {
  name: "303 · the page outline beside the form",
  render: (_, { globals }) => (
    <Screen modelo="303" locale={language(globals)} />
  ),
  play: showOutline,
};

export const Modelo100Check: Story = {
  name: "100 · Check view with the credits unresolved",
  render: (_, { globals }) => (
    <Screen
      modelo="100"
      shape="renta"
      view="check"
      locale={language(globals)}
    />
  ),
};

export const Modelo100ToPay: Story = {
  name: "100 · salaried, certificate in the register, result to pay",
  render: (_, { globals }) => (
    <Screen modelo="100" shape="renta-pay" locale={language(globals)} />
  ),
};

export const Modelo100ToRefund: Story = {
  name: "100 · salaried, certificate in the register, result to refund",
  render: (_, { globals }) => (
    <Screen modelo="100" shape="renta-refund" locale={language(globals)} />
  ),
};

export const Modelo100Activity: Story = {
  name: "100 · self-employed, result not calculated",
  render: (_, { globals }) => (
    <Screen modelo="100" shape="renta-activity" locale={language(globals)} />
  ),
};

export const Modelo100Sources: Story = {
  name: "100 · Sources view with the register's credits",
  render: (_, { globals }) => (
    <Screen
      modelo="100"
      shape="renta-pay"
      view="sources"
      locale={language(globals)}
    />
  ),
};

export const PanesHidden: Story = {
  name: "130 · To do and details hidden",
  render: (_, { globals }) => (
    <KeptPanes kept={ALL_PANES({ open: false, side: null, bottom: null })}>
      <Screen modelo="130" locale={language(globals)} />
    </KeptPanes>
  ),
};

export const PanesResized: Story = {
  name: "130 · To do and details drawn wider",
  render: (_, { globals }) => (
    <KeptPanes kept={ALL_PANES({ open: true, side: 22 * 16, bottom: 18 * 16 })}>
      <Screen modelo="130" locale={language(globals)} />
    </KeptPanes>
  ),
};

export const DetailsStacked: Story = {
  name: "130 · details chosen under the form on a wide window",
  render: (_, { globals }) => (
    <KeptPanes
      kept={ALL_PANES({
        open: true,
        placement: "bottom",
        side: null,
        bottom: null,
      })}
    >
      <Screen modelo="130" locale={language(globals)} />
    </KeptPanes>
  ),
};

export const NarrowDetailsBeside: Story = {
  name: "130 · a narrow window, details chosen beside the form",
  render: (_, { globals }) => (
    <KeptPanes
      kept={ALL_PANES({
        open: true,
        placement: "side",
        side: null,
        bottom: null,
      })}
    >
      <div className="flex h-150 w-200 max-w-full min-h-0 flex-col border border-border">
        <Screen modelo="130" locale={language(globals)} />
      </div>
    </KeptPanes>
  ),
  play: async ({ canvasElement }) => {
    const control = await waitFor(
      () => {
        const found = canvasElement.querySelector<HTMLElement>(
          "[data-pane-toggle=placement]",
        );
        if (!found) throw new Error("the arrangement control is not drawn yet");
        return found;
      },
      { timeout: 15_000 },
    );
    await expect(control).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(control);
    await expect(control).toHaveAttribute("aria-pressed", "false");
    await expect(
      canvasElement.querySelector("[data-details=bottom]"),
    ).not.toBeNull();
    await userEvent.click(control);
    await expect(control).toHaveAttribute("aria-pressed", "true");
  },
};

export const NarrowRailOpener: Story = {
  name: "130 · a narrow window, the To do and Outline opened from the toolbar",
  render: (_, { globals }) => (
    <KeptPanes kept={ALL_PANES({ open: null, side: null, bottom: null })}>
      <div className="flex h-150 w-200 max-w-full min-h-0 flex-col border border-border">
        <Screen modelo="130" locale={language(globals)} />
      </div>
    </KeptPanes>
  ),
  play: async ({ canvasElement }) => {
    const opener = await waitFor(
      () => {
        const found = canvasElement.querySelector<HTMLElement>(
          "[data-pane-toggle=side]",
        );
        if (!found) throw new Error("the rail's control is not drawn yet");
        return found;
      },
      { timeout: 15_000 },
    );
    await expect(opener).toHaveAttribute("aria-pressed", "false");
    await userEvent.click(opener);
    await expect(opener).toHaveAttribute("aria-pressed", "true");
    await expect(
      within(canvasElement).getAllByRole("separator").length,
    ).toBeGreaterThan(0);
  },
};

export const PriorValuesHidden: Story = {
  name: "130 · the earlier-return figures offer hidden",
  render: (_, { globals }) => (
    <KeptPanes
      kept={{
        [PRIOR_VALUES_PANE]: { open: false, side: null, bottom: null },
      }}
    >
      <Screen modelo="130" locale={language(globals)} />
    </KeptPanes>
  ),
};

/** The three pane controls, found once the workspace has drawn them. */
const paneControls = (canvasElement: HTMLElement) =>
  waitFor(
    () => {
      const found = ["side", "details", "placement"].map((name) =>
        canvasElement.querySelector<HTMLElement>(`[data-pane-toggle=${name}]`),
      );
      if (found.some((control) => !control))
        throw new Error("the pane controls are not drawn yet");
      return found as [HTMLElement, HTMLElement, HTMLElement];
    },
    { timeout: 15_000 },
  );

const iconOf = (control: HTMLElement) =>
  control.querySelector("svg[data-icon]")?.getAttribute("data-icon");

export const PaneControlsDetailsHidden: Story = {
  name: "130 · pane controls with the details hidden, the arrangement still set",
  render: (_, { globals }) => (
    <KeptPanes kept={ALL_PANES({ open: false, side: null, bottom: null })}>
      <Screen modelo="130" locale={language(globals)} />
    </KeptPanes>
  ),
  play: async ({ canvasElement }) => {
    const [side, details, placement] = await paneControls(canvasElement);
    await expect(details).toHaveAttribute("aria-pressed", "false");
    await expect(new Set([side, details, placement].map(iconOf)).size).toBe(3);
    const before = placement.getAttribute("aria-pressed");
    await userEvent.click(placement);
    await expect(placement).not.toHaveAttribute("aria-pressed", before ?? "");
    await userEvent.click(placement);
    await expect(placement).toHaveAttribute("aria-pressed", before ?? "");
  },
};

export const PaneControlsBeside: Story = {
  name: "130 · pane controls with the rail shown and the details beside the form",
  render: (_, { globals }) => (
    <KeptPanes
      kept={ALL_PANES({
        open: true,
        placement: "side",
        side: null,
        bottom: null,
      })}
    >
      <Screen modelo="130" locale={language(globals)} />
    </KeptPanes>
  ),
  play: async ({ canvasElement }) => {
    const controls = await paneControls(canvasElement);
    for (const control of controls)
      await expect(control).toHaveAttribute("aria-pressed", "true");
    await expect(controls.map(iconOf)).toEqual([
      "panelLeft",
      "panelRight",
      "splitBeside",
    ]);
  },
};

export const PaneControlsUnder: Story = {
  name: "130 · pane controls with the rail hidden and the details under the form",
  render: (_, { globals }) => (
    <KeptPanes
      kept={{
        [WORKSPACE_PANE_IDS.side]: { open: false, side: null, bottom: null },
        [WORKSPACE_PANE_IDS.details]: {
          open: true,
          placement: "bottom",
          side: null,
          bottom: null,
        },
      }}
    >
      <Screen modelo="130" locale={language(globals)} />
    </KeptPanes>
  ),
  play: async ({ canvasElement }) => {
    const controls = await paneControls(canvasElement);
    await expect(controls.map(iconOf)).toEqual([
      "panelLeft",
      "panelBottom",
      "splitUnder",
    ]);
    await expect(controls[2]).toHaveAttribute("aria-pressed", "false");
  },
};
