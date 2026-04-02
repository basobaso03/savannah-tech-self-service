import type { ChatApiRequest, ChatApiResponse, ChatMessage, InsightsResponse } from './types'

const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export async function fetchInsights(): Promise<InsightsResponse> {
  const response = await fetch(`${baseUrl}/chat/insights`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
  })

  if (!response.ok) {
    const detail = await response.text()
    throw new Error(detail || `Request failed with status ${response.status}`)
  }

  return response.json() as Promise<InsightsResponse>
}

export async function downloadInsightsCsv(): Promise<string> {
  const response = await fetch(`${baseUrl}/chat/insights/export`, {
    method: 'GET',
  })

  if (!response.ok) {
    const detail = await response.text()
    throw new Error(detail || `Request failed with status ${response.status}`)
  }

  return response.text()
}

export async function sendChatMessage(
  message: string,
  userId: string,
  sessionId: string,
  history: ChatMessage[],
  signal?: AbortSignal,
): Promise<ChatApiResponse> {
  const payload: ChatApiRequest = {
    message,
    userId,
    sessionId,
    history,
  }

  const response = await fetch(`${baseUrl}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
    signal,
  })

  if (!response.ok) {
    const detail = await response.text()
    throw new Error(detail || `Request failed with status ${response.status}`)
  }

  return response.json() as Promise<ChatApiResponse>
}
