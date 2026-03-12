# Pedagogical Flow Extractor

An end-to-end pipeline that ingests YouTube lecture videos, transcribes them with OpenAI Whisper, cleans Hinglish code-switching noise, extracts concept graphs using Gemini 2.5 Flash, validates them with graph theory, and renders interactive prerequisite DAGs — complete with automatic study-path generation.


---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Video Sources](#video-sources)
3. [Module Breakdown](#module-breakdown)
   - [Phase 1 — Ingestion](#phase-1--ingestion)
   - [Phase 2 — Whisper Transcription](#phase-2--whisper-transcription)
   - [Phase 3 — Preprocessing](#phase-3--preprocessing)
   - [Phase 4 — Self-Correcting Concept Extraction](#phase-4--self-correcting-concept-extraction)
   - [Phase 5 — Visualization](#phase-5--visualization)
   - [Phase 6 — Automatic Study Path Generator](#phase-6--automatic-study-path-generator)
4. [Output Structure & Rationale](#output-structure--rationale)
5. [Pipeline Demo](#pipeline-demo)
6. [Setup & Usage](#setup--usage)
7. [Dependencies](#dependencies)

---

## Architecture Overview

```
YouTube URL
    │
    ▼
┌─────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│  1. Ingest  │────▶│ 2. Transcribe     │────▶│  3. Preprocess      │
│  (yt-dlp)   │     │  (Whisper small)  │     │  (Hinglish cleaner) │
└─────────────┘     └──────────────────┘     └─────────────────────┘
                                                          │
                                                          ▼
                                             ┌────────────────────────┐
                                             │ 4. Extract & Validate  │
                                             │  Gemini 2.5 Flash      │
                                             │  + NetworkX DAG check  │◀─┐
                                             └────────────────────────┘  │ retry with
                                                          │               │ cycle feedback
                                                          │  valid DAG    │
                                                          ▼               │
                                             ┌────────────────────────┐  │
                                             │ 5. Visualize (Pyvis)   │  │
                                             │ 6. Study Path (Kahn's) │  │
                                             └────────────────────────┘  │
                                                          │  cycle found  │
                                                          └───────────────┘
```

Every phase is **idempotent**: if an output already exists on disk it is skipped, so you can re-run the pipeline safely without re-downloading or re-transcribing.

---

## Video Sources

All five videos are Hindi-English (Hinglish) Computer Science lectures from YouTube:

| Topic | Language | URL |
|---|---|---|
| Deadlock (OS) | Hinglish | https://www.youtube.com/watch?v=rWFH6PLOIEI |
| WebSockets | Hinglish | https://www.youtube.com/watch?v=favi7avxIag |
| CI/CD Pipeline | Hinglish | https://www.youtube.com/watch?v=gLptmcuCx6Q |
| REST API | Hinglish | https://www.youtube.com/watch?v=cJAyEOZQUQY |
| NGINX | Hinglish | https://www.youtube.com/watch?v=b_B1BEShfBc |

**Why Hinglish?** Real-world Indian STEM education on YouTube is overwhelmingly code-mixed. Building a pipeline robust to this is the core technical challenge the task is designed to test.

---

## Module Breakdown

### Phase 1 — Ingestion
**`src/ingestion.py` · `yt-dlp`**

Downloads audio from a YouTube URL and extracts it as a 192 kbps MP3 using FFmpeg.

**Rationale:** `yt-dlp` is the most actively maintained YouTube downloader and handles age-gating, throttling, and format negotiation automatically. Extracting audio-only keeps disk usage minimal and speeds up Whisper inference significantly.

---

### Phase 2 — Whisper Transcription
**`src/transcription.py` · `openai-whisper` (small model)**

Passes the MP3 to Whisper and returns the full transcript text plus per-segment timestamps.

**Rationale for Whisper:** Whisper is explicitly trained on multilingual and code-switched speech. The `small` model (244M parameters) strikes a practical balance between speed and accuracy for Hinglish — it correctly handles mid-sentence switches between Hindi and English, Devanagari pronunciation of English acronyms (e.g. "डेडलॉक"), and informal register without any fine-tuning, while running significantly faster than the medium or large variants.

---

### Phase 3 — Preprocessing
**`src/preprocessor.py`**

`TextCleaner` removes Whisper artefacts (`[BLANK_AUDIO]`, timestamps), strips verbal fillers (`theek hai`, `matlab`, `um`, `basically`), and normalises whitespace before the text reaches the LLM.

**Rationale:** Cleaner input reduces Gemini token usage (cost) and improves extraction consistency by removing noise that would otherwise dilute the concept signal.

---

### Phase 4 — Self-Correcting Concept Extraction
**`src/extractor.py` + `src/validate_dag.py` · `google-genai` (Gemini 2.5 Flash)**

**Extraction:** Gemini 2.5 Flash is prompted to return a strict JSON schema containing each concept's `id`, `standard_term`, `colloquial_context`, `description`, `relative_importance` (1–10), and `prerequisites` list. JSON mode (`response_mime_type: application/json`) is enforced to prevent markdown wrapping.

**Self-Correcting Validation Loop:**

```
Attempt 1: extract concepts from cleaned transcript
    │
    ▼
NetworkX DAGValidator:
  nx.is_directed_acyclic_graph(G) ──── PASS ──▶ save JSON, continue
                    │
                   FAIL (cycle found)
                    │
                    ▼
  Inject error feedback into prompt:
  "CRITICAL ERROR: Circular dependency detected: [A → B → A].
   Re-evaluate the prerequisite flow."
                    │
                    ▼
Attempt 2: re-extract with feedback ──▶ validate again
```

**Rationale for Gemini Flash:** Flash is 10–20× cheaper than Pro/Ultra and returns results in under 3 seconds, making the retry loop economically viable. The structured JSON mode eliminates post-processing fragility.

**Prerequisite resolution:** Both the validator and the mapper normalise prerequisites that arrive as string names (e.g. `"Process"`) or integer IDs into a consistent integer ID space using a `name_to_id` lookup — preventing phantom duplicate nodes.

---

### Phase 5 — Visualization
**`src/mapper.py` · `networkx` + `pyvis`**

Builds an interactive HTML graph with a professional UI injected as a post-processing step.

**Visual encoding:**

| Feature | Encoding |
|---|---|
| **Red nodes** — Leaf / Foundational | No prerequisites; entry points for the learner |
| **Blue nodes** — Core / Advanced | Have prerequisites; build on earlier concepts |
| **Node size** | Proportional to `relative_importance` (1–10); reflects how much teaching time the instructor devoted to the concept |
| **Edge width** | Proportional to the importance of the destination concept; thicker = more critical prerequisite path |

**Layout:** Hierarchical Up-Down (`direction: "UD"`, `sortMethod: "directed"`) so foundational concepts appear at the top and terminal concepts at the bottom, mirroring a natural learning progression. `avoidOverlap: 1` and `springLength: 300` prevent node crowding. The graph is fully stabilised before display so it never jumps on load.

**UI:** A dark header bar with the topic title and a floating legend are injected into the Pyvis-generated HTML as a post-processing step — keeping `mapper.py` independent of any HTML templating framework.

---

### Phase 6 — Automatic Study Path Generator
**`src/study_path.py` · `networkx`**

Consumes the validated DAG JSON and produces a structured study-path report with three components:

#### 1. Recommended Sequence
Standard topological sort (`nx.topological_sort`) — a single guaranteed-valid linear learning order, annotated with a human-readable rationale for each concept's position:

```
 1. Deadlock            (prereqs: none)  — root concept, enables: Resource, Synchronization ...
 2. Process             (prereqs: none)  — root concept, enables: Resource, Semaphore ...
 3. Resource            (prereqs: Deadlock, Process)
 4. Conditions for Deadlock  (prereqs: Deadlock, Resource)
 5. Mutual Exclusion    (prereqs: Conditions for Deadlock)
 ...
```

#### 2. Parallel Learning Groups (Kahn's BFS)
Kahn's algorithm processes the DAG level-by-level, exposing concepts that share no mutual dependency and can therefore be studied simultaneously:

```
Foundation : Deadlock, Process             ← start here, in any order
Level 2    : Synchronization, Resource     ← both safe to tackle in parallel
Level 3    : Semaphore, Conditions for Deadlock
Level 4    : Mutual Exclusion, No Preemption, Hold and Wait, Circular Wait
```

#### 3. Disconnected Component Handling
`nx.connected_components` detects isolated sub-graphs (e.g. a standalone definition node with no edges) and returns a separate ordered sequence for each component, so no concept is silently dropped from the output.

**Output format:** structured JSON saved to `output/study_paths/<topic>_study_path.json`.

---

## Output Structure & Rationale

```
output/
├── structured_data/          # Validated concept graphs (JSON)
│   └── deadlock_os.json      # { video_summary, concepts: [{id, standard_term,
│                             #   description, prerequisites, relative_importance}] }
├── visualizations/           # Interactive HTML flowcharts (open in any browser)
│   └── deadlock_os_enhanced_flow.html
└── study_paths/              # Kahn's-sorted study sequences (JSON)
    └── deadlock_os_study_path.json
```

**Why separate JSON + HTML?** The JSON is the authoritative data artifact — it can be consumed by downstream tools, search indexes, or future LLM prompts without re-running the expensive extraction step. The HTML is a human-readable, self-contained rendering of that data. Keeping them separate means either can be regenerated independently.

**Why JSON over a database?** For a five-video research task, flat JSON files provide zero-dependency portability — any machine with Python and the repo can load and inspect the data without a running database server.

---

## Pipeline Demo

A full end-to-end run of the pipeline on the **Deadlock (OS)** lecture — covering all 6 phases from audio download through to the interactive knowledge graph and study path output.

▶ **[Watch Demo on Google Drive](https://drive.google.com/file/d/1_rzqOlMasLbmv-4n8Y4SYwEGXMNGxHQT/view?usp=sharing)**


---

## Setup & Usage

### Prerequisites

- Python 3.10+
- `ffmpeg` installed on the system path:
  ```bash
  # macOS
  brew install ffmpeg
  # Ubuntu / Debian
  sudo apt install ffmpeg
  ```

### Installation

```bash
git clone <repo-url>
cd pedagogical-flow-extractor

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### Configuration

```bash
# Open .env and set your Gemini API key:
# GEMINI_API_KEY=your_key_here
```

### Run

```bash
python main.py
```

The pipeline is fully resumable — re-running it skips any phase whose output already exists on disk. To force a phase to re-run, delete the corresponding file in `data/` or `output/`.

### View Results

Open any file in `output/visualizations/` directly in a browser — no server required.

---

## Dependencies

| Package | Version | Purpose |
|---|---|---|
| `openai-whisper` | 20250625 | Hinglish-robust speech-to-text |
| `torch` | 2.10.0 | Whisper backend |
| `yt-dlp` | 2026.3.3 | YouTube audio download |
| `google-genai` | 1.66.0 | Concept extraction via Gemini 2.5 Flash |
| `networkx` | 3.4.2 | DAG construction, cycle detection, topological sort |
| `pyvis` | 0.3.2 | Interactive graph HTML generation |
| `python-dotenv` | ≥1.0.0 | `.env` API key loading |
| `ffmpeg` | system | Audio extraction (MP3 conversion) |
