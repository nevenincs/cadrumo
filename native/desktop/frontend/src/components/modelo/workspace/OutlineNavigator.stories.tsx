import type { Meta, StoryObj } from "@storybook/react-vite";
import { useEffect, useRef, useState } from "react";
import { userEvent, waitFor, within } from "storybook/test";
import { modeloFixture, type ModeloShape } from "@/dev/modeloFixture";
import { translator } from "../../../shell/strings";
import type { ModeloPort } from "../../../shell/modelo";
import type {
  ModeloWorkbenchFormProjectionV1,
  OutputLanguage,
} from "../../../shell/modeloContract";
import { OutlineNavigator } from "./OutlineNavigator";

// The form's navigator over the outline the application served for a
// synthetic taxpayer, one declaration per story. The navigator knows no
// modelo: the Modelo 100 serves its own outline, and the others one group
// per page.

const noop = () => undefined;

const UNITS = {
  "130": "66354cafad021ef81e8c4bce2a0d361a2fa3ba568efc325ee607266291fd8fb3",
  "303": "b650ba021eda8c3082ea9d66d8be078c7c6247610af8772ddd48d75b604198f6",
  "100": "b1c431589384a105701ba15942606b5f5667cb677d6fa62e743cd0293f9baee4",
} as const;

const language = (globals: Record<string, unknown>) =>
  String(globals.locale ?? "en") as OutputLanguage;

function Navigator({
  modelo,
  shape = "fixture",
  locale,
}: {
  modelo: keyof typeof UNITS;
  shape?: ModeloShape;
  locale: OutputLanguage;
}) {
  const port = useRef<ModeloPort | null>(null);
  port.current ??= modeloFixture({
    say: noop,
    translate: translator,
    wait: async () => undefined,
    signedIn: () => true,
    shape,
  });
  const [envelope, setEnvelope] =
    useState<ModeloWorkbenchFormProjectionV1 | null>(null);
  const [current, setCurrent] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    void port.current?.form(UNITS[modelo], locale).then((read) => {
      if (live) setEnvelope(read);
    });
    return () => {
      live = false;
    };
  }, [modelo, locale]);
  return (
    <div className="flex h-full min-h-0 w-72 flex-col overflow-y-auto border-r border-border bg-chrome">
      {envelope && (
        <OutlineNavigator
          key={`${modelo}-${locale}`}
          form={envelope.form.form}
          currentSectionId={current}
          onJump={setCurrent}
        />
      )}
    </div>
  );
}

const meta: Meta = {
  title: "Modelo/Outline navigator",
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;
type Story = StoryObj;

const tree = async (canvasElement: HTMLElement) =>
  waitFor(() => within(canvasElement).getByRole("tree"), { timeout: 15_000 });

export const Renta: Story = {
  name: "100 · salaried, the served Renta outline",
  render: (_, { globals }) => (
    <Navigator modelo="100" shape="renta" locale={language(globals)} />
  ),
};

export const RentaActivity: Story = {
  name: "100 · self-employed, boxes that need you and could not be calculated",
  render: (_, { globals }) => (
    <Navigator modelo="100" shape="renta-activity" locale={language(globals)} />
  ),
};

export const RentaJumped: Story = {
  name: "100 · a section jumped to is the current one",
  render: (_, { globals }) => (
    <Navigator modelo="100" shape="renta" locale={language(globals)} />
  ),
  play: async ({ canvasElement }) => {
    const outline = await tree(canvasElement);
    const section = outline.querySelector<HTMLElement>(
      '[data-outline-section="datoseconomicos-resultados.calculoimpuestores-4"]',
    );
    if (section) await userEvent.click(section);
  },
};

export const RentaCollapsed: Story = {
  name: "100 · every group folded",
  render: (_, { globals }) => (
    <Navigator modelo="100" shape="renta" locale={language(globals)} />
  ),
  play: async ({ canvasElement }) => {
    await tree(canvasElement);
    const fold = canvasElement.querySelector<HTMLElement>(
      "nav button:not([aria-pressed])",
    );
    if (fold) await userEvent.click(fold);
  },
};

export const PageDefault: Story = {
  name: "303 · one group per page, unknown and not applicable",
  render: (_, { globals }) => (
    <Navigator modelo="303" locale={language(globals)} />
  ),
};

export const PageDefaultHidden: Story = {
  name: "303 · what does not apply hidden",
  render: (_, { globals }) => (
    <Navigator modelo="303" locale={language(globals)} />
  ),
  play: async ({ canvasElement }) => {
    await tree(canvasElement);
    const hide = canvasElement.querySelector<HTMLElement>(
      "nav button[aria-pressed]",
    );
    if (hide) await userEvent.click(hide);
  },
};

export const SinglePage: Story = {
  name: "130 · one page, one group",
  render: (_, { globals }) => (
    <Navigator modelo="130" locale={language(globals)} />
  ),
};
