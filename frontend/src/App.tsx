import { useState } from 'react'
import { GraphCanvas } from './components/GraphCanvas/GraphCanvas'
import { ChatPanel } from './components/ChatPanel/ChatPanel'
import { NodeDrawer } from './components/NodeDrawer/NodeDrawer'
import { useAppStore } from './store'
import './App.css'

export default function App() {
  const { graphStats, sidePanel, setSidePanel, focusedNode } = useAppStore()
  const [rightPanelWidth] = useState(360)

  return (
    <div className="app-root">
      {/* ── Top navbar ───────────────────────────────── */}
      <header className="app-header">
        <div className="app-header-left">
          <div className="app-brand">
            <div className="brand-mark">
              <svg viewBox="0 0 28 28" fill="none" width="20" height="20">
                <circle cx="8" cy="8" r="3.5" fill="white" opacity="0.9"/>
                <circle cx="20" cy="8" r="3.5" fill="white" opacity="0.7"/>
                <circle cx="8" cy="20" r="3.5" fill="white" opacity="0.7"/>
                <circle cx="20" cy="20" r="3.5" fill="white" opacity="0.9"/>
                <line x1="11" y1="8" x2="17" y2="8" stroke="white" strokeWidth="1.5" opacity="0.6"/>
                <line x1="8" y1="11" x2="8" y2="17" stroke="white" strokeWidth="1.5" opacity="0.6"/>
                <line x1="11" y1="20" x2="17" y2="20" stroke="white" strokeWidth="1.5" opacity="0.6"/>
                <line x1="20" y1="11" x2="20" y2="17" stroke="white" strokeWidth="1.5" opacity="0.6"/>
              </svg>
            </div>
            <span className="brand-name">O2C Graph Intelligence</span>
          </div>
          <div className="header-divider" />
          <div className="breadcrumb">
            <span className="breadcrumb-item">Order to Cash</span>
            <span className="breadcrumb-sep">›</span>
            <span className="breadcrumb-item active">Process Map</span>
          </div>
        </div>

        <div className="app-header-right">
          {/* Stats pills */}
          {graphStats && (
            <div className="stats-bar">
              <div className="stat-pill">
                <span className="stat-value">{graphStats.total_nodes.toLocaleString()}</span>
                <span className="stat-label">Nodes</span>
              </div>
              <div className="stat-pill">
                <span className="stat-value">{graphStats.total_edges.toLocaleString()}</span>
                <span className="stat-label">Edges</span>
              </div>
              {graphStats.node_types['SalesOrder'] && (
                <div className="stat-pill">
                  <span className="stat-value">{graphStats.node_types['SalesOrder'].toLocaleString()}</span>
                  <span className="stat-label">Orders</span>
                </div>
              )}
              {graphStats.node_types['BillingDocument'] && (
                <div className="stat-pill">
                  <span className="stat-value">{graphStats.node_types['BillingDocument'].toLocaleString()}</span>
                  <span className="stat-label">Invoices</span>
                </div>
              )}
            </div>
          )}

          {/* Panel toggles */}
          <div className="panel-toggles">
            <button
              className={`panel-toggle-btn ${sidePanel === 'chat' ? 'active' : ''}`}
              onClick={() => setSidePanel(sidePanel === 'chat' ? null : 'chat')}
              title="Toggle chat"
            >
              <svg viewBox="0 0 18 18" fill="none" width="14" height="14">
                <path d="M2 3h14a1 1 0 011 1v8a1 1 0 01-1 1H5l-3 3V4a1 1 0 011-1z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
              </svg>
              Chat
            </button>
          </div>
        </div>
      </header>

      {/* ── Main content ─────────────────────────────── */}
      <div className="app-body">
        {/* Graph (fills remaining space) */}
        <div className="graph-section" style={{ right: sidePanel ? rightPanelWidth : 0 }}>
          <GraphCanvas />
        </div>

        {/* Right panel */}
        {sidePanel && (
          <div className="right-panel" style={{ width: rightPanelWidth }}>
            {sidePanel === 'node' && focusedNode ? (
              <NodeDrawer />
            ) : (
              <ChatPanel />
            )}
          </div>
        )}
      </div>
    </div>
  )
}
