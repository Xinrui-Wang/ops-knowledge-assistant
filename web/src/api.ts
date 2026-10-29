import type { ChatEvent } from './types'

/**
 * 用 fetch + ReadableStream 读取 SSE。
 * EventSource 只支持 GET，这里需要 POST 提交问题，所以自己解析。
 */
export async function streamChat(
  question: string,
  onEvent: (event: ChatEvent) => void,
): Promise<void> {
  const response = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })

  if (!response.ok || !response.body) {
    throw new Error(`请求失败：HTTP ${response.status}`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let boundary = buffer.indexOf('\n\n')
    while (boundary !== -1) {
      const chunk = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)
      const dataLine = chunk.split('\n').find((line) => line.startsWith('data: '))
      if (dataLine) {
        onEvent(JSON.parse(dataLine.slice(6)) as ChatEvent)
      }
      boundary = buffer.indexOf('\n\n')
    }
  }
}
