import React, { memo } from 'react';
import { Handle, Position } from '@xyflow/react';

function SkillNodeComponent({ data, selected }) {
  const isGhost = Boolean(data.is_ghost || data.isGhost);
  const isStart = data.is_start;
  const isGoal = data.is_goal;
  const isPathNode = data.is_path_node;
  const isUserSkill = data.is_user_skill;
  const isSynthesized = Boolean(data.is_synthesized);

  // Strict Monochrome Palette & Circular Geometric Aesthetic
  let circleStyles = '';
  let textStyles = '';
  let subtextStyles = '';

  if (isGhost) {
    // Ghost Nodes: Light gray backgrounds (#e5e7eb / #f3f4f6) with dashed medium-gray borders (#9ca3af) and dark gray text
    circleStyles =
      'bg-neutral-100 border-2 border-dashed border-neutral-400 text-neutral-600 hover:border-neutral-700 hover:bg-neutral-200/90 shadow-sm opacity-85 hover:opacity-100 transition-all';
    textStyles = 'text-neutral-700 font-medium';
    subtextStyles = 'text-neutral-400';
  } else if (isStart) {
    // Start Node: Solid black background with pure white text and stark ring
    circleStyles =
      'bg-neutral-950 border-2 border-neutral-950 text-white shadow-md ring-2 ring-neutral-400 ring-offset-2';
    textStyles = 'text-white font-bold';
    subtextStyles = 'text-neutral-300';
  } else if (isGoal) {
    // Goal Node: Dark slate background with pure white text and ring
    circleStyles =
      'bg-neutral-900 border-2 border-neutral-800 text-white shadow-md ring-2 ring-neutral-950 ring-offset-2';
    textStyles = 'text-white font-bold';
    subtextStyles = 'text-neutral-300';
  } else if (isPathNode) {
    // Path Node: Inverted dark slate background
    circleStyles =
      'bg-neutral-800 border-2 border-neutral-950 text-white shadow-md ring-1 ring-neutral-400';
    textStyles = 'text-white font-semibold';
    subtextStyles = 'text-neutral-300';
  } else if (isSynthesized) {
    // Emergent Synthesized Node: Crisp dark slate background with white text and monochrome double ring
    circleStyles =
      'bg-neutral-900 border-2 border-neutral-700 text-white shadow-lg ring-1 ring-neutral-400 ring-offset-1 hover:border-neutral-500';
    textStyles = 'text-white font-bold';
    subtextStyles = 'text-neutral-300';
  } else if (isUserSkill) {
    // Mastered / User skill: Stark white background with thick black border
    circleStyles =
      'bg-white border-[2.5px] border-neutral-950 text-neutral-950 shadow-sm hover:shadow-md';
    textStyles = 'text-neutral-950 font-bold';
    subtextStyles = 'text-neutral-500';
  } else {
    // Solidified Nodes: Stark white background with crisp black border and black text
    circleStyles =
      'bg-white border-2 border-neutral-900 text-neutral-900 hover:border-neutral-950 hover:shadow-md';
    textStyles = 'text-neutral-900 font-semibold';
    subtextStyles = 'text-neutral-500';
  }

  if (selected && !isGhost) {
    circleStyles += ' ring-2 ring-neutral-950 ring-offset-2 shadow-lg';
  }

  return (
    <div
      className={`group relative w-[130px] h-[130px] rounded-full flex flex-col items-center justify-center p-3 text-center transition-all duration-200 cursor-pointer select-none ${circleStyles}`}
      title={isGhost ? 'Preview: Click to solidify this pathway step' : data.label}
    >
      {/* Top & Bottom Handles (smooth curved edge routing) */}
      <Handle
        type="target"
        position={Position.Top}
        className={`!w-2 !h-2 !border !border-white !rounded-full ${
          isGhost ? '!bg-neutral-400' : '!bg-neutral-900'
        }`}
      />
      <Handle
        type="source"
        position={Position.Bottom}
        className={`!w-2 !h-2 !border !border-white !rounded-full ${
          isGhost ? '!bg-neutral-400' : '!bg-neutral-900'
        }`}
      />
      {/* Horizontal Handles (for Left-Right layout) */}
      <Handle
        type="target"
        position={Position.Left}
        id="left"
        className={`!w-2 !h-2 !border !border-white !rounded-full ${
          isGhost ? '!bg-neutral-400' : '!bg-neutral-900'
        }`}
      />
      <Handle
        type="source"
        position={Position.Right}
        id="right"
        className={`!w-2 !h-2 !border !border-white !rounded-full ${
          isGhost ? '!bg-neutral-400' : '!bg-neutral-900'
        }`}
      />

      {/* Role / Preview Status Pill */}
      <div className="mb-0.5">
        {isGhost ? (
          <span className="text-[9px] uppercase tracking-wider font-mono font-medium px-1.5 py-0.5 rounded-full border border-dashed border-neutral-400 text-neutral-500 bg-neutral-200/60">
            Preview
          </span>
        ) : isStart ? (
          <span className="text-[9px] uppercase tracking-wider font-mono font-semibold px-1.5 py-0.5 rounded-full bg-white/20 text-white">
            Start
          </span>
        ) : isGoal ? (
          <span className="text-[9px] uppercase tracking-wider font-mono font-semibold px-1.5 py-0.5 rounded-full bg-white/20 text-white">
            Goal
          </span>
        ) : isUserSkill ? (
          <span className="text-[9px] uppercase tracking-wider font-mono px-1 py-0.5 rounded-full bg-neutral-100 text-neutral-800">
            Mastered
          </span>
        ) : isSynthesized ? (
          <span className="text-[9px] uppercase tracking-wider font-mono font-semibold px-1.5 py-0.5 rounded-full bg-white/20 text-white">
            Emergent
          </span>
        ) : null}
      </div>

      {/* Centered, Wrapped Skill Label */}
      <h3 className={`text-xs leading-tight line-clamp-3 break-words px-1 max-w-[110px] ${textStyles}`}>
        {data.label}
      </h3>

      {/* Category Subtitle */}
      {data.category && (
        <span className={`text-[9px] uppercase tracking-tight line-clamp-1 mt-0.5 max-w-[95px] ${subtextStyles}`}>
          {data.category}
        </span>
      )}

      {/* Ghost Solidification CTA hint on hover */}
      {isGhost && (
        <div className="absolute -bottom-2 inset-x-0 flex justify-center pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity">
          <span className="text-[9px] bg-neutral-950 text-white px-2 py-0.5 rounded-full shadow-md font-medium whitespace-nowrap">
            + Solidify
          </span>
        </div>
      )}
    </div>
  );
}

export default memo(SkillNodeComponent);
