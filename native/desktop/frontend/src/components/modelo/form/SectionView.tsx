import { useEffect, useRef, useState, type ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { Icon } from "@/components/ui/icon";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type {
  ModeloFormCounts,
  ModeloFormText,
  PublicModeloFormBlock,
  PublicModeloFormContextFieldBlock,
  PublicModeloFormField,
} from "../../../shell/modeloContract";
import { factsGap } from "../../../shell/compose";
import { useStrings, type Translate } from "../../../shell/strings";
import { calm, FieldRow } from "./FieldRow";
import { useForm } from "./formContext";
import { GridBlock } from "./GridBlock";
import { ContextSummary, RepeatingBlock } from "./RecordsBlock";
import { editsAdmitted, fieldKey } from "./session";

/** A section as the form draws it: an official one, or the boxes not yet
 * placed and the working figures, which the read lists apart. */
export type DrawnSection = {
  id: string;
  heading: ModeloFormText;
  official_heading: string | null;
  blocks: PublicModeloFormBlock[];
  counts: ModeloFormCounts | null;
};

/** Which boxes a filter or a search keeps, or null when it keeps all. */
export type Shown = ReadonlySet<string> | null;

const keeps = (shown: Shown, field: PublicModeloFormField) =>
  shown === null || shown.has(fieldKey(field));

/** Rows of boxes drawn one after another, as one grid. */
function Rows({
  label,
  fields,
}: {
  label: string;
  fields: PublicModeloFormField[];
}) {
  return (
    <div role="grid" aria-label={label} className="flex flex-col gap-0.5">
      <div role="rowgroup" className="contents">
        {fields.map((field) => (
          <FieldRow key={fieldKey(field)} field={field} />
        ))}
      </div>
    </div>
  );
}

/** The blocks a section draws under a filter, or null when it keeps
 * none. */
function sectionBody(
  t: Translate,
  section: DrawnSection,
  shown: Shown,
): ReactNode[] | null {
  const out: ReactNode[] = [];
  let context: PublicModeloFormContextFieldBlock[] = [];
  let fields: PublicModeloFormField[] = [];
  const label = section.heading.text;
  const flush = () => {
    if (context.length && shown === null)
      out.push(
        <ContextSummary key={`context-${out.length}`} items={context} />,
      );
    if (fields.length)
      out.push(
        <Rows key={`rows-${out.length}`} label={label} fields={fields} />,
      );
    context = [];
    fields = [];
  };
  for (const block of section.blocks) {
    switch (block.kind) {
      case "context_field":
        if (fields.length) flush();
        context.push(block);
        break;
      case "field":
        if (context.length) flush();
        if (keeps(shown, block.field)) fields.push(block.field);
        break;
      case "grid": {
        flush();
        const any = block.rows.some((row) =>
          row.cells.some((cell) => cell.field && keeps(shown, cell.field)),
        );
        if (any) out.push(<GridBlock key={block.id} block={block} />);
        break;
      }
      case "repeating":
        flush();
        if (shown === null)
          out.push(<RepeatingBlock key={block.id} block={block} />);
        break;
      case "binding_inputs": {
        flush();
        const kept = block.fields.filter((field) => keeps(shown, field));
        if (kept.length)
          out.push(
            <div
              key={block.id}
              className="flex flex-col gap-0.5 rounded-lg border border-dashed border-border p-1"
            >
              <span className="px-2 pt-1 text-sm text-muted-foreground">
                {t("workspace.modelo.page.working_figures")}
              </span>
              <Rows
                label={t("workspace.modelo.page.working_figures")}
                fields={kept}
              />
            </div>,
          );
        break;
      }
    }
  }
  flush();
  return out.length ? out : null;
}

/** An estimate of a section's height before it is drawn, so the page
 * scrolls to the right place while far sections wait. */
const estimate = (section: DrawnSection) =>
  section.blocks.reduce(
    (height, block) =>
      height +
      (block.kind === "grid"
        ? 48 + block.rows.length * 48
        : block.kind === "repeating"
          ? 160
          : block.kind === "binding_inputs"
            ? 40 + block.fields.length * 48
            : 46),
    56,
  );

export function SectionView({
  section,
  shown,
  forced,
}: {
  section: DrawnSection;
  shown: Shown;
  /** Drawn whether or not it is near the view, for the chosen box. */
  forced: boolean;
}) {
  const t = useStrings();
  const { envelope, translated } = useForm();
  const ref = useRef<HTMLElement>(null);
  const [near, setNear] = useState(false);
  useEffect(() => {
    const element = ref.current;
    if (!element || near) return;
    if (typeof IntersectionObserver === "undefined") return void setNear(true);
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) setNear(true);
      },
      { rootMargin: "1200px 0px" },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [near]);
  const drawn = near || forced;
  const body = drawn ? sectionBody(t, section, shown) : null;
  if (drawn && !body) return null;
  const counts = section.counts;
  const todo = counts ? counts.needs_input + counts.blocked : 0;
  const official =
    translated &&
    section.official_heading &&
    section.official_heading !== section.heading.text
      ? section.official_heading
      : null;
  const uncalculated =
    envelope.form.form.calculation_revision_id === null &&
    editsAdmitted(envelope) &&
    section.blocks.some((block) => block.kind === "grid");
  return (
    <section
      ref={ref}
      id={`section-${section.id}`}
      aria-label={section.heading.text}
      className="scroll-mt-4"
      style={drawn ? undefined : { minHeight: estimate(section) }}
    >
      <header className="mb-1 flex items-center gap-2 border-b border-border px-2 pb-2">
        <h2 className="font-serif text-md text-foreground">
          {calm(section.heading.text)}
        </h2>
        {official && (
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                className="text-faint hover:text-muted-foreground"
                aria-label={t("workspace.modelo.disclosure.official_spanish")}
              >
                <Icon name="info" size="xs" />
              </button>
            </TooltipTrigger>
            <TooltipContent className="max-w-sm">{official}</TooltipContent>
          </Tooltip>
        )}
        {uncalculated && (
          <span className="text-sm text-faint">
            {factsGap(t).trimStart()}
            {t("workspace.modelo.legend.meaning.origin.not_calculated_yet")}
          </span>
        )}
        {todo > 0 && (
          <Tooltip>
            <TooltipTrigger asChild>
              <Badge
                variant="warning"
                className="ml-auto"
                tabIndex={0}
                aria-label={t("workspace.modelo.section.pending", {
                  heading: section.heading.text,
                  count: todo,
                })}
              >
                <Icon name="alert" size="xs" />
                {todo}
              </Badge>
            </TooltipTrigger>
            <TooltipContent>
              {t("workspace.modelo.section.pending", {
                heading: section.heading.text,
                count: todo,
              })}
            </TooltipContent>
          </Tooltip>
        )}
      </header>
      {body && <div className="flex flex-col gap-2">{body}</div>}
    </section>
  );
}
