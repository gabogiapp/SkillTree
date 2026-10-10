import csv
import logging
import re
import threading
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
import networkx as nx
from rapidfuzz import process, fuzz

from backend.config import settings
from backend.models.schemas import (
    SkillNode,
    SkillEdge,
    NeighborItem,
    NeighborResponse,
    SearchResultItem,
    SearchResponse,
    GraphStatsResponse,
    IntermediateNode,
    ConnectingEdge,
)

logger = logging.getLogger("graph_engine")
logging.basicConfig(level=logging.INFO)


def slugify(text: str) -> str:
    """
    Produce a clean, URL-safe slug from arbitrary string text.
    Handles accents, punctuation, and multiple whitespaces.
    Example: 'C++ & Python: Web Dev!' -> 'c-python-web-dev'
    """
    if not text:
        return ""
    # Normalize unicode characters
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    # Replace special symbols with words/separators
    text = text.replace("+", "-plus-").replace("&", "-and-")
    # Replace non-alphanumeric characters with hyphens
    text = re.sub(r"[^\w\s-]", "-", text).strip().lower()
    # Replace whitespace and repeated hyphens with a single hyphen
    text = re.sub(r"[-\s]+", "-", text).strip("-")
    return text or "skill-node"


class GraphEngine:
    """
    In-Memory Directed Graph Engine powered by NetworkX.
    Loads deterministic ground-truth relationships from multiple CSV datasets
    and manages dynamic graph expansion, pathfinding, and fast semantic fuzzy search.
    """

    def __init__(self, csv_path: Optional[Union[Path, List[Path]]] = None):
        if isinstance(csv_path, list):
            self.csv_paths = [Path(p) for p in csv_path]
        elif csv_path:
            self.csv_paths = [Path(csv_path)]
        else:
            configured = getattr(settings, "CSV_PATHS", None)
            self.csv_paths = [Path(p) for p in configured] if configured else [settings.CSV_PATH]

        self.csv_path = self.csv_paths[0] if self.csv_paths else settings.CSV_PATH
        self.graph = nx.DiGraph()
        self._lock = threading.RLock()


        # Lookup caches for high-speed retrieval
        # map lowercase label or slug -> node_id
        self._label_to_id: Dict[str, str] = {}
        # list of (searchable_string, node_id) for rapidfuzz matching
        self._search_keys: List[str] = []
        self._search_key_to_id: Dict[str, str] = {}

    def load_ground_truth(self, paths: Optional[List[Path]] = None) -> int:
        """
        Reads all configured CSV datasets and merges them into the unified
        in-memory directed graph.
        Supports both life/craft skills (skills_parent_child_10000.csv) and
        professional taxonomy (pure_skill_to_skill_edges.csv).
        Returns total number of edges loaded.
        """
        target_paths = paths or self.csv_paths
        if isinstance(target_paths, (str, Path)):
            target_paths = [Path(target_paths)]

        total_edges = 0
        nodes_loaded = 0

        with self._lock:
            self.graph.clear()
            self._label_to_id.clear()
            self._search_keys.clear()
            self._search_key_to_id.clear()

            for p in target_paths:
                path_obj = Path(p)
                if not path_obj.exists():
                    logger.warning(f"CSV file not found at {path_obj}. Skipping.")
                    continue

                logger.info(f"Loading ground-truth skill graph from {path_obj.name}...")
                file_edges = 0
                is_esco = "pure_skill" in path_obj.name.lower()

                with open(path_obj, mode="r", encoding="utf-8", errors="replace") as f:
                    reader = csv.DictReader(f)
                    
                    # Normalize field names flexibly
                    headers = [h.strip() for h in (reader.fieldnames or [])]
                    headers_lower = [h.lower() for h in headers]

                    parent_label_col = None
                    for cand in ["parent", "parent_label", "source", "source_label"]:
                        if cand in headers_lower:
                            parent_label_col = headers[headers_lower.index(cand)]
                            break
                    if not parent_label_col and headers:
                        parent_label_col = headers[0]

                    child_label_col = None
                    for cand in ["child", "child_label", "target", "target_label"]:
                        if cand in headers_lower:
                            child_label_col = headers[headers_lower.index(cand)]
                            break
                    if not child_label_col and len(headers) > 1:
                        child_label_col = headers[1]
                    elif not child_label_col:
                        child_label_col = headers[0]

                    relation_col = None
                    for cand in ["relation_type", "relation", "type"]:
                        if cand in headers_lower:
                            relation_col = headers[headers_lower.index(cand)]
                            break

                    parent_id_col = "parent_id" if "parent_id" in headers_lower else None
                    child_id_col = "child_id" if "child_id" in headers_lower else None

                    for row in reader:
                        p_raw = row.get(parent_label_col, "").strip()
                        c_raw = row.get(child_label_col, "").strip()
                        if not p_raw or not c_raw:
                            continue

                        rel = row.get(relation_col, "UNLOCKS").strip() if relation_col else "UNLOCKS"
                        p_id = slugify(p_raw)
                        c_id = slugify(c_raw)

                        # Ensure parent node
                        if not self.graph.has_node(p_id):
                            p_cat = "Core Domain" if not is_esco else "Professional Taxonomy"
                            self.graph.add_node(
                                p_id,
                                label=p_raw,
                                category=p_cat,
                                description=f"Deterministic skill: {p_raw}",
                                is_ground_truth=True,
                                esco_id=row.get(parent_id_col, "") if parent_id_col else "",
                            )
                            self._index_node(p_id, p_raw)
                            nodes_loaded += 1

                        # Ensure child node
                        if not self.graph.has_node(c_id):
                            c_cat = f"{p_raw.title()} Specialization" if not is_esco else "Professional Skill"
                            self.graph.add_node(
                                c_id,
                                label=c_raw,
                                category=c_cat,
                                description=f"Specialized skill in {p_raw}: {c_raw}",
                                is_ground_truth=True,
                                esco_id=row.get(child_id_col, "") if child_id_col else "",
                            )
                            self._index_node(c_id, c_raw)
                            nodes_loaded += 1

                        # Add directed edge: parent -> child
                        if not self.graph.has_edge(p_id, c_id):
                            self.graph.add_edge(
                                p_id,
                                c_id,
                                relation=rel,
                                is_ground_truth=True,
                            )
                            file_edges += 1

                logger.info(f"Loaded {file_edges} edges from {path_obj.name}.")
                total_edges += file_edges

            logger.info(
                f"Unified multi-dataset graph initialized: "
                f"{self.graph.number_of_nodes()} unique nodes, "
                f"{self.graph.number_of_edges()} edges loaded."
            )
            return total_edges

    def _index_node(self, node_id: str, label: str):

        """Register a node in fast search indexes."""
        low_label = label.lower().strip()
        self._label_to_id[low_label] = node_id
        self._label_to_id[node_id] = node_id
        
        if low_label not in self._search_key_to_id:
            self._search_keys.append(low_label)
            self._search_key_to_id[low_label] = node_id

    def resolve_id(self, node_id: str) -> Optional[str]:
        """Resolves raw ID or label string to a canonical node_id in the graph."""
        if not node_id:
            return None
        if self.graph.has_node(node_id):
            return node_id
        slug = slugify(node_id)
        if self.graph.has_node(slug):
            return slug
        return self._label_to_id.get(node_id.lower().strip())

    def get_node(self, node_id: str) -> Optional[SkillNode]:
        """Fetch node details with degrees by node_id."""
        with self._lock:
            clean_id = self.resolve_id(node_id)
            if not clean_id or not self.graph.has_node(clean_id):
                return None

            data = self.graph.nodes[clean_id]
            in_deg = self.graph.in_degree(clean_id)
            out_deg = self.graph.out_degree(clean_id)
            return SkillNode(
                id=clean_id,
                label=data.get("label", clean_id),
                category=data.get("category", "General"),
                description=data.get("description", ""),
                is_ground_truth=data.get("is_ground_truth", True),
                in_degree=in_deg,
                out_degree=out_deg,
                metadata={k: v for k, v in data.items() if k not in ("label", "category", "description", "is_ground_truth")},
            )

    def search_skills(self, query: str, limit: int = 15) -> SearchResponse:
        """
        Fuzzy search skill labels and slugs.
        Sorts results by score and connectivity (in + out degree).
        """
        clean_q = query.strip().lower()
        if not clean_q:
            return SearchResponse(query=query, total_matches=0, results=[])

        with self._lock:
            # Rapidfuzz extraction over indexed labels
            matches = process.extract(
                clean_q,
                self._search_keys,
                scorer=fuzz.WRatio,
                limit=limit * 2,
                score_cutoff=40.0,
            )

            results: List[SearchResultItem] = []
            seen_ids = set()

            # Process matches
            for key, score, _ in matches:
                node_id = self._search_key_to_id.get(key)
                if not node_id or node_id in seen_ids or not self.graph.has_node(node_id):
                    continue

                seen_ids.add(node_id)
                data = self.graph.nodes[node_id]
                in_deg = self.graph.in_degree(node_id)
                out_deg = self.graph.out_degree(node_id)
                total_deg = in_deg + out_deg

                # Slight boost for exact substring matches and connected nodes
                adj_score = score
                if clean_q == key or clean_q == node_id:
                    adj_score += 20.0
                elif key.startswith(clean_q):
                    adj_score += 10.0

                results.append(
                    SearchResultItem(
                        id=node_id,
                        label=data.get("label", node_id),
                        category=data.get("category", "General"),
                        is_ground_truth=data.get("is_ground_truth", True),
                        in_degree=in_deg,
                        out_degree=out_deg,
                        similarity_score=min(100.0, round(float(adj_score), 2)),
                    )
                )

            # Sort primarily by adjusted score, then by degree
            results.sort(key=lambda r: (r.similarity_score, r.in_degree + r.out_degree), reverse=True)
            results = results[:limit]

            return SearchResponse(
                query=query,
                total_matches=len(results),
                results=results,
            )

    def get_neighbors(self, node_id: str) -> Optional[NeighborResponse]:
        """
        Returns incoming (prerequisites) and outgoing (unlocked) neighbors.
        """
        with self._lock:
            node = self.get_node(node_id)
            if not node:
                return None

            clean_id = node.id
            prereqs: List[NeighborItem] = []
            unlocked: List[NeighborItem] = []

            # Incoming edges: pred -> clean_id (prerequisites)
            for pred in self.graph.predecessors(clean_id):
                pred_node = self.get_node(pred)
                if pred_node:
                    edge_data = self.graph.get_edge_data(pred, clean_id, default={})
                    rel = edge_data.get("relation", "REQUIRES")
                    prereqs.append(NeighborItem(node=pred_node, relation=rel, direction="incoming"))

            # Outgoing edges: clean_id -> succ (unlocked)
            for succ in self.graph.successors(clean_id):
                succ_node = self.get_node(succ)
                if succ_node:
                    edge_data = self.graph.get_edge_data(clean_id, succ, default={})
                    rel = edge_data.get("relation", "UNLOCKS")
                    unlocked.append(NeighborItem(node=succ_node, relation=rel, direction="outgoing"))

            return NeighborResponse(
                node=node,
                prerequisites=prereqs,
                unlocked=unlocked,
                total_neighbors=len(prereqs) + len(unlocked),
            )

    def find_path(self, start_id: str, target_id: str) -> Tuple[bool, List[SkillNode], List[SkillEdge]]:
        """
        Runs shortest path algorithm (BFS on unweighted DiGraph).
        Returns: (found, nodes_in_path, edges_in_path)
        """
        with self._lock:
            # Resolve possible alias or label
            s_clean = start_id if self.graph.has_node(start_id) else self._label_to_id.get(start_id.lower().strip())
            t_clean = target_id if self.graph.has_node(target_id) else self._label_to_id.get(target_id.lower().strip())

            if not s_clean or not t_clean or not self.graph.has_node(s_clean) or not self.graph.has_node(t_clean):
                return False, [], []

            if s_clean == t_clean:
                node = self.get_node(s_clean)
                return True, [node] if node else [], []

            try:
                path_node_ids = nx.shortest_path(self.graph, source=s_clean, target=t_clean)
                nodes: List[SkillNode] = []
                edges: List[SkillEdge] = []

                for nid in path_node_ids:
                    n_model = self.get_node(nid)
                    if n_model:
                        nodes.append(n_model)

                for i in range(len(path_node_ids) - 1):
                    u = path_node_ids[i]
                    v = path_node_ids[i + 1]
                    edata = self.graph.get_edge_data(u, v, default={})
                    edges.append(
                        SkillEdge(
                            source=u,
                            target=v,
                            relation=edata.get("relation", "REQUIRES"),
                            is_ground_truth=edata.get("is_ground_truth", True),
                        )
                    )

                return True, nodes, edges
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                return False, [], []

    def sample_adjacent_concepts(self, node_id: str, limit: int = 5) -> List[str]:
        """
        Returns a sample of neighbor skill labels to enrich LLM prompt context.
        """
        with self._lock:
            clean_id = node_id if self.graph.has_node(node_id) else self._label_to_id.get(node_id.lower().strip())
            if not clean_id or not self.graph.has_node(clean_id):
                return []

            neighbors = set()
            for p in self.graph.predecessors(clean_id):
                neighbors.add(self.graph.nodes[p].get("label", p))
                if len(neighbors) >= limit:
                    break
            for s in self.graph.successors(clean_id):
                neighbors.add(self.graph.nodes[s].get("label", s))
                if len(neighbors) >= limit:
                    break

            return list(neighbors)

    def get_graph_neighborhood_context(self, node_id: str, max_ancestors: int = 4) -> str:
        """
        Extracts 3-5 immediate parent/ancestor nodes and domain lineage for a skill.
        Used for Context-Aware Prompting to eliminate context drift and domain hallucination.
        Example output: "[Language Skills -> Spoken Languages -> Italian]" or "[Cooking -> Italian Cuisine]"
        """
        with self._lock:
            clean_id = node_id if self.graph.has_node(node_id) else self._label_to_id.get(node_id.lower().strip())
            if not clean_id or not self.graph.has_node(clean_id):
                return f"[{node_id}]"

            target_label = self.graph.nodes[clean_id].get("label", clean_id)
            target_category = self.graph.nodes[clean_id].get("category", "")

            # 1. Walk upward along predecessors to find ancestor chain
            ancestors: List[str] = []
            curr = clean_id
            visited = set([curr])

            while len(ancestors) < max_ancestors:
                preds = list(self.graph.predecessors(curr))
                if not preds:
                    break
                # Prioritize parent with highest degree connectivity that has not been visited
                unvisited_preds = [p for p in preds if p not in visited]
                if not unvisited_preds:
                    break
                best_pred = max(unvisited_preds, key=lambda p: self.graph.degree(p))
                visited.add(best_pred)
                p_label = self.graph.nodes[best_pred].get("label", best_pred)
                ancestors.append(p_label)
                curr = best_pred

            if ancestors:
                # Top-level ancestor -> parent -> target
                chain = list(reversed(ancestors)) + [target_label]
                return f"[{' -> '.join(chain)}]"

            # 2. If no ancestors, check if this node is a parent/hub with children (successors)
            succs = list(self.graph.successors(clean_id))
            if succs:
                sample_children = [self.graph.nodes[s].get("label", s) for s in succs[:3]]
                return f"[Domain: {target_label} (includes: {', '.join(sample_children)})]"

            # 3. Check if target_category provides meaningful domain context
            if target_category and target_category not in ("General", "Custom Skill", "User Input", "Frontier node"):
                return f"[{target_category} -> {target_label}]"

            # 4. Fuzzy check if target matches a domain branch in the ground-truth taxonomy
            fuzzy_matches = process.extract(
                target_label.lower(),
                self._search_keys,
                scorer=fuzz.token_set_ratio,
                limit=3,
                score_cutoff=75.0,
            )
            for key, _, _ in fuzzy_matches:
                matched_id = self._search_key_to_id.get(key)
                if matched_id and matched_id != clean_id:
                    m_preds = list(self.graph.predecessors(matched_id))
                    if m_preds:
                        parent_label = self.graph.nodes[m_preds[0]].get("label", m_preds[0])
                        return f"[{parent_label} -> {target_label}]"

            return f"[General Craft & Practical Knowledge -> {target_label}]"

    def get_immediate_parents_context(self, node_id: str, limit: int = 5) -> str:
        """
        Rule 3 (Context Injection Limit):
        Queries the in-memory graph for ONLY the 3 to 5 immediate parent nodes of the target skill.
        Formats the injected context tightly: 'Domain Context: [Parent1, Parent2, Parent3]'
        Prevents dumping the entire graph into the LLM context window.
        """
        with self._lock:
            clean_id = self.resolve_id(node_id)
            if not clean_id or not self.graph.has_node(clean_id):
                clean_label = node_id.replace("-", " ").title()
                return f"Domain Context: [{clean_label}]"

            # 1. Direct parent predecessors in DiGraph (parent -> child)
            preds = list(self.graph.predecessors(clean_id))
            parent_labels: List[str] = []

            for p in preds:
                p_label = self.graph.nodes[p].get("label", p)
                if p_label and p_label not in parent_labels:
                    parent_labels.append(p_label)
                if len(parent_labels) >= limit:
                    break

            # 2. If fewer than 3 direct parents, pull immediate grandparents
            # to give 3-5 tight parent concepts without dumping the graph
            if len(parent_labels) < 3 and preds:
                for p in preds:
                    for gp in self.graph.predecessors(p):
                        gp_label = self.graph.nodes[gp].get("label", gp)
                        if gp_label and gp_label not in parent_labels:
                            parent_labels.append(gp_label)
                        if len(parent_labels) >= limit:
                            break
                    if len(parent_labels) >= limit:
                        break

            # 3. If root node (0 parents), fall back tightly to category or label
            if not parent_labels:
                cat = self.graph.nodes[clean_id].get("category")
                target_label = self.graph.nodes[clean_id].get("label", clean_id)
                if cat and cat not in ("General", "Custom Skill", "User Input", "Frontier node", "Synthesized Skill"):
                    parent_labels.append(cat)
                parent_labels.append(target_label)

            return f"Domain Context: [{', '.join(parent_labels[:limit])}]"

    def get_cached_expansion(
        self,
        node_id: str,
        direction: str = "both",
        limit: int = 6,
    ) -> Optional[Tuple[List[SkillNode], List[SkillEdge]]]:
        """
        Rule 1 (Infinite Craft Caching Layer):
        Checks if the requested node has already been expanded (i.e. has outgoing edges).
        - If it has existing edges, returns the cached neighbors and edges immediately.
        - If it is a leaf node (0 outgoing edges), returns None so the caller proceeds to LLM.
        """
        with self._lock:
            clean_id = self.resolve_id(node_id)
            if not clean_id or not self.graph.has_node(clean_id):
                return None

            out_edges = list(self.graph.out_edges(clean_id, data=True))
            if not out_edges:
                return None  # Leaf node: 0 outgoing edges -> proceed to LLM

            # Node has already been expanded! Return cached neighbors immediately.
            cached_nodes: List[SkillNode] = []
            cached_edges: List[SkillEdge] = []
            seen_nodes = set()

            # 1. Outgoing unlocked edges (clean_id -> target)
            for _, target_id, data in out_edges:
                if target_id not in seen_nodes:
                    succ_node = self.get_node(target_id)
                    if succ_node:
                        cached_nodes.append(succ_node)
                        seen_nodes.add(target_id)
                        cached_edges.append(
                            SkillEdge(
                                source=clean_id,
                                target=target_id,
                                relation=data.get("relation", "UNLOCKS"),
                                is_ground_truth=data.get("is_ground_truth", True),
                            )
                        )
                if len(cached_nodes) >= limit:
                    break

            # 2. If direction includes prerequisites, also collect incoming edges up to limit
            if direction in ("both", "requires") and len(cached_nodes) < limit:
                in_edges = list(self.graph.in_edges(clean_id, data=True))
                for src_id, _, data in in_edges:
                    if src_id not in seen_nodes:
                        pred_node = self.get_node(src_id)
                        if pred_node:
                            cached_nodes.append(pred_node)
                            seen_nodes.add(src_id)
                            cached_edges.append(
                                SkillEdge(
                                    source=src_id,
                                    target=clean_id,
                                    relation=data.get("relation", "REQUIRES"),
                                    is_ground_truth=data.get("is_ground_truth", True),
                                )
                            )
                    if len(cached_nodes) >= limit:
                        break

            return cached_nodes, cached_edges

    def find_shared_successor(self, node_id_1: str, node_id_2: str) -> Optional[SkillNode]:
        """
        Caching Layer Check for Node Synthesis:
        Query if there is already a node that shares incoming REQUIRES edges from BOTH
        node_id_1 and node_id_2.
        If it exists, return it instantly; otherwise None.
        """
        with self._lock:
            id1 = self.resolve_id(node_id_1)
            id2 = self.resolve_id(node_id_2)
            if not id1 or not id2 or not self.graph.has_node(id1) or not self.graph.has_node(id2):
                return None

            succ1 = set(self.graph.successors(id1))
            succ2 = set(self.graph.successors(id2))
            common = succ1.intersection(succ2)
            if not common:
                return None

            # Prioritize a shared successor with incoming REQUIRES relations from both
            for target_id in common:
                e1 = self.graph.get_edge_data(id1, target_id, default={})
                e2 = self.graph.get_edge_data(id2, target_id, default={})
                rel1 = e1.get("relation", "").upper()
                rel2 = e2.get("relation", "").upper()
                if rel1 == "REQUIRES" and rel2 == "REQUIRES":
                    return self.get_node(target_id)

            # Return first common successor
            first_common = next(iter(common))
            return self.get_node(first_common)

    def find_close_existing_skill(self, proposed_label: str, threshold: float = 85.0) -> Optional[str]:
        """
        Checks if a proposed skill closely matches an existing node in the graph.
        Returns the existing node_id if match is above threshold, else None.
        """
        clean_text = proposed_label.strip().lower()
        if not clean_text:
            return None

        with self._lock:
            # Exact check
            if clean_text in self._label_to_id:
                return self._label_to_id[clean_text]

            # Fuzzy match against known search keys
            if not self._search_keys:
                return None

            match = process.extractOne(
                clean_text,
                self._search_keys,
                scorer=fuzz.token_sort_ratio,
                score_cutoff=threshold,
            )
            if match:
                matched_key, score, _ = match
                return self._search_key_to_id.get(matched_key)

            return None

    def merge_subgraph(
        self,
        intermediate_nodes: List[IntermediateNode],
        connecting_edges: List[ConnectingEdge],
        is_ground_truth: bool = False,
    ) -> Tuple[List[SkillNode], List[SkillEdge]]:
        """
        Atomically merges newly synthesized nodes and edges into the in-memory graph.
        Returns the created/updated SkillNode and SkillEdge models.
        """
        with self._lock:
            added_nodes: List[SkillNode] = []
            added_edges: List[SkillEdge] = []

            # 1. Upsert Nodes
            for n in intermediate_nodes:
                nid = slugify(n.id or n.label)
                label = n.label.strip() or nid

                if not self.graph.has_node(nid):
                    self.graph.add_node(
                        nid,
                        label=label,
                        category=n.category or "Synthesized Skill",
                        description=n.description or f"AI-bridged skill: {label}",
                        is_ground_truth=is_ground_truth,
                    )
                    self._index_node(nid, label)
                else:
                    # Update description/category if previously unset
                    curr = self.graph.nodes[nid]
                    if not curr.get("description") and n.description:
                        curr["description"] = n.description
                    if curr.get("category") == "General" and n.category:
                        curr["category"] = n.category

                node_model = self.get_node(nid)
                if node_model:
                    added_nodes.append(node_model)

            # 2. Add Edges
            for e in connecting_edges:
                src_id = slugify(e.source)
                tgt_id = slugify(e.target)

                # Ensure source and target nodes exist in graph (fallback placeholder if missing)
                for nid in (src_id, tgt_id):
                    if not self.graph.has_node(nid):
                        self.graph.add_node(
                            nid,
                            label=nid.replace("-", " ").title(),
                            category="Synthesized Skill",
                            description="AI-synthesized connection node",
                            is_ground_truth=is_ground_truth,
                        )
                        self._index_node(nid, nid.replace("-", " ").title())

                rel = e.relation.upper().strip() if e.relation else "REQUIRES"
                self.graph.add_edge(
                    src_id,
                    tgt_id,
                    relation=rel,
                    is_ground_truth=is_ground_truth,
                )
                added_edges.append(
                    SkillEdge(
                        source=src_id,
                        target=tgt_id,
                        relation=rel,
                        is_ground_truth=is_ground_truth,
                    )
                )

            logger.info(
                f"Merged subgraph: {len(intermediate_nodes)} nodes, "
                f"{len(connecting_edges)} edges into graph. "
                f"Total nodes now: {self.graph.number_of_nodes()}"
            )
            return added_nodes, added_edges

    def get_stats(self) -> GraphStatsResponse:
        """Calculate high-level graph statistics."""
        with self._lock:
            n = self.graph.number_of_nodes()
            e = self.graph.number_of_edges()
            gt_nodes = sum(1 for _, d in self.graph.nodes(data=True) if d.get("is_ground_truth", True))
            ai_nodes = n - gt_nodes
            density = nx.density(self.graph) if n > 0 else 0.0

            return GraphStatsResponse(
                total_nodes=n,
                total_edges=e,
                ground_truth_nodes=gt_nodes,
                ai_generated_nodes=ai_nodes,
                density=round(density, 6),
            )

    def get_subgraph(
        self,
        seed_ids: Optional[List[str]] = None,
        max_nodes: int = 35,
    ) -> Tuple[List[SkillNode], List[SkillEdge]]:
        """
        Extracts an engaging, interconnected subgraph for initial canvas rendering or inspection.
        If seed_ids is empty, selects the top high-degree hub skills and their immediate neighbors.
        """
        with self._lock:
            selected_ids = set()

            if seed_ids:
                for sid in seed_ids:
                    clean = sid if self.graph.has_node(sid) else self._label_to_id.get(sid.lower().strip())
                    if clean and self.graph.has_node(clean):
                        selected_ids.add(clean)
                        # Add immediate neighbors
                        for p in self.graph.predecessors(clean):
                            selected_ids.add(p)
                        for s in self.graph.successors(clean):
                            selected_ids.add(s)
            else:
                # Pick top hub nodes sorted by total degree
                hub_nodes = sorted(
                    self.graph.nodes(),
                    key=lambda nid: self.graph.degree(nid),
                    reverse=True,
                )[:8]

                for hub in hub_nodes:
                    selected_ids.add(hub)
                    # Add a few predecessors and successors
                    for p in list(self.graph.predecessors(hub))[:3]:
                        selected_ids.add(p)
                    for s in list(self.graph.successors(hub))[:3]:
                        selected_ids.add(s)
                    if len(selected_ids) >= max_nodes:
                        break

            # Trim to max_nodes
            final_ids = list(selected_ids)[:max_nodes]
            nodes = [self.get_node(nid) for nid in final_ids if self.get_node(nid) is not None]

            # Gather edges between selected nodes
            id_set = set(final_ids)
            edges: List[SkillEdge] = []
            for u in id_set:
                for v in self.graph.successors(u):
                    if v in id_set:
                        edata = self.graph.get_edge_data(u, v, default={})
                        edges.append(
                            SkillEdge(
                                source=u,
                                target=v,
                                relation=edata.get("relation", "REQUIRES"),
                                is_ground_truth=edata.get("is_ground_truth", True),
                            )
                        )

            return nodes, edges

    def match_resume_skills(self, input_skills: List[str]) -> Tuple[List[SkillNode], List[str], List[SkillNode]]:
        """
        Matches a list of raw skill phrases from a resume against the graph.
        Returns:
          - matched_nodes: list of SkillNode found in the graph
          - unmatched_labels: strings that didn't match closely
          - recommended_goals: high-value downstream skills unlocked by matched nodes
        """
        matched_nodes: List[SkillNode] = []
        unmatched: List[str] = []
        seen_ids = set()

        with self._lock:
            for raw in input_skills:
                phrase = raw.strip()
                if not phrase or len(phrase) < 2:
                    continue

                existing_id = self.find_close_existing_skill(phrase, threshold=settings.FUZZY_MATCH_THRESHOLD)
                if existing_id and existing_id not in seen_ids:
                    node = self.get_node(existing_id)
                    if node:
                        matched_nodes.append(node)
                        seen_ids.add(existing_id)
                else:
                    if existing_id not in seen_ids:
                        unmatched.append(phrase)

            # Suggest high-impact goals (outgoing frontier from matched skills)
            goal_candidates = set()
            for m in matched_nodes:
                for succ in self.graph.successors(m.id):
                    if succ not in seen_ids:
                        goal_candidates.add(succ)

            # Sort candidate goals by overall out-degree to give exciting career targets
            goals = [self.get_node(gid) for gid in goal_candidates if self.get_node(gid)]
            goals.sort(key=lambda g: g.out_degree + g.in_degree, reverse=True)
            recommended_goals = goals[:5]

            return matched_nodes, unmatched, recommended_goals

