import { useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { BookOpen, ChevronLeft, Search, X } from "lucide-react";
import { chapters } from "virtual:desktop-content";

export function Documentation({
  compact = false,
  onClose,
}: {
  compact?: boolean;
  onClose?: () => void;
}) {
  const [selected, setSelected] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [notice, setNotice] = useState("");
  const chapter = chapters.find((item) => item.id === selected);
  function navigate(href: string | undefined) {
    if (!href) return;
    const name = href.split("/").pop()?.split("#")[0]?.replace(/\.md$/, "");
    if (chapters.some((item) => item.id === name)) {
      setSelected(name ?? null);
      setNotice("");
    } else
      setNotice(
        "This reference is part of the full manual. Use All chapters to explore the explanations included in this preview.",
      );
  }
  return (
    <section
      className={`documentation ${compact ? "compact" : ""}`}
      aria-label="Documentation"
    >
      <header className="docs-header">
        <span className="eyebrow">
          <BookOpen size={15} /> FIELD GUIDE
        </span>
        <span className="offline-label">Available offline</span>
        {onClose && (
          <button
            className="icon-button"
            onClick={onClose}
            aria-label="Close documentation"
          >
            <X size={17} />
          </button>
        )}
      </header>
      {notice && (
        <p className="inline-notice" role="status">
          {notice}
        </p>
      )}
      <div className="docs-scroll" key={selected}>
        {chapter ? (
          <>
            <button
              className="text-button"
              onClick={() => {
                setSelected(null);
                setNotice("");
              }}
            >
              <ChevronLeft size={16} /> All chapters
            </button>
            <article className="prose">
              <Markdown
                remarkPlugins={[remarkGfm]}
                components={{
                  a: ({ href, children }) => (
                    <button
                      className="prose-link"
                      onClick={() => navigate(href)}
                    >
                      {children}
                    </button>
                  ),
                }}
              >
                {chapter.markdown}
              </Markdown>
            </article>
            <div className="chapter-footer">
              From the bundled {chapters.length}-chapter preview of the user
              manual.
            </div>
          </>
        ) : (
          <>
            <h1>Understand each step.</h1>
            <p className="muted">
              From the records you keep to the return you file. A guide to how
              your work fits together.
            </p>
            <label className="search-field">
              <Search size={17} />
              <input
                aria-label="Search documentation"
                placeholder="Find a chapter…"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </label>
            <div className="chapter-list">
              {chapters
                .filter((item) =>
                  `${item.title} ${item.markdown}`
                    .toLowerCase()
                    .includes(query.toLowerCase()),
                )
                .map((item, index) => (
                  <button key={item.id} onClick={() => setSelected(item.id)}>
                    <span className="chapter-number">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <span>{item.title}</span>
                    <span aria-hidden="true">↗</span>
                  </button>
                ))}
            </div>
            {!chapters.some((item) =>
              `${item.title} ${item.markdown}`
                .toLowerCase()
                .includes(query.toLowerCase()),
            ) && (
              <p role="status">
                No chapters match “{query}”. Try a different word.
              </p>
            )}
            <div className="docs-note">
              <BookOpen size={20} />
              <p>
                These are the existing user manual’s explanatory chapters. Full
                tutorials and command references will arrive with the packaged
                documentation.
              </p>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
