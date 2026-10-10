# 🌳 The Skill Tree — "Infinite Craft" Life & Skill Tree Builder

An interactive, dynamic skill & career knowledge graph combining **deterministic ground-truth taxonomy** (dataset: [`skills_parent_child_10000.csv`](file:///C:/Users/melon/projects/the-skill-tree/skills_parent_child_10000.csv) with 9,851+ skills and 9,998+ relationships) with an active **LLM Semantic Reasoning Intermediary (Bridge Engine)** that dynamically synthesizes transitional stepping-stone skills and expands sparse frontier nodes.

---

## 🌟 Key Architecture & Highlights

1. **In-Memory Graph Engine (`NetworkX`)**:
   - Sub-100ms loading of 9,851 nodes and 9,998 directed edges from `skills_parent_child_10000.csv`.
   - High-performance BFS / Dijkstra shortest-path pathfinding.
   - Subgraph extraction and degree ranking (prerequisites in, unlocks out).
   - Thread-safe graph mutations (`threading.RLock`).


2. **Semantic Bridge Engine (LLM Intermediary)**:
   - **Feature A: "Bridge Two Skills" (Pathway Synthesizer)**:
     - Automatically checks ground-truth shortest path first (zero LLM token waste).
     - When disconnected, prompts LLM with semantic neighbor context to synthesize 2–4 logical stepping stones and directed edges.
     - Merges synthesized nodes into the running graph (`is_ground_truth: false`) and returns the unified pathway.
   - **Feature B: "Infinite Craft Discovery" (Frontier Expansion)**:
     - Expand sparse nodes (< 3 neighbors) or on-demand.
     - Auto-links generated skills to existing graph concepts if fuzzy similarity is $\ge 82\%$, preventing duplication and driving natural convergence like Infinite Craft.
   - **Strict Pydantic JSON Schema Validation**:
     ```json
     {
       "intermediate_nodes": [
         {
           "id": "slugified-lowercase-id",
           "label": "Human Readable Label",
           "category": "Domain Category",
           "description": "Short explanation"
         }
       ],
       "connecting_edges": [
         {
           "source": "source_node_id",
           "target": "target_node_id",
           "relation": "REQUIRES | UNLOCKS | SYNERGIZES_WITH"
         }
       ]
     }
     ```
   - **Hackathon Resilience Fallback**: Deterministic algorithmic fallback activates automatically if API keys are unconfigured or if rate limits occur.

3. **Resume & Career Ingestion**:
   - Ingests raw resume text or comma-separated skills.
   - Fuzzy matches and anchors user-mastered nodes directly onto the graph canvas.
   - Recommends high-impact career target goals downstream.

4. **Interactive React Flow Frontend**:
   - Canvas with pan, zoom, minimap, controls, and dot grid background.
   - **Hierarchical Layout Engine**: Dagre (`dagre`) automatic hierarchy layout (toggle between Top-to-Bottom and Left-to-Right).
   - **Visual Distinction**:
     - 🛡️ **Ground Truth Nodes**: Deep navy card, blue borders, ESCO verified badge.
     - ✨ **AI Bridge Nodes**: Violet glow gradient border, Sparkles badge, pulse animation.
     - ⚡ **Start Skill**: Emerald glowing badge.
     - ⭐ **Goal Skill**: Amber/gold glowing badge.
   - **Sidebar Inspector**: Real-time incoming prerequisites and outgoing unlocked skills with one-click canvas jump.
   - **Search Bar**: Live fuzzy auto-complete across 10,800+ skills.

---

## 🚀 Quick Start Guide

### 1. Requirements
- Python 3.10+ (tested with Python 3.13)
- Node.js 18+ (Node.js v24 installed)

### 2. Configure Environment (Optional for Live LLM)
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Add your OpenAI or Groq API key:
```env
OPENAI_API_KEY=your_key_here
LLM_MODEL=gpt-4o-mini
```
*(If omitted, the built-in intelligent fallback synthesizer will power the demo seamlessly!)*

### 3. Run Application

#### Option A: Unified Full-Stack Server (FastAPI + Built SPA)
```bash
run_backend.bat
```
or via terminal:
```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
Open your browser to: **`http://localhost:8000`**

#### Option B: Vite Frontend Dev Server (with HMR)
```bash
# Terminal 1: Backend
python -m uvicorn backend.main:app --port 8000 --reload

# Terminal 2: Frontend
cd frontend
npm run dev
```
Open your browser to: **`http://localhost:5173`**

---

## 📡 REST API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Health check |
| `GET` | `/api/graph/stats` | Graph counts: total nodes, edges, ground truth, AI bridged |
| `GET` | `/api/graph/subgraph?max_nodes=35` | Starter interconnected subgraph for canvas |
| `GET` | `/api/skills/search?q={query}` | Fuzzy semantic search across 10,800+ skills |
| `GET` | `/api/skills/{id}` | Detailed node metadata and connectivity degree |
| `GET` | `/api/skills/{id}/neighbors` | Incoming prerequisites and outgoing unlocked skills |
| `POST` | `/api/skills/bridge` | **Feature A**: Synthesizes pathway between start and goal skills |
| `POST` | `/api/skills/{id}/expand` | **Feature B**: Infinite Craft frontier discovery |
| `POST` | `/api/skills/upload-resume` | Ingests resume text, anchors mastered nodes, suggests goals |

---

## 🧪 Testing

Run backend unit and integration tests:
```bash
python -m unittest discover backend/tests
```
All 15 unit and integration tests verify:
- Deterministic CSV ingestion (<100ms)
- Fuzzy search accuracy
- BFS shortest path execution
- LLM bridge schema validation and graph merging
- Frontier expansion deduplication
- FastAPI endpoint responses
