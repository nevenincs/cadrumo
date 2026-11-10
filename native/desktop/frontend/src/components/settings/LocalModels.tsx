import {
  useContext,
  useId,
  useLayoutEffect,
  useState,
  type FormEvent,
} from "react";
import { TextEditor } from "@/components/editors/TextEditor";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, FieldLabel } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio";
import {
  addedTo,
  engineRefusalWords,
  heldBackByEngine,
  laneModelList,
  listRefusalWords,
  type CatalogLane,
  type LaneModel,
} from "../../shell/localModelLanes";
import type {
  AgentLocalEngineToken,
  AgentLocalPlacement,
} from "../../ipc/contract";
import { formatSize } from "../../shared/numbers";
import type { AgentModelLicenceFacts } from "../../shell/agentSession";
import {
  planIsFor,
  ReviewClaimContext,
  useLocalEngine,
  useLocalModels,
  type LocalEngineState,
  type LocalModelHost,
} from "../../shell/localModels";
import { useProvisioning } from "../../shell/provisioning";
import { useStrings, type Translate } from "../../shell/strings";
import type { SetupRun, SetupStep } from "../../ipc/componentSetup";
import {
  PlanningFigure,
  RowReview,
  SetupReadState,
  StepFigure,
  type StepProgress,
} from "../setup/ProvisioningRow";
import { refusalWords } from "../setup/setupWords";

const licenceWords = (licence: AgentModelLicenceFacts) =>
  licence.spdx && licence.spdx !== licence.name
    ? `${licence.name} (${licence.spdx})`
    : licence.name;

/** Why a model was not removed from this computer, in words. */
function removalWords(t: Translate, code: string): string {
  return code === "model_not_removed"
    ? t("desktop.providers.local_model_remove_failed")
    : refusalWords(t, code);
}

/** What the catalog states of one model: its licence, said even where it is
 * not known, and its download size where it is. */
function ModelFacts({ model, locale }: { model: LaneModel; locale: string }) {
  const t = useStrings();
  return (
    <ul data-slot="model-facts" className="grid gap-0.5 text-sm">
      <li data-fact="licence">
        {model.licence
          ? t("desktop.providers.local_model_licence", {
              licence: licenceWords(model.licence),
            })
          : t("desktop.providers.local_model_licence_unknown")}
      </li>
      {model.sizeBytes !== null && (
        <li data-fact="size">
          {t("desktop.providers.local_model_size", {
            size: formatSize(locale, model.sizeBytes),
          })}
        </li>
      )}
    </ul>
  );
}

/** One listed model, its download's progress while the local AI's setup
 * pulls it, and its download or removal action. */
function LocalModelRow({
  model,
  added,
  locale,
  busy,
  refusal,
  progress,
  planning,
  review,
  onDownload,
  onRemove,
}: {
  model: LaneModel;
  added: boolean;
  locale: string;
  busy: boolean;
  refusal: string | null;
  /** What the local AI's latest setup reports of this model, where it
   * planned it and its outcome is still news. */
  progress: StepProgress | null;
  /** Set while this model's download is still being planned, which names no
   * part yet: what the engine has reported of the local AI, none at first. */
  planning: { step: SetupStep | null } | null;
  /** The local AI's setup while it awaits the person's answer on a plan for
   * this model: the row carries the answer, the one place it is asked. */
  review: SetupRun | null;
  onDownload?: () => void;
  onRemove?: () => void;
}) {
  const t = useStrings();
  const headingId = useId();
  // The download is running: the model is not on this computer yet, and
  // nothing else may start while the setup works on it.
  const inProgress = progress !== null && progress.result === null;
  return (
    <li
      data-model={model.id}
      data-added={added || undefined}
      data-installed={model.installed ?? undefined}
      aria-labelledby={headingId}
      className="grid gap-1.5 rounded-md bg-background p-2"
    >
      <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
        <h6
          id={headingId}
          className="min-w-0 font-medium wrap-anywhere text-foreground"
        >
          {model.name}
        </h6>
        {inProgress ? (
          <Badge variant="neutral">
            {t("desktop.setup.state.provisioning")}
          </Badge>
        ) : (
          model.installed !== null && (
            <Badge variant={model.installed ? "success" : "neutral"}>
              {t(
                model.installed
                  ? "desktop.providers.local_model_installed"
                  : "desktop.providers.local_model_absent",
              )}
            </Badge>
          )
        )}
      </div>
      <ModelFacts model={model} locale={locale} />
      {review ? (
        <RowReview run={review} locale={locale} reveal />
      ) : progress ? (
        <StepFigure progress={progress} name={model.name} locale={locale} />
      ) : (
        planning && <PlanningFigure step={planning.step} />
      )}
      <div className="flex flex-wrap gap-2">
        {model.installed !== true && (
          <Button
            variant="outline"
            size="sm"
            disabled={busy || inProgress || !onDownload}
            onClick={onDownload}
          >
            {t("desktop.providers.local_model_download")}
          </Button>
        )}
        {onRemove && (
          <Button variant="ghost" size="sm" disabled={busy} onClick={onRemove}>
            {t("desktop.providers.local_model_remove")}
          </Button>
        )}
      </div>
      {refusal && (
        <p role="alert" className="flex items-start gap-2 text-sm">
          <Icon name="alert" className="mt-0.5 text-destructive" />
          <span>{refusal}</span>
        </p>
      )}
    </li>
  );
}

/** The words of each engine and of each placement the service can name. Each
 * key is named whole, so the shell's key check sees every one. A token this
 * window has no words for is offered as nothing: no fallback wording. */
const ENGINE_WORDS = {
  llamacpp: {
    label: "desktop.providers.local_engine_llamacpp",
    detail: "desktop.providers.local_engine_llamacpp_detail",
  },
  ollama: {
    label: "desktop.providers.local_engine_ollama",
    detail: "desktop.providers.local_engine_ollama_detail",
  },
} as const satisfies Record<
  AgentLocalEngineToken,
  { label: string; detail: string }
>;

const PLACEMENT_WORDS = {
  auto: {
    label: "desktop.providers.local_placement_auto",
    detail: "desktop.providers.local_placement_auto_detail",
  },
  cpu_only: {
    label: "desktop.providers.local_placement_cpu_only",
    detail: "desktop.providers.local_placement_cpu_only_detail",
  },
} as const satisfies Record<
  AgentLocalPlacement,
  { label: string; detail: string }
>;

const isEngine = (token: string): token is AgentLocalEngineToken =>
  Object.hasOwn(ENGINE_WORDS, token);
const isPlacement = (token: string): token is AgentLocalPlacement =>
  Object.hasOwn(PLACEMENT_WORDS, token);

function engineWords(t: Translate, engine: AgentLocalEngineToken) {
  const words = ENGINE_WORDS[engine];
  return { label: t(words.label), detail: t(words.detail) };
}

function placementWords(t: Translate, placement: AgentLocalPlacement) {
  const words = PLACEMENT_WORDS[placement];
  return { label: t(words.label), detail: t(words.detail) };
}

/** One choice among a few, each with its label and the detail beneath it. */
function Choice<T extends string>({
  name,
  title,
  value,
  values,
  words,
  disabled,
  onChoose,
}: {
  name: string;
  title: string;
  value: T;
  values: readonly T[];
  words: (value: T) => { label: string; detail: string };
  disabled: boolean;
  onChoose: (value: T) => void;
}) {
  const titleId = useId();
  const base = useId();
  return (
    <div data-slot={name} className="grid gap-1">
      <h6 id={titleId} className="text-sm font-medium text-foreground">
        {title}
      </h6>
      <RadioGroup
        aria-labelledby={titleId}
        value={value}
        disabled={disabled}
        onValueChange={(next) => onChoose(next as T)}
      >
        {values.map((option) => {
          const { label, detail } = words(option);
          const labelId = `${base}-${option}`;
          return (
            <label
              key={option}
              data-choice={option}
              className="flex items-start gap-2 text-sm"
            >
              <RadioGroupItem
                value={option}
                aria-labelledby={labelId}
                aria-describedby={`${labelId}-detail`}
                className="mt-0.5"
              />
              <span className="grid">
                <span id={labelId} className="font-medium text-foreground">
                  {label}
                </span>
                <span
                  id={`${labelId}-detail`}
                  className="text-muted-foreground"
                >
                  {detail}
                </span>
              </span>
            </label>
          );
        })}
      </RadioGroup>
    </div>
  );
}

/** The local engine and the placement the models run on, stored together.
 * A change restarts the assistant, which the note says. */
function LocalEngineChoice({ engine }: { engine: LocalEngineState }) {
  const t = useStrings();
  const value = engine.value;
  if (value?.state !== "readable") return null;
  const choose = (
    next: AgentLocalEngineToken,
    placement: AgentLocalPlacement,
  ) => void engine.change(next, placement);
  return (
    <div data-slot="local-engine" className="grid gap-3">
      <div className="grid gap-1">
        <h6 className="text-sm font-medium text-foreground">
          {t("desktop.providers.local_engine_title")}
        </h6>
        <p className="text-sm text-muted-foreground">
          {t("desktop.providers.local_engine_lead")}
        </p>
      </div>
      <Choice
        name="local-engine-choice"
        title={t("desktop.providers.local_engine_title")}
        value={value.engine}
        values={value.choices.engine.filter(isEngine)}
        words={(option) => engineWords(t, option)}
        disabled={engine.busy}
        onChoose={(next) => choose(next, value.placement)}
      />
      <Choice
        name="local-placement-choice"
        title={t("desktop.providers.local_placement_title")}
        value={value.placement}
        values={value.choices.placement.filter(isPlacement)}
        words={(option) => placementWords(t, option)}
        disabled={engine.busy}
        onChoose={(next) => choose(value.engine, next)}
      />
      <p className="text-sm text-muted-foreground">
        {t("desktop.providers.local_engine_restarts")}
      </p>
      {engine.busy && (
        <p role="status" className="text-sm text-muted-foreground">
          {t("desktop.providers.local_engine_changing")}
        </p>
      )}
      {engine.refusal && (
        <p role="alert" className="flex items-start gap-2 text-sm">
          <Icon name="alert" className="mt-0.5 text-destructive" />
          <span>{engineRefusalWords(t, engine.refusal)}</span>
        </p>
      )}
    </div>
  );
}

/** Adds a model to the lane's list by the name the local AI pulls it by. */
function AddModel({
  busy,
  onAdd,
}: {
  busy: boolean;
  onAdd: (model: string) => Promise<boolean>;
}) {
  const t = useStrings();
  const nameId = useId();
  const [name, setName] = useState("");
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const model = name.trim();
    if (!model) return;
    void onAdd(model).then((added) => {
      if (added) setName("");
    });
  };
  return (
    <form
      data-slot="local-model-add"
      className="flex flex-wrap items-end gap-2"
      onSubmit={submit}
    >
      <Field className="min-w-0 flex-1">
        <FieldLabel htmlFor={nameId}>
          {t("desktop.providers.local_model_add_label")}
        </FieldLabel>
        <TextEditor
          id={nameId}
          value={name}
          autoCapitalize="off"
          autoCorrect="off"
          onChange={setName}
        />
      </Field>
      <Button
        type="submit"
        variant="outline"
        size="sm"
        disabled={busy || name.trim() === ""}
      >
        {t("desktop.providers.local_model_add")}
      </Button>
    </form>
  );
}

/** A local lane's model list: what the agent recommends and what the person
 * added by name, each downloaded and removed here through the local AI's
 * setup, whose progress each model shows. The list is what the agent's model
 * picker offers of the lane; the model the person picks there is the one the
 * agent and document reading run with. */
export function LocalModels({
  lane: offered,
  withEngine = false,
  host,
  locale,
  onRemoved,
  laneStatus = "ready",
  onRetryLane,
}: {
  lane: CatalogLane | null;
  /** Offers the local engine and placement choice here: set on the one
   * section that stands for the local AI. */
  withEngine?: boolean;
  host: LocalModelHost;
  locale: string;
  /** Told once a model is removed from this computer. */
  onRemoved?: () => void;
  /** Whether the catalogue supplying this lane has answered. */
  laneStatus?: "loading" | "failed" | "ready";
  onRetryLane?: () => void;
}) {
  const t = useStrings();
  const store = useProvisioning();
  const engine = useLocalEngine(host);
  // The lane of the engine that is not selected is not offered.
  const heldBack = offered !== null && heldBackByEngine(offered, engine.value);
  const lane = heldBack ? null : offered;
  const { snapshot, retry, busy, outcomes, change } = useLocalModels(host);
  // Downloading and removing are setup's: offered only where this window
  // offers setup, and a download waits while the local AI sets up.
  const localAi = store.localAiRow;
  const liveRun = localAi ? store.liveRunOf(localAi.item) : null;
  const settingUp = liveRun !== null;
  // A start that no snapshot shows yet is as much a setup under way as one
  // that does, and a second click would send it again.
  const starting = localAi !== null && store.control.startingOf(localAi.item);
  // The model whose download is under way: its row says what the setup is
  // doing before the setup names a part.
  const asked =
    lane && store.asked?.lane === lane.id ? store.asked.model : null;
  // A refused start is said on the row of the model it asked for.
  const refused = store.control.refusal;
  const onSetUp =
    store.offered && localAi !== null
      ? (model: string) => {
          if (!lane) return;
          store.downloadModel(lane.id, model);
        }
      : undefined;
  const onRemove = store.offered ? store.removeModel : undefined;
  /** What the latest local AI setup says of `model`: its progress while it
   * runs, and how it ended while the catalog does not yet show the model
   * here, or when it failed. */
  const progressOf = (model: LaneModel): StepProgress | null => {
    const part = store.modelPart(model.id);
    if (!part) {
      // A setup refused or failed before it planned a part for the model
      // the person asked for, as when the host refuses the download while it
      // plans, still says why on that model's row.
      const ended = store.settledAsk;
      return ended !== null &&
        lane !== null &&
        ended.lane === lane.id &&
        ended.model === model.id &&
        ended.run.outcome === "failed" &&
        ended.run.failure !== null &&
        model.installed !== true
        ? {
            step: null,
            completed: null,
            total: null,
            result: {
              changed: false,
              failure: ended.run.failure,
              transferred_bytes: 0,
            },
          }
        : null;
    }
    // A setup that stopped at the item itself, not in a part, settles with
    // its failure and no part failed: the model it planned and did not bring
    // here says so, instead of going back to its plain download.
    const settled = localAi ? store.runOf(localAi.item) : null;
    const itemFailure =
      settled?.stage === "settled" && settled.outcome === "failed"
        ? settled.failure
        : null;
    if (
      itemFailure !== null &&
      part.result?.failure == null &&
      model.installed !== true
    )
      return {
        step: null,
        completed: null,
        total: null,
        result: { changed: false, failure: itemFailure, transferred_bytes: 0 },
      };
    // A part planned for the person's review has not begun: it reports no
    // step until the setup runs.
    if (part.result === null) {
      if (liveRun?.stage !== "running") return null;
      // A model part reports its download until it ends; the host then
      // verifies and tidies at the item's own step, which is what the part
      // is doing in that tail.
      const itemStep = store.progressOf(liveRun.item)?.step ?? null;
      return itemStep === "verify" || itemStep === "cleanup"
        ? { ...part, step: itemStep }
        : part;
    }
    return part.result.failure !== null || model.installed !== true
      ? part
      : null;
  };
  // From the click until the engine's plan awaits the person's answer, the
  // setup names no part, so the asked model's row says what it is doing.
  const planningStep =
    localAi && (liveRun ? liveRun.stage === "planning" : starting)
      ? { step: store.progressOf(localAi.item)?.step ?? null }
      : null;
  const reviewed = store.reviewedModel();
  const claim = useContext(ReviewClaimContext);
  const [removing, setRemoving] = useState<string | null>(null);
  const [removals, setRemovals] = useState<Record<string, string>>({});
  const readable =
    snapshot.kind === "ready" && snapshot.value.state === "readable";
  const listed =
    lane && snapshot.kind === "ready"
      ? laneModelList(lane, addedTo(snapshot.value, lane.id))
      : [];
  // The plan is shown on the asked model's row only while that row is listed
  // here, and the one place that is decided is this: the row's own review and
  // the claim the program's row yields to come from the same value.
  const reviewRun = (model: LaneModel): SetupRun | null =>
    lane &&
    laneStatus === "ready" &&
    reviewed?.lane === lane.id &&
    reviewed.model === model.id &&
    liveRun?.stage === "review"
      ? liveRun
      : null;
  const holdsReview = listed.some(({ model }) => reviewRun(model) !== null);
  // A section with no program row of the local AI above it, as a second
  // lane has, answers a plan for its lane itself where no row here holds it:
  // the asked row is not listed, or nothing was asked in this window, as
  // after a reload.
  const sectionReview =
    claim === null &&
    liveRun?.stage === "review" &&
    !holdsReview &&
    planIsFor({
      lane,
      models: [...(lane?.models ?? []), ...listed.map(({ model }) => model)],
      reviewed,
      planned: (model) => store.modelPart(model) !== null,
    })
      ? liveRun
      : null;
  useLayoutEffect(() => {
    if (!holdsReview || !claim) return;
    claim(true);
    return () => claim(false);
  }, [holdsReview, claim]);
  // Removing deletes the download first, then takes a model the person added
  // off the list; a recommended model stays listed.
  const remove = async (key: string, model: LaneModel, added: boolean) => {
    if (!lane) return;
    setRemoving(key);
    setRemovals((held) => {
      const next = { ...held };
      delete next[key];
      return next;
    });
    try {
      if (model.installed === true) {
        if (!onRemove) return;
        const code = await onRemove(model.id);
        if (code) {
          setRemovals((held) => ({ ...held, [key]: code }));
          return;
        }
        onRemoved?.();
      }
      if (added)
        await change(key, (revision) =>
          host.remove(lane.id, model.id, revision),
        );
    } finally {
      setRemoving(null);
    }
  };
  const working = busy !== null || removing !== null;
  if (heldBack && !withEngine) return null;
  return (
    <section data-slot="local-models" className="grid gap-2 pt-1">
      <h6 className="text-sm font-medium text-foreground">
        {t("desktop.providers.local_models_title")}
      </h6>
      <p className="text-sm text-muted-foreground">
        {t("desktop.providers.local_models_lead")}
      </p>
      {withEngine && <LocalEngineChoice engine={engine} />}
      {sectionReview && (
        <div data-slot="local-models-review">
          <RowReview run={sectionReview} locale={locale} reveal />
        </div>
      )}
      {laneStatus === "loading" ? (
        <p role="status" className="text-sm text-muted-foreground">
          {t("desktop.providers.local_models_loading")}
        </p>
      ) : laneStatus === "failed" ? (
        <p role="alert" className="flex items-start gap-2 text-sm">
          <Icon name="alert" className="mt-0.5 text-destructive" />
          <span>{t("desktop.providers.load_failed")}</span>
          {onRetryLane && (
            <Button variant="outline" size="sm" onClick={onRetryLane}>
              {t("desktop.agent.retry")}
            </Button>
          )}
        </p>
      ) : !lane ? (
        <p className="text-sm text-muted-foreground">
          {t("desktop.providers.local_models_none")}
        </p>
      ) : snapshot.kind === "loading" ? (
        <p className="text-sm text-muted-foreground">
          {t("desktop.providers.local_models_loading")}
        </p>
      ) : snapshot.kind === "failed" ? (
        <p role="alert" className="flex items-start gap-2 text-sm">
          <Icon name="alert" className="mt-0.5 text-destructive" />
          <span>{t("desktop.providers.local_models_failed")}</span>
          <Button variant="outline" size="sm" onClick={retry}>
            {t("desktop.agent.retry")}
          </Button>
        </p>
      ) : (
        <>
          {!readable && (
            <div
              data-slot="local-models-unreadable"
              className="grid gap-2 text-sm"
            >
              <p role="alert" className="flex items-start gap-2">
                <Icon name="alert" className="mt-0.5 text-destructive" />
                <span>{t("desktop.providers.local_models_unreadable")}</span>
              </p>
              <Button
                variant="outline"
                size="sm"
                className="justify-self-start"
                disabled={working}
                onClick={() =>
                  void change("reset", (revision) => host.reset(revision))
                }
              >
                {t("desktop.providers.local_models_reset")}
              </Button>
              {outcomes.reset?.kind === "refused" && (
                <p role="alert">{listRefusalWords(t, outcomes.reset.code)}</p>
              )}
            </div>
          )}
          {store.offered && localAi === null && (
            <SetupReadState slot="local-models-setup-unread" />
          )}
          {listed.length > 0 && (
            <ul className="grid gap-2">
              {listed.map(({ model, added }) => {
                const key = `${lane.id}/${model.id}`;
                const outcome = outcomes[key];
                const removable =
                  (model.installed === true && onRemove !== undefined) ||
                  (added && readable);
                return (
                  <LocalModelRow
                    key={model.id}
                    model={model}
                    added={added}
                    locale={locale}
                    busy={
                      working ||
                      ((settingUp || starting) && model.installed !== true)
                    }
                    progress={progressOf(model)}
                    planning={asked === model.id ? planningStep : null}
                    review={reviewRun(model)}
                    refusal={
                      removals[key]
                        ? removalWords(t, removals[key])
                        : outcome?.kind === "refused"
                          ? listRefusalWords(t, outcome.code)
                          : refused?.download?.lane === lane.id &&
                              refused.download.model === model.id
                            ? refusalWords(t, refused.code)
                            : null
                    }
                    onDownload={onSetUp ? () => onSetUp(model.id) : undefined}
                    onRemove={
                      removable
                        ? () => void remove(key, model, added)
                        : undefined
                    }
                  />
                );
              })}
            </ul>
          )}
          {readable && (
            <>
              <AddModel
                busy={working}
                onAdd={(model) =>
                  change("add", (revision) =>
                    host.add(lane.id, model, revision),
                  )
                }
              />
              {outcomes.add?.kind === "refused" && (
                <p role="alert" className="flex items-start gap-2 text-sm">
                  <Icon name="alert" className="mt-0.5 text-destructive" />
                  <span>{listRefusalWords(t, outcomes.add.code)}</span>
                </p>
              )}
            </>
          )}
        </>
      )}
    </section>
  );
}
