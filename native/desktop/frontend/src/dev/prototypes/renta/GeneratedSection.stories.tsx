import type { Meta, StoryObj } from "@storybook/react-vite";
import { useMemo, useState } from "react";
import { FormView } from "@/components/modelo/form/FormView";
import { useFormSession } from "@/components/modelo/form/session";
import type { ModeloWorkbenchFormProjectionV1 } from "@/shell/modeloContract";
import { withSections, type Language } from "./fixtures";
import { prototypePort } from "./rentaPort";
import { languageOf, useFixture } from "./useFixture";

// One section of the 2025 Modelo 100 drawn by the real generated form view,
// unchanged: the form knows no modelo, it draws what the read holds.

function Loaded({
  envelope,
  language,
}: {
  envelope: ModeloWorkbenchFormProjectionV1;
  language: Language;
}) {
  const port = useMemo(() => prototypePort(envelope), [envelope]);
  const session = useFormSession({ envelope, port, language });
  const [details, setDetails] = useState(false);
  return (
    <div className="flex h-full min-h-0 flex-col bg-background">
      <FormView
        envelope={envelope}
        session={session}
        detailsOpen={details}
        onDetailsOpenChange={setDetails}
      />
    </div>
  );
}

function Drawn({ language, section }: { language: Language; section: string }) {
  const form = useFixture("form", language);
  const envelope = useMemo(
    () => (form ? withSections(form, [section]) : null),
    [form, section],
  );
  if (!envelope) return null;
  return (
    <Loaded
      key={`${language}-${section}`}
      envelope={envelope}
      language={language}
    />
  );
}

const meta: Meta = {
  title: "Prototypes/Renta/Generated section",
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;
type Story = StoryObj;

export const Employment: Story = {
  name: "Employment income",
  render: (_, { globals }) => (
    <Drawn
      language={languageOf(globals)}
      section="datoseconomicos-resultados.rdtotrabajores"
    />
  ),
};

export const DirectEstimation: Story = {
  name: "Direct estimation activity, boxes that could not be calculated",
  render: (_, { globals }) => (
    <Drawn
      language={languageOf(globals)}
      section="datoseconomicos-tomadatosampliada.regestimadirecta"
    />
  ),
};

export const Liability: Story = {
  name: "Liability and payments on account",
  render: (_, { globals }) => (
    <Drawn
      language={languageOf(globals)}
      section="datoseconomicos-resultados.calculoimpuestores-4"
    />
  ),
};
