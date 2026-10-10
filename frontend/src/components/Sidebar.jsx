import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  ArrowDownLeft,
  ArrowUpRight,
  Route,
  Zap,
  Star,
  Layers,
  Info,
  Loader2,
  Compass,
  GitBranch,
  CheckSquare,
  Square,
} from 'lucide-react';
import { fetchNeighbors } from '../api/client';

export default function Sidebar({
  selectedNode,
  onExpandNode,
  onSelectNodeById,
  onSetStartSkill,
  onSetGoalSkill,
  activePathway,
  isExpanding,
  allSolidNodes = [],
  onExploreMultiSkillNextSteps,
  isSuggestingMulti = false,
}) {
  const [neighbors, setNeighbors] = useState(null);
  const [loadingNeighbors, setLoadingNeighbors] = useState(false);
  const [activeTab, setActiveTab] = useState(selectedNode ? 'node' : 'my-skills'); // 'node' | 'my-skills' | 'pathway'
  const [selectedSkillIds, setSelectedSkillIds] = useState(new Set());

  // Automatically switch tab when a node is clicked or deselected
  useEffect(() => {
    if (selectedNode) {
      setActiveTab('node');
    } else {
      setActiveTab('my-skills');
    }
  }, [selectedNode?.id]);

  useEffect(() => {
    if (selectedNode) {
      setLoadingNeighbors(true);
      fetchNeighbors(selectedNode.id)
        .then((res) => setNeighbors(res))
        .catch((err) => console.error('Failed to fetch neighbors', err))
        .finally(() => setLoadingNeighbors(false));
    } else {
      setNeighbors(null);
    }
  }, [selectedNode?.id]);

  const handleToggleSkillId = (id) => {
    setSelectedSkillIds((curr) => {
      const next = new Set(curr);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleToggleSelectAll = () => {
    if (selectedSkillIds.size === allSolidNodes.length) {
      setSelectedSkillIds(new Set());
    } else {
      setSelectedSkillIds(new Set(allSolidNodes.map((n) => n.id)));
    }
  };

  const isGhost = Boolean(selectedNode?.is_ghost || selectedNode?.isGhost);

  return (
    <aside className="w-96 h-full bg-white border-l border-neutral-200 flex flex-col z-20 shadow-xl select-none">
      {/* Sidebar Header with Navigation Tabs */}
      <div className="p-3 border-b border-neutral-200 flex items-center justify-between bg-neutral-50 gap-1">
        <div className="flex items-center gap-1.5 overflow-x-auto">
          {selectedNode && (
            <button
              onClick={() => setActiveTab('node')}
              className={`px-2.5 py-1 text-xs rounded-lg border font-medium flex items-center gap-1 transition-all cursor-pointer ${
                activeTab === 'node'
                  ? 'bg-neutral-900 text-white border-neutral-900'
                  : 'bg-white text-neutral-600 border-neutral-300 hover:text-neutral-950'
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              Inspector
            </button>
          )}

          <button
            onClick={() => setActiveTab('my-skills')}
            className={`px-2.5 py-1 text-xs rounded-lg border font-medium flex items-center gap-1 transition-all cursor-pointer ${
              activeTab === 'my-skills'
                ? 'bg-neutral-900 text-white border-neutral-900'
                : 'bg-white text-neutral-600 border-neutral-300 hover:text-neutral-950'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            Current Skills ({allSolidNodes.length})
          </button>

          {activePathway && (
            <button
              onClick={() => setActiveTab('pathway')}
              className={`px-2.5 py-1 text-xs rounded-lg border font-medium flex items-center gap-1 transition-all cursor-pointer ${
                activeTab === 'pathway'
                  ? 'bg-neutral-900 text-white border-neutral-900'
                  : 'bg-white text-neutral-600 border-neutral-300 hover:text-neutral-950'
              }`}
            >
              <Route className="w-3.5 h-3.5" />
              Path ({activePathway.nodes?.length || 0})
            </button>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Active Pathway View */}
        {activeTab === 'pathway' && activePathway ? (
          <div className="space-y-4">
            <div className="p-3.5 rounded-xl bg-neutral-50 border border-neutral-200">
              <div className="flex items-center justify-between text-xs font-semibold text-neutral-900 mb-1">
                <span className="flex items-center gap-1.5">
                  <Route className="w-4 h-4 text-neutral-800" />
                  Synthesized Pathway
                </span>
                <span className="text-[11px] text-neutral-600 font-mono">
                  {activePathway.total_steps} Steps
                </span>
              </div>
              <p className="text-xs text-neutral-600 leading-relaxed mt-1">
                {activePathway.message}
              </p>
              <div className="mt-2.5 flex items-center gap-3 text-[11px] text-neutral-500 font-mono">
                <span>Deterministic: {activePathway.total_steps - activePathway.synthesized_count}</span>
                <span>•</span>
                <span className="text-neutral-900 font-semibold">
                  AI Bridged: {activePathway.synthesized_count}
                </span>
              </div>
            </div>

            <div className="space-y-2">
              <h4 className="text-[11px] font-bold text-neutral-500 uppercase tracking-wider">
                Step-by-Step Progression
              </h4>
              <div className="space-y-1.5">
                {activePathway.nodes.map((stepNode, idx) => (
                  <div
                    key={stepNode.id}
                    onClick={() => onSelectNodeById(stepNode.id)}
                    className="p-2.5 rounded-lg bg-neutral-50 hover:bg-neutral-100 border border-neutral-200 cursor-pointer flex items-center justify-between text-xs transition-colors"
                  >
                    <div className="flex items-center gap-2">
                      <span className="w-5 h-5 rounded-full bg-neutral-900 text-white font-mono text-[10px] flex items-center justify-center font-bold">
                        {idx + 1}
                      </span>
                      <span className="font-medium text-neutral-900">{stepNode.label}</span>
                    </div>
                    {stepNode.is_ground_truth ? (
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-neutral-200 text-neutral-700">
                        Ground Truth
                      </span>
                    ) : (
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-neutral-900 text-white font-medium">
                        AI Bridge
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : activeTab === 'node' && selectedNode ? (
          /* Selected Node View */
          <div className="space-y-4">
            {/* Main Info Card */}
            <div className={`p-4 rounded-xl border ${
              isGhost
                ? 'bg-neutral-50 border-dashed border-neutral-400'
                : 'bg-white border-neutral-200 shadow-sm'
            }`}>
              <div className="flex items-center justify-between text-[10px] text-neutral-400 font-mono mb-2">
                <span>#{selectedNode.id}</span>
                <span>
                  {isGhost ? (
                    <span className="px-1.5 py-0.5 rounded-full bg-neutral-200 text-neutral-600 font-semibold">
                      Preview Ghost
                    </span>
                  ) : selectedNode.is_ground_truth !== false ? (
                    <span className="px-1.5 py-0.5 rounded-full bg-neutral-100 text-neutral-700 font-semibold">
                      Ground Truth
                    </span>
                  ) : (
                    <span className="px-1.5 py-0.5 rounded-full bg-neutral-900 text-white font-semibold">
                      Synthesized
                    </span>
                  )}
                </span>
              </div>
              <h3 className="text-base font-bold text-neutral-900 leading-snug">
                {selectedNode.label}
              </h3>
              <p className="text-xs text-neutral-500 font-medium mt-1 uppercase tracking-wide">
                {selectedNode.category || 'General Skill'}
              </p>
              {selectedNode.description && (
                <p className="text-xs text-neutral-600 mt-2.5 leading-relaxed bg-neutral-50 p-2.5 rounded-lg border border-neutral-200">
                  {selectedNode.description}
                </p>
              )}
            </div>

            {/* Quick Action Buttons */}
            {!isGhost && (
              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() => onSetStartSkill(selectedNode)}
                  className="p-2 rounded-lg bg-neutral-100 hover:bg-neutral-200 border border-neutral-300 text-neutral-800 text-xs font-medium flex items-center justify-center gap-1.5 transition-all shadow-sm cursor-pointer"
                >
                  <Zap className="w-3.5 h-3.5 text-neutral-700" /> Set as Start
                </button>
                <button
                  onClick={() => onSetGoalSkill(selectedNode)}
                  className="p-2 rounded-lg bg-neutral-100 hover:bg-neutral-200 border border-neutral-300 text-neutral-800 text-xs font-medium flex items-center justify-center gap-1.5 transition-all shadow-sm cursor-pointer"
                >
                  <Star className="w-3.5 h-3.5 text-neutral-700" /> Set as Goal
                </button>
              </div>
            )}

            {/* Explore Pathways Action (Single Node) */}
            <div className="space-y-2">
              <button
                onClick={() => onExpandNode(selectedNode.id)}
                disabled={isExpanding}
                className="w-full py-2.5 px-3 rounded-xl bg-neutral-950 hover:bg-neutral-800 text-white font-semibold text-xs flex items-center justify-center gap-2 shadow-sm transition-all disabled:opacity-50 cursor-pointer"
              >
                {isExpanding ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin text-white" />
                    Generating Ghost Previews...
                  </>
                ) : (
                  <>
                    <Compass className="w-4 h-4 text-white" />
                    {isGhost ? 'Solidify Node into Tree' : 'Explore Potential Next Steps'}
                  </>
                )}
              </button>

              {allSolidNodes.length > 1 && !isGhost && (
                <button
                  onClick={() => {
                    setSelectedSkillIds(new Set([selectedNode.id, ...allSolidNodes.filter(n => n.id !== selectedNode.id).slice(0, 2).map(n => n.id)]));
                    setActiveTab('my-skills');
                  }}
                  className="w-full py-2 px-3 rounded-xl bg-white hover:bg-neutral-50 text-neutral-800 border border-neutral-300 font-medium text-xs flex items-center justify-center gap-1.5 transition-all shadow-sm cursor-pointer"
                >
                  <Sparkles className="w-3.5 h-3.5 text-neutral-600" />
                  Combine with My Other Skills...
                </button>
              )}
            </div>

            {/* Prerequisites (Incoming) */}
            <div className="space-y-2 pt-2 border-t border-neutral-200">
              <div className="flex items-center justify-between text-xs font-semibold text-neutral-800">
                <span className="flex items-center gap-1.5">
                  <ArrowDownLeft className="w-3.5 h-3.5 text-neutral-600" />
                  Prerequisites (Incoming)
                </span>
                <span className="text-[11px] text-neutral-400 font-mono">
                  {neighbors?.prerequisites?.length ?? 0}
                </span>
              </div>
              {loadingNeighbors ? (
                <div className="py-4 flex justify-center text-neutral-400">
                  <Loader2 className="w-4 h-4 animate-spin" />
                </div>
              ) : neighbors?.prerequisites?.length ? (
                <div className="space-y-1.5 max-h-40 overflow-y-auto pr-1">
                  {neighbors.prerequisites.map(({ node, relation }) => (
                    <div
                      key={node.id}
                      onClick={() => onSelectNodeById(node.id)}
                      className="p-2 rounded-lg bg-neutral-50 hover:bg-neutral-100 border border-neutral-200 hover:border-neutral-400 cursor-pointer flex items-center justify-between text-xs transition-all"
                    >
                      <span className="text-neutral-800 truncate pr-2 font-medium">
                        {node.label}
                      </span>
                      <span className="text-[9px] px-1 py-0.5 rounded bg-neutral-200 text-neutral-700 font-mono shrink-0">
                        {relation}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-neutral-400 italic p-2 bg-neutral-50 rounded border border-neutral-200">
                  No mapped prerequisites in ground truth.
                </p>
              )}
            </div>

            {/* Unlocked Next Steps (Outgoing) */}
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs font-semibold text-neutral-800">
                <span className="flex items-center gap-1.5">
                  <ArrowUpRight className="w-3.5 h-3.5 text-neutral-600" />
                  Unlocked Skills (Outgoing)
                </span>
                <span className="text-[11px] text-neutral-400 font-mono">
                  {neighbors?.unlocked?.length ?? 0}
                </span>
              </div>
              {loadingNeighbors ? (
                <div className="py-4 flex justify-center text-neutral-400">
                  <Loader2 className="w-4 h-4 animate-spin" />
                </div>
              ) : neighbors?.unlocked?.length ? (
                <div className="space-y-1.5 max-h-40 overflow-y-auto pr-1">
                  {neighbors.unlocked.map(({ node, relation }) => (
                    <div
                      key={node.id}
                      onClick={() => onSelectNodeById(node.id)}
                      className="p-2 rounded-lg bg-neutral-50 hover:bg-neutral-100 border border-neutral-200 hover:border-neutral-400 cursor-pointer flex items-center justify-between text-xs transition-all"
                    >
                      <span className="text-neutral-800 truncate pr-2 font-medium">
                        {node.label}
                      </span>
                      <span className="text-[9px] px-1 py-0.5 rounded bg-neutral-200 text-neutral-700 font-mono shrink-0">
                        {relation}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-neutral-400 italic p-2 bg-neutral-50 rounded border border-neutral-200">
                  Click "Explore Potential Next Steps" to preview branches.
                </p>
              )}
            </div>
          </div>
        ) : (
          /* My Current Skills & Multi-Skill Discovery View */
          <div className="space-y-4">
            <div className="p-3.5 rounded-xl bg-neutral-50 border border-neutral-200">
              <div className="flex items-center justify-between text-xs font-semibold text-neutral-900 mb-1">
                <span className="flex items-center gap-1.5">
                  <Sparkles className="w-4 h-4 text-neutral-800" />
                  Multi-Skill Discovery
                </span>
                <span className="text-[11px] text-neutral-600 font-mono">
                  {selectedSkillIds.size || allSolidNodes.length} of {allSolidNodes.length} Active
                </span>
              </div>
              <p className="text-xs text-neutral-600 leading-relaxed mt-1">
                Discover emergent stepping stones and unlockable competencies you can make with the skills you currently possess.
              </p>

              <div className="mt-3">
                <button
                  onClick={() => {
                    const ids =
                      selectedSkillIds.size > 0
                        ? Array.from(selectedSkillIds)
                        : allSolidNodes.map((n) => n.id);
                    onExploreMultiSkillNextSteps(ids);
                  }}
                  disabled={isSuggestingMulti || allSolidNodes.length === 0}
                  className="w-full py-2.5 px-3 rounded-xl bg-neutral-950 hover:bg-neutral-800 text-white font-semibold text-xs flex items-center justify-center gap-2 shadow-sm transition-all disabled:opacity-50 cursor-pointer"
                >
                  {isSuggestingMulti ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin text-white" />
                      Analyzing Current Skills...
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-4 h-4 text-white" />
                      Suggest Next Steps from {selectedSkillIds.size > 0 ? `${selectedSkillIds.size} Selected` : 'Current'} Skills
                    </>
                  )}
                </button>
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h4 className="text-[11px] font-bold text-neutral-500 uppercase tracking-wider">
                  Active Skills on Canvas ({allSolidNodes.length})
                </h4>
                {allSolidNodes.length > 0 && (
                  <button
                    onClick={handleToggleSelectAll}
                    className="text-[10px] text-neutral-600 hover:text-neutral-950 underline cursor-pointer"
                  >
                    {selectedSkillIds.size === allSolidNodes.length ? 'Deselect All' : 'Select All'}
                  </button>
                )}
              </div>

              {allSolidNodes.length === 0 ? (
                <div className="p-6 text-center text-neutral-400 space-y-2 border border-dashed border-neutral-300 rounded-2xl bg-neutral-50">
                  <Compass className="w-7 h-7 mx-auto text-neutral-400" />
                  <p className="text-xs">
                    No active skills on canvas yet. Add skills or upload a resume to explore what you can make.
                  </p>
                </div>
              ) : (
                <div className="space-y-1.5 max-h-72 overflow-y-auto pr-1">
                  {allSolidNodes.map((n) => {
                    const isChecked = selectedSkillIds.has(n.id);
                    return (
                      <div
                        key={n.id}
                        onClick={() => handleToggleSkillId(n.id)}
                        className={`p-2.5 rounded-xl border cursor-pointer flex items-center justify-between text-xs transition-all ${
                          isChecked
                            ? 'bg-neutral-900 text-white border-neutral-900 shadow-sm'
                            : 'bg-white hover:bg-neutral-50 border-neutral-200 text-neutral-800'
                        }`}
                      >
                        <div className="flex items-center gap-2 truncate pr-2">
                          {isChecked ? (
                            <CheckSquare className="w-3.5 h-3.5 text-white shrink-0" />
                          ) : (
                            <Square className="w-3.5 h-3.5 text-neutral-400 shrink-0" />
                          )}
                          <span className="truncate font-medium">{n.label || n.data?.label}</span>
                        </div>
                        <span
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelectNodeById(n.id);
                          }}
                          className={`text-[9px] px-1.5 py-0.5 rounded font-mono shrink-0 cursor-pointer ${
                            isChecked ? 'bg-neutral-800 text-neutral-300' : 'bg-neutral-100 text-neutral-600'
                          }`}
                          title="Inspect node details"
                        >
                          Inspect ➔
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="p-3 rounded-xl bg-neutral-50 border border-neutral-200 text-left text-xs space-y-2">
              <div className="flex items-center gap-1.5 text-neutral-800 font-semibold text-[11px] uppercase tracking-wide">
                <Info className="w-3.5 h-3.5 text-neutral-600" />
                How Multi-Skill Discovery Works
              </div>
              <ul className="text-[11px] text-neutral-500 space-y-1 list-disc list-inside">
                <li>Select the skills you currently possess above.</li>
                <li>Click <strong>Suggest Next Steps</strong> to preview dotted Ghost Nodes.</li>
                <li>Dotted nodes show what skills you can make with your current competencies.</li>
                <li>Click any dotted Ghost Node on the canvas to solidify it into your tree.</li>
              </ul>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
