import React, { useState, useEffect, useRef } from 'react';
import {
  Search,
  Route,
  UploadCloud,
  Layers,
  Sparkles,
  Zap,
  Star,
  RefreshCw,
  Loader2,
  GitBranch,
  Plus,
  Trash2,
} from 'lucide-react';
import { searchSkills } from '../api/client';

export default function Toolbar({
  stats,
  startSkill,
  goalSkill,
  onClearBridge,
  onBridgeSkills,
  isBridging,
  onOpenResumeModal,
  onSelectSearchResult,
  onAddCustomSkill,
  onClearCanvas,
  layoutDirection,
  onToggleLayout,
  onResetView,
  nodeCount,
  onSuggestNextSteps,
  isSuggestingMulti,
}) {
  const [query, setQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const searchRef = useRef(null);

  // Debounced search
  useEffect(() => {
    if (!query.trim()) {
      setSearchResults([]);
      setShowDropdown(false);
      return;
    }

    const timer = setTimeout(async () => {
      setIsSearching(true);
      try {
        const res = await searchSkills(query, 8);
        setSearchResults(res.results || []);
        setShowDropdown(true);
      } catch (err) {
        console.error('Search error', err);
      } finally {
        setIsSearching(false);
      }
    }, 200);

    return () => clearTimeout(timer);
  }, [query]);

  // Click outside listener for search dropdown
  useEffect(() => {
    function handleClickOutside(e) {
      if (searchRef.current && !searchRef.current.contains(e.target)) {
        setShowDropdown(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && query.trim()) {
      if (searchResults.length > 0) {
        onSelectSearchResult(searchResults[0]);
      } else {
        onAddCustomSkill(query.trim());
      }
      setShowDropdown(false);
      setQuery('');
    }
  };

  return (
    <header className="h-16 px-4 bg-white border-b border-neutral-200 flex items-center justify-between z-30 shadow-sm select-none">
      {/* Brand & Stats */}
      <div className="flex items-center gap-4 shrink-0">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl bg-neutral-950 flex items-center justify-center text-white shadow-sm">
            <GitBranch className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-tight text-neutral-900 flex items-center gap-1.5">
              Skill Pathway Explorer
              <span className="text-[10px] px-1.5 py-0.2 rounded bg-neutral-100 text-neutral-600 border border-neutral-300 font-mono">
                Graph Engine
              </span>
            </h1>
            <p className="text-[10px] text-neutral-400 font-mono">
              Deterministic Graph + LLM Bridge
            </p>
          </div>
        </div>

        {/* Live Graph Stats Badge */}
        {stats && (
          <div className="hidden xl:flex items-center gap-2 px-2.5 py-1 rounded-lg bg-neutral-50 border border-neutral-200 text-[11px] text-neutral-500">
            <span>Canvas: <strong className="text-neutral-900">{nodeCount}</strong> nodes</span>
            <span>•</span>
            <span>Taxonomy: <strong className="text-neutral-900">{stats.total_nodes}</strong> skills</span>
          </div>
        )}
      </div>

      {/* Center: Search & Auto-complete */}
      <div className="flex-1 max-w-md mx-4 relative" ref={searchRef}>
        <div className="relative">
          <Search className="w-4 h-4 text-neutral-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={() => query.trim() && setShowDropdown(true)}
            placeholder="Search or place any skill (e.g. Python, Robotics)..."
            className="w-full pl-9 pr-8 py-1.5 rounded-xl bg-neutral-50 border border-neutral-300 text-xs text-neutral-900 placeholder-neutral-400 focus:outline-none focus:ring-2 focus:ring-neutral-900 focus:border-neutral-900 transition-all"
          />
          {isSearching && (
            <Loader2 className="w-3.5 h-3.5 text-neutral-500 animate-spin absolute right-3 top-1/2 -translate-y-1/2" />
          )}
        </div>

        {/* Dropdown Results */}
        {showDropdown && query.trim() && (
          <div className="absolute top-full left-0 right-0 mt-2 bg-white border border-neutral-200 rounded-xl shadow-xl overflow-hidden z-50 divide-y divide-neutral-100 max-h-80 overflow-y-auto">
            {searchResults.map((item) => (
              <div
                key={item.id}
                onClick={() => {
                  onSelectSearchResult(item);
                  setShowDropdown(false);
                  setQuery('');
                }}
                className="p-2.5 hover:bg-neutral-50 cursor-pointer flex items-center justify-between transition-colors group"
              >
                <div className="min-w-0 pr-2">
                  <p className="text-xs font-semibold text-neutral-900 group-hover:text-neutral-950 truncate">
                    {item.label}
                  </p>
                  <p className="text-[10px] text-neutral-400 truncate">
                    {item.category} • Match: {item.similarity_score}%
                  </p>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  <span className="text-[10px] font-mono text-neutral-400">
                    deg:{item.in_degree + item.out_degree}
                  </span>
                  {item.is_ground_truth ? (
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-neutral-100 text-neutral-700 border border-neutral-200">
                      Ground Truth
                    </span>
                  ) : (
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-neutral-200 text-neutral-800 border border-neutral-300">
                      Synthesized
                    </span>
                  )}
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-neutral-900 text-white font-medium flex items-center gap-0.5">
                    <Plus className="w-2.5 h-2.5" /> Place
                  </span>
                </div>
              </div>
            ))}

            {/* Custom skill option */}
            <div
              onClick={() => {
                onAddCustomSkill(query.trim());
                setShowDropdown(false);
                setQuery('');
              }}
              className="p-2.5 bg-neutral-50 hover:bg-neutral-100 cursor-pointer flex items-center justify-between text-xs text-neutral-900 font-medium transition-colors"
            >
              <div className="flex items-center gap-2">
                <Plus className="w-3.5 h-3.5 text-neutral-600" />
                <span>Place custom skill: <strong>"{query.trim()}"</strong></span>
              </div>
              <span className="text-[10px] px-2 py-0.5 rounded bg-neutral-900 border border-neutral-900 text-white font-semibold">
                + Add
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Right: Pathway Synthesizer Bar & Actions */}
      <div className="flex items-center gap-2.5 shrink-0">
        {/* Pathway Synthesizer Status Pill */}
        <div className="hidden lg:flex items-center gap-1.5 px-3 py-1 rounded-xl bg-neutral-50 border border-neutral-200 text-xs">
          <div className="flex items-center gap-1 font-mono text-[11px]">
            <span className="text-neutral-900 font-medium flex items-center gap-0.5">
              <Zap className="w-3 h-3 text-neutral-800" />
              {startSkill ? startSkill.label : 'Select Start'}
            </span>
            <span className="text-neutral-400">➔</span>
            <span className="text-neutral-900 font-medium flex items-center gap-0.5">
              <Star className="w-3 h-3 text-neutral-800" />
              {goalSkill ? goalSkill.label : 'Select Goal'}
            </span>
          </div>

          {(startSkill || goalSkill) && (
            <button
              onClick={onClearBridge}
              className="text-[10px] text-neutral-500 hover:text-neutral-900 ml-1 underline"
            >
              Clear
            </button>
          )}

          <button
            onClick={onBridgeSkills}
            disabled={!startSkill || !goalSkill || isBridging}
            className="ml-1.5 px-2.5 py-1 rounded-lg bg-neutral-900 hover:bg-neutral-800 text-white font-semibold text-xs flex items-center gap-1.5 shadow-sm transition-all disabled:opacity-40"
          >
            {isBridging ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                Synthesizing...
              </>
            ) : (
              <>
                <Route className="w-3.5 h-3.5" />
                Bridge Pathway
              </>
            )}
          </button>
        </div>

        {/* Multi-Skill Suggestion: What Can I Make? */}
        {nodeCount > 0 && onSuggestNextSteps && (
          <button
            onClick={onSuggestNextSteps}
            disabled={isSuggestingMulti}
            className="px-3 py-1.5 rounded-xl bg-neutral-900 hover:bg-neutral-800 text-white font-semibold text-xs flex items-center gap-1.5 shadow-sm transition-all disabled:opacity-40 cursor-pointer"
            title="Suggest potential next steps and emergent skills you can make from your current skills"
          >
            {isSuggestingMulti ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Suggesting...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-3.5 h-3.5 text-neutral-300" />
                <span>What Can I Make?</span>
              </>
            )}
          </button>
        )}

        {/* Resume / Skills Ingestion Modal trigger */}
        <button
          onClick={onOpenResumeModal}
          className="p-2 rounded-xl bg-white hover:bg-neutral-100 border border-neutral-300 text-neutral-700 hover:text-neutral-950 flex items-center gap-1.5 text-xs font-medium transition-all shadow-sm"
          title="Upload Resume or Skills"
        >
          <UploadCloud className="w-4 h-4 text-neutral-700" />
          <span className="hidden sm:inline">Resume</span>
        </button>

        {/* Layout Direction Toggle */}
        <button
          onClick={onToggleLayout}
          className="p-2 rounded-xl bg-white hover:bg-neutral-100 border border-neutral-300 text-neutral-700 hover:text-neutral-950 flex items-center gap-1 text-xs font-medium transition-all shadow-sm"
          title={`Switch to ${layoutDirection === 'TB' ? 'Horizontal (LR)' : 'Vertical (TB)'} Layout`}
        >
          <Layers className="w-4 h-4 text-neutral-700" />
          <span className="hidden sm:inline">{layoutDirection}</span>
        </button>

        {/* Reset View */}
        <button
          onClick={onResetView}
          className="p-2 rounded-xl bg-white hover:bg-neutral-100 border border-neutral-300 text-neutral-600 hover:text-neutral-950 transition-all shadow-sm"
          title="Reset and fit view"
        >
          <RefreshCw className="w-4 h-4" />
        </button>

        {/* Clear Canvas */}
        {nodeCount > 0 && (
          <button
            onClick={onClearCanvas}
            className="p-2 rounded-xl bg-neutral-100 hover:bg-neutral-200 border border-neutral-300 text-neutral-700 hover:text-neutral-950 transition-all"
            title="Clear all nodes from canvas"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        )}
      </div>
    </header>
  );
}
