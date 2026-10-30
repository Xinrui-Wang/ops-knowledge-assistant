import { useEffect, useRef, useState } from 'react'

import { streamChat } from './api'
import { AssistantMessage } from './components/AssistantMessage'
import { emptyState, type AssistantState, type ChatEvent, type Message } from './types'

let sequence = 0
const nextId = () => `m${++sequence}`

function applyEvent(state: AssistantState, event: ChatEvent): AssistantState {
  switch (event.type) {
    case 'route':
      return { ...state, route: event.route, routeReason: event.reason }
    case 'retrieved':
      return { ...state, sources: event.sources }
    case 'schema_linking':
      return {
        ...state,
        schemaTables: event.detail.tables,
        schemaColumns: event.detail.columns,
        schemaCandidates: event.detail.candidates,
        schemaReason: event.detail.reason,
      }
    case 'metrics':
      return { ...state, metrics: event.items }
    case 'sql_generated':
      return { ...state, sql: event.sql }
    case 'sql_executing':
      return { ...state, sql: event.sql, executing: true }
    case 'sql_executed':
      return { ...state, columns: event.columns, rows: event.rows, executing: false }
    case 'reconciliation':
      return { ...state, reconciliation: event.detail }
    case 'citations':
      return { ...state, citations: event.items }
    case 'answer_delta':
      return { ...state, answer: state.answer + event.delta }
    case 'error':
      return { ...state, error: event.message }
    case 'done':
      return { ...state, done: true }
    default:
      return state
  }
}

const EXAMPLES = [
  '一线城市出差住宿标准是多少',
  '第三季度各大区销售额排名如何',
  '华东区第三季度售后响应是否达标',
  '销售一部一线城市住宿报销有没有超标',
  '哪个大区客单价最高',
]

export default function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async (question: string) => {
    const trimmed = question.trim()
    if (!trimmed || busy) return

    setBusy(true)
    setInput('')
    const assistantId = nextId()
    setMessages((prev) => [
      ...prev,
      { id: nextId(), role: 'user', text: trimmed },
      { id: assistantId, role: 'assistant', state: emptyState() },
    ])

    try {
      await streamChat(trimmed, (event) => {
        setMessages((prev) =>
          prev.map((message) =>
            message.id === assistantId && message.state
              ? { ...message, state: applyEvent(message.state, event) }
              : message,
          ),
        )
      })
    } catch (error) {
      setMessages((prev) =>
        prev.map((message) =>
          message.id === assistantId && message.state
            ? { ...message, state: { ...message.state, error: String(error) } }
            : message,
        ),
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="app">
      <header>
        <h1>企业运营知识助手</h1>
        <p>自动选择制度检索 / 数据查询 / 两者结合，并在冲突时同时呈现两边。</p>
      </header>

      <main>
        {messages.length === 0 && (
          <div className="welcome">
            <p>试试这些问题：</p>
            <div className="examples">
              {EXAMPLES.map((example) => (
                <button key={example} onClick={() => send(example)} disabled={busy}>
                  {example}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((message) =>
          message.role === 'user' ? (
            <div key={message.id} className="user">
              {message.text}
            </div>
          ) : (
            <div key={message.id} className="turn">
              <AssistantMessage state={message.state ?? emptyState()} />
            </div>
          ),
        )}
        <div ref={bottomRef} />
      </main>

      <footer>
        <textarea
          value={input}
          placeholder="问点什么，比如：华东区售后响应达标吗？"
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              void send(input)
            }
          }}
          rows={2}
        />
        <button onClick={() => void send(input)} disabled={busy || !input.trim()}>
          {busy ? '回答中…' : '发送'}
        </button>
      </footer>
    </div>
  )
}
