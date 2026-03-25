"""LangGraph orchestration package for the AI chat pipeline.

Phase 06 introduces a graph-based workflow to replace the sequential
handle_chat() pipeline.  This package is built incrementally across revisions:

  Rev 01 — state.py: ChatGraphState TypedDict (this revision)
  Rev 02 — nodes.py, routing.py, builder.py: graph compiles, no endpoint change
  Rev 03 — end-to-end run validated against handle_chat output
  Rev 04 — thread_id + MemorySaver checkpointer
  Rev 05 — endpoint wired to graph, handle_chat retired from active use
"""
