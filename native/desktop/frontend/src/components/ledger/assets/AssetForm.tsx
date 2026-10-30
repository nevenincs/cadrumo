import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { facts, labelled } from "../../../shell/compose";
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
  FormOptions,
  TableGroup,
} from "../../../shell/ledgerSetup";
import { tokensOf, useStrings, type Translate } from "../../../shell/strings";
import { useWritePause, WriteHold, type LandingCheck } from "../WritePause";
import { amountText, dateText, percentText } from "../movements/movementWords";
import {
  CallLine,
  ChoiceField,
  FormGrid,
  Panel,
  Reading,
  TextField,
  useSetupDraft,
  useSetupWrite,
} from "../setup/SetupParts";
import { setupCall, type SetupCall } from "../setup/setupModel";
import { grammarText } from "../setup/setupWords";
import {
  answer,
  fieldsFor,
  initialOf,
  type FormDraft,
  type FormField,
  type FormValues,
} from "./assetFields";
import {
  correctRequest,
  createRequest,
  type RevisionBase,
} from "./assetRevision";
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
};

const NO_CANDIDATES: readonly AcquisitionCandidate[] = [];
const NO_CLAIMS: readonly string[] = [];
const NO_NOTES: Readonly<Record<string, string | null>> = {};

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
 * drawn again, so what was typed is kept through a re-read. */
export function useFieldsDraft(initial: FormDraft) {
  const [held, setHeld] = useState<{
    signature: string;
    initial: FormDraft;
  } | null>(null);
  const [draft, setDraft] = useState<FormDraft>({});
  const signature = JSON.stringify(initial);
  if (held === null || signature !== held.signature) {
    setHeld({ signature, initial });
    setDraft(initial);
  }
  return {
    draft,
    initial: held?.initial ?? initial,
    /** Anything typed that is not what the record states. */
    dirty: Object.keys(draft).some(
      (key) => draft[key] !== ((held?.initial ?? initial)[key] ?? ""),
    ),
    set(changes: FormDraft) {
      setDraft((current) => ({ ...current, ...changes }));
    },
  };
}

/** What the registry allows a table class, as one line: the corridor of its
 * coefficient and its maximum period. */
const corridorText = (t: Translate, locale: string, group: TableGroup) => {
  const text = ASSET_KEYS.plan.limits;
  return facts(t, [
    labelled(
      t,
      t(text.maximum_coefficient),
      percentText(locale, group.maximum_coefficient.decimal),
    ),
    labelled(
      t,
      t(text.minimum_coefficient),
      percentText(locale, group.minimum_coefficient.decimal),
    ),
    labelled(
      t,
      t(text.maximum_period),
      t(text.period_years, { years: group.maximum_period_years.decimal }),
    ),
  ]);
};

/**
 * The fields of an act, each drawn by its control. The form decides nothing
 * about them: their choices, bounds and starting values are the backend's. A
 * field the backend named as still to fill in is marked until something is
 * typed.
 */
export function FieldsGrid({
  fields,
  options,
  draft,
  onField,
  problems,
  missing,
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
  missing: ReadonlySet<string>;
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
        const hint =
          [
            field.hint_key ? t(field.hint_key) : null,
            field.key === "authority_class_key"
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
              ? t("desktop.ledger.assets.field.acquisition_none")
              : null,
            fillIn ? t(ASSET_KEYS.write.fill_in) : null,
          ]
            .filter(Boolean)
            .join(" ") || undefined;
        const label = t(field.label_key);
        const choose = (value: string) => onField(field, value);
        return (
          <div key={field.key} data-field={field.key} className="contents">
            {field.control === "text" ||
            field.control === "date" ||
            field.control === "amount" ||
            field.control === "share" ||
            field.control === "whole" ? (
              <TextField
                label={label}
                name={field.key}
                value={raw}
                onValue={choose}
                required={field.required}
                hint={hint}
                error={
                  problem
                    ? grammarText(t, problem)
                    : fillIn
                      ? t(ASSET_KEYS.write.fill_in)
                      : null
                }
                inputMode={
                  field.control === "amount" || field.control === "share"
                    ? "decimal"
                    : field.control === "whole"
                      ? "numeric"
                      : "text"
                }
                maxLength={field.control === "text" ? 200 : 32}
              />
            ) : (
              <ChoiceField
                label={label}
                value={raw}
                onValue={choose}
                placeholder={t("desktop.ledger.form.choose")}
                hint={hint}
                options={
                  field.control === "candidate"
                    ? candidates.map((candidate) => ({
                        value: candidate.transaction_id,
                        label: t(
                          "desktop.ledger.assets.field.acquisition_option",
                          {
                            description: candidate.description,
                            date: dateText(locale, candidate.booked_date, true),
                            amount: amountText(
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
                          label:
                            option.family !== null
                              ? tokenWord(t, option.family, option.token)
                              : (option.label ?? t(ASSET_KEYS.unrecognised)),
                        }))
                }
              />
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

export type ActKind = "element" | "descriptor" | "correction" | "baja";

type Context = {
  port: LedgerPort;
  assetId: string;
  asset: AssetListRow | null;
  values: FormValues;
  /** The request the form's values make, where the act builds one. */
  create: ActivityAssetCreateRequest | null;
  correct: ActivityAssetCorrectRequest | null;
  /** How many descriptions the element's history holds once this one lands. */
  descriptions: number;
};

type Act = {
  title: string;
  submit: string;
  /** The backend's kind of record the write adds, which words it. */
  event: string;
  /** Only what changed is stated, the rest left as the record has it. */
  delta: boolean;
  send(context: Context): Promise<SetupCall<unknown>>;
  landing(context: Context): LandingCheck;
};

/** The revision a correction would make, once it lands. */
const nextRevision = (asset: AssetListRow | null) =>
  (asset?.revision_number ?? 0) + 1;

const never = async (): Promise<SetupCall<unknown>> => ({
  kind: "failed",
  code: "unavailable",
  reason: null,
});

const ACTS: Record<ActKind, Act> = {
  element: {
    title: ASSET_KEYS.action.add,
    submit: "desktop.ledger.assets.submit.create",
    event: "revision",
    delta: false,
    send: (c) =>
      c.create === null
        ? never()
        : setupCall(c.port, "ledger.actividad-asset.create", c.create, true),
    landing: (c) => elementLanding(c.port, c.assetId),
  },
  descriptor: {
    title: ASSET_KEYS.action.describe,
    submit: "desktop.ledger.form.save",
    event: "descriptor",
    delta: false,
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
    event: "revision",
    delta: true,
    send: (c) =>
      c.correct === null
        ? never()
        : setupCall(c.port, "ledger.actividad-asset.correct", c.correct, true),
    landing: (c) => correctionLanding(c.port, c.assetId, nextRevision(c.asset)),
  },
  baja: {
    title: ASSET_KEYS.action.dispose,
    submit: ASSET_KEYS.action.dispose,
    event: "baja",
    delta: false,
    send: (c) =>
      setupCall(
        c.port,
        "ledger.actividad-asset.dispose",
        { asset_id: c.assetId, disposal: disposalOf(c.values)! },
        true,
      ),
    landing: (c) => correctionLanding(c.port, c.assetId, nextRevision(c.asset)),
  },
};

/** The year of an ISO date, or null while the text is not one. */
const yearOfDate = (text: string): number | null =>
  /^\d{4}-\d{2}-\d{2}$/.test(text) ? Number(text.slice(0, 4)) : null;

/**
 * The form of an act on the register, drawn from what the backend serves for
 * it. Adding an element mints its opaque id once, when the form opens, and
 * never shows it. A write that was not seen to settle holds the page's writes
 * and is never sent again; a refusal keeps what was typed. `children` sit
 * between the fields and the buttons.
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
  const inspected = useLedgerRead(
    port,
    reader,
    "ledger.actividad-asset.inspect",
    kind === "correction" && id !== "" ? { asset_id: id } : null,
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
  const optionsYear =
    (kind === "element"
      ? yearOfDate(typed.in_service_date)
      : yearOfDate(
          typed.in_service_date || asset.row?.in_service_date || "",
        )) ?? taxYear;
  const wantsOptions =
    (kind === "element" || kind === "correction") &&
    optionsKind !== "" &&
    optionsYear !== null;
  const options = useLedgerRead(
    port,
    reader,
    "ledger.actividad-asset.form-options",
    wantsOptions ? { asset_kind: optionsKind, tax_year: optionsYear } : null,
    `${kind}:${optionsKind}:${optionsYear}`,
  );
  const loaded =
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

  const picked = candidates.find(
    (candidate) => candidate.transaction_id === form.draft.acquisition,
  );
  const answered = answer(fields, form.draft, act.delta ? form.initial : null);
  const view = viewOf(write.last, neverReused);
  const missing = new Set(view.kind === "refused" ? view.missing : []);
  const needsRow = kind === "correction" || kind === "baja";
  const stating = {
    assetId: id,
    regime: loaded?.regime ?? null,
    candidate: picked ?? null,
    base,
  };
  const create =
    kind === "element" ? createRequest(answered.values, stating) : null;
  const correct =
    kind === "correction"
      ? correctRequest(answered.values, stating, supersede)
      : null;
  // A fact every request of the act states, and the form still lacks.
  const lacking = act.delta
    ? []
    : fields.filter(
        (field) =>
          field.required && (answered.values[field.key] ?? null) === null,
      );
  const ready =
    Object.keys(answered.problems).length === 0 &&
    lacking.length === 0 &&
    (!needsRow || asset.row !== null) &&
    (kind !== "element" || create !== null) &&
    (kind !== "correction" ||
      (correct !== null && Object.keys(answered.values).length > 0)) &&
    (kind !== "baja" || disposalOf(answered.values) !== null);

  const onField = (field: FormField, value: string) => {
    if (field.key === "asset_kind" || field.key === "in_service_date")
      setTyped((current) => ({ ...current, [field.key]: value }));
    form.set({
      [field.key]: value,
      // A purchase fills the figures it knows; what it does not know stays
      // as it is, and is never read as zero.
      ...(field.control === "candidate"
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

  const send = async () => {
    if (!ready || write.busy) return;
    const sending: Context = {
      port,
      assetId: id,
      asset: asset.row,
      values: answered.values,
      create,
      correct,
      descriptions:
        (events ?? []).filter((event) => event.kind === "descriptor").length +
        1,
    };
    const done = await write.run(() => act.send(sending), act.landing(sending));
    if (viewOf(done, neverReused).kind === "saved") {
      // What the record states has changed: read it again.
      history.reload();
      inspected.reload();
      options.reload();
      asset.reload();
      onWritten?.();
    }
  };

  return (
    <Panel
      title={t(act.title)}
      className={`ledger-asset-form ledger-asset-form-${kind}`}
    >
      <form
        noValidate
        className="flex flex-col gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          void send();
        }}
      >
        <FieldsGrid
          fields={fields}
          options={loaded}
          draft={form.draft}
          onField={onField}
          problems={answered.problems}
          missing={missing}
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
            non_deductible_iva:
              picked === undefined
                ? null
                : keyedText(t, picked.non_deductible_iva_state_key, "") || null,
            acquisition:
              picked !== undefined &&
              (picked.invoice_evidence_id === null ||
                picked.evidence_fingerprint === null)
                ? t("desktop.ledger.assets.field.acquisition_no_evidence")
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
          <WriteHold>
            <Button
              type="submit"
              size="sm"
              className="ledger-asset-submit"
              aria-disabled={!ready || write.busy || undefined}
            >
              {write.busy ? t("desktop.ledger.form.saving") : t(act.submit)}
            </Button>
          </WriteHold>
        </div>
        <WriteLine
          call={write.last}
          fields={fields}
          saved={{
            done: tokenWord(t, "event_kind", act.event),
            reused: t(ASSET_KEYS.write.reused),
            reusedOf: neverReused,
          }}
        />
      </form>
    </Panel>
  );
}
