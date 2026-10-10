const API_BASE = '/api';

export async function fetchStats() {
  const res = await fetch(`${API_BASE}/graph/stats`);
  if (!res.ok) throw new Error('Failed to fetch graph stats');
  return res.json();
}

export async function fetchSubgraph(seeds = null, maxNodes = 35) {
  const params = new URLSearchParams();
  if (seeds) params.append('seeds', seeds);
  if (maxNodes) params.append('max_nodes', maxNodes);
  const res = await fetch(`${API_BASE}/graph/subgraph?${params.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch initial subgraph');
  return res.json();
}

export async function searchSkills(query, limit = 15) {
  if (!query || !query.trim()) return { results: [] };
  const res = await fetch(`${API_BASE}/skills/search?q=${encodeURIComponent(query)}&limit=${limit}`);
  if (!res.ok) throw new Error('Search failed');
  return res.json();
}

export async function fetchSkill(id) {
  const res = await fetch(`${API_BASE}/skills/${encodeURIComponent(id)}`);
  if (!res.ok) throw new Error(`Skill ${id} not found`);
  return res.json();
}

export async function fetchNeighbors(id) {
  const res = await fetch(`${API_BASE}/skills/${encodeURIComponent(id)}/neighbors`);
  if (!res.ok) throw new Error(`Neighbors for ${id} not found`);
  return res.json();
}

export async function bridgeSkills(startSkillId, targetSkillId) {
  const res = await fetch(`${API_BASE}/skills/bridge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      start_skill_id: startSkillId,
      target_skill_id: targetSkillId,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Bridge synthesis failed' }));
    throw new Error(err.detail || 'Bridge synthesis failed');
  }
  return res.json();
}

export async function expandSkill(skillId, count = 3, direction = 'both') {
  const res = await fetch(`${API_BASE}/skills/${encodeURIComponent(skillId)}/expand`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ count, direction }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Frontier expansion failed' }));
    throw new Error(err.detail || 'Frontier expansion failed');
  }
  return res.json();
}

export async function uploadResume(resumeText, skills = null) {
  const res = await fetch(`${API_BASE}/skills/upload-resume`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      resume_text: resumeText,
      skills: skills,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Resume upload failed' }));
    throw new Error(err.detail || 'Resume upload failed');
  }
  return res.json();
}

export async function createCustomSkill(label, category = 'Custom Skill', description = '') {
  const res = await fetch(`${API_BASE}/skills/custom`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ label, category, description }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to create custom skill' }));
    throw new Error(err.detail || 'Failed to create custom skill');
  }
  return res.json();
}

export async function synthesizeSkills(sourceNode1, sourceNode2) {
  const res = await fetch(`${API_BASE}/synthesize-skills`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      source_node_1: sourceNode1,
      source_node_2: sourceNode2,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Node synthesis failed' }));
    throw new Error(err.detail || 'Node synthesis failed');
  }
  return res.json();
}

export async function suggestNextSteps(skillIds, count = 3, domainContext = null) {
  const res = await fetch(`${API_BASE}/skills/suggest-next-steps`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      skill_ids: skillIds,
      count,
      domain_context: domainContext,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to suggest next steps' }));
    throw new Error(err.detail || 'Failed to suggest next steps');
  }
  return res.json();
}


