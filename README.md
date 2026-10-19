# RehlaGuide

An AI-powered travel assistant for Egypt (DEPI capstone). Given a request in Arabic or English such as *"3 days in Luxor, I love temples"*, it builds a day-by-day itinerary that respects opening hours, visit durations and travel time, and answers in the user's language.

This README documents the **knowledge base and retrieval (Member 1)**, the **travel agent and itinerary engine (Member 2)** and the **backend API (Member 3)**.

---

## 1. Status

| Area | Status |
|---|---|
| Knowledge base (30 attractions) and vector index | Implemented |
| Retrieval with filters + evaluation suite | Implemented |
| Attraction, hours, price and travel-time tools | Implemented |
| Deterministic scheduler (hours, travel, grouping) | Implemented |
| Gemini intent extraction and itinerary wording | Implemented |
| Arabic / English support | Implemented (Arabic queries are translated to English for retrieval) |
| Session memory and itinerary edits ("make day 2 lighter") | **Not implemented yet** |
| Backend API (FastAPI, `/api/v1/...`) | Implemented (see section 12) |

---

## 2. Architecture

```
User message (Arabic or English)
        |
        v
agents/intent.py     Gemini extracts JSON  ->  Python validates every field
        |
        v
agents/retrieval_adapter.py   ->   rag/retriever.py   ->   ChromaDB (MiniLM embeddings)
        |                          (Member 1)
        v
agents/scheduler.py  uses  hours.py / travel.py / attractions.py   (plain Python, no LLM)
        |
        v
agents/planner.py    Gemini words the plan  ->  guard checks times and prices
        |
        v
Reply in the user's language + structured itinerary
```

**Design principle:** the LLM is used for language (understanding the request, writing the reply). Everything that must be correct - opening hours, travel time, prices, what fits in a day - is deterministic Python, so a model mistake cannot break a hard constraint.

---

## 3. Repository structure

```
RehlaGuide/
├── rag/                         Member 1: knowledge base and retrieval
│   ├── config.py                paths, embedding model name, default top-k
│   ├── ingest.py                builds the Chroma index from raw_attractions.json
│   ├── retriever.py             search_attractions() with metadata filters
│   └── eval.py                  retrieval evaluation (51 cases)
├── agents/                      Member 2: agent, tools, itinerary
│   ├── attractions.py           load attraction records, get_attraction_details
│   ├── hours.py                 structured opening hours, check_opening_hours
│   ├── pricing.py               check_ticket_price
│   ├── travel.py                calculate_travel_time (estimate)
│   ├── scheduler.py             build_itinerary
│   ├── retrieval_adapter.py     the agent's only entry point to Member 1's retriever
│   ├── intent.py                message -> validated trip request
│   ├── planner.py               full pipeline: plan_trip()
│   ├── llm.py                   the only file that calls Gemini
│   └── data/
│       ├── attraction_extras.json   structured hours per attraction
│       └── locations.json           coordinates and notes per attraction
├── data/
│   ├── raw_attractions.json     the dataset (30 attractions)
│   └── chroma_db/               generated locally, gitignored
├── tests/                       pytest suite (LLM calls are mocked)
├── conftest.py                  empty; lets pytest import agents/ and rag/
├── .env.example                 template for your local .env
└── pyproject.toml
```

---

## 4. Setup

Requirements: Python 3.13 (see `.python-version`) and [uv](https://docs.astral.sh/uv/).

```bash
uv sync                          # install dependencies
uv run python -m rag.ingest      # build the vector index (required once, see note)
cp .env.example .env             # then put your own key in .env
```

`.env`:
```
GEMINI_API_KEY=your-key-here
GEMINI_MODEL=gemini-3.8-flash
```

Notes:
- `.env` is gitignored. **Never commit it, and never put a real key in `.env.example`.**
- `data/chroma_db/` is gitignored and is **not** in the repository. Every developer must run `rag.ingest` locally. Ingest deletes any existing index and rebuilds it from scratch, so it is safe to re-run.
- Model names are retired from time to time (a previous default, `gemini-2.5-flash`, was). If you get a `404 NOT_FOUND` for the model, change `GEMINI_MODEL` in `.env`.
- The "unauthenticated requests to the HF Hub" warning is harmless. It only concerns the embedding-model download.
- Run all commands from the repository root. `agents` and `rag` are imported as top-level packages from there.

---

## 5. Usage

Command line:
```bash
uv run python -m agents.planner "3 days in Luxor, I love temples"
uv run python -m agents.planner "ثلاثة أيام في الأقصر وأحب المعابد"
uv run python -m agents.planner "2 days in Cairo, I'm a tourist, museums, starting Friday"
```

Python:
```python
from agents.planner import plan_trip

result = plan_trip("2 days in Cairo, I'm a tourist, museums, starting Friday")
```

`plan_trip` never raises. It returns one of:

```python
{"ok": False, "error": "human-readable reason"}      # LLM down, retrieval failed, ...

{"ok": True,
 "status": "planned" | "needs_clarification" | "unsupported_region" | "out_of_scope" | "no_results",
 "language": "ar" | "en",
 "reply": "text to show the user",
 "intent": {...},                  # the validated request
 "itinerary": {...},               # only when status == "planned"
 "used_fallback": False}           # only when status == "planned"
```

| status | Meaning |
|---|---|
| `planned` | An itinerary was built. `reply` is the wording, `itinerary` the structured data. |
| `needs_clarification` | Days or region missing. `reply` is the question (in the user's language), `missing` lists the fields. |
| `unsupported_region` | The user named a place we have no data for (e.g. Dahab). |
| `out_of_scope` | The message is not a trip request. |
| `no_results` | Retrieval found nothing. |

---

## 6. Part 1 - Knowledge base and retrieval (Member 1)

### Dataset - `data/raw_attractions.json`
30 attractions across 10 regions (Cairo, Giza, Luxor, Aswan, Alexandria, Sharm El Sheikh, Saint Catherine, Hurghada, Siwa, Farafra) and 10 categories (Museum, Archaeological Site, Temple, Fortress, Cultural Center, National Park, Monastery, Aquarium, Island / Beach, Historic Oasis).

Each record has: `id`, `name`, `city`, `region`, `category`, `description`, `opening_hours` (free text), `ticket_price_egyptian_adult_egp`, `ticket_price_foreigner_adult_egp`, `estimated_visit_duration_min`, `source_url`, `last_verified`.

### Ingestion - `rag/ingest.py`
- Builds one text document per attraction (name, region, category, description, hours, prices, duration).
- Stores metadata for filtering: `id`, `name`, `region`, `category`, both prices, `estimated_duration_hours`.
- Embeds with `all-MiniLM-L6-v2` (English-only sentence-transformer) and persists to ChromaDB in `data/chroma_db/`.
- Deletes the existing index before rebuilding. Without this, every run appended another copy and the index grew to 100 rows for 30 places.

### Retrieval - `rag/retriever.py`
```python
search_attractions(query, region=None, category=None, max_duration=None, top_k=5)
```
Returns a list of `{"content": str, "metadata": {...}, "relevance_score": float}`.

- Filters are exact-match on `region` and `category`, and `<=` on `estimated_duration_hours` (hours, not minutes). Multiple filters are combined with AND.
- `relevance_score` is a Chroma **distance**: lower means closer, not higher.
- Only one region can be passed per call.

### Evaluation - `rag/eval.py`
```bash
uv run python -m rag.eval              # full evaluation
uv run python -m rag.eval --validate   # check the dataset only (no model, no DB)
uv run python -m rag.eval --json out.json
```
51 labelled queries with graded relevance (2 = the place the query is about, 1 = acceptable), in five slices: semantic, filtered, intent, Arabic and out-of-scope. It also checks index health (every attraction exactly once), filter integrity and duplicate results.

Latest results on a healthy index (30 rows, 30/30 attractions):

| Slice | n | Hit@3 | Recall@3 | nDCG@3 | MRR |
|---|---|---|---|---|---|
| Headline (semantic + intent, unfiltered) | 31 | 96.8% | 82.8% | 86.9% | 0.935 (MRR@5) |
| Semantic | 27 | 96.3% | 82.1% | 87.3% | 0.944 |
| Filtered | 10 | 100% | 91.7% | 94.8% | 1.000 |
| Intent | 4 | 100% | 87.5% | 84.5% | 0.875 |
| **Arabic** | 6 | **50.0%** | 44.4% | 24.9% | 0.222 |

Headline Hit@1 is 90.3%. Filter integrity: 0 violations. Duplicates in top-5: 0.

Findings:
- English retrieval is strong. The one English miss is *"Step Pyramid and the Imhotep Museum"* (Saqqara).
- Arabic retrieval with this English-only model is not usable directly. This is why the agent translates Arabic queries to English before searching.
- There is almost no gap between the worst in-scope top-1 distance (1.372) and the best out-of-scope top-1 distance (1.391), so a "no result" distance cutoff is only a soft signal.

---

## 7. Part 2 - Agent and itinerary (Member 2)

### 7.1 Tools

All tools return `{"ok": True, ...}` or `{"ok": False, "error": "..."}`. None of them raises on bad input.

| Tool (file) | Input | Output |
|---|---|---|
| `get_attraction_details` (`attractions.py`) | `attraction_id` | all fields of the attraction |
| `check_opening_hours` (`hours.py`) | `attraction_id`, `day` (weekday name or ISO date), `start` ("HH:MM"), optional `duration_min` | `open` true/false/None, `windows`, `confidence`, `reason`, `note` |
| `check_ticket_price` (`pricing.py`) | `attraction_id`, `visitor_type` ("egyptian" or "foreigner") | `price_egp`, `price_note`, `source_url`, `last_verified` |
| `calculate_travel_time` (`travel.py`) | `from_id`, `to_id` | `minutes`, `straight_km`, `road_km_estimate`, `estimate: True`, `long_distance` |
| `build_itinerary` (`scheduler.py`) | `candidate_ids` (most relevant first), `days`, optional `first_day`, `day_start`, `day_end`, `max_stops_per_day` | `days`, `unscheduled`, `warnings` |
| `search_attractions` (`retrieval_adapter.py`) | `query`, `region`, `category`, `max_duration_hours`, `top_k`, `apply_cutoff` | results with the full record and distance |

Behaviour worth knowing:
- `check_ticket_price` refuses to guess the visitor type. The agent must ask or know it. Only **adult** tickets are stored.
- A price of 0 EGP (ids 25 and 28) is reported with a warning, because it may mean "free" or "not recorded".
- `calculate_travel_time` is **always an estimate** and says so.

### 7.2 Data files (`agents/data/`)

`attraction_extras.json` - structured opening hours, written by hand from the dataset text and official pages because the raw `opening_hours` field is free text:
```json
"15": {"default": [["09:00","17:00"]],
       "overrides": {"thu": [["09:00","17:00"],["18:00","21:00"]]},
       "confidence": "listed", "note": "Evening session on Thursday and Friday only."}
```
- `default` applies to every day; `overrides` replace it for a specific weekday; `[]` means closed all day.
- `confidence` is `listed` or `uncertain`. Three places are `uncertain` (ids 5, 19, 22) because the sources disagree. The scheduler adds a "check before you go" warning for them.
- `validate_hours()` checks that the file matches the dataset (every id present, valid times).

`locations.json` - latitude/longitude per attraction plus notes such as "On an island; reached by a short boat ride". `validate_locations()` checks coverage and that points lie inside Egypt. Two coordinates (Hurghada Aquarium, Giftun Island) are marked as least certain.

### 7.3 Scheduler rules (`scheduler.py`)

Hard constraints, enforced in plain Python:
- A visit must fit entirely inside an opening window, on every weekday it could fall on when no date is given (no date means only places open every day are used).
- Greater Cairo is treated as one area (Cairo + Giza). Other regions are separate areas, and one day stays in one area.
- Places more than 150 km apart never share a day.
- Travel time between consecutive stops is added to the clock. Waiting for a place to open is allowed up to 90 minutes.
- Day window defaults to 09:00-18:00, at most 4 stops per day (the planner lowers this to 2-3 to spread places over the days).
- Spare days go to the area with the most candidates. Anything that does not fit is returned in `unscheduled` with a reason.

Choosing among valid options: each next stop is scored by travel time + waiting time + a small penalty for lower search rank, and the lowest score wins.

Travel estimate: straight-line (haversine) distance x 1.3 road factor, divided by an average speed (20 km/h under 5 km, 30 km/h up to 60 km, 70 km/h beyond), plus 10 minutes, rounded to 5 minutes.

### 7.4 Retrieval adapter (`retrieval_adapter.py`)
The agent never calls Member 1's retriever directly. The adapter:
- validates region and category against the real data (case-insensitive);
- expands "Cairo" to Cairo + Giza (two retriever calls, because the retriever accepts one region);
- removes duplicates, keeping each place's best distance;
- drops results beyond a distance cutoff of 1.38 (disabled with `apply_cutoff=False`, which the planner uses when the user named a region, so relevance only orders the places and never removes them);
- attaches the full record from `raw_attractions.json`;
- never raises.

If Member 1 changes retrieval internals, only this file needs to change.

### 7.5 Intent extraction (`intent.py`)
Gemini returns JSON with: task, language, an English search query, interests, region, days, travel date and visitor type. Python then validates every field: days must be 1-14, the region must exist in the data, dates must be understandable, and the visitor type must map to "egyptian"/"foreigner". Missing required details (days, region) are decided in code, not by the model, and are asked for with fixed Arabic/English templates.

### 7.6 Planner and reply guard (`planner.py`)
After scheduling, Gemini writes the itinerary in the user's language from the structured data only. A guard then checks that **every scheduled start/end time and every ticket price appears in the reply** (Arabic-Indic digits are normalised). If anything is missing or the model call fails, the reply is replaced by a plain deterministic rendering (`used_fallback: True`). Ticket prices are included only when the visitor type is known.

### 7.7 LLM wrapper (`llm.py`)
The only file that talks to Gemini. It reads `GEMINI_API_KEY` and `GEMINI_MODEL`, returns an error dict instead of raising, and retries temporary errors (503, 429, timeouts) up to three times with a short wait. Everything else receives the LLM as a function argument, which is why tests run without internet or a key.

---

## 8. Testing

```bash
uv run pytest -q
```

69 tests cover: data lookup and prices, opening-hours edge cases (window ends, split hours, weekday overrides, closed days, ISO dates), travel estimates, the scheduler (an independent checker re-validates every stop against hours, day bounds and travel gaps), the retrieval adapter (with a fake search function), intent extraction, the planner pipeline and reply guard, and the LLM retry logic. Gemini calls are mocked in all tests.

Not covered by automated tests: real Gemini calls and real Chroma retrieval. Check those manually with the commands in section 5.

---

## 9. Known limitations

- **Day trips:** Abu Simbel, Edfu and Kom Ombo are scheduled as if the traveller starts there. The journey from Aswan is not added to the day.
- **Inter-city travel:** consecutive days can be in different cities (e.g. Cairo then Luxor) with no transfer time. The plan only carries a warning.
- **Travel times are estimates** from straight-line distance. They ignore traffic and, for example, the Nile crossing in Luxor.
- **Grouping:** places are not clustered by sub-area, so a plan may split nearby places across days (e.g. West Bank sites in Luxor).
- **Ticket windows** (for example "ticket window closes 16:00") are stored as notes only, not enforced as hard limits.
- **Prices** are adult tickets only and may be outdated. The dataset records a verification date and source URL per attraction.
- **Reply wording:** the guard verifies times and prices only. The model can still phrase notes imperfectly (for example attach a note to the wrong stop).
- **Arabic:** reliant on Gemini translating the query to English. Place names in Arabic replies stay in English. Day names in Arabic ("الجمعة") depend on the model converting them to a weekday name or date.
- **Dataset size:** 30 attractions. The retrieval distance cutoff should be recalibrated if it grows.
- **No memory yet:** every request is planned from scratch.

---

## 10. Notes for integration (Member 3)

- The entry point is `agents.planner.plan_trip(message)`, returning the dict described in section 5. The API contract for `/api/v1/chat` has not been agreed, so nothing here defines it.
- Session memory is not implemented. Once it is, the function will need a session identifier or state object. This is to be agreed with Member 3.
- `rag/retriever.py` creates a new embedding model object on every call, so each search (two for Cairo) reloads the model. This is acceptable for the CLI but will be slow behind an API. Caching the vector store in the retriever is the fix (Member 1's file).
- Run from the repository root; `agents` and `rag` are not installed as packages.
- The vector index must be built on the server with `uv run python -m rag.ingest`.
- `GEMINI_API_KEY` must be supplied through the environment.

---

## 11. Roadmap

1. Session memory and itinerary edits (change a day, swap a place, add a day without discarding the rest).
2. Day-trip travel time for far attractions.
3. Better grouping of nearby places within a day.
4. Integration with the backend once the `/api/v1/chat` contract is agreed.

---

## 12. Part 3 - Backend API (Member 3)

```bash
uv run uvicorn backend.main:app --reload     # from the repository root
```
Interactive docs: http://127.0.0.1:8000/docs

### Endpoints (prefix `/api/v1`)

| Method | Path | Purpose |
|---|---|---|
| POST | `/chat` | `{"message", "session_id"?}` -> agent reply + structured itinerary |
| GET / DELETE | `/sessions/{id}` | Conversation history / end a session |
| POST | `/itinerary` | Deterministic schedule from chosen ids (no LLM): `{"attraction_ids", "days", "first_day"?, "day_start"?, "day_end"?, "max_stops_per_day"?, "visitor_type"?}` |
| GET | `/attractions` | List, filters: `region` ("Cairo" includes Giza), `category`, `q` |
| GET | `/attractions/{id}` | Full details, structured hours, map location, data freshness warnings |
| GET | `/attractions/{id}/opening?day=&start=` | Is it open for that visit? |
| GET | `/regions`, `/categories` | Valid filter values |
| GET | `/analytics` | Dashboard counters: queries, statuses, languages, top regions/attractions/interests, cache hit rate, avg latency |
| GET | `/health` | Index present, vector store loaded, LLM key set |
| DELETE | `/cache` | Clear cached answers (after a data update) |

`/chat` response:
```json
{"session_id": "...", "status": "planned", "language": "en", "reply": "...",
 "intent": {...}, "itinerary": {"days": [...], "unscheduled": [...], "warnings": [...]},
 "missing": null, "used_fallback": false, "cached": false}
```
Send `session_id` back with the next message. If the agent asked a clarifying question (`needs_clarification`), the next message is combined with the original request, so "3 days" completes "Trip to Cairo".

Every error has one shape: `{"error": {"code": "...", "message": "...", "details": ...}}`.

| HTTP | code | When |
|---|---|---|
| 400 | `bad_request` | Unknown region/category/id, bad day or time |
| 404 | `not_found` | Unknown attraction or session |
| 422 | `validation_error` | Request body/query failed validation (`details` lists fields) |
| 502 | `llm_unavailable` / `agent_error` | Gemini failed after retries |
| 503 | `llm_not_configured` / `retrieval_unavailable` | Missing `GEMINI_API_KEY`, or vector index not built |

### Design
- `backend/services/chat.py` is the only place that calls `agents.planner.plan_trip`. Endpoints are sync functions, so FastAPI runs the blocking LLM call in its thread pool.
- **Caching:** in-memory TTL + LRU cache keyed on the normalized message (case, punctuation, Arabic digits) plus today's date (the agent resolves "next Friday" against today). Only successful answers are cached. Swap `TTLCache` for Redis if we run several workers.
- **Vector store:** `rag.retriever.get_vector_store()` reloads the embedding model on every call. The backend wraps it in an `lru_cache` at startup and warms it up (`backend/services/retrieval.py`), without changing `rag/`.
- **Outdated data:** `/attractions/{id}` returns `freshness` with `stale` (older than `STALE_AFTER_DAYS`) and warnings for uncertain hours, 0 EGP prices and missing locations.
- Analytics, sessions and cache are in memory and reset on restart.
- Every response carries `X-Request-ID` and `X-Process-Time-Ms`.

Settings (all optional, see `.env.example`): `CORS_ORIGINS`, `CACHE_TTL_SECONDS`, `CACHE_MAX_ENTRIES`, `SESSION_TTL_SECONDS`, `STALE_AFTER_DAYS`, `WARMUP_ON_STARTUP`.

Tests: `tests/test_api.py` (the agent is replaced by a fake, no network needed).
