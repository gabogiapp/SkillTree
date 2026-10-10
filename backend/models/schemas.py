from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

# --- LLM Intermediary Output Schema ---

class IntermediateNode(BaseModel):
    id: str = Field(
        ...,
        description="Slugified, lowercase identifier for the skill (e.g. 'rest-api-design')",
    )
    label: str = Field(
        ...,
        description="Human-readable title/label of the skill",
    )
    category: str = Field(
        default="General",
        description="Domain category (e.g., 'Backend Engineering', 'Robotics', 'Design')",
    )
    description: str = Field(
        default="",
        description="Brief concise summary of the skill and what it entails",
    )

class ConnectingEdge(BaseModel):
    source: str = Field(
        ...,
        description="Source node id",
    )
    target: str = Field(
        ...,
        description="Target node id",
    )
    relation: str = Field(
        default="REQUIRES",
        description="Relationship type: REQUIRES | UNLOCKS | SYNERGIZES_WITH",
    )

class BridgeResponse(BaseModel):
    intermediate_nodes: List[IntermediateNode] = Field(
        default_factory=list,
        description="List of synthesized intermediate stepping-stone skills",
    )
    connecting_edges: List[ConnectingEdge] = Field(
        default_factory=list,
        description="List of directed edges connecting the path from start to target",
    )

# --- Graph Engine & API Models ---

class SkillNode(BaseModel):
    id: str
    label: str
    category: str = "General"
    description: str = ""
    is_ground_truth: bool = True
    in_degree: int = 0
    out_degree: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)

class SkillEdge(BaseModel):
    source: str
    target: str
    relation: str = "REQUIRES"
    is_ground_truth: bool = True

class NeighborItem(BaseModel):
    node: SkillNode
    relation: str
    direction: str  # "incoming" or "outgoing"

class NeighborResponse(BaseModel):
    node: SkillNode
    prerequisites: List[NeighborItem] = Field(
        default_factory=list,
        description="Incoming connections (skills required before this skill)",
    )
    unlocked: List[NeighborItem] = Field(
        default_factory=list,
        description="Outgoing connections (skills unlocked or led to by this skill)",
    )
    total_neighbors: int = 0

class SearchResultItem(BaseModel):
    id: str
    label: str
    category: str = "General"
    is_ground_truth: bool = True
    in_degree: int = 0
    out_degree: int = 0
    similarity_score: float = 100.0

class SearchResponse(BaseModel):
    query: str
    total_matches: int
    results: List[SearchResultItem]

class PathResponse(BaseModel):
    found: bool
    path_type: str  # "DIRECTED_GROUND_TRUTH" | "DIRECTED_SYNTHESIZED" | "NONE"
    start_skill: Optional[SkillNode] = None
    target_skill: Optional[SkillNode] = None
    nodes: List[SkillNode] = Field(default_factory=list)
    edges: List[SkillEdge] = Field(default_factory=list)
    total_steps: int = 0
    synthesized_count: int = 0
    message: str = ""

class ExpansionResponse(BaseModel):
    source_node: SkillNode
    new_nodes: List[SkillNode] = Field(default_factory=list)
    linked_existing_nodes: List[SkillNode] = Field(default_factory=list)
    new_edges: List[SkillEdge] = Field(default_factory=list)
    total_neighbors_now: int = 0
    domain_context: Optional[str] = None
    cached: bool = Field(default=False, description="Whether this response was served from the in-memory graph cache")
    message: str = ""

class GraphStatsResponse(BaseModel):
    total_nodes: int
    total_edges: int
    ground_truth_nodes: int
    ai_generated_nodes: int
    density: float

# --- Request Payloads ---

class BridgeRequest(BaseModel):
    start_skill_id: str = Field(..., description="Starting skill id or label")
    target_skill_id: str = Field(..., description="Target / goal skill id or label")

class ExpandRequest(BaseModel):
    count: int = Field(default=3, ge=1, le=8, description="Number of skills to generate")
    direction: str = Field(default="both", description="Expansion direction: 'both', 'unlocks', 'requires'")
    domain_context: Optional[str] = Field(default=None, description="Optional explicit domain context")
    bypass_cache: bool = Field(default=False, description="Whether to bypass the in-memory graph cache")

class ExpandNodeRequest(BaseModel):
    node_id: Optional[str] = Field(default=None, description="Target node ID or label to expand")
    skill_id: Optional[str] = Field(default=None, description="Alias for node_id")
    count: int = Field(default=3, ge=1, le=8, description="Number of skills to generate")
    direction: str = Field(default="both", description="Expansion direction: 'both', 'unlocks', 'requires'")
    domain_context: Optional[str] = Field(default=None, description="Optional explicit domain context")
    bypass_cache: bool = Field(default=False, description="Whether to bypass the in-memory graph cache")


class ResumeUploadRequest(BaseModel):
    resume_text: Optional[str] = Field(default=None, description="Raw text of resume or job history")
    skills: Optional[List[str]] = Field(default=None, description="Explicit list of skills")

class ResumeUploadResponse(BaseModel):
    extracted_skills: List[str]
    matched_skills: List[SkillNode]
    unmatched_skills: List[str]
    recommended_goals: List[SkillNode]
    message: str = ""

class SubgraphResponse(BaseModel):
    nodes: List[SkillNode]
    edges: List[SkillEdge]
    total_nodes: int
    total_edges: int

class CustomSkillRequest(BaseModel):
    label: str = Field(..., min_length=1, description="Skill name or title")
    category: Optional[str] = Field(default="Custom Skill", description="Domain category")
    description: Optional[str] = Field(default="", description="Optional description")


# --- Node Synthesis (Merging) Schemas ---

class LLMSynthesizedNode(BaseModel):
    id: Optional[str] = None
    label: str
    description: Optional[str] = ""

class LLMSynthesisResponse(BaseModel):
    synthesized_node: LLMSynthesizedNode

class SynthesizeSkillsRequest(BaseModel):
    source_node_1: str = Field(..., description="First skill ID or label to synthesize")
    source_node_2: str = Field(..., description="Second skill ID or label to synthesize")

class SynthesizeSkillsResponse(BaseModel):
    synthesized_node: SkillNode
    source_node_1: SkillNode
    source_node_2: SkillNode
    edges: List[SkillEdge] = Field(default_factory=list)
    cached: bool = False
    message: str = ""


# --- Multi-Skill Discovery Schemas ---

class LLMSuggestedSkill(BaseModel):
    id: Optional[str] = None
    label: str
    category: Optional[str] = "Emergent Skill"
    description: Optional[str] = ""
    required_input_skills: List[str] = Field(
        default_factory=list,
        description="IDs or labels of the current skills that this suggested skill directly builds upon",
    )

class LLMMultiSkillResponse(BaseModel):
    suggested_skills: List[LLMSuggestedSkill] = Field(default_factory=list)

class SuggestNextStepsRequest(BaseModel):
    skill_ids: List[str] = Field(..., min_items=1, description="List of skill IDs currently possessed")
    count: int = Field(default=3, ge=1, le=8, description="Number of suggestions to generate")
    domain_context: Optional[str] = Field(default=None, description="Optional domain context")

class SuggestNextStepsResponse(BaseModel):
    source_skills: List[SkillNode]
    new_nodes: List[SkillNode] = Field(default_factory=list)
    new_edges: List[SkillEdge] = Field(default_factory=list)
    cached: bool = False
    message: str = ""



