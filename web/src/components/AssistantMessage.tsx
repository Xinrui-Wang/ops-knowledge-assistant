import type { AssistantState, ReconciliationStatus } from '../types'

const ROUTE_LABEL: Record<string, string> = {
  rag: 'RAG · 制度检索',
  sql: 'SQL · 数据查询',
  hybrid: 'HYBRID · 制度 + 数据',
}

const STATUS_TEXT: Record<ReconciliationStatus, string> = {
  consistent: '✅ 制度要求与实际数据相符',
  violation: '⚠️ 实际数据未达到制度要求',
  conflict: '⚠️ 制度与数据存在冲突',
  insufficient: '❔ 无法直接比对',
}

function Step({ label, done }: { label: string; done: boolean }) {
  return (
    <span className={done ? 'step done' : 'step'}>
      {done ? '✓' : '·'} {label}
    </span>
  )
}

export function AssistantMessage({ state }: { state: AssistantState }) {
  const showRag = state.route === 'rag' || state.route === 'hybrid'
  const showSql = state.route === 'sql' || state.route === 'hybrid'
  const status = state.reconciliation?.status

  return (
    <div className="assistant">
      <div className="meta">
        {state.route ? (
          <span className={`badge badge-${state.route}`}>{ROUTE_LABEL[state.route]}</span>
        ) : (
          <span className="badge badge-pending">分析中…</span>
        )}
        {state.routeReason && <span className="reason">{state.routeReason}</span>}
      </div>

      <div className="steps">
        {showRag && <Step label="检索制度" done={state.sources.length > 0} />}
        {showSql && <Step label="定位表列" done={state.schemaTables.length > 0} />}
        {showSql && <Step label="生成 SQL" done={Boolean(state.sql)} />}
        {showSql && (
          <Step
            label={state.executing ? '执行 SQL 中…' : '执行 SQL'}
            done={state.columns.length > 0}
          />
        )}
        {showSql && state.metrics.length > 0 && <Step label="口径对齐" done />}
      </div>

      {state.schemaTables.length > 0 && (
        <details className="panel" open>
          <summary>选表与选列（schema linking）</summary>
          {state.schemaCandidates.length > 0 && (
            <p className="reason">向量粗筛候选：{state.schemaCandidates.join('、')}</p>
          )}
          <p>
            <b>选中表：</b>
            {state.schemaTables.join('、')}
          </p>
          <ul className="sources">
            {Object.entries(state.schemaColumns).map(([table, cols]) => (
              <li key={table}>
                <b>{table}</b>：{cols.join('、')}
              </li>
            ))}
          </ul>
          {state.schemaReason && <p className="reason">理由：{state.schemaReason}</p>}
        </details>
      )}

      {state.reconciliation && status && (
        <div className={`verdict verdict-${status}`}>
          <div className="verdict-title">{STATUS_TEXT[status]}</div>
          {state.reconciliation.policy && <p><b>制度要求：</b>{state.reconciliation.policy}</p>}
          {state.reconciliation.data && <p><b>实际数据：</b>{state.reconciliation.data}</p>}
          {state.reconciliation.explanation && <p>{state.reconciliation.explanation}</p>}
          {(status === 'violation' || status === 'conflict') && (
            <p className="verdict-note">制度与数据同时呈现，未做取舍；建议由业务方确认口径后再下结论。</p>
          )}
        </div>
      )}

      {state.answer && <div className="answer">{state.answer}</div>}

      {state.citations.length > 0 && (
        <div className="citations">
          {state.citations.map((item) => (
            <span key={item.chunk_id} className="citation" title={item.chunk_id}>
              [{item.index}] {item.citation}
            </span>
          ))}
        </div>
      )}

      {state.sql && (
        <details className="panel">
          <summary>SQL</summary>
          <pre>{state.sql}</pre>
        </details>
      )}

      {state.columns.length > 0 && (
        <details className="panel">
          <summary>查询结果（{state.rows.length} 行）</summary>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  {state.columns.map((col) => (
                    <th key={col}>{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {state.rows.map((row, index) => (
                  <tr key={index}>
                    {state.columns.map((col) => (
                      <td key={col}>{String(row[col] ?? '')}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}

      {state.sources.length > 0 && (
        <details className="panel">
          <summary>检索来源（{state.sources.length} 条）</summary>
          <ul className="sources">
            {state.sources.map((source) => (
              <li key={source.chunk_id}>
                {source.citation}
                <span className="score">{source.score}</span>
              </li>
            ))}
          </ul>
        </details>
      )}

      {state.error && <div className="error">出错了：{state.error}</div>}
    </div>
  )
}
