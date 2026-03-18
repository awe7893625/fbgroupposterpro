const BASE_URL = 'http://localhost:3080'

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`API ${path} failed (${res.status}): ${text}`)
  }
  return res.json()
}

export const api = {
  // Accounts
  getAccounts: () => apiFetch<Account[]>('/api/accounts'),
  createAccount: (data: CreateAccountInput) => apiFetch<Account>('/api/accounts', { method: 'POST', body: JSON.stringify(data) }),
  deleteAccount: (id: number) => apiFetch<void>(`/api/accounts/${id}`, { method: 'DELETE' }),

  // Groups
  getGroups: (accountId?: number) => apiFetch<Group[]>(`/api/groups${accountId ? `?account_id=${accountId}` : ''}`),
  createGroup: (data: CreateGroupInput) => apiFetch<Group>('/api/groups', { method: 'POST', body: JSON.stringify(data) }),
  deleteGroup: (id: number) => apiFetch<void>(`/api/groups/${id}`, { method: 'DELETE' }),

  // Posts
  getPosts: (status?: string) => apiFetch<Post[]>(`/api/posts${status ? `?status=${status}` : ''}`),
  createPost: (data: CreatePostInput) => apiFetch<{post_id: number; status: string}>('/api/posts', { method: 'POST', body: JSON.stringify(data) }),
  startPost: (id: number) => apiFetch<{success: boolean}>(`/api/posts/${id}/start`, { method: 'POST' }),
  deletePost: (id: number) => apiFetch<void>(`/api/posts/${id}`, { method: 'DELETE' }),

  // Reports
  getReport: (params?: { from?: string; to?: string; account_id?: number }) => {
    const q = new URLSearchParams()
    if (params?.from) q.set('from', params.from)
    if (params?.to) q.set('to', params.to)
    if (params?.account_id) q.set('account_id', String(params.account_id))
    return apiFetch<ReportResponse>(`/api/report?${q.toString()}`)
  },

  // AI
  generateContent: (data: AIGenerateInput) => apiFetch<{variants: string[]}>('/api/ai/generate', { method: 'POST', body: JSON.stringify(data) }),

  // Health
  health: () => apiFetch<{status: string; version: string}>('/api/health'),
}

// Types
export interface Account {
  id: number; name: string; email: string; status: string; proxy?: string; created_at: string
}
export interface Group {
  id: number; name: string; url: string; tag?: string; join_status: string; post_count: number; last_post_at?: string
  platform: string; platform_entity_id?: string
}
export interface Post {
  id: number; content: string; status: string; total_groups: number; success_count: number; fail_count: number; scheduled_at?: string; created_at: string
}
export interface PostRecord {
  id: number; group_name: string; status: string; fb_post_url?: string; post_url?: string; posted_at?: string; error_msg?: string
}
export interface ReportResponse {
  records: PostRecord[]; summary: { total: number; success: number; failed: number; deleted: number; success_rate: number }
}
export interface CreateAccountInput { name: string; email: string; password: string; proxy?: string }
export interface CreateGroupInput { account_id: number; url: string; name?: string; tag?: string; platform?: string; platform_entity_id?: string }
export interface CreatePostInput { account_id: number; content: string; group_ids: number[]; interval_seconds?: number; auto_delete_days?: number; scheduled_at?: string }
export interface AIGenerateInput { product_data: Record<string, string>; style?: string; variant_count?: number; license_key?: string; device_id?: string }
