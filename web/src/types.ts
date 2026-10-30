export type RouteName = 'rag' | 'sql' | 'hybrid'

export interface Source {
  citation: string
  chunk_id: string
  score: number
}

export interface Citation {
  index: number
  citation: string
  chunk_id: string
}

export type ReconciliationStatus = 'consistent' | 'violation' | 'conflict' | 'insufficient'

export interface Reconciliation {
  status: ReconciliationStatus
  policy: string
  data: string
  explanation: string
}

export type ChatEvent =
  | { type: 'route'; route: RouteName; reason: string }
  | { type: 'retrieved'; sources: Source[] }
  | {
      type: 'schema_linking'
      detail: { tables: string[]; reason: string; candidates: string[]; columns: Record<string, string[]> }
    }
  | { type: 'metrics'; items: string[] }
  | { type: 'sql_generated'; sql: string }
  | { type: 'sql_executing'; sql: string }
  | { type: 'sql_executed'; sql: string; columns: string[]; rows: Record<string, unknown>[] }
  | { type: 'reconciliation'; detail: Reconciliation }
  | { type: 'citations'; items: Citation[] }
  | { type: 'answer_delta'; delta: string }
  | { type: 'error'; message: string }
  | { type: 'done' }

export interface AssistantState {
  route?: RouteName
  routeReason?: string
  sources: Source[]
  schemaTables: string[]
  schemaColumns: Record<string, string[]>
  schemaCandidates: string[]
  schemaReason?: string
  executing: boolean
  metrics: string[]
  sql?: string
  columns: string[]
  rows: Record<string, unknown>[]
  reconciliation?: Reconciliation
  citations: Citation[]
  answer: string
  error?: string
  done: boolean
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  text?: string
  state?: AssistantState
}

export function emptyState(): AssistantState {
  return {
    sources: [],
    schemaTables: [],
    schemaColumns: {},
    schemaCandidates: [],
    executing: false,
    metrics: [],
    columns: [],
    rows: [],
    citations: [],
    answer: '',
    done: false,
  }
}
