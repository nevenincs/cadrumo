import { seededUnit } from "@/dev/seededUnits";
import { RENTA_UNIT } from "@/dev/rentaUnit";
import type { Meta, StoryObj } from "@storybook/react-vite";
import { useEffect, useRef, useState } from "react";
import { expect, userEvent, waitFor, within } from "storybook/test";
import { modeloFixture, type ModeloShape } from "@/dev/modeloFixture";
import { translator } from "../../../shell/strings";
import type { ModeloPort } from "../../../shell/modelo";
import type { OutputLanguage } from "../../../shell/modeloContract/modelo";
import type { ModeloWorkbenchFormProjectionV1 } from "../../../shell/modeloContract/modeloWorkForm";
import { OutlineNavigator } from "./OutlineNavigator";

// The form's navigator over the outline the application served for a
// synthetic taxpayer, one declaration per story. The navigator knows no
// modelo: the Modelo 100 serves its own outline, and the others one group
// per page.

const noop = () => undefined;

const UNITS = {
  "130": seededUnit("130"),
  "303": seededUnit("303"),
  "100": RENTA_UNIT,
} as const;

const language = (globals: Record<string, unknown>) =>
  String(globals.locale ?? "en") as OutputLanguage;

function Navigator({
  modelo,
  shape = "fixture",
  locale,
  withProfile = false,
}: {
  modelo: keyof typeof UNITS;
  shape?: ModeloShape;
  locale: OutputLanguage;
  /** Offers the way to the profile, as the window does where it has one. */
  withProfile?: boolean;
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
  const [opened, setOpened] = useState(0);
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
          onOpenProfile={
            withProfile ? () => setOpened((n) => n + 1) : undefined
          }
        />
      )}
      <output data-opened-profile={opened} className="sr-only">
        {opened}
      </output>
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

export const RentaKeptInProfile: Story = {
  name: "100 · a group with boxes kept in the profile leads to it",
  render: (_, { globals }) => (
    <Navigator
      modelo="100"
      shape="renta"
      locale={language(globals)}
      withProfile
    />
  ),
  play: async ({ canvasElement }) => {
    const outline = await tree(canvasElement);
    const links = outline.querySelectorAll<HTMLElement>(
      "[data-outline-profile]",
    );
    expect(links.length).toBeGreaterThan(0);
    // Only a group whose boxes the read model says are kept there has one.
    expect(links.length).toBeLessThan(
      outline.querySelectorAll("[data-outline-group]").length,
    );
    await userEvent.click(links[0]!);
    await waitFor(() =>
      expect(
        canvasElement.querySelector("[data-opened-profile]"),
      ).toHaveAttribute("data-opened-profile", "1"),
    );
  },
};

export const RentaKeptApart: Story = {
  name: "100 · the lists kept apart from the pages, the answers among them, lead to their pages",
  render: (_, { globals }) => (
    <Navigator modelo="100" shape="renta" locale={language(globals)} />
  ),
  play: async ({ canvasElement }) => {
    const outline = await tree(canvasElement);
    const kinds = ["unplaced", "working_figures", "answers"];
    for (const kind of kinds) {
      const apart = outline.querySelector<HTMLElement>(
        `[data-outline-kind="${kind}"]`,
      );
      expect(apart).not.toBeNull();
      // A list has no sections to fold: it is chosen, not opened.
      expect(apart).not.toHaveAttribute("aria-expanded");
      await userEvent.click(apart!);
      await waitFor(() =>
        expect(apart).toHaveAttribute("aria-current", "location"),
      );
    }
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
  name: "130 · one page, one group, then the answers",
  render: (_, { globals }) => (
    <Navigator modelo="130" locale={language(globals)} />
  ),
};

export const AnswersKeptApart: Story = {
  name: "130 · the answers no page takes lead to their page",
  render: (_, { globals }) => (
    <Navigator modelo="130" locale={language(globals)} />
  ),
  play: async ({ canvasElement }) => {
    const outline = await tree(canvasElement);
    const answers = outline.querySelector<HTMLElement>(
      '[data-outline-kind="answers"]',
    );
    expect(answers).not.toBeNull();
    expect(answers).not.toHaveAttribute("aria-expanded");
    await userEvent.click(answers!);
    await waitFor(() =>
      expect(answers).toHaveAttribute("aria-current", "location"),
    );
  },
};
