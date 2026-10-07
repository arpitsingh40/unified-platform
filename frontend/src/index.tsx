import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import App from "./App";

// Mount the app into the root DOM node
const rootElement = document.getElementById("root");
if (!rootElement) throw new Error("Root element not found");
const root = ReactDOM.createRoot(rootElement);
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
