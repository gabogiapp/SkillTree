import React, { useState } from 'react';
import { X, UploadCloud, CheckCircle2, Star, Sparkles, Loader2, ArrowRight } from 'lucide-react';
import { uploadResume } from '../api/client';

const SAMPLE_RESUMES = {
  software: `Skills: Python, JavaScript, Docker, Git, SQL, REST APIs, System Architecture, Linux, CI/CD pipelines. Experience in backend services and microservices.`,
  biomedical: `Proficient in toxicology, clinical trial data, pharmacology, biochemistry, laboratory quality control, medical devices materials, pathology research.`,
  data: `Skills: Data analysis, Python, Machine learning, SQL, statistics, database management, normalise data, ETL pipelines, unstructured data.`,
};

export default function ResumeModal({
  isOpen,
  onClose,
  onMatchedSkillsLoaded,
  onSelectGoalSkill,
}) {
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState(null);
  const [error, setError] = useState('');

  if (!isOpen) return null;

  async function handleAnalyze() {
    if (!text.trim()) {
      setError('Please paste your resume or skill list first.');
      return;
    }
    setError('');
    setLoading(true);
    try {
      const data = await uploadResume(text);
      setResponse(data);
      if (data.matched_skills?.length) {
        onMatchedSkillsLoaded(data.matched_skills);
      }
    } catch (err) {
      setError(err.message || 'Failed to analyze resume');
    } finally {
      setLoading(false);
    }
  }

  function handleSelectGoal(goalNode) {
    onSelectGoalSkill(goalNode);
    onClose();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm select-none">
      <div className="relative w-full max-w-2xl bg-white border border-neutral-200 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
        {/* Modal Header */}
        <div className="p-4 border-b border-neutral-200 flex items-center justify-between bg-neutral-50">
          <div className="flex items-center gap-2">
            <UploadCloud className="w-5 h-5 text-neutral-800" />
            <h3 className="font-bold text-sm text-neutral-900">
              Resume & Background Skill Ingestion
            </h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-neutral-400 hover:text-neutral-900 hover:bg-neutral-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-5 overflow-y-auto space-y-4">
          <p className="text-xs text-neutral-500 leading-relaxed">
            Paste your resume summary, job history, or skill list. We match your capabilities into the ground-truth skill graph, anchor your mastered nodes, and recommend high-impact frontier career goals.
          </p>

          {/* Quick Presets */}
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-neutral-500 font-medium">Try Sample:</span>
            <button
              onClick={() => setText(SAMPLE_RESUMES.software)}
              className="text-[11px] px-2 py-0.5 rounded bg-neutral-100 hover:bg-neutral-200 text-neutral-700 border border-neutral-300 transition-all"
            >
              Software Engineering
            </button>
            <button
              onClick={() => setText(SAMPLE_RESUMES.data)}
              className="text-[11px] px-2 py-0.5 rounded bg-neutral-100 hover:bg-neutral-200 text-neutral-700 border border-neutral-300 transition-all"
            >
              Data Science
            </button>
            <button
              onClick={() => setText(SAMPLE_RESUMES.biomedical)}
              className="text-[11px] px-2 py-0.5 rounded bg-neutral-100 hover:bg-neutral-200 text-neutral-700 border border-neutral-300 transition-all"
            >
              Biomedical
            </button>
          </div>

          {/* Text Area */}
          <div className="space-y-1">
            <textarea
              rows={6}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Paste resume text or comma-separated skills here..."
              className="w-full p-3 rounded-xl bg-neutral-50 border border-neutral-300 text-xs text-neutral-900 placeholder-neutral-400 focus:outline-none focus:ring-2 focus:ring-neutral-900 focus:border-neutral-900 font-mono"
            />
            {error && <p className="text-xs text-neutral-900 font-semibold">{error}</p>}
          </div>

          {/* Results Display */}
          {response && (
            <div className="space-y-4 pt-3 border-t border-neutral-200">
              {/* Matched Foundations */}
              <div>
                <div className="flex items-center justify-between text-xs font-semibold text-neutral-900 mb-2">
                  <span className="flex items-center gap-1.5">
                    <CheckCircle2 className="w-4 h-4 text-neutral-800" />
                    Matched Ground-Truth Skills ({response.matched_skills.length})
                  </span>
                </div>
                <div className="flex flex-wrap gap-1.5 max-h-36 overflow-y-auto p-2 bg-neutral-50 rounded-xl border border-neutral-200">
                  {response.matched_skills.map((skill) => (
                    <span
                      key={skill.id}
                      className="px-2 py-0.5 rounded-full bg-white text-neutral-800 text-[11px] font-medium border border-neutral-300 shadow-sm"
                    >
                      {skill.label}
                    </span>
                  ))}
                </div>
              </div>

              {/* Recommended Career Goals */}
              {response.recommended_goals?.length > 0 && (
                <div>
                  <div className="flex items-center justify-between text-xs font-semibold text-neutral-900 mb-2">
                    <span className="flex items-center gap-1.5">
                      <Star className="w-4 h-4 text-neutral-800" />
                      Recommended High-Impact Frontier Goals
                    </span>
                    <span className="text-[10px] text-neutral-400">Click to set target</span>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {response.recommended_goals.map((goal) => (
                      <div
                        key={goal.id}
                        onClick={() => handleSelectGoal(goal)}
                        className="p-2.5 rounded-xl bg-neutral-50 hover:bg-neutral-100 border border-neutral-200 hover:border-neutral-400 cursor-pointer flex items-center justify-between text-xs transition-all group"
                      >
                        <div className="min-w-0 pr-2">
                          <p className="font-semibold text-neutral-900 group-hover:text-neutral-950 truncate">
                            {goal.label}
                          </p>
                          <p className="text-[10px] text-neutral-500 font-mono">
                            Unlocks: {goal.out_degree} downstream skills
                          </p>
                        </div>
                        <ArrowRight className="w-4 h-4 text-neutral-400 group-hover:text-neutral-900 shrink-0" />
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="p-4 border-t border-neutral-200 bg-neutral-50 flex items-center justify-between">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl text-neutral-600 hover:text-neutral-900 text-xs font-medium hover:bg-neutral-100 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleAnalyze}
            disabled={loading}
            className="px-5 py-2 rounded-xl bg-neutral-950 hover:bg-neutral-800 text-white font-semibold text-xs flex items-center gap-2 shadow-sm transition-all disabled:opacity-50"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Parsing Taxonomy...
              </>
            ) : (
              <>
                <UploadCloud className="w-4 h-4" />
                Analyze & Ingest Skills
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
