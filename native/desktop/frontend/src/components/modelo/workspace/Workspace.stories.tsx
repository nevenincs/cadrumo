import type { Meta, StoryObj } from "@storybook/react-vite";
import { useRef } from "react";
import { userEvent, waitFor } from "storybook/test";
import { modeloFixture, type ModeloShape } from "@/dev/modeloFixture";
import { translator } from "../../../shell/strings";
import type { ModeloPort } from "../../../shell/modelo";
import type { OutputLanguage } from "../../../shell/modeloContract/modelo";
import type { WorkspaceView } from "./Workspace";
import { WorkspaceScreen } from "./WorkspaceScreen";

// One declaration's workspace over the envelopes the application read for a
// synthetic taxpayer, through the scenario's modelo port.

const noop = () => undefined;

/** The synthetic taxpayer's declarations, by the work unit the list read. */
const UNITS = {
  "130": "66354cafad021ef81e8c4bce2a0d361a2fa3ba568efc325ee607266291fd8fb3",
  "303": "b650ba021eda8c3082ea9d66d8be078c7c6247610af8772ddd48d75b604198f6",
  "347": "f8b5118f6aa31dfa3ba496cc98360941661880792b4f29c991453f94e77e97da",
  "390": "af66ad3c64bd5b1a6d6670a20a645c9966136f578c4209d2eab1e83d69f16aa3",
  "100": "b1c431589384a105701ba15942606b5f5667cb677d6fa62e743cd0293f9baee4",
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

export const Modelo390: Story = {
  name: "390 · rules not complete",
  render: (_, { globals }) => (
    <Screen modelo="390" locale={language(globals)} />
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
