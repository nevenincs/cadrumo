import { useId, useMemo } from "react";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { NativeSelect } from "@/components/ui/native-select";
import type { ServedCatalogAnswer } from "../../shell/agentCatalogContract";
import { effortWords } from "../../shell/agentCatalog";
import type { TaskModelChoice } from "../../shell/agentSession";
import { listRefusalWords } from "../../shell/localModelLanes";
import { useLocalModels, type LocalModelHost } from "../../shell/localModels";
import type { TaskModelEntry } from "../../shell/localModelsContract";
import { useStrings } from "../../shell/strings";
import {
  taskEfforts,
  taskKindRows,
  taskLanes,
  type TaskKindRow,
  type TaskLaneOption,
} from "../../shell/taskModels";
import { ReadState, SectionFailure } from "../agent/ReadState";

/** The value a model option carries: its lane and its id, which no lane id
 * or model id contains. */
const optionOf = (lane: string, model: string) => `${lane}\n${model}`;

/** The default every kind starts on: the model documents are read with. */
const READING = "";

/**
 * What each kind of background task the agent serves runs with: a model on
 * a lane, and an effort where the lane takes one for that model, or, by
 * default, the model documents are read with. The kinds, lanes, models and
 * efforts are the ones the catalogue serves; each change is stored by the
 * agent service at the revision read, and says whether it was.
 */
export function TaskModels({
  host,
  catalog,
  catalogStatus,
  onRetryCatalog,
}: {
  host: LocalModelHost;
  /** The catalogue the agent serves, once read. */
  catalog: ServedCatalogAnswer | null;
  catalogStatus: "ready" | "loading" | "failed";
  onRetryCatalog: () => void;
}) {
  const t = useStrings();
  const { snapshot, retry, busy, outcomes, change } = useLocalModels(host);
  const lists = snapshot.kind === "ready" ? snapshot.value : null;
  const rows = useMemo(
    () => (catalog && lists ? taskKindRows(catalog, lists) : []),
    [catalog, lists],
  );
  const lanes = useMemo(
    () => (catalog && lists ? taskLanes(catalog, lists) : []),
    [catalog, lists],
  );
  const chooseTask = host.chooseTask;
  if (!chooseTask) return null;
  if (snapshot.kind === "failed")
    return (
      <SectionFailure
        words={listRefusalWords(t, snapshot.code)}
        onRetry={retry}
      />
    );
  if (catalogStatus === "failed")
    return (
      <SectionFailure
        words={t("desktop.agent.read_failed")}
        onRetry={onRetryCatalog}
      />
    );
  if (!lists || !catalog)
    return <ReadState read={{ kind: "loading" }} icon="settings" />;
  const choose = (kind: string, choice: TaskModelChoice | null) =>
    void change(kind, (revision) => chooseTask(kind, choice, revision));
  return (
    <div className="grid gap-3">
      <p className="text-sm text-muted-foreground">
        {t("desktop.providers.task_models_intro")}
      </p>
      <ul className="grid gap-4">
        {rows.map((row) => {
          const outcome = outcomes[row.id];
          return (
            <TaskModelRow
              key={row.id}
              row={row}
              lanes={lanes}
              busy={busy !== null || lists.unreadable}
              words={
                outcome?.kind === "saved"
                  ? {
                      role: "status",
                      text: t("desktop.providers.task_model_saved"),
                    }
                  : outcome?.kind === "refused"
                    ? {
                        role: "alert",
                        text:
                          outcome.code === "agent_local_models_unknown"
                            ? t("desktop.providers.task_model_refused")
                            : listRefusalWords(t, outcome.code),
                      }
                    : null
              }
              onChoose={(choice) => choose(row.id, choice)}
            />
          );
        })}
      </ul>
    </div>
  );
}

function TaskModelRow({
  row,
  lanes,
  busy,
  words,
  onChoose,
}: {
  row: TaskKindRow;
  lanes: readonly TaskLaneOption[];
  busy: boolean;
  words: { role: "status" | "alert"; text: string } | null;
  onChoose: (choice: TaskModelChoice | null) => void;
}) {
  const t = useStrings();
  const modelId = useId();
  const effortId = useId();
  const descriptionId = useId();
  const setting = row.setting;
  // A stored setting the catalogue no longer offers is still what the kind
  // is set to, so it stays shown, named as stored.
  const offered = (entry: TaskModelEntry) =>
    lanes.some(
      (lane) =>
        lane.id === entry.lane &&
        lane.models.some((model) => model.id === entry.model),
    );
  const efforts = setting
    ? taskEfforts(lanes, setting.lane, setting.model)
    : [];
  const storedEffort =
    setting?.effort && !efforts.some((effort) => effort === setting.effort)
      ? setting.effort
      : null;
  return (
    <li data-slot="task-model" data-task-kind={row.id} className="grid gap-2">
      <Field>
        <FieldLabel htmlFor={modelId}>
          {t("desktop.providers.task_model_model", { task: row.name })}
        </FieldLabel>
        <FieldDescription id={descriptionId}>
          {row.description}
        </FieldDescription>
        <NativeSelect
          id={modelId}
          controlSize="sm"
          aria-describedby={descriptionId}
          disabled={busy}
          value={setting ? optionOf(setting.lane, setting.model) : READING}
          onChange={(event) => {
            const value = event.target.value;
            if (value === READING) {
              onChoose(null);
              return;
            }
            const [lane, model] = value.split("\n");
            if (lane === undefined || model === undefined) return;
            // An effort carries over where the new model takes it.
            const effort =
              setting?.effort &&
              taskEfforts(lanes, lane, model).some(
                (held) => held === setting.effort,
              )
                ? setting.effort
                : null;
            onChoose({ lane, model, effort });
          }}
        >
          <option value={READING}>
            {t("desktop.providers.task_model_reading")}
          </option>
          {setting && !offered(setting) && (
            <option value={optionOf(setting.lane, setting.model)}>
              {`${setting.lane} · ${setting.model}`}
            </option>
          )}
          {lanes.map((lane) => (
            <optgroup key={lane.id} label={lane.name}>
              {lane.models.map((model) => (
                <option key={model.id} value={optionOf(lane.id, model.id)}>
                  {model.name}
                </option>
              ))}
            </optgroup>
          ))}
        </NativeSelect>
      </Field>
      {setting && (efforts.length > 0 || storedEffort) && (
        <Field>
          <FieldLabel htmlFor={effortId}>
            {t("desktop.providers.task_model_effort", { task: row.name })}
          </FieldLabel>
          <NativeSelect
            id={effortId}
            controlSize="sm"
            disabled={busy}
            value={setting.effort ?? ""}
            onChange={(event) => {
              const effort = event.target.value;
              onChoose({
                lane: setting.lane,
                model: setting.model,
                effort: effort === "" ? null : effort,
              });
            }}
          >
            <option value="">{t("desktop.agent.effort_default")}</option>
            {storedEffort && (
              <option value={storedEffort}>{storedEffort}</option>
            )}
            {efforts.map((effort) => (
              <option key={effort} value={effort}>
                {effortWords(t, effort)}
              </option>
            ))}
          </NativeSelect>
        </Field>
      )}
      {words && (
        <p role={words.role} className="text-sm">
          {words.text}
        </p>
      )}
    </li>
  );
}
