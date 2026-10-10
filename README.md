# 🌳 Skill Pathway Explorer

An interactive, semantic **Skill Pathway Explorer & Discovery Graph** combining a high-performance **deterministic ground-truth taxonomy** (over 20,600 skills and 29,400 directional prerequisite relationships) with an active **LLM Semantic Reasoning Intermediary (Bridge Engine)** that suggests emergent skills and unifies disconnected learning pathways.

Built with a clean **circular monochrome aesthetic**, **curved Bezier edge routing**, and a **Ghost Node preview & solidification interaction model**.

---

## 🌟 Key Architecture & Capabilities

### 1. Unified In-Memory Graph Engine (`NetworkX`)
- **Fast Startup**: Loads and unifies multi-dataset taxonomies (`skills_parent_child_10000.csv` and `pure_skill_to_skill_edges.csv`) into a memory-resident `DiGraph` in under 150ms.
- **Shortest Path Search**: Breadth-First Search (BFS) and Dijkstra pathfinding across 20,600+ nodes.
- **Prerequisite & Unlock Subgraph Resolution**: Direct neighbor inspection partitioned by incoming (`REQUIRES`) and outgoing (`UNLOCKS`) degrees.
- **Thread-Safe In-Memory Mutation**: Uses `threading.RLock` to safely register newly discovered skills.

### 2. Fast-Model Triage Caching Layer
- **Graph Caching Layer**: Pre-flight inspection checks if a queried node already has outgoing edges. If present, returns cached neighbors in <5ms with **0 LLM tokens**.
- **Context Injection Limit**: Extracts tightly bounded immediate ancestor paths (`Domain Context: [Parent1, Parent2, Parent3]`) rather than dumping global graph state.
- **Strict Model Constraints**: Optimised for lightweight structured models (`gpt-4o-mini`, `llama-3.1-8b-instant`) with `max_tokens=250`, `temperature=0.3`, and strict JSON output validation.
- **Procedural Algorithmic Fallback**: Self-contained semantic heuristic engine ensures full offline functionality and test reproducibility without API keys.

### 3. Ghost Node Expansion & Solidification
- **Dotted Preview Interaction**: Expanding a node or exploring next steps renders potential skills as **translucent, dashed Ghost Nodes** branching with animated dashed edges.
- **Solidification**: Ghost nodes are non-destructive previews. Clicking a ghost node **solidifies** it into the permanent skill tree, turning its borders and edges solid and dismissing sibling previews.
- **Pane Dismissal**: Clicking on the background canvas dismisses unsolidified ghost previews.

### 4. Multi-Skill Discovery ("What Can I Make With My Skills?")
- **Many-to-1 Synthesis**: Analyzes all skills currently active on the canvas or any selected subset to suggest emergent competencies and next-step milestones that can be unlocked from your combined skillset.
- **Dotted Emergent Previews**: Generates dotted preview skills connected by dashed arrows from the prerequisite source skills.
- **Interactive Controls**: Triggerable via the top toolbar button, the canvas floating action, or the Sidebar's multi-skill checkbox panel.

### 5. Pathway Synthesizer (Bridging Disconnected Skills)
- Select any **Start Skill** and **Goal Skill**.
- If disconnected in ground-truth taxonomy, the Bridge Engine synthesizes 2–4 coherent intermediate stepping-stone skills and directional edges, fusing them into the graph.

### 6. Circular Monochrome Aesthetic
- **Minimalist Geometry**: Perfectly circular nodes (`rounded-full`) with balanced centered typography.
- **Sweeping Bezier Curves**: Smooth curved connectors rather than sharp orthogonal lines.
- **Strict Grayscale Palette**: High-contrast white canvas (`#ffffff`), dark slate nodes (`#0a0a0a`, `#171717`), and subtle gray edge markers (`#4b5563`).

---

## 🚀 Quick Start for Collaborators

### 1. Prerequisites
- **Python**: 3.10 or higher (tested with Python 3.11 & 3.13)
- **Node.js**: 18.0 or higher (tested with Node.js 20+)
- **Git**

### 2. Clone the Repository
```bash
git clone https://github.com/<your-username>/the-skill-tree.git
cd the-skill-tree
```

### 3. Backend Setup
1. Create and activate a Python virtual environment:
   ```bash
   # Windows (PowerShell)
   python -m venv .venv
   .venv\Scripts\Activate.ps1

   # macOS / Linux
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Install backend dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment variables (optional for live OpenAI API):
   ```bash
   cp .env.example .env
   ```
   *Edit `.env` to add your `OPENAI_API_KEY`. If left unconfigured, the system runs seamlessly on the built-in deterministic fallback engine.*

4. Start the backend development server:
   ```bash
   uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
   ```
   *API documentation will be live at `http://localhost:8000/docs`.*

### 4. Frontend Setup
1. Open a new terminal and navigate to `frontend`:
   ```bash
   cd frontend
   npm install
   ```

2. Start the Vite development server:
   ```bash
   npm run dev
   ```
   *Open your browser to `http://localhost:5173`.*

---

## 📡 REST API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Service health status |
| `GET` | `/api/graph/stats` | Graph counts: total nodes, edges, ground truth, AI bridged |
| `GET` | `/api/graph/subgraph` | Starter interconnected subgraph for canvas initialization |
| `GET` | `/api/skills/search?q={query}` | Fuzzy semantic auto-complete across 20,600+ skills |
| `GET` | `/api/skills/{id}` | Detailed node metadata and connectivity degree |
| `GET` | `/api/skills/{id}/neighbors` | Incoming prerequisites and outgoing unlocked skills |
| `POST` | `/api/skills/bridge` | Synthesizes learning pathway between start and goal skills |
| `POST` | `/api/expand-node` | Fast-Model Triage node expansion with graph caching |
| `POST` | `/api/skills/suggest-next-steps` | Multi-skill discovery: suggests next steps from current skills |
| `POST` | `/api/synthesize-skills` | Many-to-1 synthesis combining two distinct concepts |
| `POST` | `/api/skills/upload-resume` | Ingests resume text, anchors mastered nodes, suggests target goals |
| `POST` | `/api/skills/custom` | Creates and anchors a custom skill node onto the graph |

---

## 🧪 Test Suite

Run the full automated test suite (31 unit and integration tests):
```bash
python -m unittest discover backend/tests
```

Tests cover:
- Multi-dataset ingestion and graph connectivity
- Fast-Model Triage caching layer (0-token cache hits)
- Context-aware neighborhood injection and domain containment
- Frontier expansion deduplication and graph mutation
- Multi-skill next-step discovery and prerequisite mapping
- Many-to-1 node synthesis and caching
- Resume parser and fuzzy skill extraction
- REST API response schemas and HTTP error handling

---

## 📁 Project Structure

```text
the-skill-tree/
├── .env.example                # Environment variable configuration template
├── .gitignore                  # Git ignore rules (Python, Node, build artifacts)
├── LICENSE                     # MIT Open Source License
├── README.md                   # Project documentation
├── requirements.txt            # Python dependencies (FastAPI, NetworkX, etc.)
├── pure_skill_to_skill_edges.csv   # Ground-truth dataset (19,440+ edges)
├── skills_parent_child_10000.csv   # Ground-truth dataset (9,998+ edges)
├── run_backend.bat             # Windows shortcut to launch backend
├── run_frontend_dev.bat        # Windows shortcut to launch frontend dev
│
├── backend/
│   ├── config.py               # Settings, dataset paths, and environment loader
│   ├── main.py                 # FastAPI application and route endpoints
│   ├── models/
│   │   └── schemas.py          # Pydantic schemas for request/response payloads
│   ├── services/
│   │   ├── bridge_engine.py    # LLM reasoning intermediary & prompt architecture
│   │   └── graph_engine.py     # NetworkX in-memory DiGraph engine & fuzzy matcher
│   └── tests/                  # 31 unit & integration test files
│
└── frontend/
    ├── .gitignore              # Frontend-specific ignore rules
    ├── package.json            # Node dependencies (@xyflow/react, tailwindcss, etc.)
    ├── vite.config.js          # Vite bundler configuration & proxy
    └── src/
        ├── App.jsx             # Main interactive canvas stage & flow controller
        ├── api/client.js       # Typed fetch client for backend endpoints
        ├── components/
        │   ├── SkillNodeComponent.jsx # Custom circular monochrome React Flow node
        │   ├── Sidebar.jsx            # Node inspector & multi-skill selection panel
        │   ├── Toolbar.jsx            # Search bar, layout toggle, bridge actions
        │   └── ResumeModal.jsx        # Resume text parser modal
        └── utils/
            └── layout.js              # Dagre automatic graph hierarchy layout engine
```

---

## 🤝 Contributing & Collaboration

1. Fork or branch from `master` (`git checkout -b feature/your-feature-name`).
2. Keep sensitive keys out of commits (always use `.env`).
3. Ensure all tests pass before opening a Pull Request:
   ```bash
   python -m unittest discover backend/tests
   cd frontend && npm run build
   ```
4. Commit with descriptive messages.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
