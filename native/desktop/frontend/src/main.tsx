import React from "react";
import ReactDOM from "react-dom/client";
import { identity } from "virtual:desktop-content";
import { App } from "./App";
import "./styles.css";

document.title = `${identity.display_name} · Desktop preview`;
const root = document.getElementById("root");
if (!root) throw new Error("Application root is missing.");
ReactDOM.createRoot(root).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
