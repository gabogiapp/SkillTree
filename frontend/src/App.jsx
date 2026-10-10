import React, { useState, useEffect, useCallback } from 'react';
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  useReactFlow,
  ReactFlowProvider,
  MarkerType,
} from '@xyflow/react';
import { Plus, UploadCloud, Compass, ArrowRight, Sparkles, Loader2 } from 'lucide-react';

import SkillNodeComponent from './components/SkillNodeComponent';
import Sidebar from './components/Sidebar';
import Toolbar from './components/Toolbar';
import ResumeModal from './components/ResumeModal';
import { getLayoutedElements } from './utils/layout';
import {
  fetchStats,
  fetchSkill,
  fetchNeighbors,
  bridgeSkills,
  expandSkill,
  createCustomSkill,
  synthesizeSkills,
  suggestNextSteps,
} from './api/client';

const nodeTypes = {
  skill: SkillNodeComponent,
};

function FlowCanvas() {
  // Empty initial canvas state
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const { fitView, setCenter } = useReactFlow();

  const [stats, setStats] = useState(null);
  const [selectedNode, setSelectedNode] = useState(null);
  const [startSkill, setStartSkill] = useState(null);
  const [goalSkill, setGoalSkill] = useState(null);
  const [activePathway, setActivePathway] = useState(null);
  const [userSkillIds, setUserSkillIds] = useState(new Set());

  const [isBridging, setIsBridging] = useState(false);
  const [isExpanding, setIsExpanding] = useState(false);
  const [isSuggestingMulti, setIsSuggestingMulti] = useState(false);
  const [layoutDirection, setLayoutDirection] = useState('TB');
  const [isResumeModalOpen, setIsResumeModalOpen] = useState(false);
  const [notification, setNotification] = useState(null);

  // Quick starter input for empty state
  const [starterInput, setStarterInput] = useState('');

  const showToast = (message, type = 'info') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 3500);
  };

  // Convert raw node to circular React Flow node
  const formatNode = useCallback(
    (n, extra = {}) => {
      const isStart = startSkill?.id === n.id;
      const isGoal = goalSkill?.id === n.id;
      const isUserSkill = userSkillIds.has(n.id);
      const isGhost = Boolean(extra.is_ghost || n.is_ghost || n.isGhost);
      const isSynthesized = Boolean(extra.is_synthesized || n.is_synthesized);
      return {
        id: n.id,
        type: 'skill',
        position: extra.position || {
          x: (nodes.length % 3) * 180 + 100,
          y: Math.floor(nodes.length / 3) * 180 + 100,
        },
        data: {
          ...n,
          is_start: isStart,
          is_goal: isGoal,
          is_user_skill: isUserSkill,
          is_ghost: isGhost,
          is_synthesized: isSynthesized,
          ...extra,
        },
      };
    },
    [startSkill?.id, goalSkill?.id, userSkillIds, nodes.length]
  );

  // Format edges with smooth sweeping Bezier curves and strict monochrome styling
  const formatEdge = useCallback((e, isPath = false, isGhost = false) => {
    const isDashed = isGhost || Boolean(e.is_ghost || e.data?.is_ghost);
    return {
      id: `e-${e.source}-${e.target}`,
      source: e.source,
      target: e.target,
      type: 'default', // Smooth sweeping Bezier curve
      animated: isDashed || isPath,
      label: e.relation || '',
      labelStyle: { fill: '#6b7280', fontSize: 9, fontFamily: 'monospace' },
      labelBgStyle: { fill: '#f9fafb', fillOpacity: 0.9 },
      style: {
        stroke: isDashed ? '#9ca3af' : isPath ? '#111827' : '#4b5563',
        strokeWidth: isPath ? 2.5 : 1.5,
        strokeDasharray: isDashed ? '5 5' : undefined,
      },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: isDashed ? '#9ca3af' : isPath ? '#111827' : '#4b5563',
      },
      data: {
        is_ghost: isDashed,
      },
    };
  }, []);

  // Fetch initial high-level taxonomy stats
  useEffect(() => {
    fetchStats()
      .then(setStats)
      .catch((err) => console.error('Failed to fetch taxonomy stats', err));
  }, []);

  // Synchronize role highlights
  useEffect(() => {
    setNodes((currentNodes) =>
      currentNodes.map((n) => ({
        ...n,
        data: {
          ...n.data,
          is_start: startSkill?.id === n.id,
          is_goal: goalSkill?.id === n.id,
          is_user_skill: userSkillIds.has(n.id),
          is_path_node: activePathway?.nodes?.some((pn) => pn.id === n.id),
        },
      }))
    );
  }, [startSkill?.id, goalSkill?.id, userSkillIds, activePathway]);

  // Relayout graph elements with Dagre
  const handleRelayout = useCallback(
    (dir = layoutDirection) => {
      setNodes((currNodes) => {
        if (currNodes.length === 0) return [];
        setEdges((currEdges) => {
          const layouted = getLayoutedElements(currNodes, currEdges, dir);
          return layouted.edges;
        });
        const layouted = getLayoutedElements(currNodes, edges, dir);
        return layouted.nodes;
      });
      setTimeout(() => fitView({ padding: 0.25, duration: 600 }), 60);
    },
    [layoutDirection, edges, fitView]
  );

  // Add a permanent skill node onto canvas
  const placeSkillOnCanvas = async (skillNode) => {
    const existing = nodes.find((n) => n.id === skillNode.id);
    if (existing) {
      if (existing.data?.is_ghost) {
        handleSolidifyGhostNode(existing.id);
      } else {
        setSelectedNode(existing.data);
        setCenter(existing.position.x + 65, existing.position.y + 65, { zoom: 1.2, duration: 500 });
        showToast(`'${skillNode.label}' is already on canvas`, 'info');
      }
      return;
    }

    // Check neighbors to link with already placed nodes on canvas
    let newEdges = [];
    try {
      const nbrs = await fetchNeighbors(skillNode.id);
      const existingIds = new Set(nodes.filter((n) => !n.data.is_ghost).map((n) => n.id));

      nbrs.prerequisites.forEach((p) => {
        if (existingIds.has(p.node.id)) {
          newEdges.push({ source: p.node.id, target: skillNode.id, relation: p.relation, is_ground_truth: true });
        }
      });
      nbrs.unlocked.forEach((u) => {
        if (existingIds.has(u.node.id)) {
          newEdges.push({ source: skillNode.id, target: u.node.id, relation: u.relation, is_ground_truth: true });
        }
      });
    } catch {
      // Ignore neighbor lookup failure
    }

    const newNode = formatNode(skillNode, { is_ghost: false });
    setNodes((curr) => [...curr.filter((n) => !n.data.is_ghost), newNode]);
    if (newEdges.length > 0) {
      setEdges((curr) => [
        ...curr.filter((e) => !e.data?.is_ghost),
        ...newEdges.map((e) => formatEdge(e, false, false)),
      ]);
    }

    setSelectedNode(skillNode);
    showToast(`Placed '${skillNode.label}' on canvas`, 'success');
    setTimeout(() => {
      if (nodes.length > 0) handleRelayout();
      else fitView({ padding: 0.3, duration: 500 });
    }, 100);
  };

  // Add custom skill
  const handleAddCustomSkill = async (label) => {
    if (!label || !label.trim()) return;
    try {
      const skillNode = await createCustomSkill(label.trim());
      await placeSkillOnCanvas(skillNode);
    } catch (err) {
      showToast(err.message || 'Failed to add skill', 'error');
    }
  };

  // Clear canvas completely
  const handleClearCanvas = () => {
    setNodes([]);
    setEdges([]);
    setSelectedNode(null);
    setStartSkill(null);
    setGoalSkill(null);
    setActivePathway(null);
    showToast('Canvas cleared.', 'info');
  };

  // -------------------------------------------------------------------------
  // 1. Ghost Node Expansion Interaction
  // -------------------------------------------------------------------------

  /**
   * Explores potential next steps and renders them as translucent, dashed Ghost Nodes.
   */
  const handleExploreNextSteps = async (skillId) => {
    if (isExpanding) return;
    setIsExpanding(true);

    try {
      // Query backend for potential next steps
      const res = await expandSkill(skillId, 3);

      // Locate parent node position
      const parentNode = nodes.find((n) => n.id === skillId);
      const px = parentNode ? parentNode.position.x : 200;
      const py = parentNode ? parentNode.position.y : 200;

      // Filter for items not already solid on canvas
      const existingSolidIds = new Set(nodes.filter((n) => !n.data.is_ghost).map((n) => n.id));
      const newlyDiscoveredNodes = res.new_nodes.filter((n) => !existingSolidIds.has(n.id));

      if (newlyDiscoveredNodes.length === 0) {
        showToast('All discovered skills are already active on canvas.', 'info');
        return;
      }

      // Format as Ghost Nodes branching off the selected node
      const ghostNodes = newlyDiscoveredNodes.map((n, idx) =>
        formatNode(n, {
          is_ghost: true,
          ghost_source_id: skillId,
          position: {
            x: px + (idx - 1) * 160,
            y: py + 180,
          },
        })
      );

      // Format corresponding Ghost Edges (animated dashed lines)
      const ghostEdges = [];
      res.new_edges.forEach((e) => {
        // Only add edge if it connects to at least one ghost node
        const isConnectedToGhost =
          ghostNodes.some((gn) => gn.id === e.source || gn.id === e.target);
        if (isConnectedToGhost) {
          ghostEdges.push(formatEdge(e, false, true));
        }
      });

      // Clear any prior unsolidified ghost nodes from other explorations
      setNodes((currNodes) => {
        const solidNodes = currNodes.filter((n) => !n.data.is_ghost);
        return [...solidNodes, ...ghostNodes];
      });

      setEdges((currEdges) => {
        const solidEdges = currEdges.filter((e) => !e.data?.is_ghost);
        return [...solidEdges, ...ghostEdges];
      });

      showToast(`Previewing ${ghostNodes.length} ghost pathways. Click a ghost node to solidify.`, 'info');
      setTimeout(() => handleRelayout(), 100);
    } catch (err) {
      showToast(err.message || 'Path exploration failed', 'error');
    } finally {
      setIsExpanding(false);
    }
  };

  /**
   * Solidifies a Ghost Node: turns it into a permanent solid node,
   * converts its edge to solid, and clears unselected ghost siblings.
   */
  const handleSolidifyGhostNode = useCallback(
    (ghostNodeId) => {
      let solidifiedData = null;

      setNodes((currNodes) => {
        return currNodes
          .filter((n) => {
            // Keep all already-solid nodes and the one being solidified
            if (!n.data.is_ghost) return true;
            return n.id === ghostNodeId;
          })
          .map((n) => {
            if (n.id === ghostNodeId) {
              solidifiedData = { ...n.data, is_ghost: false };
              return {
                ...n,
                data: solidifiedData,
              };
            }
            return n;
          });
      });

      setEdges((currEdges) => {
        return currEdges
          .filter((e) => {
            // Keep edges connecting to solid nodes or the newly solidified node
            if (!e.data?.is_ghost) return true;
            return e.source === ghostNodeId || e.target === ghostNodeId;
          })
          .map((e) => {
            if (e.source === ghostNodeId || e.target === ghostNodeId) {
              return {
                ...e,
                animated: false,
                style: {
                  ...e.style,
                  stroke: '#4b5563',
                  strokeDasharray: undefined,
                },
                markerEnd: {
                  type: MarkerType.ArrowClosed,
                  color: '#4b5563',
                },
                data: { is_ghost: false },
              };
            }
            return e;
          });
      });

      if (solidifiedData) {
        setSelectedNode(solidifiedData);
        showToast(`Solidified '${solidifiedData.label}' into your skill pathway.`, 'success');
      }

      fetchStats().then(setStats);
      setTimeout(() => handleRelayout(), 100);
    },
    [handleRelayout]
  );

  // Dismiss unsolidified ghost nodes on background canvas click
  const onPaneClick = useCallback(() => {
    setNodes((curr) => {
      const hasGhosts = curr.some((n) => n.data.is_ghost);
      if (!hasGhosts) return curr;
      return curr.filter((n) => !n.data.is_ghost);
    });
    setEdges((curr) => {
      const hasGhostEdges = curr.some((e) => e.data?.is_ghost);
      if (!hasGhostEdges) return curr;
      return curr.filter((e) => !e.data?.is_ghost);
    });
  }, [setNodes, setEdges]);

  // Node selection & Ghost solidification click handler
  const onNodeClick = useCallback(
    (_, node) => {
      if (node.data?.is_ghost) {
        // User clicked a ghost node -> Solidify it!
        handleSolidifyGhostNode(node.id);
      } else {
        // User clicked a solid node -> Select it and dismiss previous ghosts
        setSelectedNode(node.data);
        setNodes((curr) => curr.filter((n) => !n.data.is_ghost));
        setEdges((curr) => curr.filter((e) => !e.data?.is_ghost));
      }
    },
    [handleSolidifyGhostNode, setNodes, setEdges]
  );

  // Double click solid node to trigger exploration
  const onNodeDoubleClick = useCallback(
    (_, node) => {
      if (!node.data?.is_ghost) {
        handleExploreNextSteps(node.id);
      }
    },
    [handleExploreNextSteps]
  );

  // -------------------------------------------------------------------------
  // Multi-Skill Discovery: Suggest Dotted Next Steps from Current Skills
  // -------------------------------------------------------------------------
  const handleExploreMultiSkillNextSteps = useCallback(
    async (requestedIds = null) => {
      if (isSuggestingMulti) return;

      const solidNodes = nodes.filter((n) => !n.data?.is_ghost);
      if (solidNodes.length === 0) {
        showToast('Please add skills to the canvas first to discover what you can make.', 'info');
        return;
      }

      // If specific IDs were passed, use them; otherwise explore from all solid skills on canvas
      const targetIds =
        Array.isArray(requestedIds) && requestedIds.length > 0
          ? requestedIds
          : solidNodes.map((n) => n.id);

      setIsSuggestingMulti(true);
      showToast(
        `Analyzing ${targetIds.length} skills to suggest what you can make next...`,
        'info'
      );

      try {
        const res = await suggestNextSteps(targetIds, 3);
        const existingSolidIds = new Set(solidNodes.map((n) => n.id));
        const newlyDiscoveredNodes = res.new_nodes.filter((n) => !existingSolidIds.has(n.id));

        if (newlyDiscoveredNodes.length === 0) {
          showToast('All suggested next steps are already active on the canvas.', 'info');
          return;
        }

        // Compute average center / placement below the contributing source skills
        const sourceNodes = solidNodes.filter((n) => targetIds.includes(n.id));
        const avgX =
          sourceNodes.length > 0
            ? sourceNodes.reduce((sum, n) => sum + n.position.x, 0) / sourceNodes.length
            : 250;
        const maxY =
          sourceNodes.length > 0
            ? Math.max(...sourceNodes.map((n) => n.position.y))
            : 200;

        // Render suggested skills as Dotted Ghost Nodes
        const ghostNodes = newlyDiscoveredNodes.map((n, idx) =>
          formatNode(n, {
            is_ghost: true,
            is_synthesized: true,
            position: {
              x: avgX + (idx - (newlyDiscoveredNodes.length - 1) / 2) * 175,
              y: maxY + 180,
            },
          })
        );

        // Render connecting dashed ghost edges from the prerequisite skills to ghost nodes
        const ghostEdges = [];
        res.new_edges.forEach((e) => {
          const connectsToGhost = ghostNodes.some((gn) => gn.id === e.target || gn.id === e.source);
          if (connectsToGhost) {
            ghostEdges.push(formatEdge(e, false, true));
          }
        });

        // Retain current solid nodes, clear previous unsolidified ghosts, add new ghost previews
        setNodes((curr) => [...curr.filter((n) => !n.data?.is_ghost), ...ghostNodes]);
        setEdges((curr) => [...curr.filter((e) => !e.data?.is_ghost), ...ghostEdges]);

        showToast(
          `Previewing ${ghostNodes.length} suggested next steps. Click any dotted node to solidify into your tree.`,
          'info'
        );
        fetchStats().then(setStats);
        setTimeout(() => handleRelayout(), 100);
      } catch (err) {
        showToast(err.message || 'Failed to discover next steps', 'error');
      } finally {
        setIsSuggestingMulti(false);
      }
    },
    [nodes, isSuggestingMulti, formatNode, formatEdge, handleRelayout]
  );

  // Bridge Pathway Synthesizer
  const handleBridgeSkills = async () => {
    if (!startSkill || !goalSkill || isBridging) return;
    setIsBridging(true);
    try {
      const res = await bridgeSkills(startSkill.id, goalSkill.id);
      setActivePathway(res);
      showToast(res.message, 'success');

      // Clear any preview ghosts
      setNodes((currNodes) => {
        const solidMap = new Map(currNodes.filter((n) => !n.data.is_ghost).map((n) => [n.id, n]));
        res.nodes.forEach((n) => {
          if (!solidMap.has(n.id)) {
            solidMap.set(n.id, formatNode(n, { is_path_node: true, is_ghost: false }));
          } else {
            const existing = solidMap.get(n.id);
            solidMap.set(n.id, {
              ...existing,
              data: { ...existing.data, is_path_node: true, is_ghost: false },
            });
          }
        });
        return Array.from(solidMap.values());
      });

      setEdges((currEdges) => {
        const edgeMap = new Map(currEdges.filter((e) => !e.data?.is_ghost).map((e) => [e.id, e]));
        res.edges.forEach((e) => {
          const edgeId = `e-${e.source}-${e.target}`;
          edgeMap.set(edgeId, formatEdge(e, true, false));
        });
        return Array.from(edgeMap.values());
      });

      fetchStats().then(setStats);
      setTimeout(() => {
        handleRelayout();
        fitView({ padding: 0.25, duration: 800 });
      }, 100);
    } catch (err) {
      showToast(err.message || 'Bridge pathway synthesis failed', 'error');
    } finally {
      setIsBridging(false);
    }
  };

  // Select node from search or sidebar list
  const handleSelectNodeById = async (nodeId) => {
    const existing = nodes.find((n) => n.id === nodeId);
    if (existing) {
      if (existing.data?.is_ghost) {
        handleSolidifyGhostNode(existing.id);
      } else {
        setSelectedNode(existing.data);
        setCenter(existing.position.x + 65, existing.position.y + 65, { zoom: 1.2, duration: 500 });
      }
    } else {
      try {
        const node = await fetchSkill(nodeId);
        await placeSkillOnCanvas(node);
      } catch (err) {
        showToast('Failed to fetch skill', 'error');
      }
    }
  };

  // Resume Ingestion callback
  const handleMatchedSkillsLoaded = (matchedList) => {
    const newSet = new Set(userSkillIds);
    matchedList.forEach((m) => newSet.add(m.id));
    setUserSkillIds(newSet);

    if (matchedList.length > 0 && !startSkill) {
      setStartSkill(matchedList[0]);
    }

    setNodes((currNodes) => {
      const map = new Map(currNodes.filter((n) => !n.data.is_ghost).map((n) => [n.id, n]));
      matchedList.forEach((m) => {
        if (!map.has(m.id)) {
          map.set(m.id, formatNode(m, { is_user_skill: true, is_ghost: false }));
        }
      });
      return Array.from(map.values());
    });

    showToast(`Placed ${matchedList.length} skills from resume onto canvas`, 'success');
    setTimeout(() => {
      handleRelayout();
      fitView({ padding: 0.25, duration: 700 });
    }, 150);
  };

  return (
    <div className="w-screen h-screen flex flex-col bg-[#f9fafb] text-neutral-900 overflow-hidden font-sans">
      {/* Toast Notification */}
      {notification && (
        <div className="fixed top-20 left-1/2 -translate-x-1/2 z-50">
          <div
            className={`px-4 py-2 rounded-xl text-xs font-semibold shadow-xl border ${
              notification.type === 'error'
                ? 'bg-neutral-900 text-white border-neutral-700'
                : 'bg-neutral-950 text-white border-neutral-800'
            }`}
          >
            {notification.message}
          </div>
        </div>
      )}

      {/* Top Toolbar */}
      <Toolbar
        stats={stats}
        startSkill={startSkill}
        goalSkill={goalSkill}
        onClearBridge={() => {
          setStartSkill(null);
          setGoalSkill(null);
          setActivePathway(null);
        }}
        onBridgeSkills={handleBridgeSkills}
        isBridging={isBridging}
        onOpenResumeModal={() => setIsResumeModalOpen(true)}
        onSelectSearchResult={(item) => placeSkillOnCanvas(item)}
        onAddCustomSkill={handleAddCustomSkill}
        onClearCanvas={handleClearCanvas}
        layoutDirection={layoutDirection}
        onToggleLayout={() => {
          const next = layoutDirection === 'TB' ? 'LR' : 'TB';
          setLayoutDirection(next);
          handleRelayout(next);
        }}
        onResetView={() => fitView({ padding: 0.25, duration: 600 })}
        nodeCount={nodes.filter((n) => !n.data?.is_ghost).length}
        onSuggestNextSteps={() => handleExploreMultiSkillNextSteps()}
        isSuggestingMulti={isSuggestingMulti}
      />

      {/* Main Interactive Stage */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Canvas */}
        <div className="flex-1 h-full relative">
          {/* FLOATING ACTION: Discover What You Can Make from Current Skills */}
          {nodes.filter((n) => !n.data?.is_ghost).length >= 1 && (
            <div className="absolute top-4 left-1/2 -translate-x-1/2 z-20 pointer-events-auto">
              <button
                onClick={() => handleExploreMultiSkillNextSteps()}
                disabled={isSuggestingMulti}
                className="px-4 py-2 rounded-full bg-neutral-950 hover:bg-neutral-800 text-white text-xs font-semibold shadow-xl border border-neutral-700 flex items-center gap-2 transition-all hover:scale-105 active:scale-95 disabled:opacity-50 cursor-pointer"
              >
                {isSuggestingMulti ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin text-white" />
                    Exploring what you can make...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-3.5 h-3.5 text-white" />
                    What Can I Make With My Skills? ({nodes.filter((n) => !n.data?.is_ghost).length})
                  </>
                )}
              </button>
            </div>
          )}

          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={onNodeClick}
            onNodeDoubleClick={onNodeDoubleClick}
            onPaneClick={onPaneClick}
            nodeTypes={nodeTypes}
            minZoom={0.2}
            maxZoom={2.5}
            fitView
          >
            {/* Minimalist dot grid background */}
            <Background color="#e5e7eb" gap={24} size={1} />
            <Controls position="bottom-left" showInteractive={false} />
            <MiniMap
              position="bottom-right"
              nodeColor={(n) => {
                if (n.data?.is_ghost) return '#d1d5db';
                if (n.data?.is_synthesized) return '#171717';
                if (n.data?.is_start) return '#111827';
                if (n.data?.is_goal) return '#374151';
                if (n.data?.is_path_node) return '#1f2937';
                return '#111827';
              }}
              maskColor="rgba(249, 250, 251, 0.85)"
              nodeStrokeWidth={2}
            />
          </ReactFlow>

          {/* EMPTY STATE OVERLAY: Shown when canvas has 0 nodes */}
          {nodes.length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center p-4 pointer-events-none z-10">
              <div className="pointer-events-auto max-w-lg w-full p-8 rounded-3xl bg-white border border-neutral-200 shadow-2xl text-center space-y-5 animate-fade-in">
                <div className="w-14 h-14 mx-auto rounded-full bg-neutral-950 flex items-center justify-center text-white shadow-md">
                  <Compass className="w-7 h-7" />
                </div>

                <div>
                  <h2 className="text-xl font-bold text-neutral-900">
                    Skill Pathway Explorer
                  </h2>
                  <p className="text-xs text-neutral-500 mt-1.5 leading-relaxed">
                    Select foundational competencies or target career milestones to explore directional pathways. Preview ghost nodes and solidify your personal progression.
                  </p>
                </div>

                {/* Direct Input Field */}
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (starterInput.trim()) {
                      handleAddCustomSkill(starterInput);
                      setStarterInput('');
                    }
                  }}
                  className="flex gap-2"
                >
                  <input
                    type="text"
                    value={starterInput}
                    onChange={(e) => setStarterInput(e.target.value)}
                    placeholder="Type a skill (e.g. Painting, Computer Coding, Singing)..."
                    className="flex-1 px-4 py-2.5 rounded-xl bg-neutral-50 border border-neutral-300 text-xs text-neutral-900 placeholder-neutral-400 focus:outline-none focus:ring-2 focus:ring-neutral-950"
                  />
                  <button
                    type="submit"
                    className="px-4 py-2.5 rounded-xl bg-neutral-950 hover:bg-neutral-800 text-white font-semibold text-xs flex items-center gap-1.5 shadow-sm transition-all"
                  >
                    <Plus className="w-4 h-4" /> Place
                  </button>
                </form>

                {/* Quick Presets */}
                <div className="space-y-2 pt-2 border-t border-neutral-100">
                  <p className="text-[11px] text-neutral-400 font-medium">Or begin with foundational competencies:</p>
                  <div className="flex flex-wrap justify-center gap-1.5">
                    {[
                      'Painting',
                      'Computer Coding',
                      'Singing',
                      'Dog Training',
                      'Plumbing',
                      'Wrestling',
                    ].map((sample) => (
                      <button
                        key={sample}
                        onClick={() => handleAddCustomSkill(sample)}
                        className="px-2.5 py-1 rounded-full bg-neutral-100 hover:bg-neutral-200 border border-neutral-300 text-neutral-700 text-xs transition-all flex items-center gap-1"
                      >
                        <Plus className="w-3 h-3 text-neutral-500" /> {sample}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Resume Import CTA */}
                <div className="pt-2">
                  <button
                    onClick={() => setIsResumeModalOpen(true)}
                    className="w-full py-2.5 rounded-xl bg-neutral-50 hover:bg-neutral-100 border border-neutral-300 text-neutral-800 text-xs font-medium flex items-center justify-center gap-2 transition-all shadow-sm"
                  >
                    <UploadCloud className="w-4 h-4 text-neutral-600" />
                    Import from Resume or Skill List
                    <ArrowRight className="w-3 h-3 text-neutral-400" />
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Quick Helper Floating Tip */}
          {nodes.length > 0 && (
            <div className="absolute bottom-4 left-20 bg-white/95 border border-neutral-300 rounded-lg px-3 py-1.5 text-[11px] text-neutral-600 pointer-events-none shadow-sm hidden sm:block">
              <span className="text-neutral-900 font-semibold">Tip:</span> Click "Explore" to preview dashed Ghost Nodes. Click a ghost node to solidify it into your tree.
            </div>
          )}
        </div>

        {/* Sidebar Inspector */}
        <Sidebar
          selectedNode={selectedNode}
          onExpandNode={(id) => {
            const n = nodes.find((node) => node.id === id);
            if (n?.data?.is_ghost) {
              handleSolidifyGhostNode(id);
            } else {
              handleExploreNextSteps(id);
            }
          }}
          onSelectNodeById={handleSelectNodeById}
          onSetStartSkill={(node) => {
            setStartSkill(node);
            showToast(`Set '${node.label}' as Start Skill`, 'info');
          }}
          onSetGoalSkill={(node) => {
            setGoalSkill(node);
            showToast(`Set '${node.label}' as Goal Target`, 'info');
          }}
          activePathway={activePathway}
          isExpanding={isExpanding}
          allSolidNodes={nodes.filter((n) => !n.data?.is_ghost)}
          onExploreMultiSkillNextSteps={handleExploreMultiSkillNextSteps}
          isSuggestingMulti={isSuggestingMulti}
        />
      </div>

      {/* Resume Ingestion Modal */}
      <ResumeModal
        isOpen={isResumeModalOpen}
        onClose={() => setIsResumeModalOpen(false)}
        onMatchedSkillsLoaded={handleMatchedSkillsLoaded}
        onSelectGoalSkill={(goalNode) => {
          setGoalSkill(goalNode);
          placeSkillOnCanvas(goalNode);
          showToast(`Target goal set to: ${goalNode.label}`, 'info');
        }}
      />
    </div>
  );
}

export default function App() {
  return (
    <ReactFlowProvider>
      <FlowCanvas />
    </ReactFlowProvider>
  );
}
