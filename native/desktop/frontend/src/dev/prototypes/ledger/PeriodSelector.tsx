import { useMemo, useRef, useState, type KeyboardEvent } from "react";
import { clsx as cx } from "clsx";
import { Icon } from "./Icon";
import { effDate, periodLabel, stepPeriod } from "./model";
import { Button, IconButton, Popover } from "./Primitives";
import { useStore } from "./store";
import type { Period } from "./types";
import { MONTH_LABEL, MONTHS, PERIOD_CODES, TODAY } from "./vocab";

/* ── The period selector (R21): one dropdown, any year. The trigger shows
   the period with ‹ › beside it; inside, ‹ year › navigates, then Year,
   the quarters, the months and All periods; the years that hold
   movements sit at the bottom for long jumps. ───────────────────────── */
export const YEAR_MIN = 1980,
  YEAR_MAX = 2200;
export const yearOk = (y: number) =>
  Number.isInteger(y) && y >= YEAR_MIN && y <= YEAR_MAX;
const periodTrigger = (p: Period, yearOnly?: boolean) =>
  yearOnly
    ? String(p.year)
    : p.code === "ALL"
      ? "All periods"
      : p.code === "0A"
        ? `${p.year} · Year`
        : /^\dT$/.test(p.code)
          ? `${p.year} · ${p.code}`
          : `${p.year} · ${MONTH_LABEL[+p.code - 1]}`;

export function PeriodControl({
  value,
  onChange,
  label = "Period",
  yearOnly,
  allowAll = true,
  size = "sm",
  className,
}: {
  value: Period;
  onChange: (next: Period) => void;
  label?: string;
  yearOnly?: boolean;
  allowAll?: boolean;
  size?: string;
  className?: string;
}) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const step = (d: number) => {
    const next = yearOnly
      ? { ...value, year: value.year + d }
      : stepPeriod(value, d);
    if (yearOk(next.year)) onChange(next);
  };
  const unit =
    yearOnly || value.code === "0A"
      ? "year"
      : /^\dT$/.test(value.code)
        ? "quarter"
        : "month";
  return (
    <div
      className={cx("period-ctl row", className)}
      role="group"
      aria-label={label}
    >
      <IconButton
        icon="back"
        label={`Previous ${unit}`}
        disabled={!yearOnly && value.code === "ALL"}
        onClick={() => step(-1)}
      />
      <Button
        variant="outline"
        size={size}
        className="period-btn"
        aria-haspopup="dialog"
        aria-expanded={!!anchor}
        aria-label={`${label}: ${yearOnly ? value.year : periodLabel(value)}`}
        onClick={(e) => setAnchor(e.currentTarget)}
      >
        <span className="tnum">{periodTrigger(value, yearOnly)}</span>
        <Icon name="chevronDown" size="xs" />
      </Button>
      <IconButton
        icon="forward"
        label={`Next ${unit}`}
        disabled={!yearOnly && value.code === "ALL"}
        onClick={() => step(1)}
      />
      {anchor ? (
        <PeriodPopover
          anchor={anchor}
          value={value}
          yearOnly={yearOnly}
          allowAll={allowAll}
          label={label}
          onChange={onChange}
          onClose={() => setAnchor(null)}
        />
      ) : null}
    </div>
  );
}
function PeriodPopover({
  anchor,
  value,
  onChange,
  onClose,
  yearOnly,
  allowAll,
  label,
}: {
  anchor: HTMLElement;
  value: Period;
  onChange: (next: Period) => void;
  onClose: () => void;
  yearOnly?: boolean;
  allowAll?: boolean;
  label: string;
}) {
  const [state] = useStore();
  const withRows = useMemo(
    () =>
      [
        ...new Set(
          Object.values(state.data.byId).map((r) => +effDate(r).slice(0, 4)),
        ),
      ].sort((a, b) => a - b),
    [state.data.byId],
  );
  const [year, setYear] = useState(
    value.code === "ALL"
      ? withRows[withRows.length - 1] || +TODAY.slice(0, 4)
      : value.year,
  );
  const gridRef = useRef<HTMLDivElement>(null);
  const apply = (p: Period) => {
    onChange(p);
    onClose();
  };
  const choose = (code: string) => apply({ year, code });
  // Arrows move between the items of the period grid, by position.
  const gridKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const dirs: Record<string, [number, number]> = {
      ArrowLeft: [-1, 0],
      ArrowRight: [1, 0],
      ArrowUp: [0, -1],
      ArrowDown: [0, 1],
    };
    const d = dirs[e.key];
    if (!d || !gridRef.current) return;
    const items = [...gridRef.current.querySelectorAll("button")];
    const cur = items.indexOf(document.activeElement as HTMLButtonElement);
    if (cur < 0) return;
    e.preventDefault();
    if (d[1] === 0) {
      items[Math.max(0, Math.min(items.length - 1, cur + d[0]))]?.focus();
      return;
    }
    const r = items[cur]!.getBoundingClientRect();
    const cx0 = r.left + r.width / 2;
    const cand = items
      .map((el) => ({ el, r: el.getBoundingClientRect() }))
      .filter((x) => (d[1] > 0 ? x.r.top > r.top + 2 : x.r.top < r.top - 2));
    if (!cand.length) return;
    const rowTop =
      d[1] > 0
        ? Math.min(...cand.map((x) => x.r.top))
        : Math.max(...cand.map((x) => x.r.top));
    const row = cand.filter((x) => Math.abs(x.r.top - rowTop) < 2);
    row
      .sort(
        (a, b) =>
          Math.abs(a.r.left + a.r.width / 2 - cx0) -
          Math.abs(b.r.left + b.r.width / 2 - cx0),
      )[0]
      ?.el.focus();
  };
  const sel = (code: string) =>
    !yearOnly && value.code === code && value.year === year;
  return (
    <Popover
      anchor={anchor}
      onClose={onClose}
      width="17rem"
      label={`Choose ${yearOnly ? "a year" : "a period"}${label && label !== "Period" ? " · " + label : ""}`}
      align="end"
      className="col g3 period-pop"
    >
      <div className="row g1 pp-year">
        <IconButton
          icon="back"
          label="Previous year"
          disabled={year <= YEAR_MIN}
          onClick={() => setYear(year - 1)}
        />
        {yearOnly ? (
          <button
            type="button"
            className="btn ghost sm f1 tnum fw6"
            data-autofocus
            aria-pressed={value.year === year}
            aria-label={`Choose ${year}`}
            onClick={() => apply({ ...value, year })}
          >
            {year}
          </button>
        ) : (
          <span className="f1 tnum fw6 pp-year-label" aria-live="polite">
            {year}
          </span>
        )}
        <IconButton
          icon="forward"
          label="Next year"
          disabled={year >= YEAR_MAX}
          onClick={() => setYear(year + 1)}
        />
      </div>
      {yearOnly ? null : (
        <div
          ref={gridRef}
          className="col g2"
          role="group"
          aria-label={`Periods of ${year}`}
          onKeyDown={gridKey}
        >
          <div className="pp-quarters">
            <button
              type="button"
              className="btn outline sm"
              data-autofocus={
                value.code === "0A" || value.code === "ALL" ? "" : undefined
              }
              aria-pressed={sel("0A")}
              aria-label={`Whole year ${year} (0A)`}
              onClick={() => choose("0A")}
            >
              Year
            </button>
            {PERIOD_CODES.map((c) => (
              <button
                key={c}
                type="button"
                className="btn outline sm"
                data-autofocus={value.code === c ? "" : undefined}
                aria-pressed={sel(c)}
                aria-label={`${year} ${c}`}
                onClick={() => choose(c)}
              >
                {c}
              </button>
            ))}
          </div>
          <div className="month-grid">
            {MONTHS.map((m, i) => (
              <button
                key={m}
                type="button"
                className="btn ghost xs"
                data-autofocus={value.code === m ? "" : undefined}
                aria-pressed={sel(m)}
                aria-label={`${MONTH_LABEL[i]} ${year}`}
                onClick={() => choose(m)}
              >
                {MONTH_LABEL[i]}
              </button>
            ))}
          </div>
        </div>
      )}
      {allowAll && !yearOnly ? (
        <div className="pp-all">
          <Button
            size="sm"
            variant="ghost"
            className="block"
            aria-pressed={value.code === "ALL"}
            onClick={() => apply({ year, code: "ALL" })}
          >
            All periods
          </Button>
        </div>
      ) : null}
      {withRows.length ? (
        <div className="col g1 pp-years">
          <span className="t-xs muted">Years with movements</span>
          <div
            className="pp-year-list"
            role="group"
            aria-label="Years with movements"
          >
            {withRows.map((y) => (
              <button
                key={y}
                type="button"
                className="btn pill tnum"
                aria-pressed={y === year}
                onClick={() =>
                  yearOnly ? apply({ ...value, year: y }) : setYear(y)
                }
              >
                {y}
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </Popover>
  );
}
