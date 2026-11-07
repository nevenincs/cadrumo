import type { Meta, StoryObj } from "@storybook/react-vite";
import { useEffect, useRef, useState } from "react";
import { expect, userEvent, waitFor } from "storybook/test";
import { modeloFixture, type ModeloShape } from "@/dev/modeloFixture";
import {
  RENTA_UNIT,
  servedYears,
  type ServedYear,
} from "@/dev/servedRentaYears";
import { translator } from "../../../shell/strings";
import type { ModeloPort } from "../../../shell/modelo";
import type { OutputLanguage } from "../../../shell/modeloContract/modelo";
import type { ModeloTaxationComparisonProjection } from "../../../shell/modeloContract/modeloWork";
import type {
  ModeloFormElection,
  PublicModeloFormExportOffer,
} from "../../../shell/modeloContract/modeloWorkForm";
import type { LedgerErrorDetail } from "../../../shell/ledger";
import { Settlement } from "./Settlement";
import { WorkspaceScreen } from "./WorkspaceScreen";
import { byName } from "@/dev/globByName";

// What the Modelo 100 of each supported filing year offers, in the real
// workspace over the envelopes the application read for the same couple in
// each year. The years are not listed here: they are the ones the stored
// envelopes cover, each as its own form states it, and a year that has no
// edition of its own is the one the form says was projected from another.
// Each story walks every year, so a year the registry adds is covered by the
// fixtures it is recorded in.

type View = "form" | "compare" | "credits" | "file";

const language = (globals: Record<string, unknown>) =>
  String(globals.locale ?? "en") as OutputLanguage;

const comparisons = byName(
  import.meta.glob<ModeloTaxationComparisonProjection>(
    "@fixtures/modelo/compare-100-0A-*.json",
    { import: "default" },
  ),
);
const refusals = byName(
  import.meta.glob<LedgerErrorDetail>(
    "@fixtures/modelo/refusal-compare-100-0A-*.json",
    { import: "default" },
  ),
);
const offers = byName(
  import.meta.glob<PublicModeloFormExportOffer>(
    "@fixtures/modelo/settlement-100-0A-*.json",
    { import: "default" },
  ),
);

const filerOf = (shape: ModeloShape) => shape.slice("renta-".length);

function Screen({
  shape,
  locale,
  view,
}: {
  shape: ModeloShape;
  locale: OutputLanguage;
  view: View;
}) {
  const port = useRef<ModeloPort | null>(null);
  port.current ??= modeloFixture({
    say: () => undefined,
    translate: translator,
    wait: async () => undefined,
    signedIn: () => true,
    shape,
  });
  return (
    <div className="flex h-full min-h-0 flex-col">
      <WorkspaceScreen
        port={port.current}
        workUnitId={RENTA_UNIT}
        language={locale}
        locale={locale}
        onBack={() => undefined}
        onOpenSurface={() => undefined}
        canOpenSurface={() => true}
        openLink={() => undefined}
        initialView={view}
      />
    </div>
  );
}

/** The workspace of one supported year, chosen from the years the
 * fixtures cover. */
function ByYear({ locale, view }: { locale: OutputLanguage; view: View }) {
  const [years, setYears] = useState<ServedYear[] | null>(null);
  const [shape, setShape] = useState<ModeloShape | null>(null);
  useEffect(() => {
    void servedYears(locale).then((read) => {
      setYears(read);
      setShape((now) => now ?? read[0]?.shape ?? null);
    });
  }, [locale]);
  if (!years || !shape) return null;
  return (
    <div className="flex h-full min-h-0 flex-col">
      <label className="flex items-center gap-2 border-b border-border p-2 text-sm">
        <span>Filing year</span>
        <select
          data-year-select
          value={shape}
          onChange={(event) => setShape(event.target.value as ModeloShape)}
        >
          {years.map((served) => (
            <option key={served.shape} value={served.shape}>
              {served.year}
              {served.projection.direction !== "authored"
                ? ` (${served.revision})`
                : ""}
            </option>
          ))}
        </select>
      </label>
      <div className="min-h-0 flex-1">
        <Screen
          key={`${shape}-${locale}-${view}`}
          shape={shape}
          locale={locale}
          view={view}
        />
      </div>
    </div>
  );
}

const meta: Meta = {
  title: "Modelo/Supported years",
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;
type Story = StoryObj;

const one = (root: ParentNode, selector: string) => {
  const found = root.querySelector<HTMLElement>(selector);
  if (!found) throw new Error(`${selector} is not drawn`);
  return found;
};

/** Chooses `served`'s year and waits for its workspace. */
async function choose(canvasElement: HTMLElement, served: ServedYear) {
  const select = await waitFor(() => one(canvasElement, "[data-year-select]"), {
    timeout: 30_000,
  });
  await userEvent.selectOptions(select, served.shape);
  await waitFor(
    () => {
      if (!canvasElement.querySelector("[role=tablist]"))
        throw new Error("the workspace is not drawn yet");
    },
    { timeout: 30_000 },
  );
}

const digits = (text: string | null) => (text ?? "").replace(/\D/g, "");

export const EveryYearOffersWhatItServes: Story = {
  name: "Every supported year: the comparison is offered where its form says so, and answers as served",
  render: (_, { globals }) => (
    <ByYear locale={language(globals)} view="compare" />
  ),
  play: async ({ canvasElement, globals }) => {
    const locale = language(globals);
    const years = await servedYears(locale);
    expect(years.length).toBeGreaterThan(1);
    for (const served of years) {
      await choose(canvasElement, served);
      const form = served.form.form.form;
      const compare = translator(locale)("desktop.modelo.view.compare");
      const tab = [...canvasElement.querySelectorAll("[role=tab]")].find((t) =>
        t.textContent?.includes(compare),
      );
      expect(tab !== undefined).toBe(form.compares_taxation);
      if (!form.compares_taxation) continue;
      const ask = await waitFor(
        () => one(canvasElement, "[data-comparison-ask]"),
        { timeout: 30_000 },
      );
      await userEvent.click(ask);
      const filer = filerOf(served.shape);
      const answer = comparisons[`compare-100-0A-${filer}-${locale}`];
      if (answer) {
        const projection = await answer();
        const result = await waitFor(
          () => one(canvasElement, "[data-comparison-result]"),
          { timeout: 30_000 },
        );
        expect(
          digits(
            one(
              one(result, "[data-comparison-mode=joint]"),
              "[data-comparison-result-amount]",
            ).textContent,
          ),
        ).toBe(digits(projection.conjunta_resultado));
        expect(
          digits(
            one(
              one(result, "[data-comparison-mode=individual]"),
              "[data-comparison-result-amount]",
            ).textContent,
          ),
        ).toBe(digits(projection.individual_resultado));
        expect(result.closest("[data-taxation-comparison]")).not.toBeNull();
        continue;
      }
      const refusal = refusals[`refusal-compare-100-0A-${filer}-${locale}`];
      if (!refusal) throw new Error(`No comparison is stored for ${filer}`);
      const detail = await refusal();
      const token = String(
        detail.context.find((fact) => fact.key === "refusal")?.value,
      );
      const drawn = await waitFor(
        () => one(canvasElement, "[data-comparison-refusal]"),
        { timeout: 30_000 },
      );
      expect(drawn).toHaveAttribute("data-comparison-refusal", token);
    }
  },
};

export const EstimateOnlyWhereTheEditionAllowsIt: Story = {
  name: "Every supported year: the estimate from the quarters is offered only where the form is projectable",
  render: (_, { globals }) => (
    <ByYear locale={language(globals)} view="credits" />
  ),
  play: async ({ canvasElement, globals }) => {
    const years = await servedYears(language(globals));
    for (const served of years) {
      await choose(canvasElement, served);
      await waitFor(() => one(canvasElement, "[data-credit]"), {
        timeout: 30_000,
      });
      expect(canvasElement.querySelector("[data-estimate-ask]") !== null).toBe(
        served.form.form.form.projectable,
      );
      // No year offers a field to type a withholding credit into.
      expect(canvasElement.querySelector("input, textarea")).toBeNull();
    }
  },
};

export const ProjectedYear: Story = {
  name: "A year after the newest authored edition: the form is projected from that edition and says so",
  render: (_, { globals }) => <ByYear locale={language(globals)} view="form" />,
  play: async ({ canvasElement, globals }) => {
    const years = await servedYears(language(globals));
    const projected = years.filter(
      (served) => served.projection.direction !== "authored",
    );
    expect(projected.length).toBeGreaterThan(0);
    for (const served of projected) {
      await choose(canvasElement, served);
      // The registry carries the newest edition forward to it.
      expect(served.projection.direction).toBe("forward");
    }
  },
};

const NO_ANSWERS: Partial<Record<ModeloFormElection, string>> = {};

/** Each supported year's settlement offer, as the application served it. */
function Offers({ locale }: { locale: OutputLanguage }) {
  const [read, setRead] = useState<
    { state: string; offer: PublicModeloFormExportOffer }[] | null
  >(null);
  useEffect(() => {
    void (async () => {
      const found = Object.entries(offers).flatMap(([path, load]) => {
        const state = new RegExp(
          `settlement-100-0A-(y\\d+-[a-z]+)-${locale}\\.json$`,
        ).exec(path)?.[1];
        return state ? [{ state, load }] : [];
      });
      setRead(
        await Promise.all(
          found.map(async ({ state, load }) => ({
            state,
            offer: structuredClone(await load()),
          })),
        ),
      );
    })();
  }, [locale]);
  if (!read) return null;
  return (
    <div className="@container flex max-w-3xl flex-col gap-6 p-6">
      {read.map(({ state, offer }) => (
        <section key={state} data-year-settlement={state}>
          <Settlement
            questions={offer.elections}
            answers={NO_ANSWERS}
            onAnswer={() => undefined}
          />
        </section>
      ))}
    </div>
  );
}

export const SettlementOfEachYear: Story = {
  name: "Every supported year: the result's settlement is offered as that year's design allows",
  render: (_, { globals }) => <Offers locale={language(globals)} />,
  play: async ({ canvasElement }) => {
    const sections = await waitFor(
      () => {
        const found = canvasElement.querySelectorAll("[data-year-settlement]");
        if (found.length === 0) throw new Error("no settlement is drawn yet");
        return found;
      },
      { timeout: 30_000 },
    );
    for (const section of sections)
      expect(section.querySelector("[data-settlement]")).not.toBeNull();
  },
};
