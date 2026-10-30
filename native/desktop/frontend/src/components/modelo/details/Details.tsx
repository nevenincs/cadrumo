import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { Spinner } from "@/components/ui/spinner";
import { listed } from "../../../shell/compose";
import type { ModeloPort } from "../../../shell/modelo";
import type {
  ModeloCasillaHelpCardV1,
  ModeloFormCounts,
  ModeloWorkbenchFormProjectionV1,
  OutputLanguage,
  PublicModeloFormField,
  SourceSurface,
} from "../../../shell/modeloContract";
import { useStrings, type Translate } from "../../../shell/strings";
import { BoxNumber } from "../form/BoxNumber";
import {
  editableHere,
  editKey,
  editsAdmitted,
  restoreIntent,
  type FormSession,
  type StagedEdit,
} from "../form/session";
import { stagedText } from "../form/stagedWords";
import { useHelpCard, type HelpCardRead } from "./useHelpCard";

// Everything about one box, in the order a filer asks: what it holds, where
// that came from, how it is worked out, what it means and what the law says.
// Every word and figure is the read model's or its help card's; the panel
// explains, and changing a value happens on the form itself.

/** The surfaces that keep a figure and can be opened from here. */
export type OpenableSurface = Exclude<SourceSurface, "none">;

function Part({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-1.5" aria-label={title}>
      <h4 className="text-sm font-medium text-muted-foreground">{title}</h4>
      {children}
    </section>
  );
}

/** The form's counts, each under its own name, in the order a filer reads
 * them. */
const SUMMARY: [string, (c: ModeloFormCounts) => number][] = [
  ["workspace.modelo.summary.imported", (c) => c.imported],
  ["workspace.modelo.summary.calculated", (c) => c.calculated],
  ["workspace.modelo.summary.entered", (c) => c.entered + c.overridden],
  [
    "workspace.modelo.summary.needs_you",
    (c) => c.needs_input + c.default_to_confirm,
  ],
  ["workspace.modelo.summary.blocked", (c) => c.blocked],
];

/** With nothing chosen: where the declaration stands, by the form's counts. */
function Summary({ envelope }: { envelope: ModeloWorkbenchFormProjectionV1 }) {
  const t = useStrings();
  const form = envelope.form.form;
  return (
    <div className="flex flex-col gap-4 p-5">
      <h3 className="font-serif text-md">
        {t("workspace.modelo.summary.title")}
      </h3>
      {form.calculation_revision_id ? (
        <dl className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-1.5 text-base">
          {SUMMARY.map(([key, count]) => (
            <div key={key} className="contents">
              <dt className="text-muted-foreground">{t(key)}</dt>
              <dd className="text-right tabular-nums">{count(form.counts)}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="text-base text-muted-foreground">
          {t("workspace.modelo.summary.not_calculated")}
        </p>
      )}
      <p className="text-sm text-muted-foreground">
        {t("workspace.modelo.details.choose_box")}
      </p>
    </div>
  );
}

/** The value the box holds, or its staged change with what it was. */
function ValueCard({
  field,
  editable,
  staged,
  onUndo,
  onRestore,
}: {
  field: PublicModeloFormField;
  editable: boolean;
  staged: StagedEdit | undefined;
  onUndo: () => void;
  onRestore: (() => void) | null;
}) {
  const t = useStrings();
  const shown = staged ? stagedText(t, staged) : field.value_text;
  return (
    <div className="flex flex-col gap-1.5 rounded-lg bg-muted p-4">
      <span
        className={cn(
          "text-lg tabular-nums",
          shown === null ? "text-faint" : "text-foreground",
        )}
      >
        {shown ?? "—"}
      </span>
      {staged ? (
        <span className="text-sm text-muted-foreground">
          {t("workspace.modelo.legend.meaning.mark.staged")}{" "}
          {t("workspace.modelo.was", {
            value: staged.field.value_text ?? "—",
          })}
        </span>
      ) : (
        (field.origin_words || field.origin_explanation) && (
          <span className="flex flex-col gap-0.5 text-sm">
            {field.origin_words && <span>{field.origin_words}</span>}
            {field.origin_explanation && (
              <span className="text-muted-foreground">
                {field.origin_explanation}
              </span>
            )}
          </span>
        )
      )}
      {field.editability_words && !editable && (
        <span className="flex items-start gap-1.5 text-sm text-muted-foreground">
          <Icon name="lock" size="xs" className="mt-0.5" />
          {field.editability_words}
        </span>
      )}
      {(staged || onRestore) && (
        <div className="mt-1 flex gap-2">
          {staged ? (
            <Button size="sm" variant="ghost" onClick={onUndo}>
              <Icon name="reset" size="xs" />
              {t("workspace.modelo.details.undo")}
            </Button>
          ) : (
            onRestore && (
              <Button size="sm" variant="ghost" onClick={onRestore}>
                <Icon name="restore" size="xs" />
                {t("workspace.modelo.review.effect.restore")}
              </Button>
            )
          )}
        </div>
      )}
    </div>
  );
}

/** A box another part of the card names, chosen on the form when pressed. */
function BoxLink({
  box,
  label,
  onPick,
}: {
  box: string;
  label: string;
  onPick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onPick}
      aria-label={label}
      className="rounded-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
    >
      <BoxNumber box={box} size="sm" />
    </button>
  );
}

/** A public address the card cites, opened in the system browser. */
function Citation({
  text,
  url,
  openLink,
}: {
  text: string;
  url: string;
  openLink: (url: string) => void;
}) {
  return (
    <Button
      variant="link"
      size="xs"
      className="h-auto justify-start p-0 text-left text-sm whitespace-normal"
      onClick={() => openLink(url)}
    >
      {text}
      <Icon name="link" size="xs" />
    </Button>
  );
}

function CardParts({
  card,
  session,
  openLink,
  onOpenSurface,
  canOpenSurface,
}: {
  card: ModeloCasillaHelpCardV1;
  session: FormSession;
  openLink: (url: string) => void;
  onOpenSurface?: (surface: OpenableSurface) => void;
  canOpenSurface?: (surface: OpenableSurface) => boolean;
}) {
  const t = useStrings();
  const goTo = (box: string) =>
    t("workspace.modelo.sources.go_to_box", { box });
  const reach = card.reach;
  const outside = card.outside_figures;
  return (
    <>
      {card.is_result && (
        <p className="text-sm text-muted-foreground">
          {t("workspace.modelo.details.is_result")}
        </p>
      )}
      {card.formula && (
        <Part title={t("workspace.modelo.details.worked_out_from")}>
          <p className="font-mono text-sm">{card.formula.text}</p>
          {card.formula.values_text && (
            <p className="font-mono text-sm text-muted-foreground tabular-nums">
              {card.formula.values_text}
            </p>
          )}
          {!card.formula.complete && (
            <p className="text-sm text-muted-foreground">
              {t("workspace.modelo.details.formula_incomplete")}
            </p>
          )}
          {outside.length > 0 && (
            <div className="flex flex-col gap-1">
              <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
                <Icon name="info" size="xs" />
                {outside.length === 1
                  ? t("workspace.modelo.details.uses_outside_one")
                  : t("workspace.modelo.details.uses_outside_many", {
                      count: outside.length,
                    })}
              </span>
              <ul className="flex flex-col gap-0.5 pl-5">
                {outside.map((figure, i) => (
                  <li
                    key={`${figure.casilla_id ?? figure.binding_id ?? ""}-${i}`}
                    className="flex flex-wrap items-center gap-x-2 text-sm"
                  >
                    <span>{figure.label}</span>
                    {figure.surface !== "none" &&
                      onOpenSurface &&
                      canOpenSurface?.(figure.surface) === true && (
                        <Button
                          size="xs"
                          variant="link"
                          className="h-auto p-0"
                          onClick={() =>
                            onOpenSurface(figure.surface as OpenableSurface)
                          }
                        >
                          {t(`workspace.modelo.surface.open.${figure.surface}`)}
                          <Icon name="forward" size="xs" />
                        </Button>
                      )}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Part>
      )}
      {card.origins.length > 0 && (
        <Part title={t("workspace.modelo.editor.block.where_from")}>
          <ul className="flex flex-col gap-0.5 text-base">
            {card.origins.map((origin, i) => (
              <li key={i}>{origin}</li>
            ))}
          </ul>
        </Part>
      )}
      {card.constraints.length > 0 && (
        <Part title={t("workspace.modelo.details.constraints")}>
          <ul className="flex flex-col gap-0.5 text-base">
            {card.constraints.map((constraint, i) => (
              <li key={i}>{constraint}</li>
            ))}
          </ul>
        </Part>
      )}
      {(card.feeds.length > 0 ||
        (reach && reach.path.length + reach.others.length > 0)) && (
        <Part title={t("workspace.modelo.details.reach")}>
          {card.feeds.length > 0 && (
            <p className="text-sm">
              {t("workspace.modelo.help.feeds", {
                boxes: listed(t, card.feeds),
              })}
            </p>
          )}
          {reach && reach.path.length > 0 && (
            <div className="flex flex-wrap items-center gap-1">
              {reach.path.map((step, i) => (
                <span key={step.casilla_id} className="flex items-center gap-1">
                  {i > 0 && (
                    <Icon name="forward" size="xs" className="text-faint" />
                  )}
                  <BoxLink
                    box={step.box}
                    label={goTo(step.box)}
                    onPick={() => session.selectCasilla(step.casilla_id)}
                  />
                </span>
              ))}
            </div>
          )}
          {reach && reach.others.length > 0 && (
            <div className="flex flex-wrap items-center gap-1">
              <span className="text-sm text-muted-foreground">
                {t("workspace.modelo.details.reach_others")}
              </span>
              {reach.others.map((other) => (
                <BoxLink
                  key={other.casilla_id}
                  box={other.box}
                  label={goTo(other.box)}
                  onPick={() => session.selectCasilla(other.casilla_id)}
                />
              ))}
            </div>
          )}
        </Part>
      )}
      {card.quotes.length > 0 && (
        <Part title={t("workspace.modelo.details.official_text")}>
          <ul className="flex flex-col gap-3">
            {card.quotes.map((quote, i) => (
              <li key={i} className="flex flex-col gap-1">
                <blockquote className="border-l-2 border-border-strong pl-3 text-base leading-relaxed">
                  {quote.fragments.join(" … ")}
                </blockquote>
                <span className="flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
                  <Citation
                    text={quote.source}
                    url={quote.source_url}
                    openLink={openLink}
                  />
                  <span>
                    {t("workspace.modelo.details.retrieved", {
                      date: quote.retrieved_at,
                    })}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </Part>
      )}
      {card.legal_basis.length > 0 && (
        <Part title={t("workspace.modelo.details.legal_basis")}>
          <ul className="flex flex-col gap-0.5">
            {card.legal_basis.map((citation) => (
              <li key={citation.permalink}>
                <Citation
                  text={citation.text}
                  url={citation.permalink}
                  openLink={openLink}
                />
              </li>
            ))}
          </ul>
        </Part>
      )}
    </>
  );
}

function CardState({ read, t }: { read: HelpCardRead; t: Translate }) {
  if (read.kind === "reading")
    return (
      <span className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner />
        {t("workspace.modelo.details.reading")}
      </span>
    );
  if (read.kind === "failed")
    return (
      <span className="flex items-center gap-2 text-sm text-muted-foreground">
        <Icon name="unknown" size="xs" />
        {t("workspace.modelo.details.card_unavailable")}
      </span>
    );
  return null;
}

/**
 * The details of the box chosen on the form, or the declaration's counts
 * with nothing chosen. The workspace places it beside the form or docked
 * under it; `onClose` is offered only where it is docked.
 */
export function Details({
  envelope,
  port,
  language,
  session,
  openLink,
  onOpenSurface,
  canOpenSurface,
  onClose,
}: {
  envelope: ModeloWorkbenchFormProjectionV1;
  port: ModeloPort;
  language: OutputLanguage;
  session: FormSession;
  /** Opens a public address the card cites in the system browser. */
  openLink: (url: string) => void;
  /** Opens the surface that keeps a figure outside this form. */
  onOpenSurface?: (surface: OpenableSurface) => void;
  /** Whether the desktop can open a surface; a link is drawn only to one it
   * can. None is drawn without it. */
  canOpenSurface?: (surface: OpenableSurface) => boolean;
  onClose?: () => void;
}) {
  const t = useStrings();
  const field = session.selected;
  const casillaId =
    field?.address.kind === "casilla" ? field.address.casilla_id : null;
  const read = useHelpCard(port, envelope, casillaId, language);
  if (!field) return <Summary envelope={envelope} />;
  const key = editKey(field);
  const staged = session.staged.get(key);
  const restore = editsAdmitted(envelope) ? restoreIntent(field) : null;
  return (
    <div className="flex flex-col gap-5 p-5">
      <div className="flex flex-col items-start gap-2">
        <div className="flex w-full items-center">
          <BoxNumber box={field.box} />
          {onClose && (
            <IconButton
              label={t("desktop.modelo.details.close")}
              size="xs"
              className="ml-auto"
              onClick={onClose}
            >
              <Icon name="close" />
            </IconButton>
          )}
        </div>
        <h3 className="font-serif text-lg leading-snug">{field.label.text}</h3>
      </div>
      <ValueCard
        field={field}
        editable={editableHere(envelope, field)}
        staged={staged}
        onUndo={() => session.unstage(key)}
        onRestore={restore ? () => session.stage(field, restore) : null}
      />
      {read?.kind === "ready" ? (
        <CardParts
          card={read.card}
          session={session}
          openLink={openLink}
          onOpenSurface={onOpenSurface}
          canOpenSurface={canOpenSurface}
        />
      ) : (
        read && <CardState read={read} t={t} />
      )}
      <Part title={t("workspace.modelo.details.what_it_means")}>
        {field.help ? (
          <p className="text-base leading-relaxed">{field.help}</p>
        ) : (
          <p className="text-sm text-muted-foreground">
            {t("workspace.modelo.help.no_explanation")}
          </p>
        )}
      </Part>
    </div>
  );
}
