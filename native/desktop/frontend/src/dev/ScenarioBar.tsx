import { SCENARIOS, type Scenario } from "./scenarios";

/** One host call, numbered so the list keeps its rows as it slides. */
export type HostCallLine = { id: number; call: string };

// The development entry's own control: it names the page as simulated and
// switches scenario and language. It is tool chrome, not product chrome, so
// its text is not in the locale catalogues and it never ships.
export function ScenarioBar({
  scenario,
  language,
  languages,
  calls,
  onScenario,
  onLanguage,
  onRestart,
}: {
  scenario: Scenario;
  language: string;
  languages: readonly string[];
  calls: readonly HostCallLine[];
  onScenario: (id: string) => void;
  onLanguage: (language: string) => void;
  onRestart: () => void;
}) {
  return (
    <details className="scenario-bar">
      <summary>
        <span className="scenario-bar-flag">Simulated host</span>
        <span className="scenario-bar-name">{scenario.title}</span>
      </summary>
      <div className="scenario-bar-body">
        <p className="scenario-bar-note">
          Nothing here reaches a desktop host. A sign-in this page accepts
          authenticated nothing.
        </p>
        <label>
          <span>Scenario</span>
          <select
            value={scenario.id}
            onChange={(event) => onScenario(event.target.value)}
          >
            {SCENARIOS.map((entry) => (
              <option key={entry.id} value={entry.id}>
                {entry.title}
              </option>
            ))}
          </select>
        </label>
        <p className="scenario-bar-summary">{scenario.summary}</p>
        <label>
          <span>Language</span>
          <select
            value={language}
            onChange={(event) => onLanguage(event.target.value)}
          >
            {languages.map((code) => (
              <option key={code} value={code}>
                {code}
              </option>
            ))}
          </select>
        </label>
        <button type="button" onClick={onRestart}>
          Restart scenario
        </button>
        <div className="scenario-bar-calls">
          <span>Host calls</span>
          <ol aria-label="Host calls">
            {calls.map(({ id, call }) => (
              <li key={id}>{call}</li>
            ))}
          </ol>
        </div>
      </div>
    </details>
  );
}
