import { useRef, useState, type KeyboardEvent } from "react";
import { Icon } from "./Icon";

export type RailItem = {
  id: string;
  icon: string;
  label: string;
  shortcut?: string;
  pressed?: boolean;
  badge?: number;
  onClick: () => void;
};

// Icon-only vertical toolbar: one tab stop, arrow keys move within it.
export function Rail({
  label,
  top,
  bottom,
}: {
  label: string;
  top: RailItem[];
  bottom: RailItem[];
}) {
  const bar = useRef<HTMLElement>(null);
  const items = [...top, ...bottom];
  const [stop, setStop] = useState(0);
  // The tab stop is kept in state, so it survives the item list changing.
  const current = Math.min(stop, items.length - 1);

  const move = (event: KeyboardEvent) => {
    const count = items.length;
    let next: number | null = null;
    if (event.key === "ArrowDown") next = (current + 1) % count;
    if (event.key === "ArrowUp") next = (current - 1 + count) % count;
    if (event.key === "Home") next = 0;
    if (event.key === "End") next = count - 1;
    if (next === null || !bar.current) return;
    event.preventDefault();
    setStop(next);
    bar.current.querySelectorAll<HTMLButtonElement>("button")[next]?.focus();
  };

  const render = (item: RailItem, index: number) => (
    <button
      key={item.id}
      className={`rail-button ${item.pressed ? "is-pressed" : ""}`}
      aria-label={item.label}
      aria-pressed={item.pressed}
      tabIndex={index === current ? 0 : -1}
      onFocus={() => setStop(index)}
      onClick={item.onClick}
      data-tip={item.shortcut ? `${item.label}  ${item.shortcut}` : item.label}
    >
      <Icon name={item.icon} />
      {item.badge ? (
        <span className="rail-badge">
          {item.badge > 99 ? "99+" : item.badge}
        </span>
      ) : null}
    </button>
  );

  return (
    <nav className="rail" aria-label={label} ref={bar} onKeyDown={move}>
      <div className="rail-group">
        {top.map((item, index) => render(item, index))}
      </div>
      <div className="rail-group">
        {bottom.map((item, index) => render(item, top.length + index))}
      </div>
    </nav>
  );
}
