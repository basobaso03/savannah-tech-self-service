import { useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { downloadInsightsCsv, fetchInsights, sendChatMessage } from './api'
import type { ChatMessage, ChatSession, InsightsResponse } from './types'

const STORAGE_KEY = 'zimnest-selfservice-chat-sessions'
const ACTIVE_SESSION_KEY = 'zimnest-selfservice-active-session'
const USER_ID_KEY = 'zimnest-selfservice-user-id'
const USER_NAME = 'User'
const ASSISTANT_NAME = 'Savannah Tech Assistant'

const STARTER_QUESTIONS = [
  'What products do you offer?',
  'How do I get started?',
  'Where is your office located?',
  'How much does pricing cost?',
  'How can I contact support?',
]

type ViewMode = 'chat' | 'admin'

type PendingChatRequest = {
  controller: AbortController
  sessionId: string
  previousSession: ChatSession
  draft: string
}

function getInitialViewMode(): ViewMode {
  return window.location.pathname.startsWith('/admin') ? 'admin' : 'chat'
}

function navigateToViewMode(mode: ViewMode) {
  const nextPath = mode === 'admin' ? '/admin' : '/'
  window.history.pushState({}, '', nextPath)
  window.dispatchEvent(new PopStateEvent('popstate'))
}

function createId() {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function hashString(value: string) {
  let hash = 0
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) >>> 0
  }
  return hash
}

function pickStarterQuestions(sessionId: string, count = 3) {
  const ordered = [...STARTER_QUESTIONS]
    .map((question, index) => ({ question, score: hashString(`${sessionId}:${question}:${index}`) }))
    .sort((left, right) => left.score - right.score)

  return ordered.slice(0, count).map((entry) => entry.question)
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat('en', {
    hour: 'numeric',
    minute: '2-digit',
  }).format(new Date(value))
}

function cloneSession(session: ChatSession): ChatSession {
  return {
    ...session,
    messages: session.messages.map((message) => ({ ...message })),
  }
}

function isAbortError(cause: unknown) {
  return cause instanceof DOMException && cause.name === 'AbortError'
}

function formatMessageContent(content: string) {
  const escaped = content
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  return escaped
    .replace(/```([\s\S]*?)```/g, (_, code: string) => `<pre><code>${code.trim()}</code></pre>`)
    .replace(/^###\s+(.+)$/gm, '<h3>$1</h3>')
    .replace(/^##\s+(.+)$/gm, '<h2>$1</h2>')
    .replace(/^#\s+(.+)$/gm, '<h1>$1</h1>')
    .replace(/^\s*[-*]\s+(.+)$/gm, '<li>$1</li>')
    .replace(/^\s*\d+[.)]\s+(.+)$/gm, '<li>$1</li>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/__(.+?)__/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/\n\n/g, '</p><p>')
}

function createEmptySession(title = 'New chat'): ChatSession {
  const now = new Date().toISOString()
  return {
    id: createId(),
    title,
    createdAt: now,
    updatedAt: now,
    messages: [],
  }
}

function createUserId() {
  return globalThis.crypto?.randomUUID?.() ?? `user-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function loadSessions(): ChatSession[] {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) {
    return [createEmptySession('Company support')]
  }

  try {
    const parsed = JSON.parse(raw) as ChatSession[]
    return parsed.length > 0 ? parsed : [createEmptySession('Company support')]
  } catch {
    return [createEmptySession('Company support')]
  }
}

function persistSessions(sessions: ChatSession[], activeSessionId: string) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions))
  localStorage.setItem(ACTIVE_SESSION_KEY, activeSessionId)
}

function Avatar({ name, accent }: { name: string; accent: 'user' | 'assistant' }) {
  return <div className={`avatar avatar-${accent}`}>{name.split(' ').map((part) => part[0]).join('').slice(0, 2)}</div>
}

function MessageBubble({
  message,
  onSuggestionClick,
}: {
  message: ChatMessage
  onSuggestionClick?: (suggestion: string) => void
}) {
  const messageClass = message.role === 'assistant' ? 'message-content markdown-content' : 'message-content'
  const renderedContent = message.role === 'assistant' ? formatMessageContent(message.content) : message.content

  return (
    <div className={`message-row message-row-${message.role}`}>
      <Avatar name={message.name} accent={message.role === 'user' ? 'user' : 'assistant'} />
      <div className="message-card">
        <div className="message-meta">
          <span className="message-name">{message.name}</span>
          <span className="message-time">{formatTime(message.createdAt)}</span>
        </div>
        <div
          className={messageClass}
          dangerouslySetInnerHTML={{
            __html: message.role === 'assistant' ? `<p>${renderedContent}</p>` : renderedContent,
          }}
        />
        {message.role === 'assistant' && (message.suggestions?.length ?? 0) > 0 ? (
          <div className="suggestion-list" aria-label="Suggested follow-up questions">
            {message.suggestions!.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                className="suggestion-chip"
                onClick={() => onSuggestionClick?.(suggestion)}
              >
                {suggestion}
              </button>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  )
}

function StarterPanel({
  sessionId,
  onChooseQuestion,
}: {
  sessionId: string
  onChooseQuestion: (question: string) => void
}) {
  const starterQuestions = useMemo(() => pickStarterQuestions(sessionId), [sessionId])

  return (
    <div className="empty-state empty-state-starter">
      <div className="starter-brand">
        <div className="brand-mark starter-brand-mark">S</div>
        <div>
          <p className="eyebrow">Savannah Tech Innovations</p>
          <h3>Support Hub</h3>
        </div>
      </div>
      <p className="starter-copy">
        Start with a suggested question or ask anything about Savannah Tech Innovations, and I’ll answer from the
        company knowledge base.
      </p>
      <div className="starter-grid" aria-label="Getting started questions">
        {starterQuestions.map((question) => (
          <button key={question} type="button" className="starter-card" onClick={() => onChooseQuestion(question)}>
            <span className="starter-card-label">Getting started</span>
            <strong>{question}</strong>
          </button>
        ))}
      </div>
    </div>
  )
}

function TypingIndicator() {
  return (
    <div className="message-row message-row-assistant">
      <Avatar name={ASSISTANT_NAME} accent="assistant" />
      <div className="message-card typing-card">
        <div className="message-meta">
          <span className="message-name">{ASSISTANT_NAME}</span>
          <span className="message-time">typing</span>
        </div>
        <div className="typing-indicator" aria-label="Assistant is typing">
          <span />
          <span />
          <span />
        </div>
      </div>
    </div>
  )
}

function MetricCard({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <article className="metric-card">
      <span className="metric-label">{label}</span>
      <strong className="metric-value">{value}</strong>
      <p className="metric-hint">{hint}</p>
    </article>
  )
}

function SectionCard({
  title,
  subtitle,
  children,
}: {
  title: string
  subtitle?: string
  children: ReactNode
}) {
  return (
    <section className="panel-card">
      <div className="panel-card-header">
        <div>
          <h3>{title}</h3>
          {subtitle ? <p>{subtitle}</p> : null}
        </div>
      </div>
      {children}
    </section>
  )
}

function AdminBar({ label, count, max }: { label: string; count: number; max: number }) {
  const width = max > 0 ? Math.max(8, Math.round((count / max) * 100)) : 8
  return (
    <div className="bar-row">
      <div className="bar-row-meta">
        <span>{label}</span>
        <strong>{count}</strong>
      </div>
      <div className="bar-track">
        <div className="bar-fill" style={{ width: `${width}%` }} />
      </div>
    </div>
  )
}

function AdminDashboard({ insights, onExport, onRefresh, loading }: { insights: InsightsResponse | null; onExport: () => void; onRefresh: () => void; loading: boolean }) {
  const categories = insights?.categories ?? {}
  const categoryEntries = Object.entries(categories).sort((left, right) => right[1] - left[1])
  const maxCategoryCount = Math.max(1, ...categoryEntries.map(([, value]) => value))

  return (
    <div className="dashboard-view">
      <header className="dashboard-hero">
        <div>
          <p className="eyebrow">Admin dashboard</p>
          <h2>Company insights and decision support</h2>
          <p className="dashboard-summary">
            This view shows what customers ask, which questions are unresolved, and where marketing follow-up is needed.
          </p>
        </div>
        <div className="dashboard-actions">
          <button type="button" className="secondary-button" onClick={onRefresh} disabled={loading}>
            {loading ? 'Refreshing...' : 'Refresh'}
          </button>
          <button type="button" className="send-button" onClick={onExport} disabled={loading}>
            Export CSV
          </button>
        </div>
      </header>

      <div className="metrics-grid">
        <MetricCard
          label="Total events"
          value={String(insights?.total_events ?? 0)}
          hint="All logged company chat turns"
        />
        <MetricCard
          label="Distinct users"
          value={String(insights?.distinct_users ?? 0)}
          hint="Unique anonymous customers seen in the logs"
        />
        <MetricCard
          label="Lead captures"
          value={String(insights?.lead_captures ?? 0)}
          hint="Requests that produced contact follow-up"
        />
        <MetricCard
          label="Unanswered requests"
          value={String(insights?.unanswered_requests ?? 0)}
          hint="Company questions still needing content"
        />
        <MetricCard
          label="Average retrieval score"
          value={(insights?.average_top_score ?? 0).toFixed(3)}
          hint="Higher values mean stronger context matches"
        />
      </div>

      <div className="dashboard-grid">
        <SectionCard title="Category breakdown" subtitle="What the assistant is seeing most often">
          <div className="bars-stack">
            {categoryEntries.length > 0 ? (
              categoryEntries.map(([label, count]) => (
                <AdminBar key={label} label={label} count={count} max={maxCategoryCount} />
              ))
            ) : (
              <p className="empty-copy">No analytics data yet.</p>
            )}
          </div>
        </SectionCard>

        <SectionCard title="Top customer questions" subtitle="Most common phrases from the chat log">
          <ul className="list-stack">
            {(insights?.top_questions ?? []).length > 0 ? (
              insights!.top_questions.map((item) => (
                <li key={item.question} className="list-item">
                  <span>{item.question}</span>
                  <strong>{item.count}</strong>
                </li>
              ))
            ) : (
              <li className="empty-copy">No questions logged yet.</li>
            )}
          </ul>
        </SectionCard>

        <SectionCard title="Top users" subtitle="Anonymous users with the most chat activity">
          <ul className="list-stack">
            {(insights?.top_users ?? []).length > 0 ? (
              insights!.top_users.map((item) => (
                <li key={item.user_id} className="list-item">
                  <span>{item.user_id}</span>
                  <strong>{item.count}</strong>
                </li>
              ))
            ) : (
              <li className="empty-copy">No user activity logged yet.</li>
            )}
          </ul>
        </SectionCard>

        <SectionCard title="Most matched knowledge topics" subtitle="Documents that are being used most">
          <ul className="list-stack">
            {(insights?.top_titles ?? []).length > 0 ? (
              insights!.top_titles.map((item) => (
                <li key={item.title} className="list-item">
                  <span>{item.title}</span>
                  <strong>{item.count}</strong>
                </li>
              ))
            ) : (
              <li className="empty-copy">No document matches yet.</li>
            )}
          </ul>
        </SectionCard>

        <SectionCard title="Recommendations" subtitle="Actions the company should take next">
          <ul className="recommendation-list">
            {(insights?.recommendations ?? []).length > 0 ? (
              insights!.recommendations.map((item) => (
                <li key={item} className="recommendation-item">
                  {item}
                </li>
              ))
            ) : (
              <li className="empty-copy">No recommendations yet.</li>
            )}
          </ul>
        </SectionCard>
      </div>
    </div>
  )
}

export default function App() {
  const [sessions, setSessions] = useState<ChatSession[]>(() => loadSessions())
  const [activeSessionId, setActiveSessionId] = useState<string>(() => localStorage.getItem(ACTIVE_SESSION_KEY) || '')
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(() => window.innerWidth > 980)
  const [userId] = useState<string>(() => {
    const existing = localStorage.getItem(USER_ID_KEY)
    if (existing) {
      return existing
    }

    const nextUserId = createUserId()
    localStorage.setItem(USER_ID_KEY, nextUserId)
    return nextUserId
  })
  const [message, setMessage] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>(() => getInitialViewMode())
  const [insights, setInsights] = useState<InsightsResponse | null>(null)
  const [isLoadingInsights, setIsLoadingInsights] = useState(false)
  const [insightsError, setInsightsError] = useState<string | null>(null)
  const messageEndRef = useRef<HTMLDivElement | null>(null)
  const pendingRequestRef = useRef<PendingChatRequest | null>(null)

  const activeSession = useMemo(
    () => sessions.find((session) => session.id === activeSessionId) ?? sessions[0],
    [sessions, activeSessionId],
  )

  useEffect(() => {
    persistSessions(sessions, activeSessionId)
  }, [sessions, activeSessionId])

  useEffect(() => {
    if (!sessions.some((session) => session.id === activeSessionId) && sessions[0]) {
      setActiveSessionId(sessions[0].id)
    }
  }, [sessions, activeSessionId])

  useEffect(() => {
    if (viewMode === 'admin') {
      void loadInsights()
    }
  }, [viewMode])

  useEffect(() => {
    if (window.innerWidth > 980) {
      setIsSidebarOpen(true)
    }
  }, [viewMode])

  useEffect(() => {
    const onLocationChange = () => {
      setViewMode(getInitialViewMode())
    }

    window.addEventListener('popstate', onLocationChange)
    return () => window.removeEventListener('popstate', onLocationChange)
  }, [])

  useEffect(() => {
    if (viewMode !== 'chat') {
      return
    }

    messageEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [viewMode, activeSession?.messages.length, isSending, activeSessionId])

  function updateActiveSession(updater: (session: ChatSession) => ChatSession) {
    setSessions((current) => current.map((session) => (session.id === activeSessionId ? updater(session) : session)))
  }

  async function sendFollowUp(suggestion: string) {
    if (isSending || !activeSession) {
      return
    }

    setMessage(suggestion)
    await submitMessage(suggestion)
  }

  function cancelPendingMessage() {
    const pending = pendingRequestRef.current
    if (!pending) {
      return
    }

    pending.controller.abort()
    setSessions((currentSessions) =>
      currentSessions.map((session) => (session.id === pending.sessionId ? cloneSession(pending.previousSession) : session)),
    )
    setActiveSessionId(pending.sessionId)
    setMessage(pending.draft)
    setIsSending(false)
    setError(null)
    pendingRequestRef.current = null
    navigateToViewMode('chat')
  }

  function createSession() {
    const session = createEmptySession(`Chat ${sessions.length + 1}`)
    setSessions((current) => [session, ...current])
    setActiveSessionId(session.id)
    setError(null)
    navigateToViewMode('chat')
    setIsSidebarOpen(false)
  }

  function renameSession(sessionId: string) {
    const current = sessions.find((session) => session.id === sessionId)
    if (!current) {
      return
    }

    const nextTitle = window.prompt('Rename chat session', current.title)?.trim()
    if (!nextTitle) {
      return
    }

    setSessions((currentSessions) =>
      currentSessions.map((session) =>
        session.id === sessionId ? { ...session, title: nextTitle, updatedAt: new Date().toISOString() } : session,
      ),
    )
  }

  function deleteSession(sessionId: string) {
    if (!window.confirm('Delete this chat session?')) {
      return
    }

    setSessions((currentSessions) => {
      const remaining = currentSessions.filter((session) => session.id !== sessionId)
      const nextSessions = remaining.length > 0 ? remaining : [createEmptySession('Company support')]
      if (activeSessionId === sessionId) {
        setActiveSessionId(nextSessions[0].id)
      }
      return nextSessions
    })

    setIsSidebarOpen(false)
  }

  async function loadInsights() {
    setIsLoadingInsights(true)
    setInsightsError(null)
    try {
      const data = await fetchInsights()
      setInsights(data)
    } catch (cause) {
      const reason = cause instanceof Error ? cause.message : 'Failed to load insights.'
      setInsightsError(reason)
    } finally {
      setIsLoadingInsights(false)
    }
  }

  async function exportInsights() {
    try {
      const csvText = await downloadInsightsCsv()
      const blob = new Blob([csvText], { type: 'text/csv;charset=utf-8;' })
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = 'chat_analytics.csv'
      anchor.click()
      URL.revokeObjectURL(url)
    } catch (cause) {
      const reason = cause instanceof Error ? cause.message : 'Failed to export insights.'
      setInsightsError(reason)
    }
  }

  async function submitMessage(overrideMessage?: string) {
    const text = (overrideMessage ?? message).trim()
    if (!text || isSending || !activeSession) {
      return
    }

    const controller = new AbortController()
    const previousSession = cloneSession(activeSession)
    pendingRequestRef.current = {
      controller,
      sessionId: activeSession.id,
      previousSession,
      draft: text,
    }

    setMessage('')
    setIsSending(true)
    setError(null)

    const userMessage: ChatMessage = {
      id: createId(),
      role: 'user',
      name: USER_NAME,
      content: text,
      createdAt: new Date().toISOString(),
    }

    const placeholderId = createId()
    const assistantPlaceholder: ChatMessage = {
      id: placeholderId,
      role: 'assistant',
      name: ASSISTANT_NAME,
      content: 'Loading response...',
      createdAt: new Date().toISOString(),
    }

    updateActiveSession((session) => ({
      ...session,
      title: session.messages.length === 0 ? text.slice(0, 40) : session.title,
      updatedAt: new Date().toISOString(),
      messages: [...session.messages, userMessage, assistantPlaceholder],
    }))

    try {
      const response = await sendChatMessage(text, userId, activeSession.id, activeSession.messages, controller.signal)
      if (pendingRequestRef.current?.controller !== controller) {
        return
      }

      updateActiveSession((session) => ({
        ...session,
        updatedAt: new Date().toISOString(),
        messages: session.messages.map((entry) =>
          entry.id === placeholderId
            ? {
                ...entry,
                content: response.answer,
                suggestions: response.suggestions ?? [],
              }
            : entry,
        ),
      }))
    } catch (cause) {
      if (isAbortError(cause)) {
        return
      }

      const reason = cause instanceof Error ? cause.message : 'Failed to send message.'
      setError(reason)
      updateActiveSession((session) => ({
        ...session,
        updatedAt: new Date().toISOString(),
        messages: session.messages.map((entry) =>
          entry.id === placeholderId
            ? {
                ...entry,
                content: 'The assistant is temporarily unavailable. Please try again.',
              }
            : entry,
        ),
      }))
    } finally {
      if (pendingRequestRef.current?.controller === controller) {
        pendingRequestRef.current = null
      }

      setIsSending(false)
    }
  }

  return (
    <div className="app-shell">
      <button
        type="button"
        className={`sidebar-backdrop ${isSidebarOpen ? 'visible' : ''}`}
        aria-hidden="true"
        tabIndex={-1}
        onClick={() => setIsSidebarOpen(false)}
      />

      <aside className={`sidebar ${isSidebarOpen ? 'sidebar-open' : ''}`}>
        <div className="brand-block">
          <div className="brand-mark">S</div>
          <div>
            <p className="eyebrow">Savannah Tech Innovations</p>
            <h1>Support Hub</h1>
          </div>
        </div>

        <button className="new-session-button" type="button" onClick={createSession}>
          + New chat session
        </button>

        <div className="sidebar-note">
          <strong>Company insight log</strong>
          <p>Use the dashboard to review traffic, lead captures, and recommendations.</p>
        </div>

        <div className="session-list">
          {sessions.map((session) => (
            <article
              key={session.id}
              className={`session-card ${session.id === activeSessionId ? 'active' : ''}`}
              role="button"
              tabIndex={0}
              onClick={() => {
                navigateToViewMode('chat')
                setActiveSessionId(session.id)
                setIsSidebarOpen(false)
              }}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault()
                  navigateToViewMode('chat')
                  setActiveSessionId(session.id)
                  setIsSidebarOpen(false)
                }
              }}
            >
              <div className="session-card-header">
                <strong>{session.title}</strong>
                <span>{session.messages.length} messages</span>
              </div>
              <div className="session-actions">
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation()
                    renameSession(session.id)
                  }}
                >
                  Rename
                </button>
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation()
                    deleteSession(session.id)
                  }}
                >
                  Delete
                </button>
              </div>
            </article>
          ))}
        </div>
      </aside>

      <main className="chat-panel">
        {viewMode === 'chat' ? (
          <>
            <header className="chat-header">
              <button
                type="button"
                className="menu-button"
                onClick={() => setIsSidebarOpen((current) => !current)}
                aria-label="Toggle sidebar"
              >
                <span className="menu-icon" aria-hidden="true">
                  <span />
                  <span />
                  <span />
                </span>
                <span className="sr-only">Toggle sidebar</span>
              </button>
              <div>
                <p className="eyebrow">Company-only assistant</p>
                <h2>{activeSession?.title ?? 'Chat'}</h2>
              </div>
              <div className="status-pill">Connected</div>
            </header>

            <section className="message-stream" aria-live="polite">
              {activeSession?.messages.length ? (
                activeSession.messages.map((entry) => (
                  <MessageBubble key={entry.id} message={entry} onSuggestionClick={submitMessage} />
                ))
              ) : (
                <StarterPanel sessionId={activeSession?.id ?? 'default'} onChooseQuestion={submitMessage} />
              )}
              {isSending ? <TypingIndicator /> : null}
              <div ref={messageEndRef} />
            </section>

            {error ? <div className="error-banner">{error}</div> : null}

            <footer className="composer">
              <textarea
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                disabled={isSending}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault()
                    void submitMessage()
                  }
                }}
                placeholder="Ask about products, support, policies, pricing, or troubleshooting..."
                rows={2}
              />
              <div className="composer-actions">
                <span>Press Enter to send, Shift+Enter for a new line.</span>
                {isSending ? (
                  <button type="button" className="cancel-button" onClick={cancelPendingMessage}>
                    Cancel
                  </button>
                ) : (
                  <button
                    type="button"
                    className="send-button"
                    onClick={() => void submitMessage()}
                    disabled={!message.trim()}
                  >
                    Send message
                  </button>
                )}
              </div>
            </footer>
          </>
        ) : (
          <>
            <header className="chat-header">
              <button
                type="button"
                className="menu-button"
                onClick={() => setIsSidebarOpen((current) => !current)}
                aria-label="Toggle sidebar"
              >
                <span className="menu-icon" aria-hidden="true">
                  <span />
                  <span />
                  <span />
                </span>
                <span className="sr-only">Toggle sidebar</span>
              </button>
              <div>
                <p className="eyebrow">Admin dashboard</p>
                <h2>Insights and recommendations</h2>
              </div>
              <div className="dashboard-actions">
                <button type="button" className="secondary-button" onClick={() => navigateToViewMode('chat')}>
                  Back to chat
                </button>
                <div className="status-pill">{isLoadingInsights ? 'Loading insights...' : 'Live analytics'}</div>
              </div>
            </header>

            {insightsError ? <div className="error-banner">{insightsError}</div> : null}

            <AdminDashboard insights={insights} onExport={exportInsights} onRefresh={loadInsights} loading={isLoadingInsights} />
          </>
        )}
      </main>
    </div>
  )
}
