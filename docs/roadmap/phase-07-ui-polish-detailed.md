# Phase 07 — UI Polish (Chat Integration)

## Goal
Expose the AI assistant through a usable UI so a user can interact with their habit data conversationally and inspect supporting evidence.

## Current State
- Frontend has Dashboard, Habits, Hydration, Notes pages
- Basic navigation and UI primitives (Card, Button, Badge, Spinner)
- No chat UI exists
- Backend AI pipeline (LangGraph) is complete but not visible

## Target Outcome
A demoable app where:
- user can open the app
- ask questions about their habits
- receive answers
- inspect evidence behind answers

---

## Design Decisions

### Chat Placement
- Slide-in panel (right side)
- Accessible globally (not a dedicated page)

### Evidence Display
- Secondary slide-in panel (to the left of chat panel)
- Triggered per assistant message
- Shows evidence items side-by-side with chat

### Thread Behavior
- thread_id managed in-memory
- resets on page refresh or navigation
- no persistence (aligned with backend MemorySaver)

### Design System
- Use existing primitives (Card, Button, Badge, Spinner)
- No external UI libraries

### Existing Pages
- No major redesign required
- Focus remains on chat experience

---

## Architecture

### API Layer
- `api/types.ts`
- `api/chat.ts`

### State Layer
- Central chat state (context or lightweight store)
  - messages
  - threadId
  - loading state

### UI Components
- ChatPanel (slide-in)
- ChatMessage
- EvidenceDrawer
- EvidenceCard

---

## Revisions

### Rev 01 — Chat API Client + Types

#### Scope
- Add ChatRequest and ChatResponse types
- Create `api/chat.ts`:
  - `sendChatMessage(req): Promise<ChatResponse>`

#### Deliverable
- Typed API client ready
- No UI yet

#### Out of scope
- rendering
- state management

---

### Rev 02 — Chat Panel + Routing

#### Scope
- Add ChatPanel (slide-in)
- Add global trigger (e.g. button or navbar)
- Add:
  - message input
  - send button
  - message list
- Add ChatMessage component
- Maintain:
  - messages list
  - thread_id
- Send messages to backend and render responses

#### Deliverable
- user can chat with AI
- multi-turn works within session

#### Out of scope
- evidence display

---

### Rev 03 — Evidence Display

#### Scope
- Add EvidenceCard component
- Add EvidenceDrawer panel (secondary slide)
- Add “View Evidence” trigger per assistant message
- Track selected message for evidence display
- Show:
  - type
  - label
  - value
- Show indicator when `used_notes = true`
- Do not render empty evidence blocks

#### Deliverable
- user can inspect supporting data for each answer

---

### Rev 04 — Integration + Polish

#### Scope
- Add “Ask AI” button on Dashboard
  - opens chat panel
  - optionally pre-fills message
- Add loading state:
  - spinner or typing indicator
- Disable input while request is in progress
- Add error handling:
  - user-friendly message on failure
- Auto-scroll to latest message
- Ensure layout:
  - independent scrolling for chat and evidence panels
  - no body scroll conflicts

#### Deliverable
- smooth demo experience
- integrated chat flow

---

## UX Rules

- Chat panel opens from the right
- Evidence panel opens adjacent to chat
- Only one evidence view active at a time
- Chat remains readable without evidence panel open
- Evidence enhances trust but does not clutter conversation

---

## Data Model (Frontend)

```ts
type ChatMessage = {
  role: "user" | "assistant"
  content: string
  intent?: string
  evidence?: EvidenceItem[]
  used_notes?: boolean
}