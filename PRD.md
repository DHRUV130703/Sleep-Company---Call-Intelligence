# PRD — LimeZip Call Intelligence

| | |
|---|---|
| **Product** | LimeZip Call Intelligence (working name) |
| **Owner** | Product (Sleep Company — Sales & CX Analytics) |
| **Status** | v1.0 — Ready for build |
| **Date** | 07 Oct 2026 |
| **Audience** | Engineering (Claude Code), Design, Sales Ops, CX leadership |
| **Companion file** | `CLAUDE.md` — build rules and conventions for the coding agent |

---

## 0. TL;DR

A **locally run** service that takes sales-call recordings between a **lead (consumer)** and either a **human sales agent** or an **AI voice bot**, and turns them into:

1. **Transcripts**: speaker-separated (Agent / Customer), timestamped, Hinglish-aware, with an audio player synced to the text.
2. **Call summaries**: what was discussed, what the customer wanted, and what was promised.
3. **Insights**: buying intent score, objections and how they were handled, BANT, customer mood, a quality scorecard, and objective metrics measured from the transcript.
4. **Actionable next steps**: what to do next and what to say, per lead.
5. **AI vs Human comparison**: a dedicated tab that compares the bot with the human team using the full record count, scores, measured metrics, outcomes, evidence quotes and a "what to fix in the bot" list.

Calls come in through **one well-built uploader** that accepts a **ZIP of recordings**, an **Excel/CSV sheet of recording links (.mp4/.mp3/.wav…)**, or **direct links**, and shows live progress through every stage until the results are ready.

The UI copies the information architecture of the two reference screens (Zipteams "All Conversations" and "Lead Details") and the "AI voice bot vs human agents" report. It uses **our own branding**. We do not copy third-party logos or brand assets.

---

## 1. Problem & Goals

### 1.1 Problem
- Sleep Company runs thousands of lead calls a month (store teams, tele-sales and now an AI voice bot). Nobody can listen to all of them.
- We can't answer basic questions with evidence: *Is the AI bot as good as our people? Where does it fail? Which leads are hot right now? What should the store say on the follow-up call?*
- Existing tools are SaaS-only, expensive per seat, and don't do a **side-by-side comparison of the bot and the human team** on the same campaign.

### 1.2 Goals (v1)
| # | Goal | Success metric |
|---|---|---|
| G1 | Ingest recordings in bulk with zero friction | 95% of valid uploads finish ingest with no manual retry. A 500-file ZIP uploads with resume after a network drop. |
| G2 | Accurate, speaker-separated Hinglish transcripts | Spot-check WER ≤ 20% on Hinglish. Speaker role (Agent/Customer) correct on ≥ 95% of calls. |
| G3 | Useful per-call summary and insights | ≥ 80% of sampled summaries rated "accurate & useful" by sales managers. |
| G4 | Actionable next steps per lead | Every connected call gets 1–3 next actions with a "Say:" script and a due date where one was mentioned. |
| G5 | A trustworthy AI vs Human comparison | Every claim in the comparison links to ≥ 1 call and a verbatim quote. Record counts always visible. |
| G6 | A codebase a non-expert can change | Scorecard dimensions, intent rubric and prompts can be edited in plain YAML/Markdown files without touching code. |

### 1.3 Non-goals (v1)
- Live/real-time call monitoring or telephony integration (dialer, CRM push). Designed for later (see §14), not built now.
- Multi-tenant SaaS, SSO, role-based permissions. This is a single-team local tool with an optional passcode.
- Training custom speech models.
- Mobile app. The web UI must still be usable on a tablet.

---

## 2. Users & Key Jobs

| Persona | Job to be done | Primary screens |
|---|---|---|
| **Sales Ops Analyst** (primary) | "Upload this week's calls, get every call transcribed and scored, and export the results." | Upload, Batches, All Conversations |
| **Sales / Store Manager** | "Which leads are hot? What did the customer say? What should my team say on the follow-up?" | All Conversations, Lead Details |
| **AI Bot Product Owner** | "Where does the bot lose to humans, with proof, and what should I change in the bot script?" | AI vs Human |
| **CX / Leadership** | "Should we scale the bot? Show me numbers I can trust." | AI vs Human (headline and record counts) |

---

## 3. Scope & Prioritisation

**P0 = must ship in v1 · P1 = should ship in v1 if time allows · P2 = later**

| Area | P0 | P1 | P2 |
|---|---|---|---|
| Ingest | ZIP, Excel/CSV of links, pasted links. Chunked resumable upload. Column mapping. Live progress. Retry. | Google Drive / Dropbox share-link conversion. `manifest.csv` inside the ZIP. | S3 bucket watch folder, CRM webhook |
| Transcription | Diarised, timestamped, Hinglish (Roman or Devanagari). Stereo channel split. Cache by file hash. | Fully offline mode (local Whisper). Custom vocabulary (product names). | Word-level confidence heatmap |
| Per-call analysis | Summary, intent, objections, BANT, outcome, mood, scorecard, next actions, key moments, measured metrics | AI-bot failure patterns per call | Custom per-campaign rubric |
| Leads | Lead list with filters and KPI header. Lead details with Insights, Conversations, Summary, Actions and Notes tabs. | Editable status, assignee, tasks | Calendar sync |
| AI vs Human | Full comparison report (all sections in §6.6), record counts, evidence quotes, CSV/JSON export | Filter by campaign or date. Save and share snapshot. | Trend over time (bot version A vs B) |
| Platform | Local run (one command), SQLite, background worker, SSE progress, config files | Optional passcode, phone masking, data retention purge | Postgres, Docker on a server, multi-user |

---

## 4. User Flows

### 4.1 Upload → Results (happy path)
```
[Upload page]
  1. Choose source tab: Files/ZIP | Spreadsheet | Links
  2. Choose "Who is on these calls?": AI voice bot | Human agents | From a column (mixed)
  3. (Spreadsheet only) Preview the first 20 rows → confirm column mapping
  4. Optional: Batch name, Campaign/purpose ("Follow-up calls to mattress enquiries"),
     Transcript script (Hinglish Roman | Devanagari | English)
  5. Click "Upload & analyse"
       → files upload in chunks with a per-file progress bar, speed and ETA
       → a batch is created and the user is sent to the Batch Progress view
[Batch progress]
  6. Each call moves through: Queued → Downloading → Preparing audio → Transcribing → Analysing → Done
     Failures show a plain-language reason with a [Retry] button
  7. When ≥ 1 call is done, results unlock progressively. The user doesn't wait for the whole batch.
[Results]
  8. "View conversations" → All Conversations (filtered to the batch)
  9. "Compare AI vs Human" → comparison tab (enabled when both sides have ≥ 1 analysed call)
```

### 4.2 Manager reviews a lead
All Conversations → filter "High Intent", "Follow-up pending" → open lead → Insights tab (intent, objections, BANT) → right panel "Path to conversion" (summary and what to say next) → Conversations tab (listen to the audio, read the transcript, jump to key moments) → mark the task done or add a note.

### 4.3 Bot owner reviews AI vs Human
AI vs Human tab → pick batches or campaign → read the headline verdict and record counts → check the "Where they differ" evidence → review scores and measured metrics → "What to fix in the bot", sorted by priority → click any cited call to open its transcript at the quoted moment → Export CSV.

---

## 5. Information Architecture

```
Sidebar (left, collapsible)
├── Upload                     /upload
├── Batches                    /batches, /batches/:id    (progress and history)
├── All Conversations          /leads                    (clone of reference screen 2)
│     └── Lead Details         /leads/:id                (clone of reference screen 3)
│           tabs: Insights · Conversations · Summary · Actions · Notes
├── Calls                      /calls, /calls/:id        (flat list of every recording)
├── AI vs Human                /compare                  (clone of reference screen 1, results part)
└── Settings                   /settings                 (providers, API keys status, rubric preview, data retention)
Footer of sidebar: workspace name, "Last processed: <time>", total audio hours processed.
```

---

## 6. Functional Requirements

### 6.1 Uploader (P0)

The uploader is the first thing users touch, so it must be fast, honest about progress, and hard to break.

#### 6.1.1 Sources
| Source | Accepted | Notes |
|---|---|---|
| **Files / ZIP** | `.zip`, or loose `.mp3 .wav .m4a .mp4 .aac .ogg .opus .webm .flac .amr` (multi-select or folder drop) | ZIP may contain nested folders and an optional `manifest.csv` (same columns as the spreadsheet). Ignore `__MACOSX/`, `.DS_Store` and hidden files. |
| **Spreadsheet** | `.xlsx`, `.xls`, `.csv` | One row per call. Must have a recording URL column. Other columns are optional (see mapping). |
| **Links** | Textarea, one per line, optional `Label \| URL` (same as the reference screen) | Same validation as spreadsheet URLs. |

#### 6.1.2 Column mapping (spreadsheet and manifest)
On file select, parse in the browser (SheetJS) and show the first 20 rows. Auto-detect columns by header name (case-insensitive, fuzzy), and let the user override them with dropdowns.

| Field | Required | Auto-detect headers |
|---|---|---|
| `recording_url` | ✅ | url, link, recording, audio, mp4, file |
| `agent_type` | if "From a column" chosen | agent_type, type, caller, bot/human, channel |
| `lead_name` | – | name, customer, lead |
| `lead_phone` | – (strongly recommended: groups calls into leads) | phone, mobile, number, contact |
| `call_datetime` | – | date, time, called_at, created |
| `agent_name` / `owner` | – | agent, owner, store, executive |
| `campaign` | – | campaign, purpose, source |
| `external_id` | – | id, call_id, crm_id |

- Values for `agent_type` are normalised: `ai, bot, voicebot, ai bot → ai`; `human, agent, person, store → human`. Unknown values block submit, and the offending rows are highlighted.
- Show a summary before submit: **"212 rows · 208 valid links · 3 duplicates removed · 1 invalid URL (row 57)"**.

#### 6.1.3 Upload engineering (P0)
- **Chunked, resumable upload** (custom protocol, simple to read):
  1. `POST /api/uploads` with `{filename, size, sha256?, mime}` → `{upload_id, chunk_size: 8MB, received_chunks: []}`
  2. `PUT /api/uploads/{id}/chunks/{index}` with the raw bytes. The server verifies the chunk length and writes it to `data/uploads/{id}/{index}.part`.
  3. `GET /api/uploads/{id}` returns the received chunks, which is used to resume after a refresh or network drop.
  4. `POST /api/uploads/{id}/complete` makes the server assemble the file, verify size and SHA-256, and return `file_id`.
- The client uploads **3 chunks in parallel**, retries each chunk with exponential backoff (1s, 2s, 4s, 8s, max 5 tries), and supports **pause, resume and cancel**.
- The client keeps upload state in `localStorage` (`upload_id`, file fingerprint = name + size + lastModified) so a page refresh offers **"Resume upload of calls_week40.zip (64%)"**.
- Per-file UI shows a progress bar, % done, MB/s, ETA and state (Hashing → Uploading → Verifying → Done / Failed).
- Hashing uses a Web Worker so the UI never freezes.
- **Limits** live in config: file ≤ 2 GB, ZIP ≤ 5 GB, ≤ 2,000 calls per batch, single recording ≤ 3 hours.
- **ZIP safety** (server): reject path traversal (zip-slip), cap total uncompressed size (10× compressed, max 20 GB) and entry count, skip non-audio entries and list them as "skipped" with a reason.
- **Link fetching** (server): streaming download with `httpx`, 30 s connect / 10 min read timeout, 3 retries on 5xx or timeout, size cap, sniff the content type, follow ≤ 5 redirects, and block private and loopback IPs (SSRF guard).
- **Deduplication**: a SHA-256 of the audio bytes is computed after download. If the same hash was already transcribed, the transcript is reused (cache hit, shown as "Reused previous transcript").

#### 6.1.4 Pre-flight estimate
After ingest (ffprobe durations are known), show: **"208 calls · 14 h 32 m of audio · estimated 18–25 min to process"**. The estimate is based on configured concurrency and the rolling average processing speed stored in DB.

#### 6.1.5 Data notice
Show a short notice under the submit button (same as the reference): *"Recordings are processed on this machine and sent to the configured transcription and analysis APIs. Avoid uploading calls you aren't permitted to process. Switch to Offline mode in Settings to keep audio on this machine."*

### 6.2 Processing Pipeline & Progress (P0)

#### 6.2.1 Stages (per call)
| # | Stage | What happens | Output stored |
|---|---|---|---|
| 1 | `queued` | Call row created | – |
| 2 | `downloading` | For URLs: stream to `data/audio/raw/` | raw file, sha256 |
| 3 | `preparing` | `ffprobe` (duration, channels, codec). `ffmpeg` converts to 16 kHz FLAC. Extract audio from video. If stereo with distinct channels, keep the channels separate for channel-based diarisation. Skip calls < 5 s or silent (marked `not_connected`). | normalised audio, duration_s, channels |
| 4 | `transcribing` | Transcriber provider (§8.2). Long audio is chunked into 10-minute pieces with a 5 s overlap and stitched. | `transcripts` row with segments JSON |
| 5 | `analysing` | (a) deterministic metrics (§7.2), (b) LLM per-call analysis (§7.1), (c) quote verification | `analyses`, `metrics` rows |
| 6 | `done` / `failed` / `skipped` | Lead upsert, lead rollups recalculated | – |

- Each stage is **idempotent**: if its output already exists, it is skipped. A crashed worker can resume.
- On startup, the worker re-queues jobs stuck in a running state for more than 10 minutes.
- Concurrency per stage is configurable (default: download 4, transcribe 3, analyse 4). A token-bucket rate limiter per provider respects requests-per-minute limits.
- Provider errors: retry on 429/5xx/timeouts with exponential backoff and jitter (max 4). Don't retry on 4xx validation errors.

#### 6.2.2 Error taxonomy (shown to the user in plain language)
| Code | User message | Action |
|---|---|---|
| `LINK_NOT_FOUND` | "The recording was not found (HTTP 404). Check the link." | Retry, Edit link |
| `LINK_FORBIDDEN` | "Access denied (HTTP 403). The link may have expired or need sign-in." | Retry, Edit link |
| `NOT_AUDIO` | "This file isn't an audio or video recording." | Remove |
| `TOO_SHORT` | "Call shorter than 5 seconds. Marked as not connected." | – (counted as Not Available) |
| `SILENT` | "No speech detected." | – |
| `PROVIDER_RATE_LIMIT` | "Transcription service is busy. Retrying automatically…" | auto |
| `PROVIDER_ERROR` | "The transcription service failed for this call." | Retry |
| `ANALYSIS_INVALID` | "Analysis couldn't be completed for this call." | Retry |

#### 6.2.3 Progress UI (Batch page)
- Header shows the batch name, a stacked progress bar (done / running / failed / queued), counts, elapsed time and ETA.
- Two columns when the batch is mixed (**AI voice bot** in blue, **Human agents** in orange, as in the reference). Otherwise one column.
- Each row shows the call label, a stage pill with a spinner, a thin stage progress bar, and the duration once known. Failed rows are red with the reason and **Retry**.
- Bulk actions: **Retry all failed**, **Cancel remaining**.
- Updates are **live via Server-Sent Events** (`GET /api/batches/{id}/events`). The client falls back to polling every 3 s if SSE disconnects. No page refresh is needed, ever.
- Results appear progressively. As soon as one call is done, its row becomes a link.

### 6.3 All Conversations — Leads list (P0, clone of reference screen 2)

**Filter bar** (top, wraps on small screens): Date range (default: last 30 days) · Customer (search) · Conversation source (batch/campaign) · Conversation owner (agent name) · **Agent type (AI / Human / All)** · Status · Disposition status · Status category · Intent bucket · **Reset all**.

**KPI card (top right)**: `13,117 Conversations` with a green pill `145 hours 24 mins`, then three sub-stats: **% Detailed** (calls ≥ 2 min with ≥ 6 speaker turns), **Talk-to-Listen ratio** (agent:customer talk time, e.g. 63:37), and **Quality Score** (mean scorecard → %).

**Lead summary row**:
- `Total Leads N` · `Unique Connected Leads N` · `Not Connected Leads N`, each with a period-over-period delta (↗ green / ↘ red against the previous equal-length period; "N/A" if there is no previous data).
- `Won N (x%)` · `Lost N (x%)` · `In Progress N (x%)`, each with a delta.

**Intent bucket cards** (clickable, they set the Intent filter): High Intent · Moderate Intent · Neutral Intent · Low Intent · Not Qualified · Not Available, each with a count and a delta.

**Leads table** (TanStack Table, virtualised, server-side paging, sort and filter):
| Column | Source |
|---|---|
| ☐ select | bulk export |
| Name (link ↗ to the lead) | lead.name, or a masked phone if unknown |
| Conversations ("N Conversations", links to the Conversations tab) | count of calls |
| Last Conversation | max(call_datetime) |
| Next Task Due Date | next open action: "08 Oct '26 – Customer visit to shop" |
| Intent | pill: bucket and score |
| Agent type | AI / Human / Both chip |
| Conversation owner | agent / store name with initials avatar |
| Status | lead status |

A column chooser ("9 Selected ▾") persists to localStorage. Bulk select → Export CSV.

### 6.4 Lead Details (P0, clone of reference screen 3)

**Header**: avatar initial, **Name ↗**, phone (masked by default, click to reveal if allowed by settings), **Owner name**. Stat cards: **Total conversation duration**, **Talk-to-Listen ratio (ⓘ tooltip)**, **Intent score /100**, **Avg call quality score %**. On the right: **Assignee** dropdown and **Status** dropdown (Follow-up pending, Callback scheduled, Store visit planned, Won, Lost, Not qualified).

**Tabs**: Insights · Conversations · Summary · Actions · Notes

**Insights tab** (left column, scrollable):
1. **Buying Intent** card: bucket label in colour ("High Intent"), score badge (81/100), then positive factors (↗ green) and negative factors (↘ red), each one line.
2. **Objections** cards, one per objection: title, **type tag** (Price, Lack of Interest, Timing, Competitor, Trust/Brand, Product fit, Delivery/Installation, Need to consult family, Other), customer quote, **How this objection was handled**, **Was the customer satisfied?** (✓ / ✗ with a sentence).
3. **BANT**: four tiles (Budget, Authority, Need, Timeline). Each shows a value or "Unknown", the evidence quote, and a status dot (known / partial / unknown).
4. **Customer mood**: start → end (positive / neutral / negative) with the trajectory.
5. **Key details captured**: products discussed, size (e.g. 75×60), city, pincode, pain points (e.g. back pain), competitor mentions.

**Right panel: Path to Conversion** (sticky):
- **Previous conversation summary**: 3–6 bullets.
- **What to do next?**: numbered actions. Each has a bold title, a 👉 **Say:** script (in the call's language), and a "why" line. If a due date was agreed in the call, show it.
- When a lead has multiple calls, the summary is cumulative across all of them, with the latest call weighted highest.

**Conversations tab**:
- List of calls (date, duration, AI/Human chip, outcome, quality %). Selecting one opens:
- **Audio player** with a waveform (wavesurfer.js), 1×/1.25×/1.5×/2× speed, skip ±10 s.
- **Transcript** with speaker-coloured bubbles (Agent / Customer), timestamps, and a highlight that follows the current word or segment. Click any line to seek. Search inside the transcript. A toggle switches between Roman and Devanagari if both are available.
- **Key moments** rail: markers on the waveform (price asked, objection, commitment, callback agreed, escalation). Click to jump.
- **Scorecard** for the call: 10 dimensions, each with score, reason and evidence quote.
- **Measured metrics** for the call (§7.2).

**Summary tab**: full per-call summaries in date order.
**Actions tab**: open and done actions (checkbox), editable due date, manual add.
**Notes tab**: free-text notes with timestamps (local DB).

### 6.5 Calls (P0)
A flat table of every recording: label, batch, agent type, agent name, lead, date, duration, stage/status, outcome, intent, quality %. Filters match All Conversations. Clicking a row opens Call Detail (same as the Conversations tab, full-width).

### 6.6 AI vs Human — Comparison tab (P0, clone of the results part of reference screen 1)

**Scope picker** at the top: batches (multi-select) or campaign, date range, and an optional "Only comparable calls" toggle (same campaign, both sides connected, duration ≥ 20 s).

Sections, in this order:

**A. Records strip** (justifies the totals, always visible):
| Total recordings | AI calls (analysed / uploaded) | Human calls (analysed / uploaded) | Failed / skipped | Not connected | Total audio (AI / Human) |
- Includes a **sample-size warning** banner when either side has < 10 analysed calls: *"Based on 3 AI and 2 human calls. Add more calls before changing the bot script."*

**B. Verdict card**: a one-to-two sentence headline generated by the LLM from the aggregates (e.g. *"Humans answer what the customer actually asked; the bot falls back to scripted lines when the customer goes off-script."*). Next to it, two big numbers: **AI avg review score 2.7 / 5** and **Human 4.4 / 5**, with "n of N calls reviewed".

**C. Where they differ**: a table with columns `Theme | AI voice bot | Human agents | Why it matters`. Each row carries **evidence**: call IDs and short verbatim quotes, each clickable to open the transcript at that timestamp. 3–6 themes.

**D. Review scores**: a diverging horizontal bar chart (AI bars go left in blue, Human bars go right in orange, dimension labels in the centre, value labels at the bar ends). Dimensions come from `config/scorecard.yaml`. Footer legend: "◂ AI scores higher · Human scores higher ▸". Includes a "Show as a table" toggle.

**E. Measured from the transcripts**: a table with inline bars per side. Rows are the metrics in §7.2, with the averages per call. Caption: *"Counted directly from who said what, not judged by the model."*

**F. Outcomes and customer mood**:
- Outcome distribution per side (Callback scheduled, Agreed next step, Store visit, Not interested, Converted, No outcome) as % of reviewed calls, with inline bars.
- Other signals: customer mood at the end (positive / neutral / negative counts), mood improved/worsened during the call, objections (handled well / total), friction points per call, customer questions left unanswered per call, calls handed off or escalated.

**G. What to fix in the bot**:
- Two columns: **Where the AI does better** / **Where humans do better** (bullets).
- **Outcomes** paragraph.
- **Repeated AI failure patterns**: a pattern name, the frequency ("1 of 3 AI calls"), and the evidence quote and call.
- **Recommended changes**: a priority tag (high / medium / low), a bold one-line change, and the rationale, sorted by priority.

**H. Every call**: two grouped lists (AI voice bot / Human agents). Each row shows the label, duration, language, outcome and quality %, and expands to that call's review, key moments and transcript.

**Actions**: **Save results (JSON)** and **Export scores (CSV)** (one row per call, all scores and metrics). A **Re-run comparison** button is enabled when new calls have been added since the last run. Comparison results are cached per (scope hash, data version).

### 6.7 Settings (P0, minimal)
- Provider selection (Transcription: OpenAI / Gemini / Local Whisper. Analysis: Gemini / Claude). Shows whether each key is present (never displays the key; keys live in `.env` only).
- Default transcript script, default concurrency.
- Phone masking on/off. Data retention (auto-delete raw audio after N days; transcripts are kept).
- Read-only preview of `scorecard.yaml` and `intent_rubric.yaml`, with "Reload config".
- Optional app passcode (P1). If set, every API call needs the session cookie.

---

## 7. Intelligence Specification

### 7.1 Per-call LLM analysis: output contract
The LLM must return **strict JSON** validated by a Pydantic model (provider structured-output / tool-use mode). If validation fails, retry once with the validation error appended. On a second failure the stage fails with `ANALYSIS_INVALID`.

```jsonc
{
  "language": "hinglish",                     // hinglish | hindi | english | other
  "speaker_roles": {"S1": "agent", "S2": "customer"},  // only if diarisation didn't assign roles
  "summary": {
    "one_liner": "Customer asked Ortho Pro price for 75x60; agreed to visit store tomorrow.",
    "bullets": ["...", "..."]                  // 3–6 bullets, facts only
  },
  "customer": {
    "name": "Nithin", "city": "Kochi", "pincode": null,
    "products_discussed": ["Ortho Pro", "Latex"], "size": "75x60",
    "pain_points": ["back pain"], "competitors_mentioned": []
  },
  "intent": {
    "score": 81, "bucket": "high",              // bucket derived in code from score + rubric, LLM value ignored
    "positive_factors": ["Asked detailed questions about models and dimensions"],
    "negative_factors": ["Hesitant due to price discrepancy"]
  },
  "objections": [{
    "type": "price",                            // enum from config
    "title": "Questioned prices quoted",
    "customer_quote": "Pehle toh 27,990 bataya tha",
    "t": 132.4,                                 // seconds
    "handling": "Clarified MRP and offer prices by size",
    "handled_well": false,
    "customer_satisfied": false,
    "better_response": "Confirm the recalled price and give a written breakdown"
  }],
  "bant": {
    "budget":    {"status": "partial", "value": "~40k", "evidence": "..."},
    "authority": {"status": "unknown", "value": null, "evidence": null},
    "need":      {"status": "known", "value": "Back pain, replacing old mattress", "evidence": "..."},
    "timeline":  {"status": "known", "value": "This week", "evidence": "..."}
  },
  "outcome": {
    "disposition": "store_visit",               // converted | store_visit | callback_scheduled | agreed_next_step | follow_up_pending | not_interested | not_qualified | no_outcome
    "next_step": "Customer visit to store",
    "next_step_due": "2026-10-08",              // resolved relative to call_datetime; null if not stated
    "escalated": false
  },
  "mood": {"start": "neutral", "end": "positive", "trajectory": "improved"},
  "scorecard": {                                 // keys from config/scorecard.yaml
    "greeting_intro": {"score": 4, "reason": "...", "evidence": "...", "t": 3.1},
    "...": {}
  },
  "key_moments": [{"t": 45.2, "type": "price_asked", "label": "Asked price of Ortho Pro", "quote": "..."}],
  "friction_points": ["Bot repeated opening line"],
  "unanswered_questions": ["Does EMI apply on offer price?"],
  "next_actions": [{
    "title": "Clarify pricing and offer details",
    "say": "Nithin, I understand there was some confusion about the pricing...",
    "why": "Price discrepancy was the main blocker",
    "due": "2026-10-08"
  }],
  "ai_failure_patterns": [                       // only when agent_type == "ai"; enum + free text
    {"pattern": "scripted_repeat", "description": "Repeated opening when asked price", "quote": "...", "t": 12.0}
  ]
}
```

**Grounding rules (in the prompt and enforced in code):**
- Every `quote`, `evidence` and `customer_quote` must be a verbatim substring of the transcript (after whitespace/case normalisation). Code checks each quote with fuzzy match ≥ 90 (rapidfuzz `partial_ratio`). A quote that fails is dropped and flagged `unverified`. Unverified quotes are never shown as evidence in the comparison.
- Unknown is a valid answer. The model must not invent budget, names, dates or prices.
- Dates are resolved by code, not the model: the model returns relative phrases ("kal", "tomorrow", "Monday"), and a helper resolves them against `call_datetime` in IST. The model may also return ISO, which is validated.

### 7.2 Deterministic metrics (computed in code from transcript segments, never by the LLM)
| Metric | Formula |
|---|---|
| Call length | audio duration (mm:ss) |
| Talk-to-listen ratio | agent speech seconds : customer speech seconds (rounded to 100) |
| Agent share of words | agent words / total words |
| Words per agent turn | agent words / agent turns |
| Words per customer turn | customer words / customer turns |
| Longest agent monologue | max words in consecutive agent segments |
| Questions asked by agent | agent sentences ending in `?` or starting with a question word (EN + Hindi list: kya, kaun, kab, kahan, kitna, kaise, kyun…) |
| Agent words per minute | agent words / agent speech minutes |
| Agent lines repeated word-for-word | count of agent segments (≥ 4 words) whose normalised text exactly equals an earlier agent segment |
| Customer replies of ≤ 3 words | % of customer turns with ≤ 3 words |
| Speaker changes per minute | turn switches / call minutes |
| Interruptions | segments starting before the other speaker's segment ended (overlap > 0.3 s) |
| Silence % | 1 − (speech time / duration) |

"Detailed call" = duration ≥ 120 s and ≥ 6 turns. "Connected" = duration ≥ 5 s and speech detected from both speakers.

### 7.3 Scoring rubrics (config, not code)

`config/scorecard.yaml` (1 = poor … 5 = excellent). Editable, and the UI and prompts read it at runtime:
```yaml
dimensions:
  - key: greeting_intro
    label: Greeting and intro
    guide: "5 = warm, names brand and purpose in first 10s; 1 = no intro or confusing"
  - key: understanding_customer
    label: Understanding the customer
    guide: "Asks about need, size, pain, budget before pitching"
  - key: relevance
    label: Relevance of answers
    guide: "Answers the exact question asked; 1 = ignores question / scripted reply"
  - key: empathy_tone
    label: Empathy and tone
  - key: clarity
    label: Clarity
  - key: objection_handling
    label: Objection handling
  - key: interruptions
    label: Handling interruptions
  - key: naturalness
    label: Naturalness
  - key: resolution
    label: Resolution
  - key: closing
    label: Closing
    guide: "Ends with a concrete, time-bound next step"
quality_score: mean_of_dimensions_as_percent   # (mean - 1) / 4 * 100
```

`config/intent_rubric.yaml`:
```yaml
buckets:            # applied in code to intent.score
  high: [75, 100]
  moderate: [50, 74]
  neutral: [30, 49]
  low: [0, 29]
special:
  not_qualified: "outcome.disposition == not_qualified (wrong number, not a buyer, job seeker)"
  not_available: "call not connected / too short / silent / voicemail"
signals:            # given to the LLM as guidance
  positive: [asked specific model/size, asked price or offer, asked EMI/delivery, agreed visit/callback, stated timeline]
  negative: [explicit refusal, "already bought", no need, repeated "busy", price far above stated budget]
objection_types: [price, lack_of_interest, timing, competitor, trust_brand, product_fit, delivery_installation, need_to_consult, other]
ai_failure_patterns: [scripted_repeat, ignores_refusal, misunderstood_intent, wrong_language, talks_over_customer, no_answer_to_question, dead_air, unnatural_voice, hallucinated_info]
```

### 7.4 Lead rollups
- A lead is keyed by the **normalised phone** (E.164, default country IN). If no phone is given, use `external_id`; if neither exists, each call is its own lead.
- `lead.intent_score` is the score of the latest connected call (with the trend shown). `lead.status` is the latest disposition unless a user has overridden it manually; manual overrides always win.
- Won = `converted`. Lost = `not_interested` or `not_qualified`. In Progress = everything else that's connected.
- The Path to Conversion summary is regenerated (one cheap LLM call) when a new call for the lead is analysed.

### 7.5 Comparison synthesis (AI vs Human)
1. **Aggregate in code**: per side, the mean of each scorecard dimension, the means of every metric, outcome %, mood counts, objection stats, and failure-pattern frequencies. **No LLM is involved in any number.**
2. **One LLM synthesis call** gets the aggregates plus per-call compact digests (summary one-liner, scores, verified quotes, failure patterns). It must never receive raw full transcripts, which keeps it cheap and bounded. It returns: `verdict_headline`, `differences[] {theme, ai, human, why, evidence[{call_id, quote}]}`, `ai_better[]`, `human_better[]`, `outcomes_paragraph`, `recommended_changes[] {priority, change, rationale}`.
3. **Validation**: every `evidence.call_id` must exist in scope, and every quote must be verified against that call's transcript. Items whose evidence all fails are dropped.
4. **Cache** the result by `(scope_hash, max(analysis.updated_at))`.

---

## 8. Engineering Architecture

### 8.1 Stack (chosen for simplicity and readability)
| Layer | Choice | Why |
|---|---|---|
| Backend API | **Python 3.12 + FastAPI** | Best audio, Excel and AI ecosystem. Typed and simple. |
| Models / DB | **SQLModel on SQLite (WAL mode)** | Zero setup locally, one file, easy to inspect. Swappable to Postgres by changing `DATABASE_URL`. |
| Migrations | Alembic | Safe schema changes |
| Background work | **A separate worker process** (`python -m app.worker`) that claims jobs from a `jobs` table | No Redis or Celery to learn. The API stays responsive. Crash-safe. |
| Live progress | **SSE** from FastAPI (reads `job_events`) | Simpler than WebSockets, and auto-reconnects |
| Audio | `ffmpeg` / `ffprobe` (system binary) | Industry standard |
| Spreadsheets | `openpyxl` + `csv` (server), SheetJS (browser preview) | – |
| HTTP | `httpx` (async, streaming) | – |
| Validation | Pydantic v2 | Shared with LLM output contracts |
| Frontend | **React 19 + Vite + TypeScript** (lint: oxlint) | Fast local dev, no server rendering needed |
| UI kit | **Tailwind CSS v4 + shadcn/ui** (Radix) | Clean, accessible, code you own |
| Data fetching | TanStack Query | Caching, retries, polling fallback |
| Tables | TanStack Table + TanStack Virtual | 10k-row lists stay smooth |
| Charts | Recharts | Diverging bars and inline bars |
| Audio player | wavesurfer.js | Waveform, regions for key moments |
| Routing | React Router | – |
| Packaging | `docker compose up` **or** `make dev` | One command either way |

### 8.2 Provider abstraction (swap AI vendors without touching the pipeline)
```python
# backend/app/providers/base.py
class Transcriber(Protocol):
    name: str
    async def transcribe(self, audio: AudioFile, opts: TranscribeOptions) -> Transcript: ...

class Analyzer(Protocol):
    name: str
    async def analyze_call(self, ctx: CallContext) -> CallAnalysis: ...
    async def synthesize_comparison(self, ctx: ComparisonContext) -> ComparisonResult: ...
```
| Provider | File | Default? | Notes |
|---|---|---|---|
| `openai` transcriber | `providers/openai_transcriber.py` | ✅ default | `gpt-4o-transcribe-diarize` returns speaker-labelled, timestamped segments (`whisper-1` has no speaker labels, so it isn't used). Model ID from `.env` (`OPENAI_TRANSCRIBE_MODEL`). Respect the API's per-file size limit by sending the normalised, compressed audio and chunking long calls (§6.2.1). Check the current OpenAI docs for limits and parameters when implementing. |
| `gemini` transcriber | `providers/gemini_transcriber.py` | alternative (A/B on real calls in M2) | Native audio input with diarisation and Hinglish. Audio > 20 MB goes through the Files API. The prompt requests JSON segments `{speaker, start, end, text}` in the chosen script. Model ID comes from `.env` (`GEMINI_TRANSCRIBE_MODEL`). |
| `local_whisper` transcriber | `providers/whisper_transcriber.py` | P1 (offline mode) | `faster-whisper` large-v3 for text and timestamps. Diarisation comes from stereo channel split, else `pyannote` (optional dependency). CPU/GPU auto-detect. |
| `gemini` analyzer | `providers/gemini_analyzer.py` | ✅ default | Structured JSON output (response schema) validated by Pydantic. Model ID from `.env` (`ANALYSIS_MODEL`, e.g. `gemini-3.8-flash`; `LEAD_SUMMARY_MODEL` for the cheap lead-summary refresh). |
| `anthropic` analyzer | `providers/claude_analyzer.py` | alternative (needs `ANTHROPIC_API_KEY`) | Claude with tool-use / structured JSON output. Model ID from `.env` (`ANALYSIS_MODEL`, e.g. `claude-sonnet-5-5`; use `claude-haiku-4-5` for the cheap lead-summary refresh). Uses prompt caching for the static rubric and system prompt. |

The rest of the codebase never imports a vendor SDK directly. It always goes through `providers.get_transcriber()` and `providers.get_analyzer()`.

**Speaker roles**: if the audio is stereo with energy concentrated per channel, the channel becomes the speaker (the dialer convention is set in config: `left=agent`). Otherwise diarised speakers are mapped to roles by the analyzer (the agent introduces the brand and asks qualifying questions). The mapping is stored and can be corrected in the UI with a **Swap speakers** button, which recomputes metrics.

### 8.3 Data model (SQLite)
```
batches        id, name, campaign, source_type(zip|sheet|links|files), agent_type_mode(ai|human|column),
               transcript_script, status, created_at, stats_json
uploads        id, filename, size, sha256, mime, chunk_size, received_chunks_json, status, file_path, created_at
calls          id, batch_id, label, agent_type(ai|human), agent_name, campaign, lead_id, external_id,
               source_url, upload_id, audio_sha256, raw_path, audio_path, duration_s, channels,
               call_datetime, stage, status(queued|running|done|failed|skipped), error_code, error_detail,
               attempts, created_at, updated_at
leads          id, phone_e164, name, owner, status, status_overridden(bool), intent_score, intent_bucket,
               path_summary_json, last_call_at, created_at, updated_at
transcripts    id, call_id, provider, model, language, script, segments_json, speaker_map_json, created_at
               -- segments: [{i, speaker:"agent"|"customer", start, end, text}]
analyses       id, call_id, provider, model, prompt_version, result_json, quality_pct, intent_score,
               intent_bucket, disposition, created_at
metrics        call_id (pk), json   -- §7.2 values
actions        id, lead_id, call_id, title, say, why, due_date, done(bool), source(ai|manual)
notes          id, lead_id, body, created_at
jobs           id, call_id, stage, status(queued|running|done|failed), run_after, attempts, locked_at, last_error
job_events     id, batch_id, call_id, stage, status, message, progress(0-100), created_at   -- SSE source
comparisons    id, scope_hash, data_version, result_json, created_at
transcript_cache  audio_sha256 (pk), transcript_id
```
Indexes: `calls(batch_id, status)`, `calls(lead_id)`, `leads(intent_bucket, last_call_at)`, `jobs(status, run_after)`, `job_events(batch_id, id)`.

**Job claim (atomic, safe with multiple worker processes):**
```sql
UPDATE jobs SET status='running', locked_at=now, attempts=attempts+1
WHERE id = (SELECT id FROM jobs WHERE status='queued' AND run_after<=now AND stage=:stage
            ORDER BY id LIMIT 1)
RETURNING *;
```

### 8.4 File storage (local disk, configurable root)
```
data/
  app.db
  uploads/{upload_id}/{index}.part      (deleted after assembly)
  audio/raw/{sha256}.{ext}
  audio/norm/{sha256}.flac
  exports/
```
The API serves audio with **HTTP Range** support so the player can seek.

### 8.5 API (REST, JSON, all under `/api`)
| Method | Path | Purpose |
|---|---|---|
| POST | `/uploads` | Create a chunked upload |
| PUT | `/uploads/{id}/chunks/{n}` | Upload a chunk |
| GET | `/uploads/{id}` | Upload status and received chunks |
| POST | `/uploads/{id}/complete` | Assemble and verify |
| POST | `/sheets/preview` | (fallback) parse a sheet server-side and return headers and rows |
| POST | `/batches` | Create a batch `{name, campaign, agent_type_mode, transcript_script, source: {type, upload_ids[] \| rows[] \| links[]}, mapping}` |
| GET | `/batches` · `/batches/{id}` | List / detail with counts |
| GET | `/batches/{id}/events` | **SSE** progress stream |
| POST | `/batches/{id}/retry-failed` · `/calls/{id}/retry` | Retry |
| POST | `/batches/{id}/cancel` | Cancel queued |
| GET | `/calls` · `/calls/{id}` | List (filters) / detail (transcript, analysis, metrics) |
| GET | `/calls/{id}/audio` | Stream normalised audio (Range) |
| POST | `/calls/{id}/swap-speakers` | Fix roles and recompute metrics |
| GET | `/leads` | List with filters, sort and paging |
| GET | `/leads/kpis` | Header KPIs and intent buckets with deltas (same filters) |
| GET | `/leads/{id}` | Lead detail with rollups |
| PATCH | `/leads/{id}` | status, assignee |
| GET/POST/PATCH | `/leads/{id}/actions`, `/leads/{id}/notes` | Tasks and notes |
| POST | `/compare` | `{batch_ids?, campaign?, date_from?, date_to?, comparable_only}` → result (cached) |
| GET | `/compare/export.csv` · `/compare/export.json` | Exports |
| GET | `/settings` · POST `/settings/reload-config` | Settings |
| GET | `/health` | ffmpeg present, keys present, DB ok, worker heartbeat |
| GET | `/stats` | Sidebar footer: total/analysed calls, audio seconds processed, last processed time |

Errors use one shape: `{"error": {"code": "LINK_NOT_FOUND", "message": "…", "detail": {...}}}`.

### 8.6 Prompts
- Stored as plain Markdown in `backend/app/prompts/` (`transcribe.md`, `analyze_call.md`, `lead_path.md`, `compare.md`) with `{{placeholders}}`. Each file begins with a `version:` line, which is stored in `analyses.prompt_version` so re-analysis can target outdated versions.
- The analysis prompt includes the campaign context, agent type, call date (IST), the rubric from YAML, the transcript as numbered lines `[i][mm:ss] AGENT: …`, and the grounding rules from §7.1.
- **Re-analyse without re-transcribing**: `POST /calls/{id}/reanalyze` and a batch-level equivalent. Prompt or rubric changes don't cost a transcription.

### 8.7 Configuration
`.env` (secrets and machine settings) and `config/*.yaml` (business rules):
```
GEMINI_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=            # optional
TRANSCRIBER=openai            # openai | gemini | local_whisper
ANALYZER=gemini               # gemini | anthropic
OPENAI_TRANSCRIBE_MODEL=gpt-4o-transcribe-diarize
GEMINI_TRANSCRIBE_MODEL=gemini-3.5-transcribe
ANALYSIS_MODEL=gemini-3.8-flash
LEAD_SUMMARY_MODEL=gemini-3.5-flash-lite
DATA_DIR=./data
DATABASE_URL=sqlite:///./data/app.db
CONCURRENCY_DOWNLOAD=4
CONCURRENCY_TRANSCRIBE=3
CONCURRENCY_ANALYZE=4
MAX_FILE_GB=2
DEFAULT_TIMEZONE=Asia/Kolkata
DEFAULT_COUNTRY=IN
STEREO_LEFT_IS=agent
MASK_PHONES=true
APP_PASSCODE=
RAW_AUDIO_RETENTION_DAYS=30
HOST=127.0.0.1
PORT=8000
```

### 8.8 Repository layout (keep it this shape; one concern per file)
```
LimeZip/
├── PRD.md
├── CLAUDE.md
├── README.md                     # setup, run, change-a-rubric guide
├── Makefile                      # make setup | dev | worker | test | lint
├── docker-compose.yml
├── .env.example
├── config/
│   ├── scorecard.yaml
│   └── intent_rubric.yaml
├── backend/
│   ├── pyproject.toml
│   ├── alembic/
│   ├── app/
│   │   ├── main.py               # FastAPI app, routers mounted
│   │   ├── config.py             # Settings (pydantic-settings) + YAML loaders
│   │   ├── db.py                 # engine, session, WAL pragma
│   │   ├── models.py             # SQLModel tables (§8.3)
│   │   ├── schemas.py            # Pydantic API + LLM contracts (§7.1)
│   │   ├── errors.py             # error codes + user messages (§6.2.2)
│   │   ├── api/
│   │   │   ├── uploads.py
│   │   │   ├── batches.py        # incl. SSE
│   │   │   ├── calls.py
│   │   │   ├── leads.py
│   │   │   ├── compare.py
│   │   │   └── settings.py
│   │   ├── ingest/
│   │   │   ├── chunks.py         # chunk write/assemble/verify
│   │   │   ├── zip_reader.py     # safe extraction
│   │   │   ├── sheet_reader.py   # xlsx/csv + column mapping
│   │   │   └── downloader.py     # streaming fetch + SSRF guard
│   │   ├── pipeline/
│   │   │   ├── stages.py         # download, prepare, transcribe, analyse – one function each
│   │   │   ├── audio.py          # ffprobe/ffmpeg wrappers
│   │   │   ├── metrics.py        # §7.2 pure functions
│   │   │   ├── grounding.py      # quote verification, date resolution
│   │   │   ├── leads.py          # lead upsert + rollups
│   │   │   └── compare.py        # aggregation + synthesis call + validation
│   │   ├── providers/
│   │   │   ├── base.py
│   │   │   ├── gemini_transcriber.py
│   │   │   ├── whisper_transcriber.py
│   │   │   ├── claude_analyzer.py
│   │   │   └── gemini_analyzer.py
│   │   ├── prompts/              # *.md prompt templates
│   │   └── worker.py             # job loop, concurrency, retries, heartbeat
│   └── tests/
│       ├── fixtures/             # 3 short sample calls (AI, human, broken link) + golden JSON
│       ├── test_metrics.py
│       ├── test_grounding.py
│       ├── test_zip_reader.py
│       ├── test_sheet_reader.py
│       ├── test_chunks.py
│       └── test_pipeline_fake_providers.py
└── frontend/
    ├── package.json
    ├── index.html
    └── src/
        ├── main.tsx, App.tsx, routes.tsx
        ├── styles/tokens.css     # design tokens (§9.2)
        ├── lib/api.ts            # typed fetch client
        ├── lib/upload/           # chunkedUpload.ts, hashWorker.ts, resumeStore.ts
        ├── lib/sse.ts            # SSE with polling fallback
        ├── components/ui/        # shadcn primitives
        ├── components/           # KpiCard, IntentCard, StagePill, DivergingBarChart, InlineBar,
        │                         # TranscriptView, AudioPlayer, EvidenceQuote, FilterBar, DataTable…
        └── pages/
            ├── UploadPage.tsx
            ├── BatchesPage.tsx, BatchDetailPage.tsx
            ├── LeadsPage.tsx, LeadDetailPage.tsx
            ├── CallsPage.tsx, CallDetailPage.tsx
            ├── ComparePage.tsx
            └── SettingsPage.tsx
```

### 8.9 Testing strategy
- **Unit tests**: metrics formulas (hand-computed fixtures), grounding (quote match and date resolution with "kal", "parso", "Monday"), ZIP safety (zip-slip, bomb), sheet column auto-detect, chunk assemble and checksum.
- **Pipeline test with fake providers**: `FakeTranscriber` / `FakeAnalyzer` return golden JSON, so the batch runs end-to-end in CI with no API keys.
- **Contract test**: every LLM output fixture validates against `schemas.CallAnalysis`.
- **Frontend**: Vitest for the upload state machine and the SSE reducer. One Playwright smoke test: upload fixture ZIP → see Done → open the Compare tab.
- **Eval set (P1)**: 20 labelled real calls with expected intent bucket, disposition and objections. `make eval` prints the agreement %, and it is run before changing prompts.

---

## 9. Design Specification

### 9.1 Principles
1. **Evidence over opinion**: every insight can be traced to a quote and timestamp. Quotes are clickable.
2. **Numbers you can trust**: record counts and sample sizes are always visible next to aggregates.
3. **Progress is never a mystery**: every long operation shows stage, %, ETA and a clear error with a fix.
4. **Calm density**: a data-dense layout with lots of whitespace, one accent per meaning, and no decorative colour.
5. **Familiar**: layouts mirror the reference tools, so the team needs no training.

### 9.2 Visual tokens (`styles/tokens.css`, light and dark)
| Token | Light | Use |
|---|---|---|
| `--bg` | `#F7F7F8` | page |
| `--surface` | `#FFFFFF` | cards, tables |
| `--border` | `#E6E7EB` | 1px hairlines |
| `--text` / `--text-muted` | `#111318` / `#6B7280` | – |
| `--ai` | `#2F6FDE` (blue) | everything AI-bot |
| `--human` | `#E8692C` (orange) | everything human |
| `--positive` / `--negative` / `--warning` | `#16A34A` / `#DC2626` / `#D97706` | deltas, satisfied ✓/✗, warnings |
| `--intent-high/mod/neutral/low` | green / teal / slate / red scale | intent pills |
| Radius | 12px cards, 8px inputs, 999px pills | – |
| Shadow | none on cards (border only). `0 1px 2px rgb(0 0 0 / .04)` on popovers | – |
| Font | **Inter** (UI), **JetBrains Mono** (links, IDs, timestamps) | – |
| Type scale | 12 / 13 / 14 (body) / 16 / 20 / 24 / 32 (KPIs) / 44 (verdict scores) | tabular numbers on all metrics |
| Spacing | 4px grid. Cards have 20–24px padding. 16px side gutter on mobile. | – |

AI and Human always use the same colours and order (AI on the left, Human on the right), on every screen, chart and legend.

### 9.3 Upload page (wireframe)
```
┌──────────────────────────────────────────────────────────────────────────┐
│ Analyse calls                                                            │
│ Upload recordings. We'll transcribe, summarise and score every call.     │
│                                                                          │
│ [ Files / ZIP ] [ Spreadsheet ] [ Links ]          ← segmented control   │
│ ┌──────────────────────────────────────────────────────────────────────┐ │
│ │                    ⬆                                                 │ │
│ │     Drop a ZIP, audio/video files, or a folder here                  │ │
│ │     or  [Browse files]   ·  mp3 wav m4a mp4 … up to 2 GB each        │ │
│ └──────────────────────────────────────────────────────────────────────┘ │
│  (dashed border; on drag-over: border --ai, bg tint, "Release to add")   │
│                                                                          │
│ Who is on these calls?   (●) AI voice bot  ( ) Human agents  ( ) Column  │
│ Campaign / purpose (optional) [ Follow-up calls to mattress enquiries ] │
│ Transcript script [ Hinglish (Roman) ▾ ]   Batch name [ Week 40 ]        │
│                                                                          │
│ Files (3)                                                       Clear    │
│  calls_week40.zip   1.2 GB  ███████████░░░░ 64%  12.4 MB/s  ETA 0:41 ⏸ ✕ │
│  call_118.mp4        8 MB   ██████████████ Verified ✓                    │
│  notes.pdf                  Skipped — not an audio file                  │
│                                                                          │
│ [ Upload & analyse ]  [ Open saved results ]                             │
│ ⓘ data notice (§6.1.5)                                                   │
└──────────────────────────────────────────────────────────────────────────┘
```
- **Spreadsheet tab**: after selecting a file, show a mapping panel with a header-to-field dropdown per column, a 20-row preview table with invalid cells in red, and the validation summary line.
- **Links tab**: a monospace textarea with live line validation (a ✓ or ✗ gutter per line) and two side-by-side textareas when "AI vs Human" mode is picked (exactly like the reference: *AI voice bot recordings* with a blue left border, *Human agent recordings* with an orange left border).
- **Micro-interactions**: progress bars animate width at 200 ms ease-out. Completed files collapse into a "✓ 205 files ready" summary. A resume banner appears on revisit. All motion respects `prefers-reduced-motion`.

### 9.4 Other screens
- **Batch progress**: as §6.2.3. Stage pills use neutral grey (queued), blue pulse (running), green (done) and red (failed).
- **All Conversations**: exact reference structure (§6.3). Intent cards are equal-width and wrap to 2 columns on tablet. The table header is sticky.
- **Lead Details**: a 2-column layout (≈ 65 / 35). The right Path to Conversion panel is sticky and becomes a tab on screens < 1100 px.
- **Compare**: a single long, scrollable report with section cards (as in the reference) and a sticky mini table of contents on desktop. Charts get a `figure` caption and an accessible table alternative.
- **Empty states**: every list has an illustration-free empty state with one CTA ("No calls yet. Upload recordings →").
- **Loading**: skeletons that match the final layout. No full-page spinners.
- **Accessibility**: WCAG 2.1 AA contrast, full keyboard navigation (upload zone is focusable, with Enter to browse), `aria-live="polite"` for progress updates, and colour is never the only signal (icons and labels go with green and red).

---

## 10. Non-Functional Requirements

| Area | Requirement |
|---|---|
| **Performance** | UI first paint < 1.5 s locally. Leads list (10k leads) interactions < 200 ms. A 100-call batch (avg 3 min) completes in < 15 min with default concurrency (provider-bound). |
| **Reliability** | No lost work on crash or restart (idempotent stages, re-queue stale jobs). An upload resumes after a refresh or network loss. |
| **Scalability** | 2,000 calls per batch and 50k calls total on SQLite. Postgres is a config change. |
| **Privacy** | Runs on `127.0.0.1` by default. Phones are masked in the UI and exports unless disabled. Raw audio retention is enforced daily. API keys live only in `.env` and are never logged. Logs must not contain transcript text at INFO level. |
| **Security** | SSRF guard on link fetching. ZIP-slip and bomb protection. Upload size limits. Optional passcode. CORS limited to the frontend origin. |
| **Observability** | Structured JSON logs (`call_id`, `stage`, `duration_ms`, `provider`, `tokens_in/out`). `/health` endpoint. Per-batch processing time and token usage in `batches.stats_json`, shown in Batch detail. |
| **Cost control** | Transcript cache by audio hash. Re-analyse without re-transcribe. The comparison uses digests, not full transcripts. Prompt caching for static system and rubric content. |
| **Portability** | macOS, Linux and Windows (WSL). Requires Python 3.12, Node 20+ and ffmpeg. The Docker image bundles ffmpeg. |

---

## 11. Milestones & Acceptance Criteria

| # | Milestone | Done when… |
|---|---|---|
| **M0** | Skeleton | `make setup && make dev` starts the API, worker and frontend. `/health` is green. Sidebar and routes render empty states. Tokens are applied. |
| **M1** | Uploader and ingest | All three sources work. Chunked upload pauses and resumes and survives a refresh. Sheet mapping preview works. ZIP safety tests pass. A batch is created with call rows. Duplicates are removed. |
| **M2** | Pipeline and progress | Download, prepare and transcribe run in the worker. Live SSE progress page with ETA. Errors use the taxonomy and Retry works. A killed worker resumes. The transcript cache works. |
| **M3** | Per-call analysis and Call Detail | Analysis JSON validated and grounded. Metrics computed. Call Detail with waveform player, synced transcript, key moments, scorecard and metrics. Swap speakers works. |
| **M4** | Leads | All Conversations with KPIs, deltas, intent cards, filters and a virtualised table. Lead Details with Insights, Path to Conversion, Conversations, Summary, Actions and Notes. |
| **M5** | AI vs Human | All sections A–H. Every evidence quote verified and clickable. Records strip and sample warning. CSV/JSON export. Cached results. |
| **M6** | Polish | Dark mode, accessibility pass, README "how to change things" guide, eval script, Docker compose, fake-provider E2E test in CI. |

**v1 is accepted when** a real batch of ≥ 50 AI calls and ≥ 50 human calls from the same campaign can be uploaded from an Excel of links and processed without manual intervention (except for genuinely broken links), and a sales manager agrees with the intent bucket on ≥ 80% of 20 sampled leads.

---

## 12. Risks & Mitigations
| Risk | Mitigation |
|---|---|
| Hinglish transcription errors (product names, prices) | Custom vocabulary hint in the transcribe prompt (product names, sizes, "Ortho Pro", "SmartGRID", rupee amounts). Spot-check eval set. |
| Wrong Agent/Customer roles break metrics | Stereo channel split when available. LLM role mapping. A one-click Swap speakers that recomputes everything. |
| LLM hallucinated evidence | Code-verified quotes. Unverified quotes are hidden from evidence. Numbers are never computed by the LLM. |
| Small samples lead to bad decisions | Records strip and a sample-size banner. No "winner" language when n < 10 on either side. |
| Provider rate limits or cost | Per-provider token bucket, cache, re-analyse without re-transcribe, configurable concurrency. |
| Signed or expiring recording URLs | Clear 403 messaging. Download happens immediately after batch creation. |
| Customer PII in third-party APIs | Data notice, offline mode (local Whisper), phone masking, retention purge. |

## 13. Open Questions (defaults chosen; confirm with stakeholders)
1. Do recordings from our dialer come as **stereo (agent/customer split)**? *Default: auto-detect.*
2. Which **transcript script** do managers prefer to read, Roman Hinglish or Devanagari? *Default: Roman.*
3. Should lead **status changes** sync back to CRM? *Default: no (v2).*
4. **Retention**: how long can we keep raw audio? *Default: 30 days, transcripts kept.*
5. Is a **shared server deployment** (multiple managers) needed in v1? *Default: no, single machine.*

## 14. Future (v2+)
CRM/dialer webhooks for auto-ingest · bot version A/B trend lines · per-agent coaching reports · real-time assist · Postgres and multi-user auth · scheduled weekly AI vs Human digest emails.

---

## Appendix A — Glossary
- **Connected call**: ≥ 5 s with speech from both sides.
- **Detailed call**: ≥ 120 s and ≥ 6 turns.
- **Quality score %**: `(mean scorecard − 1) / 4 × 100`.
- **Talk-to-listen**: agent speech time : customer speech time.
- **Disposition**: the outcome of a call (§7.1 enum). **Status category**: Won / Lost / In Progress roll-up.

## Appendix B — Reference screens → feature mapping
| Reference | Implemented in |
|---|---|
| Screen 1 "AI voice bot vs human agents" (inputs) | Upload page, Links tab, AI-vs-Human mode (§6.1, §9.3) |
| Screen 1 (progress) | Batch progress (§6.2.3) |
| Screen 1 (results: verdict, differ, scores, measured, outcomes, fixes, every call) | Compare tab (§6.6) |
| Screen 2 "All Conversations" | Leads list (§6.3) |
| Screen 3 "Lead Details" (Buying intent, Objections, BANT, Path to Conversion) | Lead Details (§6.4) |
