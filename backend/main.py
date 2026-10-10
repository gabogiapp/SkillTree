import logging
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.config import settings
from backend.models.schemas import (
    SearchResponse,
    NeighborResponse,
    PathResponse,
    ExpansionResponse,
    GraphStatsResponse,
    SubgraphResponse,
    BridgeRequest,
    ExpandRequest,
    ExpandNodeRequest,
    ResumeUploadRequest,
    ResumeUploadResponse,
    SkillNode,
    CustomSkillRequest,
    IntermediateNode,
    SynthesizeSkillsRequest,
    SynthesizeSkillsResponse,
    SuggestNextStepsRequest,
    SuggestNextStepsResponse,
)
from backend.services.graph_engine import GraphEngine, slugify
from backend.services.bridge_engine import BridgeEngine


logger = logging.getLogger("main_api")
logging.basicConfig(level=logging.INFO)

# Global Graph & Bridge singletons
graph_engine = GraphEngine(settings.CSV_PATHS)
bridge_engine = BridgeEngine(graph_engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Load CSV into in-memory NetworkX DiGraph
    logger.info("Initializing GraphEngine with CSV dataset...")
    edges_count = graph_engine.load_ground_truth()
    stats = graph_engine.get_stats()
    logger.info(
        f"Skill graph ready: {stats.total_nodes} nodes, "
        f"{stats.total_edges} edges in memory."
    )
    yield
    logger.info("Shutting down Skill Tree API.")


app = FastAPI(
    title="The Skill Tree - Infinite Craft Engine",
    description="Interactive Life & Skill Tree Builder with LLM Bridge Reasoning",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for Next.js/Vite/Localhost frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- System & Stats Endpoints ---

@app.get("/api/health", tags=["System"])
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "version": "1.0.0"}


@app.get("/api/graph/stats", response_model=GraphStatsResponse, tags=["Graph"])
async def get_graph_stats():
    """Returns total nodes, edges, ground-truth count, AI-generated count, and density."""
    return graph_engine.get_stats()


@app.get("/api/graph/subgraph", response_model=SubgraphResponse, tags=["Graph"])
async def get_initial_subgraph(
    seeds: Optional[str] = Query(None, description="Comma-separated list of seed skill IDs"),
    max_nodes: int = Query(35, ge=5, le=100, description="Maximum nodes to return"),
):
    """
    Returns an interconnected starter subgraph for canvas rendering.
    If no seeds provided, defaults to highest-degree hub nodes.
    """
    seed_list = [s.strip() for s in seeds.split(",")] if seeds else None
    nodes, edges = graph_engine.get_subgraph(seed_ids=seed_list, max_nodes=max_nodes)
    return SubgraphResponse(
        nodes=nodes,
        edges=edges,
        total_nodes=len(nodes),
        total_edges=len(edges),
    )


# --- Skill Search & Neighbors ---

@app.get("/api/skills/search", response_model=SearchResponse, tags=["Skills"])
async def search_skills(
    q: str = Query(..., min_length=1, description="Search term for skill name or slug"),
    limit: int = Query(15, ge=1, le=50, description="Max results to return"),
):
    """
    Fuzzy semantic search across all ground-truth and AI-generated skills.
    Ranked by relevance score and graph degree connectivity.
    """
    return graph_engine.search_skills(query=q, limit=limit)


@app.get("/api/skills/{skill_id}", response_model=SkillNode, tags=["Skills"])
async def get_skill(skill_id: str):
    """Fetch complete metadata and degree counts for a skill."""
    node = graph_engine.get_node(skill_id)
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill '{skill_id}' not found in graph.",
        )
    return node


@app.get("/api/skills/{skill_id}/neighbors", response_model=NeighborResponse, tags=["Skills"])
async def get_skill_neighbors(skill_id: str):
    """
    Returns incoming (prerequisites) and outgoing (unlocked) neighbors
    with edge relation metadata.
    """
    res = graph_engine.get_neighbors(skill_id)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill '{skill_id}' not found in graph.",
        )
    return res


@app.post("/api/skills/custom", response_model=SkillNode, tags=["Skills"])
async def create_custom_skill(req: CustomSkillRequest):
    """Allows user to input a custom skill directly into the system."""
    clean_label = req.label.strip()
    if not clean_label:
        raise HTTPException(status_code=400, detail="Skill label cannot be empty.")

    # Check if close match exists
    existing_id = graph_engine.find_close_existing_skill(clean_label, threshold=95.0)
    if existing_id:
        node = graph_engine.get_node(existing_id)
        if node:
            return node

    # Add as new skill node
    new_id = slugify(clean_label)
    graph_engine.merge_subgraph(
        intermediate_nodes=[
            IntermediateNode(
                id=new_id,
                label=clean_label,
                category=req.category or "Custom Skill",
                description=req.description or f"User defined skill: {clean_label}",
            )
        ],
        connecting_edges=[],
        is_ground_truth=False,
    )
    node = graph_engine.get_node(new_id)
    if not node:
        raise HTTPException(status_code=500, detail="Failed to instantiate skill node.")
    return node


# --- Feature A: Bridge Two Skills (Pathway Synthesizer) ---


@app.post("/api/skills/bridge", response_model=PathResponse, tags=["Bridge Engine"])
async def bridge_skills(req: BridgeRequest):
    """
    Synthesizes a learning path between two skills.
    1. Checks if a path exists in the ground-truth graph.
    2. If disconnected, invokes LLM to generate stepping-stone skills and directed edges.
    3. Merges new nodes into the graph and returns the unified path.
    """
    try:
        path_res = bridge_engine.bridge_pathway(
            start_id=req.start_skill_id,
            target_id=req.target_skill_id,
        )
        return path_res
    except Exception as e:
        logger.error(f"Error bridging skills {req.start_skill_id} -> {req.target_skill_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pathway synthesis failed: {str(e)}",
        )


# --- Feature B: Infinite Craft Discovery (Frontier Expansion - Fast-Model Triage) ---

@app.post("/api/expand-node", response_model=ExpansionResponse, tags=["Bridge Engine"])
async def expand_node_triage(req: ExpandNodeRequest):
    """
    Fast-Model Triage Node Expansion:
    1. The 'Infinite Craft' Caching Layer: Checks graph database first. If node has existing
       outgoing edges, returns cached neighbors immediately and exits (0 LLM tokens).
    2. If leaf node (0 outgoing edges), queries 3-5 immediate parent nodes as tightly formatted
       'Domain Context: [Parent1, Parent2, Parent3]' without dumping the entire graph.
    3. Calls LLM with strict API constraints (max_tokens=250, temperature=0.3, json_object).
    4. Immediately writes new nodes/edges to the Graph Database so subsequent clicks hit cache.
    """
    target_id = req.node_id or req.skill_id
    if not target_id or not target_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either 'node_id' or 'skill_id' must be provided in request body.",
        )
    clean_target = target_id.strip()
    try:
        expansion_res = bridge_engine.expand_frontier(
            skill_id=clean_target,
            count=req.count,
            direction=req.direction,
            domain_context=req.domain_context,
            bypass_cache=req.bypass_cache,
        )
        return expansion_res
    except Exception as e:
        logger.error(f"Error in Fast-Model Triage expansion for '{clean_target}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Node expansion failed: {str(e)}",
        )


@app.post("/api/skills/{skill_id}/expand", response_model=ExpansionResponse, tags=["Bridge Engine"])
async def expand_skill_frontier(skill_id: str, req: ExpandRequest = ExpandRequest()):
    """
    Fast-Model Triage Frontier Expansion (Path Parameter):
    1. The 'Infinite Craft' Caching Layer: Returns cached neighbors if node has existing outgoing edges.
    2. Context Injection Limit: Injects 3-5 immediate parent nodes without dumping the graph.
    3. Strict LLM API constraints: max_tokens=250, temperature=0.3, JSON mode.
    4. Graph Database Write: Merges new nodes/edges immediately so subsequent clicks hit cache.
    """
    try:
        expansion_res = bridge_engine.expand_frontier(
            skill_id=skill_id,
            count=req.count,
            direction=req.direction,
            domain_context=req.domain_context,
            bypass_cache=req.bypass_cache,
        )
        return expansion_res
    except Exception as e:
        logger.error(f"Error expanding skill frontier for {skill_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Frontier expansion failed: {str(e)}",
        )


# --- Feature C: Node Synthesis (Merging / Many-to-1) ---

@app.post("/api/synthesize-skills", response_model=SynthesizeSkillsResponse, tags=["Bridge Engine"])
async def synthesize_skills_endpoint(req: SynthesizeSkillsRequest):
    """
    Node Synthesis (Many-to-1 Merging):
    1. Caching Layer Check: Query if there is already a node that shares incoming REQUIRES edges
       from both source_node_1 and source_node_2. If exists, returns it instantly.
    2. Emergent LLM synthesis: Calls LLM to discover logical emergent concept combining both nodes.
    3. Graph solidification: Writes synthesized Node C and the two directed edges into the graph database.
    """
    s1 = req.source_node_1.strip()
    s2 = req.source_node_2.strip()
    if not s1 or not s2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both 'source_node_1' and 'source_node_2' must be non-empty strings.",
        )
    if s1.lower() == s2.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot synthesize a node with itself. Please drag two distinct nodes.",
        )

    try:
        response = bridge_engine.synthesize_skills(source_1=s1, source_2=s2)
        return response
    except Exception as e:
        logger.error(f"Error synthesizing skills '{s1}' + '{s2}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Node synthesis failed: {str(e)}",
        )


# --- Feature D: Multi-Skill Discovery (Suggest Next Steps from Current Skills) ---

@app.post("/api/skills/suggest-next-steps", response_model=SuggestNextStepsResponse, tags=["Bridge Engine"])
@app.post("/api/suggest-next-steps", response_model=SuggestNextStepsResponse, tags=["Bridge Engine"])
async def suggest_next_steps_endpoint(req: SuggestNextStepsRequest):
    """
    Multi-Skill Discovery:
    Analyzes multiple skills currently possessed by the learner and suggests
    potential emergent skills and directional next steps that can be unlocked/made
    from the combination of current skills.
    """
    clean_ids = [s.strip() for s in req.skill_ids if s and s.strip()]
    if not clean_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one valid skill ID must be provided in 'skill_ids'.",
        )
    try:
        response = bridge_engine.suggest_next_steps(
            skill_ids=clean_ids,
            count=req.count,
            domain_context=req.domain_context,
        )
        return response
    except Exception as e:
        logger.error(f"Error suggesting next steps for {clean_ids}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Multi-skill next step discovery failed: {str(e)}",
        )


# --- Feature E: Resume & Skill List Ingestion ---

@app.post("/api/skills/upload-resume", response_model=ResumeUploadResponse, tags=["Resume Ingestion"])
async def upload_resume_skills(req: ResumeUploadRequest):
    """
    Ingests user resume text or list of skills.
    Fuzzy-matches them into the ground-truth skill graph,
    and returns matched foundations plus recommended career target goals.
    """
    raw_skills = []
    if req.skills:
        raw_skills.extend(req.skills)

    if req.resume_text:
        # Heuristic extraction from bullet points, commas, newlines
        lines = re.split(r"[\n,\u2022\-\*\|;]", req.resume_text)
        for line in lines:
            cleaned = line.strip()
            # Retain reasonable skill phrases (between 2 and 40 characters)
            if 2 <= len(cleaned) <= 40 and not cleaned.isdigit():
                raw_skills.append(cleaned)

    if not raw_skills:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid skills or resume text provided.",
        )

    matched, unmatched, recommended_goals = graph_engine.match_resume_skills(raw_skills)

    return ResumeUploadResponse(
        extracted_skills=list(dict.fromkeys(raw_skills))[:30],
        matched_skills=matched,
        unmatched_skills=unmatched[:15],
        recommended_goals=recommended_goals,
        message=f"Matched {len(matched)} skills to the knowledge tree with {len(recommended_goals)} suggested targets.",
    )


# --- Static SPA Hosting for Production/Local Deployment ---
frontend_dist = settings.BASE_DIR / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

    @app.get("/{full_path:path}", tags=["Frontend"])
    async def serve_frontend(full_path: str):
        file_path = frontend_dist / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(frontend_dist / "index.html")
