import { useRef, useEffect, useState, useCallback } from 'react'
import { useAppStore } from '../../store'
import { useChat } from '../../hooks/useChat'
import { NODE_TYPE_CONFIG } from '../../hooks/useGraph'
import './ChatPanel.css'

const EXAMPLE_QUERIES = [
  'Trace billing document 90504248',
  'Which products appear in the most billing documents?',
  'Find sales orders delivered but not billed',
  'Show me the top 10 customers by total billed amount',
]

export function ChatPanel() {
  const { messages, highlightedNodes, setHighlightedNodes, clearHighlights } = useAppStore()
  const { sendMessage, isLoading, cancel } = useChat()
  const [input, setInput] = useState('')
  const endRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = useCallback(() => {
    const text = input.trim()
    if (!text || isLoading) return
    sendMessage(text)
    setInput('')
    inputRef.current?.focus()
  }, [input, isLoading, sendMessage])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }, [handleSend])

  return (
    <div className="chat-panel">
      {/* Header */}
      <div className="chat-header">
        <div className="chat-header-left">
          <div className="chat-logo">
            <svg viewBox="0 0 24 24" fill="none" width="18" height="18">
              <path d="M4 6h16M4 10h10M4 14h7" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              <circle cx="18" cy="15" r="4" stroke="currentColor" strokeWidth="1.5"/>
              <path d="M21 18l1.5 1.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          </div>
          <div>
            <div className="chat-title">O2C Intelligence</div>
            <div className="chat-subtitle">Ask about your Order-to-Cash data</div>
          </div>
        </div>
        {highlightedNodes.size > 0 && (
          <button className="clear-highlights-btn" onClick={clearHighlights} title="Clear highlights">
            <span>{highlightedNodes.size} highlighted</span>
            <span>×</span>
          </button>
        )}
      </div>

      {/* Flow path indicator */}
      <div className="flow-path-bar">
        {['Sales Order', 'Delivery', 'Billing', 'Journal Entry', 'Payment'].map((step, i, arr) => (
          <span key={step} className="flow-path-item">
            <span className="flow-step">{step}</span>
            {i < arr.length - 1 && <span className="flow-sep">›</span>}
          </span>
        ))}
      </div>

      {/* Messages area */}
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            <div className="empty-icon">
              <svg viewBox="0 0 48 48" fill="none" width="40" height="40">
                <rect x="4" y="4" width="40" height="40" rx="8" fill="#EEF2FF"/>
                <path d="M14 18h20M14 24h14M14 30h10" stroke="#3B6FE0" strokeWidth="2" strokeLinecap="round"/>
                <circle cx="36" cy="34" r="7" fill="#1B3A8C"/>
                <path d="M33 34l2 2 4-4" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <p className="empty-title">Query your O2C data</p>
            <p className="empty-sub">Ask questions in plain English. The system translates them into live database queries.</p>
            <div className="example-queries">
              {EXAMPLE_QUERIES.map((q) => (
                <button key={q} className="example-chip" onClick={() => { setInput(q); inputRef.current?.focus() }}>
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id} className={`message message--${msg.role}`}>
            {msg.role === 'assistant' && (
              <div className="msg-avatar assistant-avatar">
                <svg viewBox="0 0 20 20" fill="none" width="12" height="12">
                  <circle cx="10" cy="10" r="8" stroke="white" strokeWidth="1.5"/>
                  <path d="M7 10l2 2 4-4" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </div>
            )}
            <div className={`msg-bubble msg-bubble--${msg.role}`}>
              <MessageContent content={msg.content} isStreaming={msg.isStreaming} />
              {msg.referencedNodes && msg.referencedNodes.length > 0 && !msg.isStreaming && (
                <div className="ref-nodes">
                  <span className="ref-nodes-label">Referenced nodes</span>
                  <div className="ref-nodes-list">
                    {msg.referencedNodes.slice(0, 8).map((nid) => {
                      const typeMatch = nid.match(/^([A-Z]+(?:I|E)?)_/)
                      const prefix = typeMatch?.[1] ?? ''
                      const typeMap: Record<string, string> = {
                        SO: 'SalesOrder', SOI: 'SalesOrderItem', C: 'Customer',
                        P: 'Product', PL: 'Plant', D: 'Delivery', DI: 'DeliveryItem',
                        BD: 'BillingDocument', JE: 'JournalEntry', PAY: 'Payment',
                      }
                      const nodeType = typeMap[prefix] ?? ''
                      const cfg = NODE_TYPE_CONFIG[nodeType]
                      return (
                        <button
                          key={nid}
                          className="ref-node-chip"
                          onClick={() => setHighlightedNodes([nid])}
                          style={{ borderColor: cfg?.color ?? '#94A3B8', color: cfg?.color ?? '#64748B' }}
                        >
                          <span className="ref-node-dot" style={{ background: cfg?.color ?? '#94A3B8' }} />
                          {nid.split('_').slice(1, 3).join('_')}
                        </button>
                      )
                    })}
                    {msg.referencedNodes.length > 8 && (
                      <span className="ref-nodes-more">+{msg.referencedNodes.length - 8} more</span>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={endRef} />
      </div>

      {/* Input area */}
      <div className="chat-input-area">
        <div className="input-wrapper">
          <textarea
            ref={inputRef}
            className="chat-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about orders, deliveries, billing, payments…"
            rows={1}
          />
          {isLoading ? (
            <button className="send-btn stop-btn" onClick={cancel}>
              <svg viewBox="0 0 16 16" fill="currentColor" width="14" height="14">
                <rect x="3" y="3" width="10" height="10" rx="1"/>
              </svg>
            </button>
          ) : (
            <button className="send-btn" onClick={handleSend} disabled={!input.trim()}>
              <svg viewBox="0 0 16 16" fill="none" width="14" height="14">
                <path d="M2 8h12M9 3l5 5-5 5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
          )}
        </div>
        <div className="input-hint">Enter to send · Shift+Enter for new line</div>
      </div>
    </div>
  )
}

function MessageContent({ content, isStreaming }: { content: string; isStreaming?: boolean }) {
  // Hide the REFERENCED_NODES JSON tail from display
  const display = content.replace(/\nREFERENCED_NODES:.*$/s, '').trim()

  return (
    <div className="msg-content">
      {display.split('\n').map((line, i) => (
        <p key={i} className={line.startsWith('  ') ? 'msg-line indented' : 'msg-line'}>
          {line || '\u00A0'}
        </p>
      ))}
      {isStreaming && <span className="cursor-blink">▌</span>}
    </div>
  )
}
