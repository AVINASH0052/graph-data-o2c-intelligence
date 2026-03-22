import { useEffect, useRef, useCallback, useState } from 'react'
import Graph from 'graphology'
import Sigma from 'sigma'
import { useAppStore } from '../../store'
import { fetchGraph, fetchNodeDetail, searchNodes } from '../../api/client'
import { buildGraphology, useGraphLayout, NODE_TYPE_CONFIG } from '../../hooks/useGraph'
import type { GraphNode } from '../../types'
import './GraphCanvas.css'

type HoveredNodeInfo = {
  id: string
  label: string
  nodeType: string
  attrs: Record<string, string>
  x: number
  y: number
}

export function GraphCanvas() {
  const containerRef = useRef<HTMLDivElement>(null)
  const sigmaRef = useRef<Sigma | null>(null)
  const graphRef = useRef<Graph | null>(null)

  const {
    highlightedNodes,
    isolatedNodeIds,
    setFocusedNode,
    setGraphStats,
    setGraphLoading,
    setGraphError,
    isGraphLoading,
    graphError,
    searchQuery,
    setSearchQuery,
    clearHighlights,
    sidePanel,
  } = useAppStore()

  const runLayout = useGraphLayout(graphRef)
  const [searchResults, setSearchResults] = useState<GraphNode[]>([])
  const [showSearch, setShowSearch] = useState(false)
  const [nodeTypeFilter, setNodeTypeFilter] = useState<string>('all')
  const [hoveredNode, setHoveredNode] = useState<HoveredNodeInfo | null>(null)

  // Load graph data
  useEffect(() => {
    let cancelled = false
    setGraphLoading(true)

    fetchGraph(2000)
      .then(async (data) => {
        if (cancelled) return
        setGraphError(null)

        const g = buildGraphology(data.nodes, data.edges)
        graphRef.current = g
        runLayout()

        // Fetch stats separately
        const { fetchStats } = await import('../../api/client')
        const stats = await fetchStats()
        setGraphStats(stats)

        if (!containerRef.current) return
        if (sigmaRef.current) sigmaRef.current.kill()

        const renderer = new Sigma(g, containerRef.current, {
          renderEdgeLabels: false,
          defaultEdgeColor: '#C7D2E8',
          defaultEdgeType: 'arrow',
          edgeProgramClasses: {},
          nodeProgramClasses: {},
          labelFont: 'Inter, sans-serif',
          labelSize: 11,
          labelWeight: '500',
          labelColor: { color: '#1E293B' },
          minCameraRatio: 0.05,
          maxCameraRatio: 5,
        })

        // Node click → open detail panel
        renderer.on('clickNode', ({ node }) => {
          const attrs = g.getNodeAttributes(node)
          setFocusedNode({
            id: node,
            label: attrs.label,
            node_type: attrs.node_type,
            community: attrs.community,
            color: attrs.color,
            size: attrs.size,
            attributes: attrs.attributes ?? {},
          })
        })

        // Background click → clear
        renderer.on('clickStage', () => {
          clearHighlights()
        })

        renderer.on('enterNode', ({ node, event }) => {
          const attrs = g.getNodeAttributes(node)
          const pointerX = typeof event?.x === 'number' ? event.x : 0
          const pointerY = typeof event?.y === 'number' ? event.y : 0

          setHoveredNode({
            id: node,
            label: String(attrs.label ?? node),
            nodeType: String(attrs.node_type ?? 'Unknown'),
            attrs: (attrs.attributes ?? {}) as Record<string, string>,
            x: pointerX,
            y: pointerY,
          })
        })

        renderer.on('leaveNode', () => {
          setHoveredNode(null)
        })

        sigmaRef.current = renderer
        setGraphLoading(false)
      })
      .catch((err) => {
        if (!cancelled) {
          setGraphError(err.message)
          setGraphLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, []) // eslint-disable-line

  // Apply highlights reactively
  useEffect(() => {
    const g = graphRef.current
    const renderer = sigmaRef.current
    if (!g || !renderer) return

    g.forEachNode((id, attrs) => {
      const isHighlighted = highlightedNodes.has(id)
      const isAnyHighlighted = highlightedNodes.size > 0
      const cfg = NODE_TYPE_CONFIG[attrs.node_type as string]

      g.setNodeAttribute(id, 'color',
        isHighlighted
          ? (cfg?.ringColor ?? '#F59E0B')
          : isAnyHighlighted
          ? '#A9B7D0'
          : (attrs.originalColor ?? cfg?.color ?? '#94A3B8')
      )
      g.setNodeAttribute(id, 'size',
        isHighlighted ? Math.min((attrs.size ?? 6) * 2.2, 28) : (attrs.size ?? 6)
      )
      g.setNodeAttribute(id, 'zIndex', isHighlighted ? 10 : 0)
    })

    g.forEachEdge((id, attrs, src, tgt) => {
      const srcHighlighted = highlightedNodes.has(src)
      const tgtHighlighted = highlightedNodes.has(tgt)
      const anyHighlighted = highlightedNodes.size > 0
      g.setEdgeAttribute(id, 'color',
        srcHighlighted && tgtHighlighted
          ? '#F59E0B'
          : anyHighlighted
          ? '#D3DCEB'
          : '#C7D2E8'
      )
      g.setEdgeAttribute(id, 'size',
        srcHighlighted && tgtHighlighted ? 2 : 0.5
      )
    })

    renderer.refresh()
  }, [highlightedNodes])

  // The graph container width changes when the right panel toggles.
  // Sigma's WebGL canvas must be resized to match the new container dimensions.
  useEffect(() => {
    const renderer = sigmaRef.current
    if (!renderer) return
    const timers = [50, 200, 700].map((ms) =>
      window.setTimeout(() => {
        renderer.resize()
        renderer.refresh()
      }, ms),
    )
    return () => timers.forEach((id) => window.clearTimeout(id))
  }, [sidePanel])

  // Filter by node type
  useEffect(() => {
    const g = graphRef.current
    const renderer = sigmaRef.current
    if (!g || !renderer) return

    g.forEachNode((id, attrs) => {
      const hiddenByType = nodeTypeFilter !== 'all' && attrs.node_type !== nodeTypeFilter
      const hiddenByIsolation = isolatedNodeIds ? !isolatedNodeIds.has(id) : false
      const hidden = hiddenByType || hiddenByIsolation
      g.setNodeAttribute(id, 'hidden', hidden)
    })
    g.forEachEdge((id, _attrs, src, tgt) => {
      const sh = g.getNodeAttribute(src, 'hidden')
      const th = g.getNodeAttribute(tgt, 'hidden')
      g.setEdgeAttribute(id, 'hidden', sh || th)
    })
    renderer.refresh()
  }, [nodeTypeFilter, isolatedNodeIds])

  // Handle search
  const handleSearch = useCallback(async (q: string) => {
    setSearchQuery(q)
    if (q.length < 2) { setSearchResults([]); return }
    const results = await searchNodes(q)
    setSearchResults(results)
    setShowSearch(true)
  }, [setSearchQuery])

  const focusNodeInGraph = useCallback((nodeId: string) => {
    const renderer = sigmaRef.current
    const g = graphRef.current
    if (!renderer || !g || !g.hasNode(nodeId)) return

    // Use Sigma's display data (framed graph coords) for camera, not raw graph coords
    const nodeDisplayData = renderer.getNodeDisplayData(nodeId)
    if (nodeDisplayData) {
      renderer.getCamera().animate(
        { x: nodeDisplayData.x, y: nodeDisplayData.y, ratio: 0.08 },
        { duration: 600, easing: 'quadraticInOut' },
      )
    }
    setShowSearch(false)
    setSearchResults([])
    setSearchQuery('')

    // Set as focused node immediately with graph attributes
    const attrs = g.getNodeAttributes(nodeId)
    setFocusedNode({
      id: nodeId,
      label: attrs.label,
      node_type: attrs.node_type,
      community: attrs.community,
      color: attrs.color,
      size: attrs.size,
      attributes: attrs.attributes ?? {},
    })

    // Then fetch and update with detailed attributes
    fetchNodeDetail(nodeId).then((detail) => {
      setFocusedNode({
        id: nodeId,
        label: attrs.label,
        node_type: attrs.node_type,
        community: attrs.community,
        color: attrs.color,
        size: attrs.size,
        attributes: detail.node?.attributes ?? attrs.attributes ?? {},
      })
    })
  }, [setFocusedNode, setSearchQuery])

  const zoomIn = () => sigmaRef.current?.getCamera().animatedZoom({ duration: 300 })
  const zoomOut = () => sigmaRef.current?.getCamera().animatedUnzoom({ duration: 300 })
  const resetView = () => sigmaRef.current?.getCamera().animatedReset({ duration: 400 })

  return (
    <div className="graph-canvas-wrapper">
      {/* Top toolbar */}
      <div className="graph-toolbar">
        <div className="graph-search-wrapper">
          <svg className="search-icon" viewBox="0 0 20 20" fill="none">
            <circle cx="8.5" cy="8.5" r="5.5" stroke="currentColor" strokeWidth="1.5"/>
            <path d="M13 13l3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          <input
            className="graph-search"
            placeholder="Search nodes…"
            value={searchQuery}
            onChange={(e) => handleSearch(e.target.value)}
            onFocus={() => searchResults.length > 0 && setShowSearch(true)}
            onBlur={() => setTimeout(() => setShowSearch(false), 200)}
          />
          {showSearch && searchResults.length > 0 && (
            <div className="search-dropdown">
              {searchResults.map((n) => {
                const cfg = NODE_TYPE_CONFIG[n.node_type]
                return (
                  <button key={n.id} className="search-result-item" onMouseDown={() => focusNodeInGraph(n.id)}>
                    <span className="search-result-dot" style={{ background: cfg?.color ?? '#94A3B8' }} />
                    <span className="search-result-label">{n.label}</span>
                    <span className="search-result-type">{cfg?.label ?? n.node_type}</span>
                  </button>
                )
              })}
            </div>
          )}
        </div>

        <select
          className="node-type-filter"
          value={nodeTypeFilter}
          onChange={(e) => setNodeTypeFilter(e.target.value)}
        >
          <option value="all">All node types</option>
          {Object.entries(NODE_TYPE_CONFIG).map(([type, cfg]) => (
            <option key={type} value={type}>{cfg.label}</option>
          ))}
        </select>
      </div>

      {/* Sigma canvas */}
      <div ref={containerRef} className="sigma-container" />

      {/* Hover card */}
      {hoveredNode && (
        <div
          className="node-hover-card"
          style={{ left: hoveredNode.x + 14, top: hoveredNode.y + 14 }}
        >
          <div className="node-hover-title">{NODE_TYPE_CONFIG[hoveredNode.nodeType]?.label ?? hoveredNode.nodeType}</div>
          <div className="node-hover-row">
            <span className="node-hover-key">ID</span>
            <span className="node-hover-value mono">{hoveredNode.id}</span>
          </div>
          {Object.entries(hoveredNode.attrs)
            .filter(([, v]) => v && v !== 'null' && v !== 'undefined')
            .slice(0, 8)
            .map(([k, v]) => (
              <div key={k} className="node-hover-row">
                <span className="node-hover-key">{camelToLabel(k)}</span>
                <span className="node-hover-value mono">{String(v)}</span>
              </div>
            ))}
        </div>
      )}

      {/* Zoom controls */}
      <div className="zoom-controls">
        <button className="zoom-btn" onClick={zoomIn} title="Zoom in">+</button>
        <button className="zoom-btn" onClick={resetView} title="Reset view">⊙</button>
        <button className="zoom-btn" onClick={zoomOut} title="Zoom out">−</button>
      </div>

      {/* Loading overlay */}
      {isGraphLoading && (
        <div className="graph-overlay">
          <div className="graph-loading">
            <div className="flow-loader">
              <span>SO</span>
              <div className="flow-arrow" />
              <span>DEL</span>
              <div className="flow-arrow" />
              <span>BILL</span>
              <div className="flow-arrow" />
              <span>JE</span>
            </div>
            <p>Loading O2C graph…</p>
          </div>
        </div>
      )}

      {/* Error */}
      {graphError && !isGraphLoading && (
        <div className="graph-overlay">
          <div className="graph-error">
            <span>⚠</span>
            <p>{graphError}</p>
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="graph-legend">
        {Object.entries(NODE_TYPE_CONFIG).slice(0, 6).map(([type, cfg]) => (
          <div key={type} className="legend-item">
            <span className="legend-dot" style={{ background: cfg.color }} />
            <span className="legend-text">{cfg.label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function camelToLabel(s: string): string {
  return s
    .replace(/([A-Z])/g, ' $1')
    .replace(/^./, (m) => m.toUpperCase())
    .trim()
}
