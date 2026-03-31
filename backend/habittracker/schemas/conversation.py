"""Conversation memory schema.

ConversationTurn is the typed unit of conversation history used by the
LangGraph pipeline and the chat provider interface.  It lives in schemas/
(not inside graph/) because it crosses module boundaries:

  graph/state.py      — stores list[ConversationTurn] in ChatGraphState
  graph/nodes.py      — reads / writes ConversationTurn entries
  providers/base.py   — ChatProvider.complete() receives list[ConversationTurn]
  providers/ollama_chat.py — serialises ConversationTurn to the Ollama payload

Using a TypedDict means instances are plain dicts at runtime, so they are
directly serialisable by MemorySaver (msgpack) and directly passable to the
Ollama HTTP payload without any extra conversion step.
"""

from typing_extensions import TypedDict


class ConversationTurn(TypedDict):
    """A single message in a conversation.

    role:    "system" | "user" | "assistant"
    content: The text content for that role.
    """

    role: str
    content: str
