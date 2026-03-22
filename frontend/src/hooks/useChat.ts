import { useCallback, useRef, useState } from 'react'
import type { ChatMessage } from '../types'
import { useAppStore } from '../store'

const BASE = import.meta.env.VITE_API_URL || ''

export function useChat() {
  const { addMessage, updateLastMessage, finalizeLastMessage, sessionId, highlightedNodes, setHighlightedNodes } = useAppStore()
  const [isLoading, setIsLoading] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || isLoading) return

    // Add user message
    const userId = crypto.randomUUID()
    addMessage({ id: userId, role: 'user', content: text, timestamp: new Date() })

    // Add streaming assistant placeholder
    const assistantId = crypto.randomUUID()
    addMessage({
      id: assistantId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      isStreaming: true,
    })

    setIsLoading(true)
    abortRef.current = new AbortController()

    try {
      const response = await fetch(`${BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          session_id: sessionId,
          highlighted_node_ids: Array.from(highlightedNodes),
        }),
        signal: abortRef.current.signal,
      })

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      let accumulated = ''
      let refNodes: string[] = []

      while (reader) {
        const { done, value } = await reader.read()
        if (done) break

        const raw = decoder.decode(value)
        const lines = raw.split('\n')
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const payload = line.slice(6).trim()
            if (payload === '[DONE]') break
            try {
              const { chunk } = JSON.parse(payload)
              accumulated += chunk
              const cleaned = accumulated.replace(/\n?\*\*?\s*REFERENCED_NODES\s*\*\*?\s*:\s*\[[\s\S]*?\]\s*$/i, '')
              updateLastMessage(cleaned, refNodes.length > 0 ? refNodes : undefined)
            } catch { /* ignore malformed */ }
          }
        }
      }

      const finalRefMatch = accumulated.match(/\*\*?\s*REFERENCED_NODES\s*\*\*?\s*:\s*(\[[\s\S]*?\])\s*$/i)
      if (finalRefMatch) {
        try { refNodes = JSON.parse(finalRefMatch[1]) } catch { /* ignore */ }
      }

      const finalCleaned = accumulated.replace(/\n?\*\*?\s*REFERENCED_NODES\s*\*\*?\s*:\s*\[[\s\S]*?\]\s*$/i, '')
      const referenceBlock = `\n\nReferenced Nodes:\n${
        refNodes.length > 0 ? refNodes.map((id) => `- ${id}`).join('\n') : '- None'
      }`
      updateLastMessage(`${finalCleaned}${referenceBlock}`, refNodes.length > 0 ? refNodes : undefined)

      finalizeLastMessage(refNodes)
      if (refNodes.length > 0) setHighlightedNodes(refNodes)
    } catch (err: unknown) {
      if ((err as Error).name !== 'AbortError') {
        updateLastMessage('Sorry, there was an error processing your request.')
        finalizeLastMessage([])
      }
    } finally {
      setIsLoading(false)
    }
  }, [
    isLoading,
    addMessage,
    updateLastMessage,
    finalizeLastMessage,
    sessionId,
    highlightedNodes,
    setHighlightedNodes,
  ])

  const cancel = useCallback(() => {
    abortRef.current?.abort()
    finalizeLastMessage([])
    setIsLoading(false)
  }, [finalizeLastMessage])

  return { sendMessage, isLoading, cancel }
}
