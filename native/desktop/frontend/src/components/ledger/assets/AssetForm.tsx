import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from "react";
import { TypedField } from "@/components/editors/TypedField";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { facts, labelled, listed } from "../../../shell/compose";
import type {
  LedgerDefinitionId,
  LedgerPort,
  LedgerRequest,
  LedgerResult,
} from "../../../shell/ledger";
import type { GrammarRefusal } from "../../../shell/ledgerGrammar";
import type {
  AcquisitionCandidate,
  ActivityAssetCorrectRequest,
  ActivityAssetCreateRequest,
  AssetListRow,
  TableGroup,
  FormOptions,
} from "../../../shell/ledgerSetup";
import { tokensOf, useStrings, type Translate } from "../../../shell/strings";
import { useWritePause, WriteHold, type LandingCheck } from "../WritePause";
import { formatDay } from "../../../shared/dateFormats";
import {
  formatAmount,
  formatDecimal,
  formatPercent,
} from "../../../shared/numbers";
import {
  CallLine,
  ChoiceField,
  FormGrid,
  Panel,
  Reading,
  useSetupDraft,
  useSetupWrite,
} from "../setup/SetupParts";
import { EditorField } from "../setup/EditorField";
import { setupCall, type SetupCall } from "../setup/setupModel";
import { grammarText } from "../setup/setupWords";
import {
  answer,
  fieldsFor,
  formKeyOf,
  FURTHER_PURCHASE,
  initialOf,
  specOf,
  type FormDraft,
  type FormField,
  type FormValues,
} from "./assetFields";
import {
  bajaRequest,
  correctRequest,
  createRequest,
  type RevisionBase,
} from "./assetRevision";
import { usePurchasePrefill, useAssetSuggestions } from "./assetSuggestions";
import {
  correctionLanding,
  currentDescriptor,
  descriptorLanding,
  describeRequest,
  disposalOf,
  elementLanding,
  INCOMPLETE,
  missingLabels,
  neverReused,
  purchaseOf,
  purchaseValues,
  refusalWord,
  viewOf,
} from "./assetWrites";
import {
  ASSET_FAMILY,
  ASSET_KEYS,
  keyedText,
  tokenWord,
  type AssetFamily,
} from "./assetsWords";

/** What every act form is given: the page's port and the account it reads
 * for, and the two things a form tells the page. */
export type ActProps = {
  port: LedgerPort;
  /** Null while the account withholds the ledger; omitted, the port's own. */
  reader?: string | null;
  locale: string;
  /** The tax year the page stands on, which the registry's options are read
   * for where the form states no date of its own. */
  taxYear?: number | null;
  /** The person left the form. */
  onClose?: () => void;
  /** The form wrote: the page reads the register again. */
  onWritten?: () => void;
  /** An element was added: the page shows it. */
  onAdded?: (assetId: string) => void;
};

const NO_CANDIDATES: readonly AcquisitionCandidate[] = [];
const NO_CLAIMS: readonly string[] = [];
const NO_NOTES: Readonly<Record<string, string | null>> = {};
const NO_KEYS: ReadonlySet<string> = new Set();

/** The tokens of a family, from the generated words that the backend's enum
 * produced. */
const familyTokens = (family: AssetFamily) => tokensOf(ASSET_FAMILY[family]);

// ---- Reading --------------------------------------------------------------------

/**
 * Reads one operation while the form shows, again when `key` changes, on
 * `reload` or after the page re-reads a write it held, and drops what it read
 * with the account. A null `payload` reads nothing; an omitted `reader` reads
 * the port's own ledger; a read that a later one replaced is never shown.
 */
export function useLedgerRead<D extends LedgerDefinitionId>(
  port: LedgerPort,
  reader: string | null | undefined,
  id: D,
  payload: LedgerRequest<D> | null,
  key: string,
): { read: SetupCall<LedgerResult<D>> | null; reload(): void } {
  const [read, setRead] = useState<SetupCall<LedgerResult<D>> | null>(null);
  const [round, setRound] = useState(0);
  const { round: reread } = useWritePause();
  const latest = useRef(payload);
  latest.current = payload;
  useEffect(() => {
    const asked = latest.current;
    if (reader === null || asked === null) return;
    let active = true;
    void setupCall(port, id, asked, false).then((answered) => {
      if (active) setRead(answered);
    });
    return () => {
      active = false;
      setRead(null);
    };
  }, [port, reader, id, key, round, reread]);
  const reload = useCallback(() => setRound((value) => value + 1), []);
  return { read, reload };
}

/** The element a form acts on, as the register lists it now. */
export function useAssetRow(
  port: LedgerPort,
  reader: string | null | undefined,
  assetId: string | null,
): { row: AssetListRow | null; reload(): void } {
  const { read, reload } = useLedgerRead(
    port,
    reader,
    "ledger.actividad-asset.list",
    assetId === null ? null : {},
    assetId ?? "",
  );
  const row =
    assetId !== null && read?.kind === "done"
      ? ((read.result.rows ?? []).find((found) => found.asset_id === assetId) ??
        null)
      : null;
  return { row, reload };
}

// ---- The form's text -----------------------------------------------------------

/** The text of a form, started from what the record states. It starts again
 * only when what the record states changes, never when the same fields are
 * drawn again, and what was typed is kept through a re-read and through a
 * change of what the record states. */
export function useFieldsDraft(initial: FormDraft) {
  const [held, setHeld] = useState<{
    signature: string;
    initial: FormDraft;
  } | null>(null);
  const [draft, setDraft] = useState<FormDraft>({});
  const signature = JSON.stringify(initial);
  if (held === null || signature !== held.signature) {
    const before = held?.initial ?? {};
    setHeld({ signature, initial });
    setDraft((current) => ({
      ...initial,
      ...Object.fromEntries(
        Object.entries(current).filter(
          ([key, typed]) => typed !== (before[key] ?? ""),
        ),
      ),
    }));
  }
  const set = useCallback((changes: FormDraft) => {
    setDraft((current) => ({ ...current, ...changes }));
  }, []);
  return {
    draft,
    initial: held?.initial ?? initial,
    /** Anything typed that is not what the record states. */
    dirty: Object.keys(draft).some(
      (key) => draft[key] !== ((held?.initial ?? initial)[key] ?? ""),
    ),
    set,
  };
}

/** Brings a form into view and puts the cursor in its first field, when it
 * opens and when `ready` becomes true. */
export function useFocusOnOpen(
  form: RefObject<HTMLElement | null>,
  ready: boolean,
) {
  useEffect(() => {
    const element = form.current;
    if (!ready || element === null) return;
    element.scrollIntoView?.({ block: "nearest" });
    element
      .querySelector<HTMLElement>(
        "input:not([disabled]), select:not([disabled]), textarea:not([disabled])",
      )
      ?.focus({ preventScroll: true });
  }, [form, ready]);
}

/** What the registry allows a table class, as one line: the corridor of its
 * coefficient and its maximum period. */
const corridorText = (t: Translate, locale: string, group: TableGroup) => {
  const text = ASSET_KEYS.plan.limits;
  return facts(t, [
    labelled(
      t,
      t(text.maximum_coefficient),
      formatPercent(locale, group.maximum_coefficient.decimal, {
        unit: "fraction",
      }),
    ),
    labelled(
      t,
      t(text.minimum_coefficient),
      formatPercent(locale, group.minimum_coefficient.decimal, {
        unit: "fraction",
      }),
    ),
    labelled(
      t,
      t(text.maximum_period),
      t(text.period_years, {
        years: formatDecimal(locale, group.maximum_period_years.decimal),
      }),
    ),
  ]);
};

/** A choice's word: the generated word of its family, the catalogue key it
 * names, the text served with it, else the generic word. */
function choiceWord(
  t: Translate,
  option: FormField["choices"][number],
): string {
  if (option.family !== null) return tokenWord(t, option.family, option.token);
  if (option.word !== undefined) {
    const said = t(option.word);
    return said === option.word ? t(ASSET_KEYS.unrecognised) : said;
  }
  return option.label ?? t(ASSET_KEYS.unrecognised);
}

/**
 * The fields of an act, each drawn by its control. The form decides nothing
 * about them: their choices, bounds and starting values are the backend's. A
 * required field still to fill in is marked until something is typed; a
 * field the record cannot do without says so when it is emptied.
 */
export function FieldsGrid({
  fields,
  options,
  draft,
  onField,
  problems,
  missing,
  cleared = NO_KEYS,
  candidates,
  purchaseKnown,
  notes = NO_NOTES,
  locale,
}: {
  fields: readonly FormField[];
  options: FormOptions | null;
  draft: FormDraft;
  onField(field: FormField, value: string): void;
  problems: Record<string, GrammarRefusal>;
  /** The fields to mark as still to fill in. */
  missing: ReadonlySet<string>;
  /** The fields emptied that the record cannot do without. */
  cleared?: ReadonlySet<string>;
  candidates: readonly AcquisitionCandidate[];
  /** Fields the picked purchase does not know. */
  purchaseKnown: ReadonlySet<string>;
  /** What the backend says of a field's value, by field key. */
  notes?: Readonly<Record<string, string | null>>;
  locale: string;
}) {
  const t = useStrings();
  const unstated = (field: FormField) => (draft[field.key] ?? "") === "";
  return (
    <FormGrid>
      {fields.map((field) => {
        const raw = draft[field.key] ?? "";
        const problem = problems[field.key];
        const fillIn = missing.has(field.key) && unstated(field);
        const emptied = cleared.has(field.key);
        const hint =
          [
            field.hint_key ? t(field.hint_key) : null,
            field.key === "amortization.authority_class_key"
              ? (() => {
                  const group = options?.table_groups.find(
                    (found) => found.class_key === raw,
                  );
                  return group ? corridorText(t, locale, group) : null;
                })()
              : null,
            notes[field.key] ?? null,
            purchaseKnown.has(field.key) && unstated(field)
              ? t("desktop.ledger.assets.field.not_known")
              : null,
            field.control === "candidate" && candidates.length === 0
              ? t("desktop.ledger.assets.field.acquisition_none", {
                  movements: t("desktop.ledger.section.movements"),
                  documents: t("desktop.ledger.section.documents"),
                })
              : null,
          ]
            .filter(Boolean)
            .join(" ") || undefined;
        const error = problem
          ? grammarText(t, problem)
          : emptied
            ? t("desktop.ledger.assets.write.cannot_clear")
            : fillIn
              ? t(ASSET_KEYS.write.fill_in)
              : null;
        const label = t(field.label_key);
        const choose = (value: string) => onField(field, value);
        const spec = specOf(field);
        return (
          <div key={field.key} data-field={field.key} className="contents">
            {spec === null ? (
              <ChoiceField
                label={label}
                value={raw}
                onValue={choose}
                placeholder={t("desktop.ledger.form.choose")}
                hint={hint}
                required={field.required}
                error={error}
                options={
                  field.control === "candidate"
                    ? candidates.map((candidate) => ({
                        value: candidate.transaction_id,
                        label: t(
                          "desktop.ledger.assets.field.acquisition_option",
                          {
                            description: candidate.description,
                            date: formatDay(locale, candidate.booked_date),
                            amount: formatAmount(
                              locale,
                              candidate.amount.decimal,
                            ),
                          },
                        ),
                      }))
                    : field.control === "flag"
                      ? [
                          { value: "yes", label: t("desktop.ledger.form.yes") },
                          { value: "no", label: t("desktop.ledger.form.no") },
                        ]
                      : field.choices.map((option) => ({
                          value: option.token,
                          label: choiceWord(t, option),
                        }))
                }
              />
            ) : (
              <EditorField label={label} hint={hint} error={error}>
                {(control) => (
                  <TypedField
                    {...control}
                    field={spec}
                    name={field.key}
                    required={field.required}
                    value={raw}
                    onChange={choose}
                    {...field.offers}
                  />
                )}
              </EditorField>
            )}
          </div>
        );
      })}
    </FormGrid>
  );
}

/** What stands where an act's options are not yet drawn: the read, or why it
 * did not answer. */
export function OptionsRead({ call }: { call: SetupCall<unknown> | null }) {
  const t = useStrings();
  if (call === null)
    return <Reading label={t("desktop.ledger.form.reading")} />;
  return (
    <CallLine
      call={call}
      refusal={() =>
        call.kind === "refused"
          ? (refusalWord(t, viewRefusal(call)) ?? t(ASSET_KEYS.write.refused))
          : null
      }
    />
  );
}

const viewRefusal = (call: SetupCall<unknown>) => {
  const view = viewOf(call, neverReused);
  return view.kind === "refused" ? view : { reasonKey: null, reasonFacts: [] };
};

// ---- How a write ended, in the form ---------------------------------------------

/**
 * The line under a form for how its last call ended: saved or already there,
 * refused with what was kept, incomplete with what to fill in, or a call that
 * failed or was not seen to settle. A refusal is worded by the backend's
 * reason key and facts and never by its English.
 */
export function WriteLine({
  call,
  fields,
  saved,
}: {
  call: SetupCall<unknown> | null;
  fields: readonly FormField[];
  /** The words for a write that landed, new and already there; null where a
   * landing is not worth a line, as for a forecast. */
  saved: {
    done: string;
    reused: string;
    reusedOf: (result: unknown) => boolean;
  } | null;
}) {
  const t = useStrings();
  const view = viewOf(call, saved?.reusedOf ?? neverReused);
  const kept = t("desktop.ledger.assets.write.kept");
  if (view.kind === "none") return null;
  if (view.kind === "saved")
    return saved ? (
      <Alert
        tone="success"
        icon={<Icon name="check" />}
        className="ledger-asset-saved"
      >
        {view.reused ? saved.reused : saved.done}
      </Alert>
    ) : null;
  if (view.kind === "refused") {
    if (view.code === INCOMPLETE && view.missing.length > 0)
      return (
        <Alert
          tone="warning"
          role="alert"
          icon={<Icon name="alert" />}
          className="ledger-asset-incomplete"
        >
          {t(ASSET_KEYS.write.incomplete, {
            fields: missingLabels(t, fields, view.missing),
          })}
        </Alert>
      );
    return (
      <Alert
        tone="danger"
        role="alert"
        icon={<Icon name="refused" />}
        className="ledger-asset-refused"
      >
        <span>{refusalWord(t, view) ?? t(ASSET_KEYS.write.refused)}</span>
        <span className="text-sm text-muted-foreground">{kept}</span>
      </Alert>
    );
  }
  return (
    <>
      <CallLine call={call} />
      {view.kind === "failed" && (
        <p className="text-sm text-muted-foreground">{kept}</p>
      )}
    </>
  );
}

// ---- The acts --------------------------------------------------------------------

export type ActKind =
  "element" | "descriptor" | "correction" | "baja" | "baja_change";

type Context = {
  port: LedgerPort;
  assetId: string;
  asset: AssetListRow | null;
  values: FormValues;
  /** The request the form's values make, where the act builds one. */
  create: ActivityAssetCreateRequest | null;
  correct: ActivityAssetCorrectRequest | null;
  /** The revision a change of the baja supersedes. */
  base: RevisionBase | null;
  /** Whether the baja is to be taken out. */
  removing: boolean;
  /** How many descriptions the element's history holds once this one lands. */
  descriptions: number;
};

type Act = {
  title: string;
  submit: string;
  /** What a write that landed says. */
  done: string;
  /** Only what changed is stated, the rest left as the record has it. */
  delta: boolean;
  /** Asks again before sending: what a baja does is not easily undone. */
  confirms: boolean;
  send(context: Context): Promise<SetupCall<unknown>>;
  landing(context: Context): LandingCheck;
};

/** The revision a correction supersedes: the one the element stands at when
 * the form sends it. */
const supersededRevision = (asset: AssetListRow | null) =>
  asset?.revision_number ?? 0;

const never = async (): Promise<SetupCall<unknown>> => ({
  kind: "failed",
  code: "unavailable",
  reason: null,
});

const ACTS: Record<ActKind, Act> = {
  element: {
    title: ASSET_KEYS.action.add,
    submit: "desktop.ledger.assets.submit.create",
    done: "desktop.ledger.assets.write.element_added",
    delta: false,
    confirms: false,
    send: (c) =>
      c.create === null
        ? never()
        : setupCall(c.port, "ledger.actividad-asset.create", c.create, true),
    landing: (c) => elementLanding(c.port, c.assetId),
  },
  descriptor: {
    title: ASSET_KEYS.action.describe,
    submit: "desktop.ledger.form.save",
    done: "desktop.ledger.assets.write.described",
    delta: false,
    confirms: false,
    send: (c) =>
      setupCall(
        c.port,
        "ledger.actividad-asset.describe",
        describeRequest(c.assetId, c.values),
        true,
      ),
    landing: (c) => descriptorLanding(c.port, c.assetId, c.descriptions),
  },
  correction: {
    title: ASSET_KEYS.action.correct,
    submit: "desktop.ledger.assets.submit.correct",
    done: "desktop.ledger.assets.write.corrected",
    delta: true,
    confirms: false,
    send: (c) =>
      c.correct === null
        ? never()
        : setupCall(c.port, "ledger.actividad-asset.correct", c.correct, true),
    landing: (c) =>
      correctionLanding(c.port, c.assetId, supersededRevision(c.asset)),
  },
  baja: {
    title: ASSET_KEYS.action.dispose,
    submit: ASSET_KEYS.action.dispose,
    done: "desktop.ledger.assets.write.baja_recorded",
    delta: false,
    confirms: true,
    send: (c) =>
      setupCall(
        c.port,
        "ledger.actividad-asset.dispose",
        { asset_id: c.assetId, disposal: disposalOf(c.values)! },
        true,
      ),
    landing: (c) =>
      correctionLanding(c.port, c.assetId, supersededRevision(c.asset)),
  },
  baja_change: {
    title: "desktop.ledger.assets.action.change_baja",
    submit: "desktop.ledger.assets.baja.change_submit",
    done: "desktop.ledger.assets.write.baja_changed",
    delta: false,
    confirms: true,
    send: async (c) => {
      const disposal = c.removing ? null : disposalOf(c.values);
      const request = bajaRequest(c.base, disposal);
      return request === null || (!c.removing && disposal === null)
        ? never()
        : setupCall(c.port, "ledger.actividad-asset.correct", request, true);
    },
    landing: (c) =>
      correctionLanding(c.port, c.assetId, supersededRevision(c.asset)),
  },
};

/** The year of an ISO date, or null while the text is not one. */
const yearOfDate = (text: string): number | null =>
  /^\d{4}-\d{2}-\d{2}$/.test(text) ? Number(text.slice(0, 4)) : null;

/** What a form asks the person to confirm before it sends, if it does. */
type Confirming = "save" | "remove" | null;

/**
 * The form of an act on the register, drawn from what the backend serves for
 * it. Adding an element mints its opaque id once, when the form opens, and
 * never shows it. The send is always available: with something missing it
 * marks what to fill in and sends nothing. A write that was not seen to
 * settle holds the page's writes and is never sent again; a refusal keeps
 * what was typed. `children` sit between the fields and the buttons.
 */
export function AssetForm({
  port,
  reader,
  locale,
  taxYear = null,
  kind,
  assetId,
  supersede = NO_CLAIMS,
  onClose,
  onWritten,
  onAdded,
  children,
}: ActProps & {
  kind: ActKind;
  /** The element acted on; null when adding one. */
  assetId: string | null;
  /** Effective claims recorded again in the same write, for a correction. */
  supersede?: readonly string[];
  /** Drawn between the fields and the buttons; given a function, it is told
   * what the form states now and whether that could be sent. */
  children?:
    ReactNode | ((form: { values: FormValues; ready: boolean }) => ReactNode);
}) {
  const t = useStrings();
  const act = ACTS[kind];
  const [minted] = useState(() =>
    kind === "element" ? crypto.randomUUID() : "",
  );
  const id = kind === "element" ? minted : (assetId ?? "");
  const asset = useAssetRow(port, reader, kind === "element" ? null : id);
  const history = useLedgerRead(
    port,
    reader,
    "ledger.actividad-asset.timeline",
    kind === "descriptor" && id !== "" ? { asset_id: id } : null,
    id,
  );
  const events =
    history.read?.kind === "done" ? (history.read.result.events ?? []) : null;
  // A correction supersedes the revision the register holds now.
  const changesRevision = kind === "correction" || kind === "baja_change";
  const inspected = useLedgerRead(
    port,
    reader,
    "ledger.actividad-asset.inspect",
    (changesRevision || kind === "descriptor") && id !== ""
      ? { asset_id: id }
      : null,
    id,
  );
  const base: RevisionBase | null =
    inspected.read?.kind === "done" && inspected.read.result.revisions
      ? (inspected.read.result.revisions.at(-1) ?? null)
      : null;

  // The options the registry admits depend on the element's kind and year,
  // which a new element states in its own form.
  const [typed, setTyped] = useState({ asset_kind: "", in_service_date: "" });
  const optionsKind =
    kind === "element" ? typed.asset_kind : (asset.row?.asset_kind ?? "");
  // A baja is read for the year the page stands on: the reasons it offers do
  // not depend on the year the element came into service.
  const optionsYear =
    kind === "element"
      ? yearOfDate(typed.in_service_date)
      : kind === "baja" || kind === "baja_change"
        ? (taxYear ?? yearOfDate(asset.row?.in_service_date ?? ""))
        : (yearOfDate(
            typed.in_service_date || asset.row?.in_service_date || "",
          ) ?? taxYear);
  const wantsOptions =
    (kind === "element" ||
      kind === "correction" ||
      kind === "baja" ||
      kind === "baja_change") &&
    optionsKind !== "" &&
    optionsYear !== null &&
    optionsYear !== undefined;
  const options = useLedgerRead(
    port,
    reader,
    "ledger.actividad-asset.form-options",
    wantsOptions ? { asset_kind: optionsKind, tax_year: optionsYear } : null,
    `${kind}:${optionsKind}:${optionsYear}`,
  );
  const loaded: FormOptions | null =
    options.read?.kind === "done" ? options.read.result.options : null;

  const context = {
    kind,
    row: asset.row,
    descriptor: events === null ? null : currentDescriptor(events),
    revision: base?.revision ?? null,
    tokens: familyTokens,
    options: loaded,
  };
  // The form starts from the record; the fields it draws follow what is typed.
  const form = useFieldsDraft(initialOf(context, fieldsFor(context, {})));
  const fields = fieldsFor(context, form.draft);
  const formRef = useRef<HTMLFormElement>(null);
  useFocusOnOpen(formRef, true);
  const purchases = useLedgerRead(
    port,
    reader,
    "ledger.actividad-asset.acquisition-candidates",
    fields.some((field) => field.control === "candidate") ? {} : null,
    id,
  );
  const candidates =
    purchases.read?.kind === "done"
      ? (purchases.read.result.candidates ?? NO_CANDIDATES)
      : NO_CANDIDATES;
  const write = useSetupWrite(facts(t, [t(act.title), asset.row?.name]));
  useSetupDraft(form.dirty);

  // A new element starts on the first way of acquiring one the backend offers.
  const { set: setDraft } = form;
  const shape = form.draft.acquisition_shape ?? "";
  const firstShape = loaded?.acquisition_shapes?.[0] ?? "";
  useEffect(() => {
    if (kind === "element" && shape === "" && firstShape !== "")
      setDraft({ acquisition_shape: firstShape });
  }, [kind, shape, firstShape, setDraft]);

  const picked = candidates.find(
    (candidate) => candidate.transaction_id === form.draft.acquisition,
  );
  const further = candidates.find(
    (candidate) => candidate.transaction_id === form.draft[FURTHER_PURCHASE],
  );
  usePurchasePrefill({
    active: kind === "descriptor",
    purchase: base === null ? null : purchaseOf(base.revision),
    stated: context.descriptor,
    draft: form.draft,
    set: setDraft,
  });
  const offered = useAssetSuggestions({
    kind,
    fields,
    draft: form.draft,
    set: setDraft,
    purchase: picked,
  });
  const answered = answer(fields, form.draft, act.delta ? form.initial : null);
  const view = viewOf(write.last, neverReused);
  const [tried, setTried] = useState(false);
  const [confirming, setConfirming] = useState<Confirming>(null);
  // A fact every request of the act states, and the form still lacks.
  const lacking = act.delta
    ? []
    : fields.filter(
        (field) =>
          field.required && (answered.values[field.key] ?? null) === null,
      );
  const toFill = [...lacking.map((field) => field.key), ...answered.cleared];
  const missing = new Set([
    ...(view.kind === "refused" ? view.missing.map(formKeyOf) : []),
    ...(tried ? toFill : []),
  ]);
  const needsRow = changesRevision || kind === "baja";
  const stating = {
    assetId: id,
    regime: loaded?.regime ?? null,
    candidate: picked ?? null,
    further: further ?? null,
    base,
    options: loaded,
  };
  const create =
    kind === "element" ? createRequest(answered.values, stating) : null;
  const correct =
    kind === "correction"
      ? correctRequest(answered.values, stating, supersede)
      : null;
  const changed =
    Object.keys(answered.values).length > 0 || answered.cleared.length > 0;
  const ready =
    Object.keys(answered.problems).length === 0 &&
    toFill.length === 0 &&
    (!needsRow || asset.row !== null) &&
    (kind !== "element" || create !== null) &&
    (kind !== "correction" || (correct !== null && changed)) &&
    (kind !== "baja" || disposalOf(answered.values) !== null) &&
    (kind !== "baja_change" ||
      (base !== null && disposalOf(answered.values) !== null));

  const onField = (field: FormField, value: string) => {
    if (field.key === "asset_kind" || field.key === "in_service_date")
      setTyped((current) => ({ ...current, [field.key]: value }));
    form.set({
      [field.key]: value,
      // A purchase fills the figures it knows; what it does not know stays
      // as it is, and is never read as zero.
      ...(field.control === "candidate" && field.key === "acquisition"
        ? Object.fromEntries(
            Object.entries(
              purchaseValues(
                candidates.find(
                  (candidate) => candidate.transaction_id === value,
                ),
              ),
            ).filter((entry): entry is [string, string] => entry[1] !== null),
          )
        : {}),
    });
  };

  const send = async (removing = false) => {
    if (write.busy) return;
    const sending: Context = {
      port,
      assetId: id,
      asset: asset.row,
      values: answered.values,
      create,
      correct,
      base,
      removing,
      descriptions:
        (events ?? []).filter((event) => event.kind === "descriptor").length +
        1,
    };
    const done = await write.run(() => act.send(sending), act.landing(sending));
    setConfirming(null);
    if (viewOf(done, neverReused).kind === "saved") {
      setTried(false);
      // What the record states has changed: read it again.
      history.reload();
      inspected.reload();
      options.reload();
      asset.reload();
      onWritten?.();
      if (kind === "element") onAdded?.(id);
    }
  };

  const submit = () => {
    if (write.busy) return;
    if (!ready) {
      setTried(true);
      return;
    }
    if (act.confirms) setConfirming("save");
    else void send();
  };

  const waiting =
    kind === "element" &&
    (typed.asset_kind === "" || typed.in_service_date === "")
      ? t("desktop.ledger.assets.write.options_wait")
      : null;
  const whollyShare = loaded?.basis_stages
    .flatMap((stage) => stage.wholly_business_facts)
    .find((found) => found.fact === "business_use_share");
  const whollyBusiness = whollyShare
    ? t("desktop.ledger.assets.field.wholly_business_hint", {
        share: formatPercent(locale, whollyShare.value.decimal, {
          unit: "fraction",
        }),
      })
    : null;
  const name = asset.row?.name ?? t(ASSET_KEYS.list.no_name);
  const bajaDate = disposalOf(answered.values)?.disposal_date ?? "";
  const stillToFill = listed(
    t,
    toFill.map((key) => {
      const found = fields.find((field) => field.key === key);
      return found ? t(found.label_key) : key;
    }),
  );

  return (
    <Panel
      title={
        kind === "element"
          ? t(act.title)
          : facts(t, [t(act.title), asset.row?.name])
      }
      className={`ledger-asset-form ledger-asset-form-${kind}`}
    >
      <form
        ref={formRef}
        noValidate
        className="flex flex-col gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        <FieldsGrid
          fields={offered}
          options={loaded}
          draft={form.draft}
          onField={onField}
          problems={answered.problems}
          missing={missing}
          cleared={new Set(answered.cleared)}
          candidates={candidates}
          purchaseKnown={
            new Set(
              picked === undefined
                ? []
                : Object.entries(purchaseValues(picked))
                    .filter(([, known]) => known === null)
                    .map(([key]) => key),
            )
          }
          notes={{
            opening_status: t(
              "desktop.ledger.assets.field.opening_status_hint",
            ),
            business_use_share: whollyBusiness,
            method: waiting,
            acquisition_shape: waiting,
            non_deductible_iva:
              picked === undefined
                ? null
                : keyedText(t, picked.non_deductible_iva_state_key, "") || null,
            acquisition:
              picked !== undefined &&
              (picked.invoice_evidence_id === null ||
                picked.evidence_fingerprint === null)
                ? t("desktop.ledger.assets.field.acquisition_no_evidence", {
                    documents: t("desktop.ledger.section.documents"),
                  })
                : null,
          }}
          locale={locale}
        />
        {options.read !== null && options.read.kind !== "done" && (
          <OptionsRead call={options.read} />
        )}
        {options.read?.kind === "done" &&
          options.read.result.outcome === "refused" && (
            <OptionsRead call={options.read} />
          )}
        {typeof children === "function"
          ? children({ values: answered.values, ready })
          : children}
        {confirming !== null ? (
          <Alert
            tone="warning"
            role="alertdialog"
            icon={<Icon name="alert" />}
            className="ledger-asset-confirm"
          >
            <span>
              {confirming === "remove"
                ? t("desktop.ledger.assets.baja.remove_confirm", { name })
                : t(
                    kind === "baja_change"
                      ? "desktop.ledger.assets.baja.change_confirm"
                      : "desktop.ledger.assets.baja.confirm",
                    {
                      name,
                      date: formatDay(locale, bajaDate),
                    },
                  )}
            </span>
            <span className="flex flex-wrap gap-2">
              <Button
                type="button"
                size="sm"
                variant="ghost"
                className="ledger-asset-confirm-back"
                aria-disabled={write.busy || undefined}
                onClick={() => {
                  if (!write.busy) setConfirming(null);
                }}
              >
                {t("desktop.ledger.assets.baja.confirm_back")}
              </Button>
              <WriteHold>
                <Button
                  type="button"
                  size="sm"
                  className="ledger-asset-confirm-yes"
                  aria-disabled={write.busy || undefined}
                  onClick={() => void send(confirming === "remove")}
                >
                  {write.busy
                    ? t("desktop.ledger.form.saving")
                    : t(
                        confirming === "remove"
                          ? "desktop.ledger.assets.baja.remove_yes"
                          : "desktop.ledger.assets.baja.confirm_yes",
                      )}
                </Button>
              </WriteHold>
            </span>
          </Alert>
        ) : (
          <div className="flex flex-wrap gap-2">
            {onClose && (
              <Button
                type="button"
                size="sm"
                variant="ghost"
                aria-disabled={write.busy || undefined}
                onClick={() => {
                  if (!write.busy) onClose();
                }}
              >
                {t("desktop.ledger.form.cancel")}
              </Button>
            )}
            {kind === "baja_change" && (
              <WriteHold>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="ledger-asset-remove"
                  aria-disabled={write.busy || base === null || undefined}
                  onClick={() => {
                    if (!write.busy && base !== null) setConfirming("remove");
                  }}
                >
                  {t("desktop.ledger.assets.baja.remove")}
                </Button>
              </WriteHold>
            )}
            <WriteHold>
              <Button
                type="submit"
                size="sm"
                className="ledger-asset-submit"
                aria-disabled={write.busy || undefined}
              >
                {write.busy ? t("desktop.ledger.form.saving") : t(act.submit)}
              </Button>
            </WriteHold>
          </div>
        )}
        {tried &&
          !ready &&
          confirming === null &&
          (toFill.length > 0 ||
            Object.keys(answered.problems).length > 0 ||
            (kind === "correction" && !changed)) && (
            <p
              role="alert"
              className="ledger-asset-missing flex items-start gap-1.5 text-sm text-destructive"
            >
              <Icon name="alert" size="xs" className="mt-0.5" />
              <span>
                {toFill.length > 0
                  ? t("desktop.ledger.assets.write.missing", {
                      fields: stillToFill,
                    })
                  : Object.keys(answered.problems).length > 0
                    ? t("desktop.ledger.assets.write.fix_marked")
                    : t("desktop.ledger.assets.write.nothing_changed")}
              </span>
            </p>
          )}
        <WriteLine
          call={write.last}
          fields={fields}
          saved={{
            done: t(act.done),
            reused: t(ASSET_KEYS.write.reused),
            reusedOf: neverReused,
          }}
        />
      </form>
    </Panel>
  );
}
