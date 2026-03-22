import { useState, useCallback } from 'react'
import { useAppStore } from '../../store'
import { fetchNodeDetail } from '../../api/client'
import { NODE_TYPE_CONFIG } from '../../hooks/useGraph'
import './NodeDrawer.css'

export function NodeDrawer() {
  const { focusedNode, isolatedNodeIds, setFocusedNode, setHighlightedNodes, setIsolatedNodes } = useAppStore()
  const [neighbours, setNeighbours] = useState<{ id: string; node_type: string; label: string; attributes: Record<string, string> }[]>([])
  const [edges, setEdges] = useState<{ source: string; target: string; edge_type: string }[]>([])
  const [expanded, setExpanded] = useState(false)
  const [loadingNeighbours, setLoadingNeighbours] = useState(false)
  const isIsolated = !!(focusedNode && isolatedNodeIds?.has(focusedNode.id))

  const handleExpand = useCallback(async () => {
    if (!focusedNode) return

    if (expanded) {
      if (isIsolated) {
        setIsolatedNodes(null)
      } else {
        const ids = [focusedNode.id, ...neighbours.map((n) => n.id)]
        setIsolatedNodes(ids)
      }
      return
    }

    setLoadingNeighbours(true)
    try {
      const detail = await fetchNodeDetail(focusedNode.id)
      setNeighbours(detail.neighbors ?? [])
      setEdges(detail.edges ?? [])
      setExpanded(true)

      // Highlight all adjacent nodes
      const ids = [focusedNode.id, ...(detail.neighbors ?? []).map((n: { id: string }) => n.id)]
      setHighlightedNodes(ids)

      // Keep only focused node + connected nodes visible
      setIsolatedNodes(ids)
    } finally {
      setLoadingNeighbours(false)
    }
  }, [expanded, focusedNode, isIsolated, neighbours, setHighlightedNodes, setIsolatedNodes])

  if (!focusedNode) return null

  const cfg = NODE_TYPE_CONFIG[focusedNode.node_type] ?? { color: '#94A3B8', icon: '◎', label: focusedNode.node_type }
  const attrs = focusedNode.attributes ?? {}

  return (
    <div className="node-drawer">
      <div className="node-drawer-header" style={{ borderLeftColor: cfg.color }}>
        <div className="node-type-badge" style={{ background: cfg.color + '18', color: cfg.color }}>
          <span>{cfg.icon}</span>
          <span>{cfg.label}</span>
        </div>
        <button
          className="close-btn"
          onClick={() => {
            setIsolatedNodes(null)
            setFocusedNode(null)
          }}
        >
          ×
        </button>
      </div>

      <div className="node-id">
        <span className="node-id-label">ID</span>
        <span className="node-id-value mono">{focusedNode.id}</span>
      </div>

      <div className="node-attrs">
        {Object.entries(attrs).filter(([, v]) => v && v !== 'null' && v !== 'undefined').map(([k, v]) => (
          <div key={k} className="attr-row">
            <span className="attr-key">{camelToLabel(k)}</span>
            <span className="attr-val mono">{String(v)}</span>
          </div>
        ))}
      </div>

      <button
        className="expand-btn"
        onClick={handleExpand}
        disabled={loadingNeighbours}
      >
        {loadingNeighbours
          ? 'Loading…'
          : !expanded
          ? 'Expand connections'
          : isIsolated
          ? 'Show all nodes'
          : `Show only connections (${neighbours.length})`}
      </button>

      {expanded && neighbours.length > 0 && (
        <div className="neighbours-section">
          <div className="neighbours-title">Connections</div>
          {edges.map((e, i) => {
            const isSource = e.source === focusedNode.id
            const otherId = isSource ? e.target : e.source
            const other = neighbours.find((n) => n.id === otherId)
            const otherCfg = NODE_TYPE_CONFIG[other?.node_type ?? ''] ?? { color: '#94A3B8', icon: '◎', label: other?.node_type }

            return (
              <div key={i} className="neighbour-row">
                <div className="edge-direction">
                  {isSource ? (
                    <span className="edge-arrow out">→</span>
                  ) : (
                    <span className="edge-arrow in">←</span>
                  )}
                  <span className="edge-type-pill">{e.edge_type}</span>
                </div>
                <div className="neighbour-info">
                  <span className="neighbour-dot" style={{ background: otherCfg?.color ?? '#94A3B8' }} />
                  <span className="neighbour-type">{otherCfg?.label}</span>
                  <span className="neighbour-id mono">{otherId.split('_').slice(1).join('_') || otherId}</span>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

function camelToLabel(s: string): string {
  return s
    .replace(/([A-Z])/g, ' $1')
    .replace(/^./, (m) => m.toUpperCase())
    .trim()
}
