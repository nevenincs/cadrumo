import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, within } from "storybook/test";
import { ModeloEnvelope } from "@/dev/ModeloEnvelope";
import { Tabs, TabsList } from "@/components/ui/tabs";
import { storyLanguage } from "../details/Details.stories";
import { PageTab } from "./PageTab";

// The tabs of a form's pages, drawn from the headings the application served
// for the pages of two Modelo 100 reads: the 2025 edition, which serves words
// for every page, and the 2024 edition, which serves only each page's
// registry path with the disclosure `technical`. The window words nothing of
// its own: a tab reads exactly what was served, and a path is drawn as the
// key it is.

function Pages({ name }: { name: string }) {
  return (
    <ModeloEnvelope name={name}>
      {(read) => (
        <div
          data-served={JSON.stringify(
            read.form.form.pages.map((page) => page.heading),
          )}
        >
          <Tabs value={read.form.form.pages[0]?.id} className="p-4">
            <TabsList aria-label="pages" className="overflow-x-auto">
              {read.form.form.pages.map((page) => (
                <PageTab key={page.id} page={page} panel="panel" />
              ))}
            </TabsList>
          </Tabs>
        </div>
      )}
    </ModeloEnvelope>
  );
}

/** Every tab reads what its page served, and is drawn as a key only where the
 * page served one. */
const readsWhatWasServed =
  (kind: "words" | "technical"): Story["play"] =>
  async ({ canvasElement }) => {
    const tabs = await within(canvasElement).findAllByRole("tab");
    const served = JSON.parse(
      canvasElement
        .querySelector("[data-served]")!
        .getAttribute("data-served")!,
    ) as { text: string; disclosure: string }[];
    await expect(tabs.length).toBe(served.length);
    await expect(tabs.length).toBeGreaterThan(1);
    for (const [index, tab] of tabs.entries()) {
      const heading = served[index]!;
      await expect(heading.disclosure === "technical").toBe(
        kind === "technical",
      );
      await expect(tab.getAttribute("data-heading-disclosure")).toBe(
        heading.disclosure,
      );
      const key = tab.querySelector("[data-key]");
      if (kind === "technical") {
        await expect(key?.getAttribute("data-key")).toBe(heading.text);
        await expect(tab.textContent).toBe(heading.text);
      } else {
        await expect(key).toBeNull();
        await expect(tab.textContent?.toLowerCase()).toBe(
          heading.text.toLowerCase(),
        );
      }
    }
  };

const meta: Meta = {
  title: "Modelo/Form/Page tab",
  parameters: { layout: "padded" },
};
export default meta;
type Story = StoryObj;

export const ServedWords: Story = {
  name: "100 · pages served with words",
  render: (_, { globals }) => (
    <Pages name={`modelo-100-0A-${storyLanguage(globals.locale)}`} />
  ),
  play: readsWhatWasServed("words"),
};

export const ServedKeyOnly: Story = {
  name: "100 · pages served with only their registry path",
  render: (_, { globals }) => (
    <Pages name={`modelo-100-0A-y2024-${storyLanguage(globals.locale)}`} />
  ),
  play: readsWhatWasServed("technical"),
};
