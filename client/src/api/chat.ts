import { apiFetch } from "./client";
import type { ChatRequest, ChatResponse } from "./types";

/**
 * Send a chat message to the AI assistant.
 *
 * Passes an optional thread_id so multi-turn conversations work within a
 * session.  The server always returns a thread_id in the response — callers
 * should store it and include it in subsequent requests on the same thread.
 *
 * Throws ApiError on non-2xx responses (e.g. 503 when Ollama is unavailable).
 */
export async function sendChatMessage(req: ChatRequest): Promise<ChatResponse> {
  return apiFetch<ChatResponse>("/v1/chat/", {
    method: "POST",
    body: JSON.stringify(req),
  });
}
