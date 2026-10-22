import { Fragment, useMemo, type ReactNode } from "react";
import { cn } from "@/components/ui/cn";
import { cadrumoLink } from "./cadrumoLink";

// The agent writes Markdown. This reads the part of it a reply uses (the
// CommonMark blocks, GitHub's tables and strikethrough, and bare addresses)
// into elements, never into HTML: nothing the agent writes becomes markup,
// and a reply still being written reads as far as it has got. What does not
// parse is shown as written.

/** Opens an address the agent linked to, outside the window. */
export type OpenLink = (url: string) => void;

type Align = "left" | "center" | "right" | null;

type Block =
  | { kind: "paragraph"; text: string }
  | { kind: "heading"; level: number; text: string }
  | { kind: "code"; language: string; text: string }
  | { kind: "quote"; blocks: Block[] }
  | { kind: "list"; ordered: boolean; start: number; items: Block[][] }
  | { kind: "table"; align: Align[]; head: string[]; rows: string[][] }
  | { kind: "rule" };

const FENCE = /^ {0,3}(`{3,}|~{3,})\s*([^\s`]*)[^`]*$/;
const HEADING = /^ {0,3}(#{1,6})(?:[ \t]+(.*?))?(?:[ \t]+#+)?[ \t]*$/;
const RULE = /^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$/;
const QUOTE = /^ {0,3}> ?(.*)$/;
const ITEM = /^( *)([-*+]|\d{1,9}[.)])(?:[ \t]+(.*))?$/;
const DELIMITER_ROW = /^ *\|? *:?-+:? *(?:\| *:?-+:? *)*\|? *$/;

const indentOf = (line: string) => line.length - line.trimStart().length;
const blank = (line: string) => line.trim() === "";

/** The cells of a table row, with its outer pipes and escaped pipes read. */
function cells(line: string): string[] {
  const row = line
    .trim()
    .replace(/^\|/, "")
    .replace(/(?<!\\)\|$/, "");
  return row
    .split(/(?<!\\)\|/)
    .map((cell) => cell.trim().replace(/\\\|/g, "|"));
}

function startsTable(lines: readonly string[], at: number): boolean {
  const head = lines[at];
  const rule = lines[at + 1];
  return (
    head !== undefined &&
    rule !== undefined &&
    head.includes("|") &&
    DELIMITER_ROW.test(rule) &&
    cells(head).length === cells(rule).length
  );
}

/** Whether a line begins a block other than a paragraph, so that it ends
 * one. A numbered item breaks a paragraph only when it starts at 1. */
function interrupts(lines: readonly string[], at: number): boolean {
  const line = lines[at] ?? "";
  const item = ITEM.exec(line);
  return (
    FENCE.test(line) ||
    HEADING.test(line) ||
    RULE.test(line) ||
    QUOTE.test(line) ||
    (item !== null &&
      item[3] !== undefined &&
      (!/^\d/.test(item[2] ?? "") ||
        Number.parseInt(item[2] ?? "", 10) === 1)) ||
    startsTable(lines, at)
  );
}

function parseBlocks(lines: readonly string[]): Block[] {
  const blocks: Block[] = [];
  let at = 0;
  while (at < lines.length) {
    const line = lines[at] ?? "";
    if (blank(line)) {
      at += 1;
      continue;
    }
    const fence = FENCE.exec(line);
    if (fence) {
      const mark = fence[1] ?? "```";
      const close = new RegExp(
        `^ {0,3}${mark[0] === "`" ? "`" : "~"}{${mark.length},}\\s*$`,
      );
      const body: string[] = [];
      at += 1;
      // A fence not closed yet runs to the end, as a reply being written has it.
      while (at < lines.length && !close.test(lines[at] ?? "")) {
        body.push(lines[at] ?? "");
        at += 1;
      }
      at += 1;
      blocks.push({
        kind: "code",
        language: fence[2] ?? "",
        text: body.join("\n"),
      });
      continue;
    }
    const heading = HEADING.exec(line);
    if (heading) {
      blocks.push({
        kind: "heading",
        level: heading[1]?.length ?? 1,
        text: heading[2] ?? "",
      });
      at += 1;
      continue;
    }
    if (RULE.test(line)) {
      blocks.push({ kind: "rule" });
      at += 1;
      continue;
    }
    if (QUOTE.test(line)) {
      const quoted: string[] = [];
      while (at < lines.length && !blank(lines[at] ?? "")) {
        const inner = QUOTE.exec(lines[at] ?? "");
        if (!inner && interrupts(lines, at)) break;
        quoted.push(inner ? (inner[1] ?? "") : (lines[at] ?? ""));
        at += 1;
      }
      blocks.push({ kind: "quote", blocks: parseBlocks(quoted) });
      continue;
    }
    const item = ITEM.exec(line);
    if (item) {
      at = parseList(lines, at, blocks);
      continue;
    }
    if (startsTable(lines, at)) {
      const align = cells(lines[at + 1] ?? "").map((cell): Align => {
        const left = cell.startsWith(":");
        const right = cell.endsWith(":");
        return left && right
          ? "center"
          : right
            ? "right"
            : left
              ? "left"
              : null;
      });
      const head = cells(line);
      const rows: string[][] = [];
      at += 2;
      while (
        at < lines.length &&
        !blank(lines[at] ?? "") &&
        (lines[at] ?? "").includes("|")
      ) {
        const row = cells(lines[at] ?? "");
        rows.push(head.map((_, index) => row[index] ?? ""));
        at += 1;
      }
      blocks.push({ kind: "table", align, head, rows });
      continue;
    }
    const text: string[] = [line.trim()];
    at += 1;
    while (
      at < lines.length &&
      !blank(lines[at] ?? "") &&
      !interrupts(lines, at)
    ) {
      text.push((lines[at] ?? "").trim());
      at += 1;
    }
    blocks.push({ kind: "paragraph", text: text.join("\n") });
  }
  return blocks;
}

/** Reads the list that starts at `start` into `blocks`; returns where it
 * ends. An item holds what is indented past its marker, and the lines that
 * run on from its text. */
function parseList(
  lines: readonly string[],
  start: number,
  blocks: Block[],
): number {
  const first = ITEM.exec(lines[start] ?? "");
  const base = first?.[1]?.length ?? 0;
  const ordered = /^\d/.test(first?.[2] ?? "");
  const items: string[][] = [];
  let content = 0;
  let at = start;
  while (at < lines.length) {
    const line = lines[at] ?? "";
    const item = ITEM.exec(line);
    const sameList =
      item !== null &&
      (item[1]?.length ?? 0) <= base + 1 &&
      /^\d/.test(item[2] ?? "") === ordered;
    if (sameList) {
      content = (item[1]?.length ?? 0) + (item[2]?.length ?? 0) + 1;
      items.push([item[3] ?? ""]);
      at += 1;
      continue;
    }
    if (blank(line)) {
      let next = at + 1;
      while (next < lines.length && blank(lines[next] ?? "")) next += 1;
      const after = lines[next];
      const goesOn =
        after !== undefined &&
        (indentOf(after) >= content ||
          (ITEM.test(after) &&
            indentOf(after) <= base + 1 &&
            /^\d/.test(ITEM.exec(after)?.[2] ?? "") === ordered));
      if (!goesOn) break;
      items.at(-1)?.push("");
      at += 1;
      continue;
    }
    const current = items.at(-1);
    if (!current) break;
    if (indentOf(line) >= content || indentOf(line) > base) {
      current.push(line.slice(Math.min(indentOf(line), content)));
    } else if (!blank(current.at(-1) ?? "") && !interrupts(lines, at)) {
      current.push(line.trim());
    } else {
      break;
    }
    at += 1;
  }
  blocks.push({
    kind: "list",
    ordered,
    start: ordered ? Number.parseInt(first?.[2] ?? "1", 10) : 1,
    items: items.map((item) => parseBlocks(item)),
  });
  return at;
}

/** The addresses a reply may open: those the host opens outside the window. */
const OPENABLE = /^(?:https:\/\/[^\s/?#@]+[^\s]*|mailto:[^\s]+)$/i;
const BARE_URL = /https:\/\/[^\s<>"'`]+/y;
const PUNCTUATION = /[\\!"#$%&'()*+,\-./:;<=>?@[\]^_`{|}~]/;

/** A bare address without the punctuation that closes the sentence around
 * it, and a closing parenthesis it did not open. */
function trimmedUrl(url: string): string {
  let end = url.length;
  while (end > 0) {
    const last = url[end - 1] ?? "";
    if (".,;:!?'\"*_".includes(last)) end -= 1;
    else if (
      last === ")" &&
      (url.slice(0, end).match(/\(/g)?.length ?? 0) <
        (url.slice(0, end).match(/\)/g)?.length ?? 0)
    )
      end -= 1;
    else break;
  }
  return url.slice(0, end);
}

/** Where the `close` that ends a span opened just before `from` is, or -1.
 * A closer has text before it, and an underscore one ends a word. */
function closer(text: string, from: number, close: string): number {
  let at = text.indexOf(close, from);
  while (at !== -1) {
    const before = text[at - 1] ?? "";
    const after = text[at + close.length] ?? "";
    const word = close[0] === "_" && /[\p{L}\p{N}]/u.test(after);
    if (at > from && !/\s/.test(before) && !word) return at;
    at = text.indexOf(close, at + 1);
  }
  return -1;
}

/** The target of a link written `(target "title")`, from the parenthesis on,
 * and how long that is; null where it is not one. */
function linkTarget(
  text: string,
  at: number,
): { url: string; length: number } | null {
  if (text[at] !== "(") return null;
  let depth = 0;
  for (let end = at; end < text.length; end += 1) {
    const char = text[end];
    if (char === "\\") end += 1;
    else if (char === "(") depth += 1;
    else if (char === ")") {
      depth -= 1;
      if (depth === 0) {
        const inside = text.slice(at + 1, end).trim();
        const url = /^<([^>]*)>|^(\S*)/.exec(inside);
        return { url: url?.[1] ?? url?.[2] ?? "", length: end - at + 1 };
      }
    }
  }
  return null;
}

/** The label of `[label]` that starts at `at`, and where it ends. */
function bracketed(
  text: string,
  at: number,
): { label: string; end: number } | null {
  let depth = 0;
  for (let end = at; end < text.length; end += 1) {
    const char = text[end];
    if (char === "\\") end += 1;
    else if (char === "`") {
      const close = text.indexOf("`", end + 1);
      if (close === -1) return null;
      end = close;
    } else if (char === "[") depth += 1;
    else if (char === "]") {
      depth -= 1;
      if (depth === 0) return { label: text.slice(at + 1, end), end: end + 1 };
    }
  }
  return null;
}

const SPANS = [
  ["**", "strong"],
  ["__", "strong"],
  ["~~", "del"],
  ["*", "em"],
  ["_", "em"],
] as const;

function Link({
  url,
  onOpenLink,
  children,
}: {
  url: string;
  onOpenLink?: OpenLink;
  children: ReactNode;
}) {
  // An address the host would refuse is not a door that does not open: its
  // words stay, and the address is there to read.
  if (!OPENABLE.test(url) && cadrumoLink(url).kind !== "page")
    return <span title={url}>{children}</span>;
  return (
    <a
      href={url}
      title={url}
      className="text-primary underline underline-offset-2 hover:text-primary/80 wrap-anywhere"
      // The window never leaves the app: the address opens in the browser.
      onClick={(event) => {
        event.preventDefault();
        onOpenLink?.(url);
      }}
      onAuxClick={(event) => event.preventDefault()}
    >
      {children}
    </a>
  );
}

function inline(text: string, onOpenLink: OpenLink | undefined): ReactNode[] {
  const out: ReactNode[] = [];
  let plain = "";
  const flush = () => {
    if (plain) out.push(plain);
    plain = "";
  };
  const push = (node: ReactNode) => {
    flush();
    out.push(<Fragment key={out.length}>{node}</Fragment>);
  };
  let at = 0;
  while (at < text.length) {
    const char = text[at] ?? "";
    const previous = text[at - 1] ?? " ";
    if (char === "\\" && PUNCTUATION.test(text[at + 1] ?? "")) {
      plain += text[at + 1];
      at += 2;
      continue;
    }
    if (char === "\n") {
      push(<br />);
      at += 1;
      continue;
    }
    if (char === "`") {
      const run = /^`+/.exec(text.slice(at))?.[0] ?? "`";
      const close = text.indexOf(run, at + run.length);
      if (close !== -1) {
        const code = text.slice(at + run.length, close).replace(/\n/g, " ");
        push(
          <code className="rounded-sm bg-muted px-1 font-mono text-sm wrap-anywhere">
            {/^ .* $/.test(code) ? code.slice(1, -1) : code}
          </code>,
        );
        at = close + run.length;
        continue;
      }
      plain += run;
      at += run.length;
      continue;
    }
    if (char === "!" && text[at + 1] === "[") {
      // An image is not fetched: its words stand for it, linked where it
      // can be opened.
      const label = bracketed(text, at + 1);
      const target = label && linkTarget(text, label.end);
      if (label && target) {
        push(
          <Link url={target.url} onOpenLink={onOpenLink}>
            {inline(label.label || target.url, onOpenLink)}
          </Link>,
        );
        at = label.end + target.length;
        continue;
      }
    }
    if (char === "[") {
      const label = bracketed(text, at);
      const target = label && linkTarget(text, label.end);
      if (label && target) {
        push(
          <Link url={target.url} onOpenLink={onOpenLink}>
            {inline(label.label, onOpenLink)}
          </Link>,
        );
        at = label.end + target.length;
        continue;
      }
    }
    if (char === "<") {
      const auto = /^<((?:https:\/\/|mailto:)[^\s<>]+)>/i.exec(text.slice(at));
      if (auto?.[1]) {
        push(
          <Link url={auto[1]} onOpenLink={onOpenLink}>
            {auto[1]}
          </Link>,
        );
        at += auto[0].length;
        continue;
      }
    }
    if (char === "h" && !/[\p{L}\p{N}]/u.test(previous)) {
      BARE_URL.lastIndex = at;
      const bare = BARE_URL.exec(text);
      if (bare) {
        const url = trimmedUrl(bare[0]);
        push(
          <Link url={url} onOpenLink={onOpenLink}>
            {url}
          </Link>,
        );
        at += url.length;
        continue;
      }
    }
    const span = SPANS.find(([mark]) => text.startsWith(mark, at));
    if (span) {
      const [mark, tag] = span;
      const opens =
        !/\s/.test(text[at + mark.length] ?? " ") &&
        !(mark[0] === "_" && /[\p{L}\p{N}]/u.test(previous));
      const close = opens ? closer(text, at + mark.length, mark) : -1;
      if (close !== -1) {
        const inner = inline(text.slice(at + mark.length, close), onOpenLink);
        push(
          tag === "strong" ? (
            <strong className="font-semibold">{inner}</strong>
          ) : tag === "em" ? (
            <em>{inner}</em>
          ) : (
            <del>{inner}</del>
          ),
        );
        at = close + mark.length;
        continue;
      }
      plain += mark;
      at += mark.length;
      continue;
    }
    plain += char;
    at += 1;
  }
  flush();
  return out;
}

const HEADING_SIZE = [
  "text-lg",
  "text-base",
  "text-base",
  "text-sm",
  "text-sm",
  "text-sm",
];
const ALIGN = { left: "text-left", center: "text-center", right: "text-right" };

function BlockView({
  block,
  onOpenLink,
}: {
  block: Block;
  onOpenLink?: OpenLink;
}) {
  switch (block.kind) {
    case "paragraph":
      return <p className="wrap-anywhere">{inline(block.text, onOpenLink)}</p>;
    case "heading": {
      const Tag = `h${Math.min(block.level + 2, 6)}` as "h3";
      return (
        <Tag
          className={cn(
            "font-semibold text-foreground wrap-anywhere",
            HEADING_SIZE[block.level - 1],
          )}
        >
          {inline(block.text, onOpenLink)}
        </Tag>
      );
    }
    case "code":
      return (
        <pre
          className="overflow-x-auto rounded-md bg-muted px-3 py-2 font-mono text-xs leading-relaxed"
          data-language={block.language || undefined}
        >
          <code>{block.text}</code>
        </pre>
      );
    case "quote":
      return (
        <blockquote className="border-l-2 border-border pl-3 text-muted-foreground">
          <Blocks blocks={block.blocks} onOpenLink={onOpenLink} />
        </blockquote>
      );
    case "list": {
      const items = apart(
        block.items.map((item, index) => (
          <li key={index} className="pl-1">
            <Blocks blocks={item} onOpenLink={onOpenLink} gap="gap-1" />
          </li>
        )),
      );
      return block.ordered ? (
        <ol
          start={block.start}
          className="grid list-decimal gap-1 pl-5 marker:text-muted-foreground"
        >
          {items}
        </ol>
      ) : (
        <ul className="grid list-disc gap-1 pl-5 marker:text-muted-foreground">
          {items}
        </ul>
      );
    }
    case "table":
      return (
        <div className="max-w-full overflow-x-auto">
          <table className="border-collapse text-sm">
            <thead>
              <tr>
                {block.head.map((cell, index) => (
                  <th
                    key={index}
                    className={cn(
                      "border-b border-border px-2 py-1 text-left font-semibold",
                      ALIGN[block.align[index] ?? "left"],
                    )}
                  >
                    {inline(cell, onOpenLink)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {block.rows.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {row.map((cell, index) => (
                    <td
                      key={index}
                      className={cn(
                        "border-b border-border/60 px-2 py-1 align-top",
                        ALIGN[block.align[index] ?? "left"],
                      )}
                    >
                      {inline(cell, onOpenLink)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    case "rule":
      return <hr className="border-border" />;
  }
}

function Blocks({
  blocks,
  onOpenLink,
  gap = "gap-2.5",
}: {
  blocks: readonly Block[];
  onOpenLink?: OpenLink;
  gap?: string;
}) {
  return (
    <div className={cn("grid min-w-0", gap)}>
      {apart(
        blocks.map((block, index) => (
          <BlockView key={index} block={block} onOpenLink={onOpenLink} />
        )),
      )}
    </div>
  );
}

/** `nodes` with a line break between each two. A grid draws none of them,
 * but the text of the reply, copied or read aloud, keeps its blocks apart. */
function apart(nodes: ReactNode[]): ReactNode[] {
  return nodes.flatMap((node, index) => (index === 0 ? [node] : ["\n", node]));
}

/** The blocks of a Markdown text, for tests and for the view below. */
export function markdownBlocks(text: string): Block[] {
  return parseBlocks(text.replace(/\r\n?/g, "\n").split("\n"));
}

/** A reply's Markdown, drawn as rich text. The host handles external links
 * and the exact local AEAT setup route; no other scheme is actionable. */
export function Markdown({
  text,
  onOpenLink,
  className,
}: {
  text: string;
  onOpenLink?: OpenLink;
  className?: string;
}) {
  const blocks = useMemo(() => markdownBlocks(text), [text]);
  return (
    <div className={cn("min-w-0 text-foreground", className)}>
      <Blocks blocks={blocks} onOpenLink={onOpenLink} />
    </div>
  );
}
