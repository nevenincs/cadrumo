import { useState } from "react";
import { IntegerEditor } from "@/components/editors/IntegerEditor";
import { TextEditor } from "@/components/editors/TextEditor";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { facts } from "@/shell/compose";
import {
  servedRefusalWords,
  type LedgerErrorDetail,
} from "../../../shell/ledger";
import type {
  CounterpartyFilingName as StatedFilingName,
  CounterpartyFilingNamePart,
  CounterpartyFilingNameSlot,
  CounterpartyFilingNameSlotRefusal,
  LedgerCounterpartyResult,
} from "../../../shell/ledgerClassificationSetup";
import {
  COUNTERPARTY_KINDS,
  type CounterpartyKind,
} from "../../../shell/counterpartyAsk";
import type { OutputLanguage } from "../../../shell/ledger";
import { servedRefusal } from "../../../shell/refusal";
import { RefusalNotice } from "../../RefusalNotice";
import { formatTime } from "../../../shared/dateFormats";
import { useStrings } from "../../../shell/strings";
import { WriteHold, type Landing } from "../WritePause";
import { EditorField } from "./EditorField";
import { CallLine, ChoiceField, FormGrid, useSetupWrite } from "./SetupParts";
import type { SetupProps } from "./setupProps";
import { setupCall } from "./setupModel";

type RenderingDraft = { key: number; width: string; text: string };
type Draft = {
  kind: string;
  primer: string;
  segundo: string;
  noSecond: boolean;
  nombre: string;
  razon: string;
  renderings: RenderingDraft[];
};

let nextKey = 0;
const draftOf = (
  stated: StatedFilingName | null | undefined,
  initialKind: CounterpartyKind | null,
): Draft => ({
  kind: stated?.party_kind ?? initialKind ?? "",
  primer: stated?.primer_apellido ?? "",
  segundo: stated?.segundo_apellido ?? "",
  noSecond: stated?.no_second_surname ?? false,
  nombre: stated?.nombre ?? "",
  razon: stated?.razon_social ?? "",
  renderings: (stated?.renderings ?? []).map((rendering) => ({
    key: nextKey++,
    width: String(rendering.width),
    text: rendering.text,
  })),
});

/** How the export files one slot: whole, by the stated rendering for its
 * width, or not, for the served reason. */
type SlotState = "fits" | "uses_rendering" | CounterpartyFilingNameSlotRefusal;

/** Slots of one width that the export files the same way, with the
 * editions they belong to, in served order. */
type SlotGroup = {
  width: number;
  state: SlotState;
  editions: { words: string; language: OutputLanguage }[];
};

const SLOT_STATE_LOCALE_KEYS: Record<SlotState, string> = {
  fits: "desktop.ledger.counterparty.filing_name.slot.fits",
  uses_rendering: "desktop.ledger.counterparty.filing_name.slot.uses_rendering",
  missing: "desktop.ledger.counterparty.filing_name.slot.missing",
  single_surname: "desktop.ledger.counterparty.filing_name.slot.single_surname",
  too_wide: "desktop.ledger.counterparty.filing_name.slot.too_wide",
};

const slotState = (slot: CounterpartyFilingNameSlot): SlotState =>
  slot.refusal ?? (slot.uses_rendering ? "uses_rendering" : "fits");

/** The served slots, one row per width and outcome, each edition once. */
export function slotGroups(
  slots: readonly CounterpartyFilingNameSlot[],
): SlotGroup[] {
  const groups = new Map<string, SlotGroup>();
  for (const slot of slots) {
    const state = slotState(slot);
    const key = `${slot.width}:${state}`;
    const group = groups.get(key) ?? { width: slot.width, state, editions: [] };
    if (!group.editions.some((held) => held.words === slot.edition_words))
      group.editions.push({
        words: slot.edition_words,
        language: slot.edition_words_language,
      });
    groups.set(key, group);
  }
  return [...groups.values()];
}

const savedWidth = (width: string): number | null => {
  const read = Number(width);
  return width.trim() !== "" && Number.isInteger(read) && read > 0
    ? read
    : null;
};

/**
 * The name a counterparty is filed under in the informative returns that list
 * it, stated once for it: a natural person's surnames and given name, or an
 * entity's company name, and shorter renderings for fields too narrow for it.
 * The view serves every export field the name is filed into, with its width
 * and whether the stated name fills it, and the longest each part can be to
 * fit whole; a field the name is too wide for offers a rendering of its
 * width. What the name is checked against is the backend's; nothing is
 * decided here.
 */
export function CounterpartyFilingName({
  port,
  result,
  country,
  actor,
  initialKind = null,
  onSaved,
}: Pick<SetupProps, "port"> & {
  result: LedgerCounterpartyResult;
  country: string;
  /** Who states it, as typed for the counterparty's other answers. */
  actor: string;
  /** The kind a way out already bound, for a name not yet stated. */
  initialKind?: CounterpartyKind | null;
  onSaved(): Promise<void> | void;
}) {
  const t = useStrings();
  const locale = t.locale ?? "en";
  const write = useSetupWrite(
    t("desktop.ledger.counterparty.filing_name.title"),
  );
  const stated = result.filing_name ?? null;
  const [draft, setDraft] = useState<Draft>(() => draftOf(stated, initialKind));
  const groups = slotGroups(result.filing_name_slots ?? []);
  // A served width the stated name is too wide for, and no rendering is
  // drafted for yet, is offered as a rendering of that width.
  const tooWide = [
    ...new Set(
      groups
        .filter((group) => group.state === "too_wide")
        .map((group) => group.width),
    ),
  ].filter(
    (width) =>
      !draft.renderings.some(
        (rendering) => savedWidth(rendering.width) === width,
      ),
  );
  const limits = new Map(
    (result.filing_name_part_limits ?? []).map((limit) => [
      limit.part,
      limit.max_length,
    ]),
  );
  const limitHint = (part: CounterpartyFilingNamePart) => {
    const count = limits.get(part);
    return count === undefined
      ? undefined
      : t("desktop.ledger.counterparty.filing_name.part_limit", { count });
  };
  const patch = (next: Partial<Draft>) =>
    setDraft((held) => ({ ...held, ...next }));
  const natural = draft.kind === "natural_person";
  const entity = draft.kind === "entity";
  const widths = draft.renderings.map((rendering) =>
    savedWidth(rendering.width),
  );
  const complete = natural
    ? draft.primer.trim() !== "" &&
      draft.nombre.trim() !== "" &&
      (draft.noSecond
        ? draft.segundo.trim() === ""
        : draft.segundo.trim() !== "")
    : entity && draft.razon.trim() !== "";
  const renderingsReady = draft.renderings.every(
    (rendering, at) => widths[at] !== null && rendering.text.trim() !== "",
  );
  const canSave =
    complete && renderingsReady && actor.trim() !== "" && !write.busy;
  // A view re-reads the stored name, so an uncertain write is told by it.
  const untold = async (): Promise<Landing> => "untold";
  const refused = write.last?.kind === "refused" ? write.last : null;
  // A refusal is shown as served: its words, then its ways out in order.
  const refusalDetail = refused
    ? (refused.detail as LedgerErrorDetail | null)
    : null;
  const served =
    refused &&
    (servedRefusalWords(refusalDetail) !== null ||
      refusalDetail?.precondition_verdict_json)
      ? servedRefusal(servedRefusalWords(refusalDetail), refusalDetail)
      : null;

  const save = async () => {
    if (!canSave) return;
    const done = await write.run(
      () =>
        setupCall(
          port,
          "ledger.counterparty",
          {
            action: "filing_name",
            tax_identifier: result.tax_identifier,
            country_code: country || null,
            party_kind: draft.kind,
            primer_apellido: natural ? draft.primer.trim() : null,
            segundo_apellido:
              natural && !draft.noSecond ? draft.segundo.trim() : null,
            no_second_surname: natural && draft.noSecond,
            nombre: natural ? draft.nombre.trim() : null,
            razon_social: entity ? draft.razon.trim() : null,
            renderings: draft.renderings.map((rendering, at) => ({
              width: widths[at]!,
              text: rendering.text.trim(),
            })),
            asserted_by: actor.trim(),
          },
          true,
        ),
      untold,
    );
    if (done.kind === "done") await onSaved();
  };

  const part = (
    label: string,
    value: string,
    onChange: (value: string) => void,
    required = true,
    hint?: string,
  ) => (
    <EditorField label={label} hint={hint}>
      {(control) => (
        <TextEditor
          id={control.id}
          value={value}
          onChange={onChange}
          invalid={control.invalid}
          describedBy={control.describedBy}
          required={required}
        />
      )}
    </EditorField>
  );
  const kindWords = (kind: string) =>
    kind === "entity"
      ? t("desktop.ledger.counterparty.filing_name.kind.entity")
      : t("desktop.ledger.counterparty.filing_name.kind.natural_person");
  const setRendering = (at: number, change: Partial<RenderingDraft>) =>
    patch({
      renderings: draft.renderings.map((held, i) =>
        i === at ? { ...held, ...change } : held,
      ),
    });

  return (
    <section
      className="ledger-counterparty-filing-name flex flex-col gap-2"
      aria-label={t("desktop.ledger.counterparty.filing_name.title")}
    >
      <h4 className="text-sm font-medium">
        {t("desktop.ledger.counterparty.filing_name.title")}
      </h4>
      {stated ? (
        <dl className="ledger-counterparty-filing-name-stated grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
          <dt className="text-muted-foreground">
            {t("desktop.ledger.counterparty.filing_name.kind_label")}
          </dt>
          <dd>{kindWords(stated.party_kind)}</dd>
          {stated.razon_social && (
            <>
              <dt className="text-muted-foreground">
                {t("desktop.ledger.counterparty.filing_name.razon_social")}
              </dt>
              <dd className="wrap-anywhere">{stated.razon_social}</dd>
            </>
          )}
          {stated.primer_apellido && (
            <>
              <dt className="text-muted-foreground">
                {t("desktop.ledger.counterparty.filing_name.primer_apellido")}
              </dt>
              <dd className="wrap-anywhere">{stated.primer_apellido}</dd>
            </>
          )}
          {(stated.segundo_apellido || stated.no_second_surname) && (
            <>
              <dt className="text-muted-foreground">
                {t("desktop.ledger.counterparty.filing_name.segundo_apellido")}
              </dt>
              <dd className="wrap-anywhere">
                {stated.segundo_apellido ??
                  t(
                    "desktop.ledger.counterparty.filing_name.no_second_surname",
                  )}
              </dd>
            </>
          )}
          {stated.nombre && (
            <>
              <dt className="text-muted-foreground">
                {t("desktop.ledger.counterparty.filing_name.nombre")}
              </dt>
              <dd className="wrap-anywhere">{stated.nombre}</dd>
            </>
          )}
          {stated.renderings.map((rendering) => (
            <div key={rendering.width} className="contents">
              <dt className="text-muted-foreground">
                {t("desktop.ledger.counterparty.filing_name.rendering_for", {
                  width: rendering.width,
                })}
              </dt>
              <dd className="wrap-anywhere">{rendering.text}</dd>
            </div>
          ))}
          <dt className="text-muted-foreground">
            {t("desktop.ledger.counterparty.filing_name.stated_by")}
          </dt>
          <dd>
            {facts(t, [
              stated.asserted_by,
              formatTime(locale, stated.asserted_at),
            ])}
          </dd>
        </dl>
      ) : (
        <p className="text-sm text-muted-foreground">
          {t("desktop.ledger.counterparty.filing_name.unstated")}
        </p>
      )}
      {(result.findings ?? []).map((finding) => (
        <Alert
          key={finding.code}
          tone="warning"
          role="alert"
          icon={<Icon name="alert" />}
          className="ledger-counterparty-filing-name-finding"
        >
          {finding.words ? (
            <span lang={finding.words_language ?? undefined}>
              {finding.words}
            </span>
          ) : (
            t("desktop.ledger.counterparty.filing_name.kind_contradicts", {
              declared: kindWords(finding.declared_kind),
              observed: kindWords(finding.observed_form),
            })
          )}
        </Alert>
      ))}
      {groups.length > 0 && (
        <section
          className="flex flex-col gap-1"
          aria-label={t("desktop.ledger.counterparty.filing_name.slots")}
        >
          <h5 className="text-sm font-medium">
            {t("desktop.ledger.counterparty.filing_name.slots")}
          </h5>
          <ul className="ledger-counterparty-filing-name-slots flex flex-col gap-1 text-sm">
            {groups.map((group) => (
              <li
                key={`${group.width}:${group.state}`}
                data-slot-state={group.state}
                data-slot-width={group.width}
                className="flex flex-wrap items-baseline gap-x-2"
              >
                <span className="font-medium tabular-nums">
                  {t("desktop.ledger.counterparty.filing_name.slot.width", {
                    width: group.width,
                  })}
                </span>
                <span
                  className={
                    group.state === "fits" || group.state === "uses_rendering"
                      ? "text-muted-foreground"
                      : "text-warning-foreground"
                  }
                >
                  {t(SLOT_STATE_LOCALE_KEYS[group.state])}
                </span>
                <span className="text-muted-foreground">
                  {group.editions.map((edition, at) => (
                    <span key={edition.words} lang={edition.language}>
                      {at > 0 ? "; " : ""}
                      {edition.words}
                    </span>
                  ))}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
      <FormGrid>
        <ChoiceField
          label={t("desktop.ledger.counterparty.filing_name.kind_label")}
          value={draft.kind}
          onValue={(kind) => patch({ kind })}
          placeholder={t("desktop.ledger.form.choose")}
          options={COUNTERPARTY_KINDS.map((kind) => ({
            value: kind,
            label: kindWords(kind),
          }))}
        />
        {entity &&
          part(
            t("desktop.ledger.counterparty.filing_name.razon_social"),
            draft.razon,
            (razon) => patch({ razon }),
            true,
            limitHint("razon_social"),
          )}
        {natural && (
          <>
            {part(
              t("desktop.ledger.counterparty.filing_name.primer_apellido"),
              draft.primer,
              (primer) => patch({ primer }),
              true,
              limitHint("primer_apellido"),
            )}
            {part(
              t("desktop.ledger.counterparty.filing_name.segundo_apellido"),
              draft.segundo,
              (segundo) => patch({ segundo }),
              !draft.noSecond,
              limitHint("segundo_apellido"),
            )}
            {part(
              t("desktop.ledger.counterparty.filing_name.nombre"),
              draft.nombre,
              (nombre) => patch({ nombre }),
              true,
              limitHint("nombre"),
            )}
            <label className="flex items-center gap-2 text-sm">
              <Checkbox
                className="ledger-counterparty-no-second-surname"
                checked={draft.noSecond}
                onChange={(event) =>
                  patch({
                    noSecond: event.target.checked,
                    segundo: event.target.checked ? "" : draft.segundo,
                  })
                }
              />
              {t("desktop.ledger.counterparty.filing_name.no_second_surname")}
            </label>
          </>
        )}
      </FormGrid>
      {(natural || entity) && (
        <fieldset className="flex flex-col gap-2">
          <legend className="text-sm font-medium">
            {t("desktop.ledger.counterparty.filing_name.renderings")}
          </legend>
          <p className="text-sm text-muted-foreground">
            {t("desktop.ledger.counterparty.filing_name.renderings_hint")}
          </p>
          {draft.renderings.map((rendering, at) => (
            <div
              key={rendering.key}
              className="ledger-counterparty-rendering flex flex-wrap items-end gap-2"
            >
              <EditorField
                label={t("desktop.ledger.counterparty.filing_name.width")}
                className="w-32"
              >
                {(control) => (
                  <IntegerEditor
                    id={control.id}
                    value={rendering.width}
                    onChange={(width) => setRendering(at, { width })}
                    invalid={control.invalid}
                    describedBy={control.describedBy}
                  />
                )}
              </EditorField>
              <EditorField
                label={t("desktop.ledger.counterparty.filing_name.text")}
                className="w-64"
              >
                {(control) => (
                  <TextEditor
                    id={control.id}
                    value={rendering.text}
                    onChange={(text) => setRendering(at, { text })}
                    invalid={control.invalid}
                    describedBy={control.describedBy}
                  />
                )}
              </EditorField>
              <IconButton
                size="sm"
                label={t(
                  "desktop.ledger.counterparty.filing_name.rendering_remove",
                )}
                onClick={() =>
                  patch({
                    renderings: draft.renderings.filter((_, i) => i !== at),
                  })
                }
              >
                <Icon name="close" />
              </IconButton>
            </div>
          ))}
          <div className="flex flex-wrap gap-2">
            {tooWide.map((width) => (
              <Button
                key={width}
                size="sm"
                variant="outline"
                className="ledger-counterparty-rendering-for-slot"
                data-slot-width={width}
                onClick={() =>
                  patch({
                    renderings: [
                      ...draft.renderings,
                      { key: nextKey++, width: String(width), text: "" },
                    ],
                  })
                }
              >
                {t(
                  "desktop.ledger.counterparty.filing_name.rendering_for_slot",
                  {
                    width,
                  },
                )}
              </Button>
            ))}
            <Button
              size="sm"
              variant="outline"
              className="ledger-counterparty-rendering-add"
              onClick={() =>
                patch({
                  renderings: [
                    ...draft.renderings,
                    { key: nextKey++, width: "", text: "" },
                  ],
                })
              }
            >
              {t("desktop.ledger.counterparty.filing_name.rendering_add")}
            </Button>
          </div>
        </fieldset>
      )}
      <div>
        <WriteHold>
          <Button
            size="sm"
            variant="outline"
            className="ledger-counterparty-filing-name-save"
            aria-disabled={!canSave || undefined}
            onClick={() => canSave && void save()}
          >
            {t("desktop.ledger.counterparty.filing_name.save")}
          </Button>
        </WriteHold>
      </div>
      {served ? (
        <RefusalNotice refusal={served} />
      ) : (
        <CallLine call={write.last} onReread={() => void onSaved()} />
      )}
    </section>
  );
}
