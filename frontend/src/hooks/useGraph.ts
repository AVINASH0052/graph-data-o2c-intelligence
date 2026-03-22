import { useEffect, useCallback, useRef } from 'react'
import Graph from 'graphology'
import type { GraphNode, GraphEdge } from '../types'

// Node type → visual config 
export const NODE_TYPE_CONFIG: Record<string, { color: string; ringColor: string; icon: string; label: string }> = {
  SalesOrder:       { color: '#1B3A8C', ringColor: '#3B6FE0', icon: '📋', label: 'Sales Order' },
  SalesOrderItem:   { color: '#3B6FE0', ringColor: '#7BA7F5', icon: '📦', label: 'SO Item' },
  Customer:         { color: '#D97706', ringColor: '#F59E0B', icon: '🏢', label: 'Customer' },
  Product:          { color: '#059669', ringColor: '#10B981', icon: '🔧', label: 'Product' },
  Plant:            { color: '#7C3AED', ringColor: '#A78BFA', icon: '🏭', label: 'Plant' },
  Delivery:         { color: '#0891B2', ringColor: '#22D3EE', icon: '🚚', label: 'Delivery' },
  DeliveryItem:     { color: '#0E7490', ringColor: '#67E8F9', icon: '📫', label: 'Del. Item' },
  BillingDocument:  { color: '#B45309', ringColor: '#F59E0B', icon: '🧾', label: 'Billing Doc' },
  JournalEntry:     { color: '#9D174D', ringColor: '#F472B6', icon: '📒', label: 'Journal Entry' },
  Payment:          { color: '#166534', ringColor: '#4ADE80', icon: '💳', label: 'Payment' },
}

export function buildGraphology(nodes: GraphNode[], edges: GraphEdge[]): Graph {
  const g = new Graph({ multi: false, type: 'directed' })

  for (const n of nodes) {
    const cfg = NODE_TYPE_CONFIG[n.node_type] ?? { color: '#94A3B8', ringColor: '#CBD5E1' }
    g.addNode(n.id, {
      label: n.label,
      x: Math.random() * 100 - 50,
      y: Math.random() * 100 - 50,
      size: n.size ?? 6,
      color: cfg.color,
      node_type: n.node_type,
      community: n.community,
      attributes: n.attributes,
      originalColor: cfg.color,
      ringColor: cfg.ringColor,
    })
  }

  for (const e of edges) {
    if (g.hasNode(e.source) && g.hasNode(e.target) && !g.hasEdge(e.source, e.target)) {
      g.addDirectedEdge(e.source, e.target, {
        label: e.edge_type,
        size: 0.5,
        color: '#C7D2E8',
        edge_type: e.edge_type,
      })
    }
  }

  return g
}

export function useGraphLayout(graphRef: React.MutableRefObject<Graph | null>) {
  const workerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const runLayout = useCallback(() => {
    if (!graphRef.current) return
    const g = graphRef.current
    const n = g.order

    // Assign positions based on node type to create a natural O2C flow layout
    const typeOrder: Record<string, number> = {
      Customer: 0,
      SalesOrder: 1,
      SalesOrderItem: 2,
      Delivery: 3,
      DeliveryItem: 4,
      Plant: 5,
      BillingDocument: 6,
      JournalEntry: 7,
      Payment: 8,
      Product: 9,
    }

    const typeGroups: Record<string, string[]> = {}
    g.forEachNode((id, attrs) => {
      const t = attrs.node_type as string
      if (!typeGroups[t]) typeGroups[t] = []
      typeGroups[t].push(id)
    })

    const totalTypes = Object.keys(typeOrder).length
    Object.entries(typeGroups).forEach(([type, ids]) => {
      const col = typeOrder[type] ?? totalTypes
      const xBase = (col / totalTypes) * 200 - 100
      ids.forEach((id, i) => {
        const row = i - ids.length / 2
        g.setNodeAttribute(id, 'x', xBase + (Math.random() - 0.5) * 15)
        g.setNodeAttribute(id, 'y', row * 4 + (Math.random() - 0.5) * 3)
      })
    })
  }, [graphRef])

  useEffect(() => {
    return () => {
      if (workerRef.current) clearTimeout(workerRef.current)
    }
  }, [])

  return runLayout
}
