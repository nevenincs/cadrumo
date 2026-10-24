import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { BoxNumber, valueWords, type Staged } from "./FormView";
import type { FormField, ModeloForm } from "./types";
import {
  calm,
  citation,
  editing,
  FAMILY_ICON,
  familyWords,
  originWords,
  SURFACE_WORD,
  TONE_TEXT,
} from "./vocabulary";
import { w } from "./words";

// Everything about one box, in the order a filer asks: what it holds, where
// that came from, how it is worked out, what it means and what the law says.
// It explains; changing a value happens on the form itself.

function Part({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <h4 className="text-sm font-medium text-muted-foreground">{title}</h4>
      {children}
    </div>
  );
}

/** With nothing chosen: where the declaration stands, by the form's counts. */
function Summary({ form }: { form: ModeloForm }) {
  const c = form.counts;
  const lines: [string, number][] = [
    ["Brought in from your data", c.imported],
    ["Worked out from other boxes", c.calculated],
    ["Entered by you", c.entered + c.overridden],
    ["Need you", c.needs_input + c.default_to_confirm],
    ["Could not be worked out", c.blocked],
  ];
  return (
    <div className="flex flex-col gap-4 p-5">
      <h3 className="font-serif text-md">This declaration</h3>
      {form.calculation_revision_id ? (
        <dl className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-1.5 text-base">
          {lines.map(([word, n]) => (
            <div key={word} className="contents">
              <dt className="text-muted-foreground">{word}</dt>
              <dd className="text-right tabular-nums">{n}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="text-base text-muted-foreground">
          Not calculated yet: the boxes fill in when it is.
        </p>
      )}
      <p className="text-sm text-muted-foreground">
        Choose a box to see where its value comes from and what it means.
      </p>
    </div>
  );
}

export function Inspector({
  form,
  field,
  locale,
  staged,
  onRevert,
  onRestore,
  onJump,
  operand,
  onClose,
}: {
  form: ModeloForm;
  field: FormField | null;
  locale: string;
  staged: Staged[string] | undefined;
  onRevert: () => void;
  onRestore: () => void;
  onJump: (casillaId: string) => void;
  operand: (casillaId: string) => FormField | null;
  onClose?: () => void;
}) {
  if (!field) return <Summary form={form} />;
  const o = originWords(field, locale);
  const { editable, why } = editing(field, locale);
  const failed = field.origin === "calculation_failed" && !staged;
  const words = failed
    ? { text: "—", tone: "text-faint" }
    : valueWords(field, locale, staged, !form.calculation_revision_id);
  const family = field.source?.family;
  const surface = field.bindings[0]?.policy.surface;
  const missing = field.formula_operands.filter((id) => !operand(id));
  return (
    <div className="flex flex-col gap-5 p-5">
      <div className="flex flex-col items-start gap-2">
        <div className="flex w-full items-center">
          <BoxNumber box={field.box} />
          {onClose && (
            <IconButton
              label="Close details"
              size="xs"
              className="ml-auto @6xl:hidden"
              onClick={onClose}
            >
              <Icon name="close" />
            </IconButton>
          )}
        </div>
        <h3 className="font-serif text-lg leading-snug">
          {calm(field.label.text)}
        </h3>
      </div>

      <div className="flex flex-col gap-1.5 rounded-lg bg-muted p-4">
        <span
          className={cn("text-lg tabular-nums", words.tone || "text-faint")}
        >
          {words.text || "—"}
        </span>
        {staged ? (
          <span className="text-sm text-muted-foreground">
            {w("workspace.modelo.legend.meaning.mark.staged", locale)}{" "}
            {w("workspace.modelo.was", locale, {
              value: staged.was || "—",
            })}
          </span>
        ) : (
          <span
            className={cn(
              "flex items-start gap-1.5 text-sm",
              TONE_TEXT[o.tone],
            )}
          >
            <Icon name={o.icon} size="xs" className="mt-0.5" />
            <span>
              {o.word === o.sentence
                ? o.word
                : `${o.word}. ${o.sentence}`.replace(
                    /\.\s*([^.]*)\.\s*\1/,
                    ". $1",
                  )}
            </span>
          </span>
        )}
        {!editable && !failed && field.origin !== "calculated" && (
          <span className="flex items-start gap-1.5 text-sm text-muted-foreground">
            <Icon name="lock" size="xs" className="mt-0.5" />
            {why}
          </span>
        )}
        {(staged || field.origin === "overrides_source") && (
          <div className="mt-1 flex gap-2">
            {staged && (
              <Button size="sm" variant="ghost" onClick={onRevert}>
                <Icon name="reset" size="xs" />
                Undo
              </Button>
            )}
            {field.origin === "overrides_source" && !staged && (
              <Button size="sm" variant="ghost" onClick={onRestore}>
                <Icon name="restore" size="xs" />
                {w("workspace.modelo.review.effect.restore", locale)}
              </Button>
            )}
          </div>
        )}
      </div>

      {field.formula_operands.length > 0 && (
        <Part title="Worked out from">
          <ul className="flex flex-col">
            {field.formula_operands.map((id) => {
              const source = operand(id);
              if (!source) return null;
              const v = valueWords(source, locale);
              return (
                <li key={id}>
                  <button
                    type="button"
                    onClick={() => onJump(id)}
                    className="grid w-full grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2 rounded-md px-1.5 py-1 text-left hover:bg-accent"
                  >
                    <BoxNumber box={source.box} size="sm" />
                    <span className="truncate text-sm">
                      {calm(source.label.text)}
                    </span>
                    <span className={cn("text-sm tabular-nums", v.tone)}>
                      {v.text || "—"}
                    </span>
                  </button>
                </li>
              );
            })}
            {missing.length > 0 && (
              <li className="flex items-center gap-2 px-1.5 py-1 text-sm text-muted-foreground">
                <Icon name="info" size="xs" />
                {missing.length === 1
                  ? "It also uses a figure kept outside this form."
                  : `It also uses ${missing.length} figures kept outside this form.`}
              </li>
            )}
          </ul>
        </Part>
      )}

      {family && field.formula_operands.length === 0 && (
        <Part title="Where it comes from">
          <span className="flex items-center gap-2 text-base">
            <Icon
              name={FAMILY_ICON[family]}
              className="text-muted-foreground"
            />
            {familyWords(family, locale)}
          </span>
          {field.origin === "not_imported_yet" && (
            <span className="text-sm text-warning">
              {w(
                "workspace.modelo.legend.meaning.origin.not_imported_yet",
                locale,
              )}
            </span>
          )}
          {surface && SURFACE_WORD[surface] && (
            <Button size="sm" variant="link" className="self-start">
              {SURFACE_WORD[surface]}
              <Icon name="forward" size="xs" />
            </Button>
          )}
        </Part>
      )}

      <Part title="What it means">
        {field.help ? (
          <p className="text-base leading-relaxed">{field.help}</p>
        ) : (
          <p className="text-sm text-muted-foreground">
            {w("workspace.modelo.help.no_explanation", locale)}
          </p>
        )}
      </Part>

      {field.legal_refs.length > 0 && (
        <Part title="Legal basis">
          <ul className="flex flex-col gap-0.5">
            {field.legal_refs.map((ref) => (
              <li key={ref}>
                <button
                  type="button"
                  className="text-sm text-foreground underline decoration-border-strong underline-offset-4 hover:decoration-foreground"
                >
                  {citation(ref)}
                </button>
              </li>
            ))}
          </ul>
        </Part>
      )}
    </div>
  );
}
