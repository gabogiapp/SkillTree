import json
import logging
import re
from typing import List, Optional, Tuple, Dict, Any
from openai import OpenAI
from pydantic import ValidationError

from backend.config import settings
from backend.models.schemas import (
    IntermediateNode,
    ConnectingEdge,
    BridgeResponse,
    PathResponse,
    ExpansionResponse,
    SkillNode,
    SkillEdge,
    LLMSynthesisResponse,
    SynthesizeSkillsResponse,
    LLMSynthesizedNode,
    LLMSuggestedSkill,
    LLMMultiSkillResponse,
    SuggestNextStepsResponse,
)
from backend.services.graph_engine import GraphEngine, slugify

logger = logging.getLogger("bridge_engine")
logging.basicConfig(level=logging.INFO)

SYSTEM_PROMPT_MULTI_SKILL_EXPAND = """You are an expert curriculum architect and knowledge graph reasoning engine for a Skill Pathway Explorer.
Your task is to analyze a set of skills that a learner currently possesses, and suggest 3 to 4 logical next-step skills or emergent competencies that can be unlocked, created, or synthesized by combining or building upon these current skills.

Rules:
1. Suggest 3 to 4 distinct next-step skills or emergent milestones.
2. Each suggested skill must be human-readable, concise (1-4 words), and intuitive.
3. For each suggested skill, specify which of the input skills it directly requires / builds upon (in 'required_input_skills').
4. Do not output generic combinations like 'Skill A and Skill B'. Find the authentic emergent concept, specialization, or advanced milestone.
5. Keep descriptions concise (1 sentence max).
6. Output strictly valid JSON matching this schema:
{
  "suggested_skills": [
    {
      "id": "slugified-lowercase-id",
      "label": "Human Readable Label",
      "category": "Domain Category",
      "description": "Short explanation of the skill",
      "required_input_skills": ["source_skill_id_or_label_1", "source_skill_id_or_label_2"]
    }
  ]
}"""

SYSTEM_PROMPT_SYNTHESIZE = """You are a determinist Graph API. Your task is to synthesize two distinct concepts into a single, logical emergent concept, skill, or field of study that naturally combines them.
- The output MUST be a valid JSON object matching the schema: { "synthesized_node": { "id": "string", "label": "string", "description": "string" } }.
- Do not output generic combinations like 'Concept 1 and Concept 2'. Find the actual semantic intersection. 
- Keep the label concise (1-4 words). Keep it human-readable."""

SYSTEM_PROMPT_BRIDGE = """You are an expert graph reasoning intermediary and curriculum architect for an Infinite Craft-style Skill Tree engine.
Your task is to synthesize a logical, step-by-step learning pathway connecting a START skill to a TARGET skill.

Rules:
1. Generate between 2 to 4 intermediate stepping-stone skills.
2. Form a coherent, monotonic prerequisite progression from START to TARGET.
3. Output strictly valid JSON matching this exact schema:
{
  "intermediate_nodes": [
    {
      "id": "slugified-lowercase-id",
      "label": "Human Readable Label",
      "category": "Domain Category (e.g., Software Engineering, Systems, AI)",
      "description": "Short 1-2 sentence description of this skill"
    }
  ],
  "connecting_edges": [
    {
      "source": "source_node_id",
      "target": "target_node_id",
      "relation": "REQUIRES"
    }
  ]
}

Ensure the connecting edges establish a complete directed chain:
START -> intermediate_1 -> intermediate_2 -> ... -> TARGET.
Allowed relation values: "REQUIRES", "UNLOCKS", "SYNERGIZES_WITH".
Do not wrap JSON with markdown code blocks if returning in JSON mode."""

SYSTEM_PROMPT_EXPAND = """You are an expert knowledge graph reasoning engine for an Infinite Craft-style Skill Tree.
You are generating skills for a semantic skill tree. You will be given a target skill and its broader Domain Context. You MUST generate prerequisites and unlocks that strictly align with this Domain Context. Do not append corporate, tech, or engineering jargon to non-technical concepts. Keep the generated skills broad, intuitive, and human-readable.

Output strictly valid JSON matching this exact schema:
{
  "intermediate_nodes": [
    {
      "id": "slugified-lowercase-id",
      "label": "Human Readable Label",
      "category": "Domain Category",
      "description": "Short explanation of the skill"
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

Rules:
1. For prerequisite skills: edge source is the prerequisite id, edge target is the target skill id, and relation is "REQUIRES".
2. For unlockable skills: edge source is the target skill id, edge target is the unlockable skill id, and relation is "UNLOCKS".
3. Strictly adhere to the Domain Context. Never hallucinate corporate, tech, or engineering jargon for non-technical fields (e.g. languages, cooking, arts, music, crafts).
4. Keep skill descriptions concise (1 sentence max) to strictly comply with the 250 token limit.
5. Do not wrap output in markdown code blocks when JSON mode is active."""



class BridgeEngine:
    """
    AI Semantic Reasoning Intermediary (Bridge Engine).
    Synthesizes transitional stepping-stone skills and directional edges between disconnected
    nodes or expands sparse frontier nodes into the graph.
    """

    def __init__(self, graph_engine: GraphEngine):
        self.graph_engine = graph_engine
        self._client: Optional[OpenAI] = None

    @property
    def client(self) -> Optional[OpenAI]:
        """Lazy initialization of OpenAI client."""
        if self._client is None and settings.OPENAI_API_KEY:
            try:
                self._client = OpenAI(
                    api_key=settings.OPENAI_API_KEY,
                    base_url=settings.OPENAI_BASE_URL if settings.OPENAI_BASE_URL else None,
                )
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                self._client = None
        return self._client

    # -------------------------------------------------------------------------
    # Feature A: "Bridge Two Skills" (Pathway Synthesizer)
    # -------------------------------------------------------------------------
    def bridge_pathway(self, start_id: str, target_id: str) -> PathResponse:
        """
        Synthesizes a pathway between start_id and target_id.
        1. Checks shortest path on existing graph.
        2. If path exists, returns deterministic ground-truth path immediately.
        3. If disconnected, calls LLM Bridge to synthesize intermediate stepping stones,
           merges them into graph, and returns unified pathway.
        """
        # Resolve start and target nodes
        start_node = self.graph_engine.get_node(start_id)
        target_node = self.graph_engine.get_node(target_id)

        if not start_node or not target_node:
            # Try searching or auto-creating if not found
            if not start_node:
                start_node_id = slugify(start_id)
                self.graph_engine.merge_subgraph(
                    [IntermediateNode(id=start_node_id, label=start_id.replace("-", " ").title(), category="User Input", description="Entry skill")],
                    [],
                    is_ground_truth=False,
                )
                start_node = self.graph_engine.get_node(start_node_id)

            if not target_node:
                target_node_id = slugify(target_id)
                self.graph_engine.merge_subgraph(
                    [IntermediateNode(id=target_node_id, label=target_id.replace("-", " ").title(), category="User Target", description="Goal skill")],
                    [],
                    is_ground_truth=False,
                )
                target_node = self.graph_engine.get_node(target_node_id)

        # 1. Check existing graph path
        found, nodes, edges = self.graph_engine.find_path(start_node.id, target_node.id)
        if found:
            logger.info(f"Existing direct path found between {start_node.id} and {target_node.id} ({len(nodes)} hops)")
            return PathResponse(
                found=True,
                path_type="DIRECTED_GROUND_TRUTH",
                start_skill=start_node,
                target_skill=target_node,
                nodes=nodes,
                edges=edges,
                total_steps=len(nodes),
                synthesized_count=sum(1 for n in nodes if not n.is_ground_truth),
                message="Found direct deterministic path in ground-truth graph.",
            )

        # 2. Path is severed / disconnected: Invoke LLM Bridge
        logger.info(f"No direct path between {start_node.id} and {target_node.id}. Invoking Bridge Engine...")
        start_context = self.graph_engine.sample_adjacent_concepts(start_node.id, limit=4)
        target_context = self.graph_engine.sample_adjacent_concepts(target_node.id, limit=4)

        bridge_data = self._synthesize_bridge_llm(
            start_node=start_node,
            target_node=target_node,
            start_context=start_context,
            target_context=target_context,
        )

        # Normalize IDs in bridge response
        sanitized_nodes, sanitized_edges = self._sanitize_and_chain_bridge(
            start_id=start_node.id,
            target_id=target_node.id,
            bridge_data=bridge_data,
        )

        # 3. Merge synthesized nodes and edges into graph
        self.graph_engine.merge_subgraph(
            intermediate_nodes=sanitized_nodes,
            connecting_edges=sanitized_edges,
            is_ground_truth=False,
        )

        # 4. Re-query graph for unified path
        found_after, unified_nodes, unified_edges = self.graph_engine.find_path(start_node.id, target_node.id)
        if not found_after:
            # Fallback direct construction in case of graph traversal edge anomaly
            all_node_dict = {n.id: n for n in [start_node] + [self.graph_engine.get_node(n.id) for n in sanitized_nodes if self.graph_engine.get_node(n.id)] + [target_node]}
            unified_nodes = [all_node_dict[k] for k in all_node_dict if all_node_dict[k] is not None]
            unified_edges = [
                SkillEdge(source=e.source, target=e.target, relation=e.relation, is_ground_truth=False)
                for e in sanitized_edges
            ]

        synth_count = sum(1 for n in unified_nodes if not n.is_ground_truth)
        logger.info(f"Pathway synthesized successfully: {len(unified_nodes)} nodes ({synth_count} AI-bridged)")

        return PathResponse(
            found=True,
            path_type="DIRECTED_SYNTHESIZED",
            start_skill=start_node,
            target_skill=target_node,
            nodes=unified_nodes,
            edges=unified_edges,
            total_steps=len(unified_nodes),
            synthesized_count=synth_count,
            message="Pathway synthesized via AI Bridge Engine and merged into knowledge graph.",
        )

    # -------------------------------------------------------------------------
    # Feature B: "Infinite Craft Discovery" (Frontier Expansion)
    # -------------------------------------------------------------------------
    def expand_frontier(
        self,
        skill_id: str,
        count: int = 3,
        direction: str = "both",
        domain_context: Optional[str] = None,
        bypass_cache: bool = False,
    ) -> ExpansionResponse:
        """
        Fast-Model Triage Frontier Expansion:
        Rule 1: The "Infinite Craft" Caching Layer (Critical)
                Checks the Graph Database first. If the node has existing outgoing edges,
                returns cached neighbors immediately and exits (0 LLM tokens).
                If leaf node (0 outgoing edges), proceeds to LLM.
        Rule 2: Strict LLM API constraints (max_tokens=250, temperature=0.3, JSON mode).
        Rule 3: Context Injection Limit (3-5 immediate parent nodes formatted tightly).
        Database Write: Merges new nodes/edges immediately so subsequent clicks hit cache.
        """
        node = self.graph_engine.get_node(skill_id)
        if not node:
            clean_id = slugify(skill_id)
            self.graph_engine.merge_subgraph(
                [IntermediateNode(id=clean_id, label=skill_id.replace("-", " ").title(), category="User Input", description="Frontier node")],
                [],
                is_ground_truth=False,
            )
            node = self.graph_engine.get_node(clean_id)

        # ---------------------------------------------------------------------
        # 1. The "Infinite Craft" Caching Layer (Critical)
        # ---------------------------------------------------------------------
        if not bypass_cache:
            cached_result = self.graph_engine.get_cached_expansion(
                node.id, direction=direction, limit=max(count, 3) * 2
            )
            if cached_result is not None:
                cached_nodes, cached_edges = cached_result
                cached_ctx = domain_context or self.graph_engine.get_immediate_parents_context(node.id)
                logger.info(
                    f"Cache Hit for '{node.label}' (id: '{node.id}'): "
                    f"Returning {len(cached_nodes)} cached neighbors immediately (0 LLM tokens used)."
                )
                return ExpansionResponse(
                    source_node=node,
                    new_nodes=cached_nodes,
                    linked_existing_nodes=[],
                    new_edges=cached_edges,
                    total_neighbors_now=len(cached_nodes),
                    domain_context=cached_ctx,
                    cached=True,
                    message=f"Cache Hit: Retrieved {len(cached_nodes)} existing skills from graph database (0 tokens).",
                )

        # ---------------------------------------------------------------------
        # 2. Leaf Node Detected (0 outgoing edges) -> Proceed to LLM
        # Rule 3: Context Injection Limit (3-5 immediate parent nodes only)
        # ---------------------------------------------------------------------
        graph_neighborhood = domain_context or self.graph_engine.get_immediate_parents_context(node.id)
        logger.info(f"Leaf node expansion for '{node.label}': {graph_neighborhood}")

        # ---------------------------------------------------------------------
        # 3. Rule 2: Strict LLM API Call with sub-second / token constraints
        # ---------------------------------------------------------------------
        expansion_data = self._synthesize_expansion_llm(
            node=node,
            graph_neighborhood=graph_neighborhood,
            count=count,
            direction=direction,
        )

        new_nodes: List[IntermediateNode] = []
        linked_existing_nodes: List[SkillNode] = []
        final_edges: List[ConnectingEdge] = []

        # Process generated nodes & link with existing graph concepts
        for item in expansion_data.intermediate_nodes:
            existing_match_id = self.graph_engine.find_close_existing_skill(
                item.label, threshold=settings.FUZZY_MATCH_THRESHOLD
            )
            if existing_match_id and existing_match_id != node.id:
                # Link to existing node
                matched_node = self.graph_engine.get_node(existing_match_id)
                if matched_node:
                    linked_existing_nodes.append(matched_node)
                    # Use existing node id
                    item.id = existing_match_id
            else:
                item.id = slugify(item.id or item.label)
                new_nodes.append(item)

        # Build connecting edges
        for edge in expansion_data.connecting_edges:
            src = slugify(edge.source)
            tgt = slugify(edge.target)
            final_edges.append(ConnectingEdge(source=src, target=tgt, relation=edge.relation))

        # Ensure at least one edge connects source node to the new/linked nodes
        if not final_edges:
            for item in (new_nodes + [IntermediateNode(id=n.id, label=n.label, category=n.category) for n in linked_existing_nodes]):
                final_edges.append(ConnectingEdge(source=node.id, target=item.id, relation="UNLOCKS"))

        # ---------------------------------------------------------------------
        # 4. Immediate Write to Graph Database: write back so subsequent clicks hit cache
        # ---------------------------------------------------------------------
        merged_nodes, merged_edges = self.graph_engine.merge_subgraph(
            intermediate_nodes=new_nodes,
            connecting_edges=final_edges,
            is_ground_truth=False,
        )

        updated_neighbors = self.graph_engine.get_neighbors(node.id)
        total_now = updated_neighbors.total_neighbors if updated_neighbors else 0

        return ExpansionResponse(
            source_node=node,
            new_nodes=merged_nodes,
            linked_existing_nodes=linked_existing_nodes,
            new_edges=merged_edges,
            total_neighbors_now=total_now,
            domain_context=graph_neighborhood,
            cached=False,
            message=f"Discovered {len(merged_nodes)} new concepts and linked {len(linked_existing_nodes)} existing nodes in {graph_neighborhood}.",
        )

    # -------------------------------------------------------------------------
    # Internal LLM Calls & Fallbacks
    # -------------------------------------------------------------------------
    def _synthesize_bridge_llm(
        self,
        start_node: SkillNode,
        target_node: SkillNode,
        start_context: List[str],
        target_context: List[str],
    ) -> BridgeResponse:
        """Calls OpenAI or falls back to smart procedural synthesis."""
        client = self.client
        if client:
            prompt = (
                f"Synthesize a step-by-step transitional learning path from:\n"
                f"START SKILL: '{start_node.label}' (id: '{start_node.id}')\n"
                f"Start Domain Context: {', '.join(start_context) or 'Fundamental Skills'}\n\n"
                f"to:\n"
                f"TARGET SKILL: '{target_node.label}' (id: '{target_node.id}')\n"
                f"Target Domain Context: {', '.join(target_context) or 'Specialized Skills'}\n\n"
                f"Create 2 to 4 intermediate stepping-stone skills with strictly valid JSON schema."
            )
            try:
                response = client.chat.completions.create(
                    model=settings.LLM_MODEL,
                    temperature=settings.LLM_TEMPERATURE,
                    max_tokens=settings.LLM_MAX_TOKENS,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT_BRIDGE},
                        {"role": "user", "content": prompt},
                    ],
                )
                raw_json = response.choices[0].message.content
                data = json.loads(raw_json)
                return BridgeResponse.model_validate(data)
            except Exception as e:
                logger.warning(f"LLM Bridge call failed ({e}). Falling back to algorithmic synthesis.")

        return self._algorithmic_fallback_bridge(start_node, target_node)

    def _synthesize_expansion_llm(
        self,
        node: SkillNode,
        graph_neighborhood: str,
        count: int,
        direction: str,
    ) -> BridgeResponse:
        """
        Fast-Model Triage LLM expansion:
        Rule 2 Constraints:
          - max_tokens: 250 (prevents token bloat, sub-second responses)
          - temperature: 0.3 (deterministic, logical graph edges)
          - JSON mode: response_format={"type": "json_object"}
        Rule 3:
          - Uses tightly bounded graph neighborhood context (Domain Context: [Parent1, Parent2, ...])
        Resilience:
          - Full try/catch block handling malformed JSON, schema validation, and API exceptions.
        """
        client = self.client
        if client:
            prompt = (
                f"Expand the skill: '{node.label}'.\n"
                f"The broader domain context of this skill is: {graph_neighborhood}.\n"
                f"Based strictly on this context, generate 3 prerequisite skills and 3 unlockable skills."
            )
            try:
                response = client.chat.completions.create(
                    model=settings.LLM_MODEL,
                    temperature=settings.LLM_TEMPERATURE,
                    max_tokens=settings.LLM_MAX_TOKENS,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT_EXPAND},
                        {"role": "user", "content": prompt},
                    ],
                )
                raw_json = response.choices[0].message.content
                if not raw_json or not raw_json.strip():
                    raise ValueError("Empty response received from LLM")
                data = json.loads(raw_json)
                return BridgeResponse.model_validate(data)
            except (json.JSONDecodeError, ValidationError, Exception) as e:
                logger.warning(
                    f"LLM Frontier Expansion call failed or produced malformed JSON ({type(e).__name__}: {e}). "
                    f"Falling back safely to context-aware algorithmic synthesis."
                )

        return self._algorithmic_fallback_expand(node, graph_neighborhood, count)

    def _sanitize_and_chain_bridge(
        self,
        start_id: str,
        target_id: str,
        bridge_data: BridgeResponse,
    ) -> Tuple[List[IntermediateNode], List[ConnectingEdge]]:
        """
        Ensures intermediate node IDs are slugified and guarantees
        a complete directed chain from start_id -> intermediate_nodes -> target_id.
        """
        nodes = bridge_data.intermediate_nodes
        for n in nodes:
            n.id = slugify(n.id or n.label)

        # Filter out nodes matching start or target
        nodes = [n for n in nodes if n.id not in (start_id, target_id)]

        # If no intermediate nodes were generated, create at least one transitional node
        if not nodes:
            fallback_label = f"Applied {start_id.replace('-', ' ').title()} in {target_id.replace('-', ' ').title()}"
            fallback_id = slugify(fallback_label)
            nodes.append(
                IntermediateNode(
                    id=fallback_id,
                    label=fallback_label,
                    category="Transitional Skill",
                    description="Bridge bridging foundational concept to target objective.",
                )
            )

        # Build chain: start -> node[0] -> node[1] -> ... -> target
        edges: List[ConnectingEdge] = []
        ordered_chain = [start_id] + [n.id for n in nodes] + [target_id]

        for i in range(len(ordered_chain) - 1):
            edges.append(
                ConnectingEdge(
                    source=ordered_chain[i],
                    target=ordered_chain[i + 1],
                    relation="REQUIRES",
                )
            )

        return nodes, edges

    def _algorithmic_fallback_bridge(self, start_node: SkillNode, target_node: SkillNode) -> BridgeResponse:
        """
        Intelligent offline synthesizer for hackathon demo resilience when LLM keys are unset.
        Generates 2 logically sound stepping-stone skills bridging start to target.
        """
        s_title = start_node.label.strip().title()
        t_title = target_node.label.strip().title()

        step1_label = f"Intermediate {s_title} & Architecture"
        step1_id = slugify(step1_label)

        step2_label = f"Applied Integration for {t_title}"
        step2_id = slugify(step2_label)

        nodes = [
            IntermediateNode(
                id=step1_id,
                label=step1_label,
                category="Intermediate Foundations",
                description=f"Deepening core proficiency in {s_title} with modern architectural patterns.",
            ),
            IntermediateNode(
                id=step2_id,
                label=step2_label,
                category="Applied Integration",
                description=f"Synthesizing intermediate skills into real-world pipelines for {t_title}.",
            ),
        ]

        edges = [
            ConnectingEdge(source=start_node.id, target=step1_id, relation="REQUIRES"),
            ConnectingEdge(source=step1_id, target=step2_id, relation="REQUIRES"),
            ConnectingEdge(source=step2_id, target=target_node.id, relation="REQUIRES"),
        ]

        return BridgeResponse(intermediate_nodes=nodes, connecting_edges=edges)

    def _algorithmic_fallback_expand(
        self,
        node: SkillNode,
        graph_neighborhood: str,
        count: int,
    ) -> BridgeResponse:
        """
        Domain-aligned fallback expansion for frontier discovery.
        Strictly inspects graph_neighborhood and target label to eliminate corporate/tech hallucination.
        Generates 3 prerequisites and 3 unlockables conforming to the prompt specification.
        """
        title = node.label.strip().title()
        ctx_lower = (graph_neighborhood + " " + node.label).lower()

        nodes: List[IntermediateNode] = []
        edges: List[ConnectingEdge] = []

        # 1. Language / Spoken Communication Domain
        if any(w in ctx_lower for w in ["language", "spoken", "speak", "italian", "french", "spanish", "german", "japanese", "chinese", "linguist", "accent", "grammar", "vocabulary", "english"]):
            cat_prereq = "Language Foundations"
            cat_unlock = "Fluency & Expression"
            prereqs = [
                (f"Basic {title} Vocabulary & Phonics", cat_prereq, f"Core vocabulary words and essential phonetic pronunciation in {title}."),
                (f"{title} Grammar & Sentence Construction", cat_prereq, f"Fundamental sentence patterns, verb conjugations, and syntax in {title}."),
                (f"Listening & Reading Comprehension in {title}", cat_prereq, f"Understanding spoken dialogues and everyday written texts in {title}."),
            ]
            unlocks = [
                (f"Conversational Fluency in {title}", cat_unlock, f"Speaking spontaneously and comfortably in casual and professional {title} discussions."),
                (f"Reading Literature & Media in {title}", cat_unlock, f"Enjoying native-level cultural media, books, and articles in {title}."),
                (f"Advanced Idiomatic Nuance in {title}", cat_unlock, f"Mastering dialect subtleties, cultural idioms, and natural colloquial speech in {title}."),
            ]

        # 2. Culinary / Food / Cooking Domain
        elif any(w in ctx_lower for w in ["cook", "culinary", "food", "baking", "pastry", "cuisine", "recipe", "wine", "knife", "dish", "ingredient"]):
            cat_prereq = "Culinary Foundations"
            cat_unlock = "Gastronomy & Plating"
            prereqs = [
                (f"Knife Skills & Mise en Place for {title}", cat_prereq, f"Precision knife work and proper preparation of ingredients for {title}."),
                (f"Flavor Profiling & Seasoning in {title}", cat_prereq, f"Balancing acidity, salt, fat, and heat in traditional {title} dishes."),
                (f"Fundamental Cooking Techniques for {title}", cat_prereq, f"Mastering simmering, roasting, and sautéing methods essential to {title}."),
            ]
            unlocks = [
                (f"Authentic Regional Specialties in {title}", cat_unlock, f"Recreating iconic heritage and regional variations of {title}."),
                (f"Menu Design & Plating Aesthetics in {title}", cat_unlock, f"Composing elevated multi-course dining experiences with {title}."),
                (f"Culinary Artistry & Innovation in {title}", cat_unlock, f"Modern interpretations and creative reinvention of classic {title}."),
            ]

        # 3. Arts / Music / Craft / Sports / Physical Disciplines
        elif any(w in ctx_lower for w in ["paint", "art", "draw", "sing", "music", "sport", "sculpt", "dance", "wrestl", "martial", "chess", "sew", "knit", "wood"]):
            cat_prereq = "Artistic Foundations"
            cat_unlock = "Performance & Mastery"
            prereqs = [
                (f"Foundational {title} Techniques", cat_prereq, f"Essential mechanics, posture, and core physical handling for {title}."),
                (f"Core Principles & Form in {title}", cat_prereq, f"Understanding the fundamental rules, balance, and aesthetics of {title}."),
                (f"Daily Practice Drills for {title}", cat_prereq, f"Muscle memory drills and foundational conditioning for {title}."),
            ]
            unlocks = [
                (f"Creative Expression & Style in {title}", cat_unlock, f"Developing a distinctive personal touch and interpretative nuance in {title}."),
                (f"Complex Repertoire in {title}", cat_unlock, f"Tackling advanced compositions, challenging pieces, and competitive scenarios in {title}."),
                (f"Mastery & Performance in {title}", cat_unlock, f"Peak technical execution, exhibition, and artistic leadership in {title}."),
            ]

        # 4. Technical / Software / Engineering Domain
        elif any(w in ctx_lower for w in ["coding", "software", "python", "data", "engineer", "algorithm", "robotics", "dev", "systems", "cloud", "security", "ai"]):
            cat_prereq = "Technical Foundations"
            cat_unlock = "Advanced Engineering"
            prereqs = [
                (f"Core Principles of {title}", cat_prereq, f"Fundamental computational models and concepts underlying {title}."),
                (f"Syntax & Tooling Setup for {title}", cat_prereq, f"Environment configuration, CLI tools, and basic syntax for {title}."),
                (f"Algorithm Design & Problem Solving in {title}", cat_prereq, f"Writing robust logical solutions and foundational algorithms in {title}."),
            ]
            unlocks = [
                (f"Architectural Patterns in {title}", cat_unlock, f"Designing modular, scalable, and maintainable software systems with {title}."),
                (f"Performance Optimization in {title}", cat_unlock, f"Profiling, benchmarking, and optimizing efficiency in {title}."),
                (f"Production Deployment of {title}", cat_unlock, f"Reliable delivery, CI/CD, and monitoring for production-ready {title}."),
            ]

        # 5. General Life Skills / Trades / Hands-on Practices
        else:
            cat_prereq = "Core Foundations"
            cat_unlock = "Practical Mastery"
            prereqs = [
                (f"Safety & Tool Fundamentals for {title}", cat_prereq, f"Essential equipment, safety protocols, and preparation for {title}."),
                (f"Core Practical Techniques in {title}", cat_prereq, f"Hands-on execution of everyday essential methods in {title}."),
                (f"Troubleshooting & Basic Assessment in {title}", cat_prereq, f"Diagnosing issues and verifying quality in {title}."),
            ]
            unlocks = [
                (f"Independent Project Execution in {title}", cat_unlock, f"Managing and executing comprehensive projects from start to finish in {title}."),
                (f"Advanced Problem Solving in {title}", cat_unlock, f"Handling complex, non-standard challenges and custom tasks in {title}."),
                (f"Master Artisan Execution in {title}", cat_unlock, f"Refined craftsmanship, precision, and mentorship in {title}."),
            ]

        # Build prerequisites: prereq -> target (relation: REQUIRES)
        for label, cat, desc in prereqs[:count]:
            nid = slugify(label)
            nodes.append(IntermediateNode(id=nid, label=label, category=cat, description=desc))
            edges.append(ConnectingEdge(source=nid, target=node.id, relation="REQUIRES"))

        # Build unlocks: target -> unlock (relation: UNLOCKS)
        for label, cat, desc in unlocks[:count]:
            nid = slugify(label)
            nodes.append(IntermediateNode(id=nid, label=label, category=cat, description=desc))
            edges.append(ConnectingEdge(source=node.id, target=nid, relation="UNLOCKS"))

        return BridgeResponse(intermediate_nodes=nodes, connecting_edges=edges)

    # -------------------------------------------------------------------------
    # Feature D: "Node Synthesis" (Many-to-1 Merging)
    # -------------------------------------------------------------------------
    def synthesize_skills(self, source_1: str, source_2: str) -> SynthesizeSkillsResponse:
        """
        Synthesizes two distinct nodes into an emergent, hybrid concept (Many-to-1).
        1. Resolves source nodes A and B (auto-instantiates if missing).
        2. Caching Layer Check: Query if there is already a node that shares incoming
           REQUIRES edges from BOTH source_1 and source_2. If exists, returns it instantly.
        3. If not in cache, invokes LLM with SYSTEM_PROMPT_SYNTHESIZE.
        4. Writes new synthesized Node C and the two directed edges (A -> C and B -> C)
           into the graph database so subsequent syntheses hit the cache.
        """
        node_1 = self.graph_engine.get_node(source_1)
        if not node_1:
            clean_1 = slugify(source_1)
            self.graph_engine.merge_subgraph(
                [IntermediateNode(id=clean_1, label=source_1.replace("-", " ").title(), category="User Input")],
                [],
                is_ground_truth=False,
            )
            node_1 = self.graph_engine.get_node(clean_1)

        node_2 = self.graph_engine.get_node(source_2)
        if not node_2:
            clean_2 = slugify(source_2)
            self.graph_engine.merge_subgraph(
                [IntermediateNode(id=clean_2, label=source_2.replace("-", " ").title(), category="User Input")],
                [],
                is_ground_truth=False,
            )
            node_2 = self.graph_engine.get_node(clean_2)

        # ---------------------------------------------------------------------
        # 1. Caching Layer Check
        # Query if there is already a node that shares incoming edges from BOTH
        # ---------------------------------------------------------------------
        shared_successor = self.graph_engine.find_shared_successor(node_1.id, node_2.id)
        if shared_successor:
            logger.info(
                f"Synthesis Cache Hit for '{node_1.label}' + '{node_2.label}': "
                f"Returning existing emergent concept '{shared_successor.label}' (0 tokens)."
            )
            cached_edges = [
                SkillEdge(source=node_1.id, target=shared_successor.id, relation="REQUIRES", is_ground_truth=shared_successor.is_ground_truth),
                SkillEdge(source=node_2.id, target=shared_successor.id, relation="REQUIRES", is_ground_truth=shared_successor.is_ground_truth),
            ]
            return SynthesizeSkillsResponse(
                synthesized_node=shared_successor,
                source_node_1=node_1,
                source_node_2=node_2,
                edges=cached_edges,
                cached=True,
                message=f"Retrieved existing hybrid '{shared_successor.label}' from graph cache (0 tokens).",
            )

        # ---------------------------------------------------------------------
        # 2. LLM Bridge Engine Synthesis Call
        # ---------------------------------------------------------------------
        logger.info(f"Synthesizing emergent concept for '{node_1.label}' + '{node_2.label}' via LLM...")
        synth_data = self._synthesize_hybrid_llm(node_1, node_2)

        synth_id = slugify(synth_data.id or synth_data.label)
        if synth_id in (node_1.id, node_2.id):
            synth_id = f"{synth_id}-hybrid"

        # ---------------------------------------------------------------------
        # 3. Graph Database Solidification: Write Node C & Edges (A -> C, B -> C)
        # ---------------------------------------------------------------------
        synth_node_item = IntermediateNode(
            id=synth_id,
            label=synth_data.label,
            category=f"Hybrid ({node_1.label} × {node_2.label})",
            description=synth_data.description or f"Emergent synthesis combining {node_1.label} and {node_2.label}.",
        )
        connecting_edges = [
            ConnectingEdge(source=node_1.id, target=synth_id, relation="REQUIRES"),
            ConnectingEdge(source=node_2.id, target=synth_id, relation="REQUIRES"),
        ]

        merged_nodes, merged_edges = self.graph_engine.merge_subgraph(
            intermediate_nodes=[synth_node_item],
            connecting_edges=connecting_edges,
            is_ground_truth=False,
        )

        synthesized_node = self.graph_engine.get_node(synth_id) or merged_nodes[0]

        return SynthesizeSkillsResponse(
            synthesized_node=synthesized_node,
            source_node_1=node_1,
            source_node_2=node_2,
            edges=merged_edges,
            cached=False,
            message=f"Discovered emergent concept: '{synthesized_node.label}'.",
        )

    def _synthesize_hybrid_llm(self, node_1: SkillNode, node_2: SkillNode) -> LLMSynthesizedNode:
        """
        Calls LLM to synthesize two concepts with SYSTEM_PROMPT_SYNTHESIZE and user prompt:
        "Synthesize these two concepts: '{source_node_1}' + '{source_node_2}'."
        """
        client = self.client
        if client:
            user_prompt = f"Synthesize these two concepts: '{node_1.label}' + '{node_2.label}'."
            try:
                response = client.chat.completions.create(
                    model=settings.LLM_MODEL,
                    temperature=settings.LLM_TEMPERATURE,
                    max_tokens=settings.LLM_MAX_TOKENS,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT_SYNTHESIZE},
                        {"role": "user", "content": user_prompt},
                    ],
                )
                raw_json = response.choices[0].message.content
                if not raw_json or not raw_json.strip():
                    raise ValueError("Empty response received from LLM")
                data = json.loads(raw_json)
                parsed = LLMSynthesisResponse.model_validate(data)
                return parsed.synthesized_node
            except (json.JSONDecodeError, ValidationError, Exception) as e:
                logger.warning(
                    f"LLM Synthesis call failed ({type(e).__name__}: {e}). "
                    f"Using algorithmic hybrid fallback."
                )

        return self._algorithmic_fallback_synthesis(node_1, node_2)

    def _algorithmic_fallback_synthesis(self, node_1: SkillNode, node_2: SkillNode) -> LLMSynthesizedNode:
        """
        Procedural heuristic fallback for emergent concept synthesis.
        Finds true semantic intersections for common pairings.
        """
        l1 = node_1.label.lower()
        l2 = node_2.label.lower()
        pair = {l1, l2}

        # Knowledge intersection table
        if any("paint" in x or "art" in x for x in pair) and any("code" in x or "program" in x or "python" in x for x in pair):
            return LLMSynthesizedNode(id="creative-coding", label="Creative Coding", description="The intersection of fine visual arts and algorithmic programming.")
        if any("bio" in x for x in pair) and any("data" in x or "code" in x or "python" in x for x in pair):
            return LLMSynthesizedNode(id="bioinformatics", label="Bioinformatics", description="Computational modeling and data analysis for biological systems.")
        if any("music" in x or "sing" in x for x in pair) and any("code" in x or "tech" in x for x in pair):
            return LLMSynthesizedNode(id="audio-engineering", label="Audio Engineering", description="Technical sound design, digital signal processing, and audio synthesis.")
        if any("robot" in x for x in pair) and any("art" in x or "craft" in x or "origami" in x for x in pair):
            return LLMSynthesizedNode(id="kinetic-sculpture", label="Kinetic Sculpture", description="Mechanical movement integrated into physical expressive art.")
        if any("language" in x or "italian" in x for x in pair) and any("code" in x or "ai" in x for x in pair):
            return LLMSynthesizedNode(id="computational-linguistics", label="Computational Linguistics", description="Natural language processing and semantic language modeling.")

        # Default clean synthesis
        t1 = node_1.label.strip().title()
        t2 = node_2.label.strip().title()
        hybrid_label = f"{t1} & {t2} Integration"
        return LLMSynthesizedNode(
            id=slugify(hybrid_label),
            label=hybrid_label,
            description=f"Emergent discipline combining {t1} principles with practical {t2} methodology.",
        )

    # -------------------------------------------------------------------------
    # Feature D: Multi-Skill Discovery (Suggest Next Steps from Current Skills)
    # -------------------------------------------------------------------------
    def suggest_next_steps(
        self,
        skill_ids: List[str],
        count: int = 3,
        domain_context: Optional[str] = None,
    ) -> SuggestNextStepsResponse:
        """
        Analyzes a set of skills the learner currently possesses and suggests
        logical next-step skills or emergent competencies that can be unlocked
        or synthesized from them.
        """
        if not skill_ids:
            return SuggestNextStepsResponse(source_skills=[], message="No skill IDs provided.")

        # 1. Resolve source skills from graph
        source_skills: List[SkillNode] = []
        source_id_map: Dict[str, SkillNode] = {}

        for sid in skill_ids:
            clean_id = slugify(sid)
            node = self.graph_engine.get_node(clean_id) or self.graph_engine.get_node(sid)
            if not node:
                fuzzy = self.graph_engine.fuzzy_match_node(sid, threshold=75)
                if fuzzy:
                    node = self.graph_engine.get_node(fuzzy)
            if not node:
                node = SkillNode(
                    id=clean_id,
                    label=sid.strip().title(),
                    category="Current Skill",
                    is_ground_truth=False,
                )
            if node.id not in source_id_map:
                source_skills.append(node)
                source_id_map[node.id] = node
                source_id_map[node.label.lower()] = node

        if not source_skills:
            return SuggestNextStepsResponse(source_skills=[], message="Could not resolve current skills.")

        # 2. Call LLM or Algorithmic Fallback to discover multi-skill next steps
        logger.info(
            f"Suggesting next steps for {len(source_skills)} current skills: "
            f"{[s.label for s in source_skills]}"
        )
        llm_response = self._suggest_multi_skill_llm(
            source_skills=source_skills,
            count=count,
            domain_context=domain_context,
        )

        intermediate_nodes: List[IntermediateNode] = []
        connecting_edges: List[ConnectingEdge] = []
        current_ids = set(s.id for s in source_skills)

        for item in llm_response.suggested_skills:
            item_id = slugify(item.id or item.label)
            if item_id in current_ids:
                continue

            node_item = IntermediateNode(
                id=item_id,
                label=item.label.strip(),
                category=item.category or "Emergent Skill",
                description=item.description or "Emergent skill building upon current competencies.",
            )
            intermediate_nodes.append(node_item)

            # Determine which input skills this suggestion connects to
            matched_sources: List[SkillNode] = []
            for req in item.required_input_skills:
                clean_req = slugify(req)
                for s in source_skills:
                    if s.id == clean_req or clean_req in s.id or req.lower() in s.label.lower():
                        if s not in matched_sources:
                            matched_sources.append(s)

            # Fallback: connect from all source skills if <= 2, or first 2 if none matched
            if not matched_sources:
                matched_sources = source_skills[:min(2, len(source_skills))]

            for src in matched_sources:
                connecting_edges.append(
                    ConnectingEdge(
                        source=src.id,
                        target=item_id,
                        relation="REQUIRES",
                    )
                )

        # 3. Write into graph engine
        merged_nodes, merged_edges = self.graph_engine.merge_subgraph(
            intermediate_nodes=intermediate_nodes,
            connecting_edges=connecting_edges,
            is_ground_truth=False,
        )

        return SuggestNextStepsResponse(
            source_skills=source_skills,
            new_nodes=merged_nodes,
            new_edges=merged_edges,
            cached=False,
            message=f"Suggested {len(merged_nodes)} potential next steps from your current skills.",
        )

    def _suggest_multi_skill_llm(
        self,
        source_skills: List[SkillNode],
        count: int,
        domain_context: Optional[str] = None,
    ) -> LLMMultiSkillResponse:
        """Calls OpenAI with structured output or falls back to procedural heuristic synthesis."""
        client = self.client
        if client:
            skills_bullets = "\n".join([f"- {s.label} (domain: {s.category})" for s in source_skills])
            ctx_str = f"\nBroader Context: {domain_context}" if domain_context else ""
            user_prompt = (
                f"The learner currently possesses the following skills:\n{skills_bullets}{ctx_str}\n\n"
                f"Based on what they have at the moment, suggest {count} logical next-step or emergent skills they can unlock or make."
            )
            try:
                response = client.chat.completions.create(
                    model=settings.LLM_MODEL,
                    temperature=0.3,
                    max_tokens=400,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT_MULTI_SKILL_EXPAND},
                        {"role": "user", "content": user_prompt},
                    ],
                )
                raw_json = response.choices[0].message.content
                if raw_json and raw_json.strip():
                    data = json.loads(raw_json)
                    return LLMMultiSkillResponse.model_validate(data)
            except Exception as e:
                logger.warning(f"LLM Multi-skill expansion call failed ({e}). Using algorithmic fallback.")

        return self._algorithmic_fallback_multi_skill(source_skills, count)

    def _algorithmic_fallback_multi_skill(
        self,
        source_skills: List[SkillNode],
        count: int = 3,
    ) -> LLMMultiSkillResponse:
        """
        Procedural deterministic fallback for multi-skill next step discovery.
        Generates realistic emergent combinations based on current skills.
        """
        labels = [s.label for s in source_skills]
        ids = [s.id for s in source_skills]
        suggested: List[LLMSuggestedSkill] = []

        if len(source_skills) >= 2:
            s1, s2 = source_skills[0], source_skills[1]
            pair_synth = self._algorithmic_fallback_synthesis(s1, s2)
            suggested.append(
                LLMSuggestedSkill(
                    id=pair_synth.id,
                    label=pair_synth.label,
                    category="Emergent Specialization",
                    description=pair_synth.description or f"Synthesized competency combining {s1.label} and {s2.label}.",
                    required_input_skills=[s1.id, s2.id],
                )
            )

        if len(source_skills) >= 3:
            s2, s3 = source_skills[1], source_skills[2]
            pair_synth2 = self._algorithmic_fallback_synthesis(s2, s3)
            suggested.append(
                LLMSuggestedSkill(
                    id=pair_synth2.id,
                    label=pair_synth2.label,
                    category="Emergent Specialization",
                    description=pair_synth2.description or f"Synthesized competency combining {s2.label} and {s3.label}.",
                    required_input_skills=[s2.id, s3.id],
                )
            )

        first_title = source_skills[0].label.title()
        last_title = source_skills[-1].label.title()
        composite_label = f"Advanced {first_title} & {last_title} Practice"
        suggested.append(
            LLMSuggestedSkill(
                id=slugify(composite_label),
                label=composite_label,
                category="Mastery Pathway",
                description=f"Applied interdisciplinary mastery unifying {', '.join(labels[:3])}.",
                required_input_skills=ids[:2],
            )
        )

        for s in source_skills:
            if len(suggested) >= count:
                break
            try:
                nbrs = self.graph_engine.get_neighbors(s.id)
                if nbrs and nbrs.unlocked:
                    for unl in nbrs.unlocked:
                        if unl.node.id not in ids and all(x.id != unl.node.id for x in suggested):
                            suggested.append(
                                LLMSuggestedSkill(
                                    id=unl.node.id,
                                    label=unl.node.label,
                                    category=unl.node.category or "Advanced Unlock",
                                    description=unl.node.description or f"Direct advancement unlocked by {s.label}.",
                                    required_input_skills=[s.id],
                                )
                            )
                            if len(suggested) >= count:
                                break
            except Exception:
                pass

        return LLMMultiSkillResponse(suggested_skills=suggested[:count])


