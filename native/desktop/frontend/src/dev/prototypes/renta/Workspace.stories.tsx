import type { Meta, StoryObj } from "@storybook/react-vite";
import type { Language } from "./fixtures";
import type { OutlineMode } from "./Outline";
import { RentaWorkspace } from "./RentaWorkspace";
import { languageOf, useFixture } from "./useFixture";

// The Renta workspace shell over the 2025 Modelo 100 as the application
// serves it today: one generated form, a navigator over its pages and
// sections, and the served header. See `fixtures.ts` for how each fixture
// was read.

function Shell({
  language,
  mode,
  section,
}: {
  language: Language;
  mode: OutlineMode;
  section: string;
}) {
  const form = useFixture("form", language);
  const outline = useFixture("outline", language);
  const result = useFixture("result", language);
  if (!form || !outline || !result) return null;
  return (
    <RentaWorkspace
      key={`${language}-${mode}`}
      envelope={form}
      outline={outline}
      result={result.failed.header}
      language={language}
      initialMode={mode}
      initialSection={section}
    />
  );
}

const meta: Meta = {
  title: "Prototypes/Renta/Workspace",
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;
type Story = StoryObj;

export const ProposedOutline: Story = {
  name: "Proposed outline, activity section open",
  render: (_, { globals }) => (
    <Shell
      language={languageOf(globals)}
      mode="proposed"
      section="datoseconomicos-tomadatosampliada.regestimadirecta"
    />
  ),
};

export const ServedOutline: Story = {
  name: "Sections as served today, technical headings disclosed",
  render: (_, { globals }) => (
    <Shell
      language={languageOf(globals)}
      mode="served"
      section="datoseconomicos-resultados.rdtotrabajores"
    />
  ),
};

export const OutsideExcerpt: Story = {
  name: "A section the excerpt does not hold",
  render: (_, { globals }) => (
    <Shell
      language={languageOf(globals)}
      mode="proposed"
      section="datoseconomicos.general"
    />
  ),
};
