import axios from 'axios'
import type { GraphResponse, GraphStats } from '../types'

const BASE = import.meta.env.VITE_API_URL || ''

export const api = axios.create({ baseURL: BASE })

export async function fetchGraph(limit = 2000, nodeTypes?: string): Promise<GraphResponse> {
  const params: Record<string, string | number> = { limit }
  if (nodeTypes) params.node_types = nodeTypes
  const { data } = await api.get('/api/graph', { params })
  return data
}

export async function fetchNodeDetail(nodeId: string) {
  const { data } = await api.get(`/api/graph/node/${encodeURIComponent(nodeId)}`)
  return data
}

export async function searchNodes(q: string) {
  const { data } = await api.get('/api/graph/search', { params: { q, limit: 20 } })
  return data.results
}

export async function fetchStats(): Promise<GraphStats> {
  const { data } = await api.get('/api/graph/stats')
  return data
}
