import { useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import type { LedgerCounterpartyResult } from "../../../shell/ledgerSetup";
import { useStrings } from "../../../shell/strings";
import { WriteHold } from "../WritePause";
import { stampText } from "../movements/movementWords";
import {
  CallLine,
  ChoiceField,
  FormGrid,
  Panel,
  TextField,
  useSetupDraft,
  useSetupWrite,
} from "./SetupParts";
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
  const countryWrong = country !== "" && !TWO_LETTERS.test(country);
  const stateWrong = state !== "" && !TWO_LETTERS.test(state);
  const canConfirm =
    result !== null && TWO_LETTERS.test(country) && scope !== "" && !stateWrong;

  const confirm = async () => {
    if (!result || !canConfirm) return;
    const done = await write.run(() =>
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
    );
    if (done.kind === "done") setViewed(done);
  };
  const withdraw = async () => {
    if (!result) return;
    const done = await write.run(() =>
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
      ? `${tokenText(t, "counterparty.scope", value)} · ${tokenText(t, "counterparty.source", source ?? null)}`
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
        <TextField
          label={t("desktop.ledger.counterparty.tax_id")}
          value={taxId}
          onValue={setTaxId}
          mono
          className="w-64"
          maxLength={256}
        />
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
                  ? `${answer.identification_state} · ${tokenText(t, "counterparty.source", answer.identification_source)}`
                  : t("desktop.ledger.counterparty.undetermined")}
              </dd>
              <dt className="text-muted-foreground">
                {t("desktop.ledger.counterparty.confirmed")}
              </dt>
              <dd>
                {result.facts
                  ? stampText(locale, result.facts.asserted_at)
                  : t("desktop.ledger.counterparty.not_confirmed")}
              </dd>
            </dl>
            {answer?.contradiction_detail && (
              <span className="text-sm">{answer.contradiction_detail}</span>
            )}
          </Alert>
          <FormGrid>
            <TextField
              label={t("desktop.ledger.counterparty.country")}
              value={country}
              onValue={setCountry}
              hint={t("desktop.ledger.form.two_letters")}
              error={countryWrong ? t("desktop.ledger.form.two_letters") : null}
              maxLength={2}
              required
            />
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
            <TextField
              label={t("desktop.ledger.counterparty.state")}
              value={state}
              onValue={setState}
              hint={t("desktop.ledger.form.two_letters")}
              error={stateWrong ? t("desktop.ledger.form.two_letters") : null}
              maxLength={2}
            />
            <TextField
              label={t("desktop.ledger.counterparty.note")}
              value={note}
              onValue={setNote}
              maxLength={4096}
            />
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
