# Data Model Overview

## Core entities
- User
- Habit
- HabitLog
- BottleEvent
- Note
- DailySummary

## Purpose of each entity

### User
Represents the app user.

### Habit
Represents a trackable habit such as water intake, stretching, or walking.

### HabitLog
Stores completion or progress records for a habit.

### BottleEvent
Stores bottle-related events such as pickup time, sip event, or manual hydration log.

### Note
Stores free-text notes or reflections entered by the user.
These may later be embedded into pgvector for semantic retrieval.

### DailySummary
Stores precomputed daily metrics such as counts, streak-related stats, and summaries.

## Future entities
- VisionEvent
- PostureEvent
- CameraSession
- Device

## Notes
Structured product data is the primary data source.
Embeddings are a secondary layer used only for semantic search and AI features.