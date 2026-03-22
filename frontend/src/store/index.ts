import { create } from 'zustand'
import type { ChatMessage, GraphNode, GraphStats } from '../types'

interface AppState {
  // Graph
  highlightedNodes: Set<string>
  isolatedNodeIds: Set<string> | null
  focusedNode: GraphNode | null
  graphStats: GraphStats | null
  isGraphLoading: boolean
  graphError: string | null

  // Chat
  messages: ChatMessage[]
  sessionId: string
  isChatLoading: boolean

  // UI
  sidePanel: 'chat' | 'node' | null
  searchQuery: string

  // Actions
  setHighlightedNodes: (ids: string[]) => void
  setIsolatedNodes: (ids: string[] | null) => void
  clearHighlights: () => void
  setFocusedNode: (node: GraphNode | null) => void
  setGraphStats: (stats: GraphStats) => void
  setGraphLoading: (v: boolean) => void
  setGraphError: (e: string | null) => void
  addMessage: (msg: ChatMessage) => void
  updateLastMessage: (content: string, referencedNodes?: string[]) => void
  finalizeLastMessage: (referencedNodes?: string[]) => void
  setSidePanel: (panel: 'chat' | 'node' | null) => void
  setSearchQuery: (q: string) => void
}

export const useAppStore = create<AppState>((set, get) => ({
  highlightedNodes: new Set(),
  isolatedNodeIds: null,
  focusedNode: null,
  graphStats: null,
  isGraphLoading: false,
  graphError: null,

  messages: [],
  sessionId: crypto.randomUUID(),
  isChatLoading: false,

  sidePanel: 'chat',
  searchQuery: '',

  setHighlightedNodes: (ids) =>
    set({ highlightedNodes: new Set(ids) }),

  setIsolatedNodes: (ids) =>
    set({ isolatedNodeIds: ids ? new Set(ids) : null }),

  clearHighlights: () => set({ highlightedNodes: new Set() }),

  setFocusedNode: (node) =>
    set({ focusedNode: node, sidePanel: node ? 'node' : 'chat' }),

  setGraphStats: (stats) => set({ graphStats: stats }),
  setGraphLoading: (v) => set({ isGraphLoading: v }),
  setGraphError: (e) => set({ graphError: e }),

  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),

  updateLastMessage: (content, referencedNodes) =>
    set((s) => {
      const msgs = [...s.messages]
      const last = msgs[msgs.length - 1]
      if (last && last.role === 'assistant') {
        msgs[msgs.length - 1] = {
          ...last,
          content,
          referencedNodes: referencedNodes ?? last.referencedNodes,
        }
      }
      return { messages: msgs }
    }),

  finalizeLastMessage: (referencedNodes) =>
    set((s) => {
      const msgs = [...s.messages]
      const last = msgs[msgs.length - 1]
      if (last && last.role === 'assistant') {
        msgs[msgs.length - 1] = {
          ...last,
          isStreaming: false,
          referencedNodes: referencedNodes ?? last.referencedNodes,
        }
      }
      return { messages: msgs, isChatLoading: false }
    }),

  setSidePanel: (panel) => set({ sidePanel: panel }),
  setSearchQuery: (q) => set({ searchQuery: q }),
}))
