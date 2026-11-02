import { useMemo, useState } from "react";
import { FormView } from "@/components/modelo/form/FormView";
import { useFormSession } from "@/components/modelo/form/session";
import { AttentionMark } from "@/components/modelo/workspace/Marks";
import type {
  ModeloFormResultView,
  ModeloWorkbenchFormProjectionV1,
  OutputLanguage,
} from "@/shell/modeloContract";
import { useStrings } from "@/shell/strings";
import { withSections, type Outline as OutlineData } from "./fixtures";
import { Outline, type OutlineMode } from "./Outline";
import { prototypePort } from "./rentaPort";

// The Renta workspace: a section navigator over the one generated form, the
// served header above it, and the real form view drawing the chosen
// section. The fixture holds a few sections of the declaration; choosing
// another says so instead of drawing anything in its place.

function Section({
  envelope,
  language,
}: {
  envelope: ModeloWorkbenchFormProjectionV1;
  language: OutputLanguage;
}) {
  const port = useMemo(() => prototypePort(envelope), [envelope]);
  const session = useFormSession({ envelope, port, language });
  const [details, setDetails] = useState(false);
  return (
    <FormView
      envelope={envelope}
      session={session}
      detailsOpen={details}
      onDetailsOpenChange={setDetails}
    />
  );
}

export function RentaWorkspace({
  envelope,
  outline,
  result,
  language,
  initialMode = "proposed",
  initialSection,
}: {
  envelope: ModeloWorkbenchFormProjectionV1;
  outline: OutlineData;
  result: ModeloFormResultView;
  language: OutputLanguage;
  initialMode?: OutlineMode;
  initialSection: string;
}) {
  const t = useStrings();
  const [mode, setMode] = useState<OutlineMode>(initialMode);
  const [selected, setSelected] = useState(initialSection);
  const [onlyAttention, setOnlyAttention] = useState(false);
  const held = useMemo(
    () =>
      new Set(
        envelope.form.form.pages.flatMap((page) =>
          page.sections.map((section) => section.id),
        ),
      ),
    [envelope],
  );
  const shown = useMemo(
    () => (held.has(selected) ? withSections(envelope, [selected]) : null),
    [envelope, held, selected],
  );
  return (
    <div className="flex h-full min-h-0 flex-col bg-background">
      <header className="flex items-center gap-3 border-b border-border px-4 py-2">
        <span
          data-state={result.state}
          className="text-base font-semibold"
          title={result.help.join(" ")}
        >
          {result.short_text}
        </span>
        <span className="flex items-center gap-1.5">
          {envelope.header?.attention.map((entry) => (
            <AttentionMark key={entry.level} entry={entry} />
          ))}
        </span>
      </header>
      <div className="flex min-h-0 flex-1">
        <Outline
          outline={outline}
          mode={mode}
          onModeChange={setMode}
          selected={selected}
          onSelect={setSelected}
          onlyAttention={onlyAttention}
          onOnlyAttentionChange={setOnlyAttention}
        />
        <main className="flex min-h-0 min-w-0 flex-1 flex-col">
          {shown ? (
            <Section key={selected} envelope={shown} language={language} />
          ) : (
            <p className="p-4 text-sm text-muted-foreground">
              {t("desktop.renta.proto.excerpt")}
            </p>
          )}
        </main>
      </div>
    </div>
  );
}
