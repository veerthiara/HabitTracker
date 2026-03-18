import { useState } from "react";
import { apiBaseUrl, fetchBackendRoot } from "./api";

type RequestState = "idle" | "loading" | "success" | "error";

function App() {
  const [state, setState] = useState<RequestState>("idle");
  const [message, setMessage] = useState("No response yet");

  async function handleCallBackend() {
    setState("loading");

    try {
      const payload = await fetchBackendRoot();
      setMessage(payload.message);
      setState("success");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unknown error");
      setState("error");
    }
  }

  return (
    <main className="container">
      <h1>Minimal Client</h1>
      <p>API base: {apiBaseUrl}</p>
      <button type="button" onClick={handleCallBackend} disabled={state === "loading"}>
        {state === "loading" ? "Calling backend..." : "Call backend /"}
      </button>
      <p>Status: {state}</p>
      <pre>{message}</pre>
    </main>
  );
}

export default App;
