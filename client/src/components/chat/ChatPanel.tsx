import { useEffect, useRef, useState } from "react";
import { useChat } from "../../context/ChatContext";
import { Spinner } from "../ui/Spinner";
import { ChatMessage } from "./ChatMessage";
import styles from "./ChatPanel.module.css";

export function ChatPanel() {
  const { isOpen, closePanel, messages, loading, sendMessage, clearThread } = useChat();
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to newest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Focus input when panel opens
  useEffect(() => {
    if (isOpen) inputRef.current?.focus();
  }, [isOpen]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || loading) return;
    sendMessage(input);
    setInput("");
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as unknown as React.FormEvent);
    }
  }

  return (
    <>
      {/* Backdrop — clicking outside closes panel */}
      {isOpen && <div className={styles.backdrop} onClick={closePanel} />}

      <aside className={[styles.panel, isOpen ? styles.open : ""].join(" ")}>
        {/* Header */}
        <div className={styles.header}>
          <div className={styles.headerLeft}>
            <span className={styles.headerIcon}>◈</span>
            <div>
              <p className={styles.headerTitle}>AI Assistant</p>
              <p className={styles.headerSub}>Ask about your habits &amp; data</p>
            </div>
          </div>
          <div className={styles.headerActions}>
            <button
              className={styles.iconBtn}
              onClick={clearThread}
              title="Start new thread"
              disabled={messages.length === 0}
            >
              ↺
            </button>
            <button className={styles.iconBtn} onClick={closePanel} title="Close">
              ✕
            </button>
          </div>
        </div>

        {/* Message list */}
        <div className={styles.messages}>
          {messages.length === 0 && (
            <div className={styles.empty}>
              <p className={styles.emptyTitle}>Ask me anything</p>
              <p className={styles.emptySub}>
                "How much water did I drink today?"<br />
                "Did I complete my morning habit?"<br />
                "What patterns appear in my notes?"
              </p>
            </div>
          )}

          {messages.map((msg) => (
            <ChatMessage key={msg.id} message={msg} />
          ))}

          {loading && (
            <div className={styles.thinking}>
              <Spinner size="sm" />
              <span>Thinking…</span>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <form className={styles.inputRow} onSubmit={handleSubmit}>
          <textarea
            ref={inputRef}
            className={styles.input}
            placeholder="Ask about your habits…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            disabled={loading}
          />
          <button
            type="submit"
            className={styles.sendBtn}
            disabled={!input.trim() || loading}
            title="Send"
          >
            ↑
          </button>
        </form>
      </aside>
    </>
  );
}
