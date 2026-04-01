/**
 * ChatContext — central state for the slide-in chat panel.
 *
 * Responsibilities:
 *   - Track whether the panel is open
 *   - Hold the conversation messages list
 *   - Hold the current thread_id (reset on page refresh, per design decision)
 *   - Expose sendMessage() which calls the API and appends results
 *   - Track loading / error state
 */
import {
  createContext,
  useCallback,
  useContext,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { sendChatMessage } from "../api/chat";
import type { EvidenceItem } from "../api/types";

// ── Types ─────────────────────────────────────────────────────────────────────

export type MessageRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  intent?: string;
  used_notes?: boolean;
  evidence?: EvidenceItem[];
  error?: boolean;
}

interface ChatState {
  isOpen: boolean;
  messages: ChatMessage[];
  loading: boolean;
  openPanel: () => void;
  closePanel: () => void;
  togglePanel: () => void;
  sendMessage: (text: string) => Promise<void>;
  clearThread: () => void;
}

// ── Context ───────────────────────────────────────────────────────────────────

const ChatContext = createContext<ChatState | null>(null);

let _msgCounter = 0;
function nextId() {
  return `msg-${++_msgCounter}`;
}

// ── Provider ──────────────────────────────────────────────────────────────────

export function ChatProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const threadIdRef = useRef<string | undefined>(undefined);

  const openPanel = useCallback(() => setIsOpen(true), []);
  const closePanel = useCallback(() => setIsOpen(false), []);
  const togglePanel = useCallback(() => setIsOpen((v) => !v), []);

  const clearThread = useCallback(() => {
    setMessages([]);
    threadIdRef.current = undefined;
  }, []);

  const sendMessage = useCallback(async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || loading) return;

    // Append user message immediately
    const userMsg: ChatMessage = { id: nextId(), role: "user", content: trimmed };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const resp = await sendChatMessage({
        message: trimmed,
        thread_id: threadIdRef.current,
      });

      // Persist the thread_id for the next turn
      threadIdRef.current = resp.thread_id;

      const assistantMsg: ChatMessage = {
        id: nextId(),
        role: "assistant",
        content: resp.answer,
        intent: resp.intent,
        used_notes: resp.used_notes,
        evidence: resp.evidence,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      const detail =
        err instanceof Error ? err.message : "Something went wrong. Try again.";
      setMessages((prev) => [
        ...prev,
        { id: nextId(), role: "assistant", content: detail, error: true },
      ]);
    } finally {
      setLoading(false);
    }
  }, [loading]);

  return (
    <ChatContext.Provider
      value={{
        isOpen,
        messages,
        loading,
        openPanel,
        closePanel,
        togglePanel,
        sendMessage,
        clearThread,
      }}
    >
      {children}
    </ChatContext.Provider>
  );
}

// ── Hook ──────────────────────────────────────────────────────────────────────

export function useChat(): ChatState {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error("useChat must be used inside <ChatProvider>");
  return ctx;
}
