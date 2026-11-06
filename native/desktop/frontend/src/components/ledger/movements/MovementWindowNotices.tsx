import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { useStrings } from "../../../shell/strings";

/**
 * What the Movements section says above its grid about the selection and
 * the window: selected movements the view hides, a selection of every
 * movement shown where filters hide others, a search over a window read in
 * part, matches in other periods, and a window read in part.
 */
export function MovementWindowNotices({
  hiddenSelected,
  selected,
  allShownSelected,
  hiddenByFilters,
  shown,
  loaded,
  total,
  found,
  searching,
  partial,
  elsewhere,
  period,
  onShowHidden,
  onKeepVisible,
  onSelectAll,
  readAll,
  onElsewhere,
}: {
  /** Selected movements the grid does not draw. */
  hiddenSelected: number;
  selected: number;
  /** Every movement shown is selected. */
  allShownSelected: boolean;
  /** Loaded movements the filters and search hide. */
  hiddenByFilters: number;
  /** Movements the grid draws. */
  shown: number;
  /** Movements of the window loaded. */
  loaded: number;
  /** Movements in the window. */
  total: number;
  /** Loaded movements the filters and search keep. */
  found: number;
  /** A search is typed. */
  searching: boolean;
  partial: boolean;
  /** Matches of the search in other periods, null where unknown. */
  elsewhere: number | null;
  /** The period shown, in words. */
  period: string;
  onShowHidden: () => void;
  onKeepVisible: () => void;
  onSelectAll: () => void;
  readAll: () => void;
  onElsewhere: () => void;
}) {
  const t = useStrings();
  return (
    <>
      {hiddenSelected > 0 && (
        <div
          role="alert"
          className="ledger-hidden-selection flex flex-wrap items-center gap-2"
        >
          <Alert
            tone="warning"
            role="none"
            icon={<Icon name="alert" />}
            className="flex-1"
          >
            {t("desktop.ledger.selection.hidden", {
              hidden: hiddenSelected,
              selected,
            })}
          </Alert>
          <Button variant="outline" size="sm" onClick={onShowHidden}>
            {t("desktop.ledger.selection.show")}
          </Button>
          <Button variant="ghost" size="sm" onClick={onKeepVisible}>
            {t("desktop.ledger.selection.keep_visible")}
          </Button>
        </div>
      )}
      {hiddenSelected === 0 &&
        selected > 1 &&
        allShownSelected &&
        hiddenByFilters > 0 && (
          <p
            role="status"
            className="flex flex-wrap items-center gap-2 text-sm"
          >
            {t("desktop.ledger.selection.all_shown", { count: shown })}
            <Button variant="link" size="xs" onClick={onSelectAll}>
              {t("desktop.ledger.selection.select_all", {
                count: loaded,
                period,
              })}
            </Button>
          </p>
        )}
      {searching && partial && (
        <p
          role="status"
          className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground"
        >
          {t("desktop.ledger.search.loaded", { found, loaded })}
          <Button variant="link" size="xs" onClick={readAll}>
            {t("desktop.ledger.search.load_all", { total })}
          </Button>
        </p>
      )}
      {elsewhere !== null && elsewhere > 0 && (
        <p
          role="status"
          className="ledger-elsewhere flex flex-wrap items-center gap-2 text-sm text-muted-foreground"
        >
          {t("desktop.ledger.search.elsewhere", { count: elsewhere })}
          <Button variant="link" size="xs" onClick={onElsewhere}>
            {t("desktop.ledger.search.show")}
          </Button>
        </p>
      )}
      {partial && !searching && (
        <p
          role="status"
          className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground"
        >
          {t("desktop.ledger.window.partial")}
          <Button variant="link" size="xs" onClick={readAll}>
            {t("desktop.ledger.search.load_all", { total })}
          </Button>
        </p>
      )}
    </>
  );
}
