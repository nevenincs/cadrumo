import { useId, useState } from "react";
import { Icon } from "@/components/ui/icon";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type {
  ModeloFormOrigin,
  ModeloWorkbenchFormProjectionV1,
  PublicModeloWorkForm,
} from "../../../shell/modeloContract/modeloWorkForm";
import { useStrings } from "../../../shell/strings";
import { BoxNumber } from "../form/BoxNumber";
import { OutlineNavigator } from "../workspace/OutlineNavigator";
import {
  editKey,
  editsAdmitted,
  type FormSession,
  type PlacedField,
} from "../form/session";

// Beside the form: the boxes the read model says need the filer, and the
// form's outline. A box leaves To do once the filer has staged a change for
// it; which boxes need the filer is the read model's standing, never the
// rail's own judgement.

type Rail = "todo" | "outline";

/** The boxes on pages that may apply that the read model says need the
 * filer, grouped by their origin token in form order, and apart from them
 * those whose calculation failed. */
function todoOf(form: PublicModeloWorkForm, session: FormSession) {
  const excluded = new Set(
    form.pages.filter((page) => page.applies === false).map((page) => page.id),
  );
  const open = session.placed.filter(
    (p) => !excluded.has(p.pageId) && !session.staged.has(editKey(p.field)),
  );
  const failed = open.filter((p) => p.field.origin === "calculation_failed");
  const groups = new Map<ModeloFormOrigin, PlacedField[]>();
  for (const p of open)
    if (
      p.field.standing === "needs_you" &&
      p.field.origin !== "calculation_failed"
    )
      groups.set(p.field.origin, [...(groups.get(p.field.origin) ?? []), p]);
  return { groups: [...groups], failed };
}

function TodoList({
  envelope,
  session,
  onPicked,
  onOpenCheck,
}: {
  envelope: ModeloWorkbenchFormProjectionV1;
  session: FormSession;
  onPicked?: () => void;
  onOpenCheck?: () => void;
}) {
  const t = useStrings();
  const [openFailed, setOpenFailed] = useState(false);
  if (!editsAdmitted(envelope))
    return (
      <p className="flex gap-2 p-4 text-sm text-muted-foreground">
        <Icon name="lock" size="xs" className="mt-0.5" />
        {envelope.rules_incomplete
          ? t("workspace.modelo.editor.rules_incomplete")
          : (envelope.admission_refusal_words ??
            t("workspace.modelo.editability.no_admission"))}
      </p>
    );
  const todo = todoOf(envelope.form.form, session);
  // Missing values no box holds are the check's to name; the read model
  // counts them with the missing boxes, so the list states them too.
  const elsewhere = envelope.header.missing_elsewhere;
  const elsewhereLine = elsewhere && (
    <button
      type="button"
      data-todo-elsewhere=""
      onClick={onOpenCheck}
      disabled={!onOpenCheck}
      className="flex w-full items-start gap-2 rounded-md border border-border px-2 py-2 text-left hover:bg-accent"
    >
      <Icon name="alert" size="xs" className="mt-0.5 text-warning" />
      <span className="text-sm">{elsewhere.words}</span>
      <Icon name="forward" size="xs" className="mt-0.5 ml-auto text-faint" />
    </button>
  );
  if (!todo.groups.length && !todo.failed.length && !elsewhereLine)
    return (
      <p className="flex gap-2 p-4 text-sm text-muted-foreground">
        <Icon name="check" size="xs" className="mt-0.5 text-success" />
        {t("workspace.modelo.todo.none")}
      </p>
    );
  const item = (p: PlacedField) => (
    <li key={p.key}>
      <button
        type="button"
        onClick={() => {
          session.selectAddress(p.field.address);
          onPicked?.();
        }}
        aria-current={session.selectedKey === p.key}
        className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left hover:bg-accent aria-[current=true]:bg-selected"
      >
        <BoxNumber box={p.field.box} size="sm" />
        <span className="truncate text-sm">{p.field.label.text}</span>
      </button>
    </li>
  );
  return (
    <div className="flex flex-col gap-3 p-2">
      {elsewhereLine}
      {todo.groups.map(([origin, list]) => {
        const word = t(`workspace.modelo.origin.${origin}`);
        return (
          <section key={origin} aria-label={word}>
            <p className="px-2 pb-1 text-xs font-medium text-warning">{word}</p>
            <ul>{list.map(item)}</ul>
          </section>
        );
      })}
      {todo.failed.length > 0 && (
        <div className="rounded-md border border-border">
          <button
            type="button"
            onClick={() => setOpenFailed(!openFailed)}
            aria-expanded={openFailed}
            className="flex w-full items-start gap-2 px-2 py-2 text-left"
          >
            <Icon name="alert" size="xs" className="mt-0.5 text-destructive" />
            <span className="flex flex-col">
              <span className="text-sm">
                {t("workspace.modelo.todo.failed", {
                  count: todo.failed.length,
                })}
              </span>
              <span className="text-xs text-muted-foreground">
                {t("workspace.modelo.todo.failed_lead")}
              </span>
            </span>
            <Icon
              name={openFailed ? "chevronUp" : "chevronDown"}
              size="xs"
              className="mt-0.5 ml-auto text-faint"
            />
          </button>
          {openFailed && <ul className="px-1 pb-1">{todo.failed.map(item)}</ul>}
        </div>
      )}
    </div>
  );
}

/** The section the form shows the filer at: the chosen box's, else the
 * last one jumped to. */
function currentSection(session: FormSession): string | null {
  const chosen = session.selectedKey
    ? session.placed.find((p) => p.key === session.selectedKey)
    : undefined;
  return chosen?.sectionId ?? session.reveal?.sectionId ?? null;
}

/** The rail beside the form: To do and the outline, as two tabs. The
 * workspace places it; `onPicked` follows a pick, to show the form. */
export function TodoRail({
  envelope,
  session,
  onPicked,
  onOpenProfile,
  onOpenCheck,
}: {
  envelope: ModeloWorkbenchFormProjectionV1;
  session: FormSession;
  onPicked?: () => void;
  /** Opens the profile, where the boxes it keeps are corrected. */
  onOpenProfile?: () => void;
  /** Opens the check, which names the missing values no box holds. */
  onOpenCheck?: () => void;
}) {
  const t = useStrings();
  const [rail, setRail] = useState<Rail>("todo");
  const panel = useId();
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <Tabs
        value={rail}
        onValueChange={(value) => setRail(value as Rail)}
        className="flex-none px-2"
      >
        <TabsList aria-label={t("desktop.modelo.side.label")}>
          <TabsTrigger value="todo" aria-controls={panel}>
            {t("workspace.modelo.todo.title")}
          </TabsTrigger>
          <TabsTrigger value="outline" aria-controls={panel}>
            {t("desktop.modelo.side.outline")}
          </TabsTrigger>
        </TabsList>
      </Tabs>
      <div
        id={panel}
        role="tabpanel"
        className="min-h-0 flex-1 overflow-y-auto border-t border-border"
      >
        {rail === "todo" ? (
          <TodoList
            envelope={envelope}
            session={session}
            onPicked={onPicked}
            onOpenCheck={onOpenCheck}
          />
        ) : (
          <OutlineNavigator
            form={envelope.form.form}
            currentSectionId={currentSection(session)}
            onOpenProfile={onOpenProfile}
            onJump={(sectionId) => {
              session.goSection(sectionId);
              onPicked?.();
            }}
          />
        )}
      </div>
    </div>
  );
}
