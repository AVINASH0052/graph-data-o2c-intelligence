export interface GraphNode {
  id: string
  label: string
  node_type: string
  community: number
  color: string
  size: number
  attributes: Record<string, string>
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  edge_type: string
}

export interface GraphResponse {
  nodes: GraphNode[]
  edges: GraphEdge[]
  total_nodes: number
  total_edges: number
  shown_nodes: number
  shown_edges: number
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  referencedNodes?: string[]
  isStreaming?: boolean
}

export interface GraphStats {
  total_nodes: number
  total_edges: number
  node_types: Record<string, number>
  edge_types: Record<string, number>
}
