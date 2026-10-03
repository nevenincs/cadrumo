import { identity } from "virtual:desktop-content";

export function App() {
  return (
    <main className="front-page">
      <h1>{identity.display_name}</h1>
    </main>
  );
}
