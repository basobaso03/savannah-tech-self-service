export type MessageRole = 'user' | 'assistant'

export interface ChatMessage {
  id: string
  role: MessageRole
  name: string
  content: string
  createdAt: string
  suggestions?: string[]
}

export interface ChatSession {
  id: string
  title: string
  createdAt: string
  updatedAt: string
  messages: ChatMessage[]
}

export interface ChatApiResponse {
  category: 'answerable' | 'unrelated' | 'company_related_missing' | string
  answer: string
  lead_saved?: boolean
  suggestions?: string[]
  matched_chunks?: Array<{
    id: number
    score: number
    content: string
    metadata: Record<string, unknown>
  }>
}

export interface ChatApiRequest {
  message: string
  userId: string
  sessionId: string
  history: ChatMessage[]
}

export interface InsightsResponse {
  total_events: number
  distinct_users: number
  categories: Record<string, number>
  lead_captures: number
  unanswered_requests: number
  average_top_score: number
  top_questions: Array<{ question: string; count: number }>
  top_titles: Array<{ title: string; count: number }>
  top_users: Array<{ user_id: string; count: number }>
  recommendations: string[]
}
