import { useState } from "react";
import { CountryEditor } from "@/components/editors/CountryEditor";
import { NotesEditor } from "@/components/editors/NotesEditor";
import { TaxIdEditor } from "@/components/editors/TaxIdEditor";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { facts } from "@/shell/compose";
import { useFieldSuggestions } from "../suggestions/SuggestionsProvider";
import type { LedgerCounterpartyResult } from "../../../shell/ledgerSetup";
import { useStrings } from "../../../shell/strings";
import { WriteHold, type Landing } from "../WritePause";
import { formatTime } from "../../../shared/dateFormats";
import {
  CallLine,
  ChoiceField,
  FormGrid,
  Panel,
  readLanding,
  useSetupDraft,
  useSetupWrite,
} from "./SetupParts";
import { EditorField } from "./EditorField";
import type { SetupProps } from "./setupProps";
import { setupCall, type SetupCall } from "./setupModel";
import { tokenText } from "./setupWords";

/** Where a counterparty can be established, as the registry names it. */
export const TERRITORIAL_SCOPES = [
  "es_mainland",
  "es_canarias",
  "es_ceuta_melilla",
  "eu_member",
  "third_country",
] as const;

const TWO_LETTERS = /^[A-Za-z]{2}$/;

/**
 * What the ledger answers for one counterparty, by its tax id: where it is
 * established and which State identifies it for VAT, and where each answer
 * comes from. The person confirms the facts or withdraws an earlier
 * confirmation; each is its own write.
 */
export function CounterpartiesPane({ port, locale }: SetupProps) {
  const t = useStrings();
  const [taxId, setTaxId] = useState("");
  const [viewed, setViewed] =
    useState<SetupCall<LedgerCounterpartyResult> | null>(null);
  const [country, setCountry] = useState("");
  const [scope, setScope] = useState("");
  const [state, setState] = useState("");
  const [note, setNote] = useState("");
  const [withdrawing, setWithdrawing] = useState(false);
  // A form with anything typed into it that is not yet written.
  useSetupDraft([country, scope, state, note].some(Boolean));
  const write = useSetupWrite(t("desktop.ledger.counterparty.title"));
  const taxIds = useFieldSuggestions("party_tax_id");
  const countries = useFieldSuggestions("country");
  const states = useFieldSuggestions("state");

  const view = async (id = taxId) => {
    setViewed(
      await setupCall(
        port,
        "ledger.counterparty",
        { action: "view", tax_identifier: id.trim() },
        false,
      ),
    );
  };
  const result = viewed?.kind === "done" ? viewed.result : null;
  /** How a confirmation or a withdrawal landed: what the counterparty
   * stands on, viewed again. */
  const viewLanding = (
    id: string,
    judge: (known: LedgerCounterpartyResult["facts"]) => Landing,
  ) =>
    readLanding(
      port,
      "ledger.counterparty",
      { action: "view", tax_identifier: id },
      (read) => judge(read.facts),
    );
  const countryWrong = country !== "" && !TWO_LETTERS.test(country);
  const stateWrong = state !== "" && !TWO_LETTERS.test(state);
  const canConfirm =
    result !== null && TWO_LETTERS.test(country) && scope !== "" && !stateWrong;

  const confirm = async () => {
    if (!result || !canConfirm) return;
    const done = await write.run(
      () =>
        setupCall(
          port,
          "ledger.counterparty",
          {
            action: "confirm",
            tax_identifier: result.tax_identifier,
            country_code: country.toUpperCase(),
            territorial_scope: scope,
            identification_state: state ? state.toUpperCase() : null,
            note: note.trim(),
          },
          true,
        ),
      viewLanding(result.tax_identifier, (known) =>
        known !== null &&
        known.territorial_scope === scope &&
        known.identification_state === (state ? state.toUpperCase() : null) &&
        known.note === note.trim()
          ? "saved"
          : "not_saved",
      ),
    );
    if (done.kind === "done") setViewed(done);
  };
  const withdraw = async () => {
    if (!result) return;
    const done = await write.run(
      () =>
        setupCall(
          port,
          "ledger.counterparty",
          {
            action: "withdraw",
            tax_identifier: result.tax_identifier,
            note: note.trim(),
          },
          true,
        ),
      viewLanding(result.tax_identifier, (known) =>
        known === null ? "saved" : "not_saved",
      ),
    );
    setWithdrawing(false);
    if (done.kind === "done") setViewed(done);
  };
  const answer = result?.resolution;
  const sourced = (
    value: string | null | undefined,
    source: string | null | undefined,
  ) =>
    value
      ? facts(t, [
          tokenText(t, "counterparty.scope", value),
          tokenText(t, "counterparty.source", source ?? null),
        ])
      : t("desktop.ledger.counterparty.undetermined");

  return (
    <Panel title={t("desktop.ledger.counterparty.title")}>
      <form
        className="flex flex-wrap items-end gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          if (taxId.trim()) void view();
        }}
      >
        <EditorField
          label={t("desktop.ledger.counterparty.tax_id")}
          className="w-64"
        >
          {(control) => (
            <TaxIdEditor
              id={control.id}
              value={taxId}
              onChange={setTaxId}
              invalid={control.invalid}
              describedBy={control.describedBy}
              maxLength={256}
              {...taxIds}
              onPick={(picked) => void view(picked.value)}
            />
          )}
        </EditorField>
        <Button
          type="submit"
          size="sm"
          variant="outline"
          className="ledger-counterparty-view"
          aria-disabled={!taxId.trim() || undefined}
        >
          {t("desktop.ledger.counterparty.view")}
        </Button>
      </form>
      <CallLine call={viewed} />
      {result && (
        <div className="ledger-counterparty-answer flex flex-col gap-3">
          <Alert icon={<Icon name="info" />}>
            <span className="font-medium">
              {t("desktop.ledger.counterparty.answer")}
            </span>
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
              <dt className="text-muted-foreground">
                {t("desktop.ledger.counterparty.established")}
              </dt>
              <dd>
                {sourced(answer?.territorial_scope, answer?.territorial_source)}
              </dd>
              <dt className="text-muted-foreground">
                {t("desktop.ledger.counterparty.vat_state")}
              </dt>
              <dd>
                {answer?.identification_state
                  ? facts(t, [
                      answer.identification_state,
                      tokenText(
                        t,
                        "counterparty.source",
                        answer.identification_source,
                      ),
                    ])
                  : t("desktop.ledger.counterparty.undetermined")}
              </dd>
              <dt className="text-muted-foreground">
                {t("desktop.ledger.counterparty.confirmed")}
              </dt>
              <dd>
                {result.facts
                  ? formatTime(locale, result.facts.asserted_at)
                  : t("desktop.ledger.counterparty.not_confirmed")}
              </dd>
            </dl>
            {answer?.contradiction_detail && (
              <span className="text-sm">{answer.contradiction_detail}</span>
            )}
          </Alert>
          <FormGrid>
            <EditorField
              label={t("desktop.ledger.counterparty.country")}
              error={countryWrong ? t("desktop.ledger.form.two_letters") : null}
            >
              {(control) => (
                <CountryEditor
                  id={control.id}
                  value={country}
                  onChange={setCountry}
                  invalid={control.invalid}
                  describedBy={control.describedBy}
                  maxLength={2}
                  required
                  {...countries}
                />
              )}
            </EditorField>
            <ChoiceField
              label={t("desktop.ledger.counterparty.scope_label")}
              value={scope}
              onValue={setScope}
              placeholder={t("desktop.ledger.form.choose")}
              options={TERRITORIAL_SCOPES.map((value) => ({
                value,
                label: tokenText(t, "counterparty.scope", value),
              }))}
            />
            <EditorField
              label={t("desktop.ledger.counterparty.state")}
              error={stateWrong ? t("desktop.ledger.form.two_letters") : null}
            >
              {(control) => (
                <CountryEditor
                  id={control.id}
                  value={state}
                  onChange={setState}
                  invalid={control.invalid}
                  describedBy={control.describedBy}
                  maxLength={2}
                  {...states}
                />
              )}
            </EditorField>
            <EditorField label={t("desktop.ledger.counterparty.note")}>
              {(control) => (
                <NotesEditor
                  id={control.id}
                  value={note}
                  onChange={setNote}
                  invalid={control.invalid}
                  describedBy={control.describedBy}
                  maxLength={4096}
                />
              )}
            </EditorField>
          </FormGrid>
          <div className="flex flex-wrap gap-2">
            <WriteHold>
              <Button
                size="sm"
                className="ledger-counterparty-confirm"
                aria-disabled={!canConfirm || write.busy || undefined}
                onClick={() => canConfirm && !write.busy && void confirm()}
              >
                {t("desktop.ledger.counterparty.confirm")}
              </Button>
            </WriteHold>
            {result.facts && (
              <Button
                size="sm"
                variant="outline"
                aria-expanded={withdrawing}
                onClick={() => setWithdrawing(!withdrawing)}
              >
                {t("desktop.ledger.counterparty.withdraw")}
              </Button>
            )}
          </div>
          {withdrawing && (
            <Alert tone="warning" icon={<Icon name="alert" />}>
              <span>{t("desktop.ledger.counterparty.withdraw_what")}</span>
              <span className="flex gap-2">
                <Button
                  size="xs"
                  variant="ghost"
                  onClick={() => setWithdrawing(false)}
                >
                  {t("desktop.ledger.form.cancel")}
                </Button>
                <WriteHold>
                  <Button
                    size="xs"
                    variant="destructive"
                    className="ledger-counterparty-withdraw"
                    onClick={() => void withdraw()}
                  >
                    {t("desktop.ledger.counterparty.withdraw_confirm")}
                  </Button>
                </WriteHold>
              </span>
            </Alert>
          )}
          <CallLine
            call={write.last}
            onReread={() => void view(result.tax_identifier)}
          />
        </div>
      )}
    </Panel>
  );
}
