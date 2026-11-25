import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, within } from "storybook/test";
import { ModeloEnvelope } from "@/dev/ModeloEnvelope";
import { Tabs, TabsList } from "@/components/ui/tabs";
import { storyLanguage } from "../details/Details.stories";
import { PageTab, type PageTabPage } from "./PageTab";

// The tabs of a form's pages, drawn from the headings the application served.
// A Modelo 100 read serves words for every page; a page the application could
// name only by its registry path serves that path with the disclosure
// `technical`, which no scenario world serves today, so that case is drawn
// from served heading objects that carry no tax facts. The window words
// nothing of its own: a tab reads exactly what was served, and a path is
// drawn as the key it is.

function Tabbed({ pages }: { pages: PageTabPage[] }) {
  return (
    <div data-served={JSON.stringify(pages.map((page) => page.heading))}>
      <Tabs value={pages[0]?.id} className="p-4">
        <TabsList aria-label="pages" className="overflow-x-auto">
          {pages.map((page) => (
            <PageTab key={page.id} page={page} panel="panel" />
          ))}
        </TabsList>
      </Tabs>
    </div>
  );
}

function Pages({ name }: { name: string }) {
  return (
    <ModeloEnvelope name={name}>
      {(read) => <Tabbed pages={read.form.form.pages} />}
    </ModeloEnvelope>
  );
}

/** Every tab reads what its page served, and is drawn as a key only where the
 * page served one; `technical` says whether some page here served a key. */
const readsWhatWasServed =
  (technical: boolean): Story["play"] =>
  async ({ canvasElement }) => {
    const tabs = await within(canvasElement).findAllByRole("tab");
    const served = JSON.parse(
      canvasElement
        .querySelector("[data-served]")!
        .getAttribute("data-served")!,
    ) as { text: string; disclosure: string }[];
    await expect(tabs.length).toBe(served.length);
    await expect(tabs.length).toBeGreaterThan(1);
    await expect(served.some((h) => h.disclosure === "technical")).toBe(
      technical,
    );
    for (const [index, tab] of tabs.entries()) {
      const heading = served[index]!;
      await expect(tab.getAttribute("data-heading-disclosure")).toBe(
        heading.disclosure,
      );
      const key = tab.querySelector("[data-key]");
      if (heading.disclosure === "technical") {
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
  play: readsWhatWasServed(false),
};

export const ServedKeyOnly: Story = {
  name: "a page served with only its registry path, beside one in words",
  render: () => (
    <Tabbed
      pages={[
        {
          id: "page-key",
          heading: { text: "page-key", disclosure: "technical" },
          applies: true,
          counts: null,
        },
        {
          id: "page-words",
          heading: { text: "Served words", disclosure: "localized" },
          applies: true,
          counts: null,
        },
      ]}
    />
  ),
  play: readsWhatWasServed(true),
};
