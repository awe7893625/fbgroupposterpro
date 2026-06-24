function getBase(): string {
  if (typeof window === 'undefined') return ''
  return localStorage?.getItem('remote_api_base') || window.location.origin
}

export class LicenseRequiredError extends Error {
  constructor(public payload: any) {
    super(payload?.message || 'License required')
    this.name = 'LicenseRequiredError'
  }
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${getBase()}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(typeof window !== 'undefined' && localStorage?.getItem('remote_token') && {
        'X-Access-Token': localStorage.getItem('remote_token')!
      }),
      ...options?.headers,
    },
  })
  if (res.status === 402) {
    throw new LicenseRequiredError(await res.json().catch(() => ({})))
  }
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

  // 程式化改圖（品牌浮層/聯絡資訊/外框/拼圖）
  processImage: (data: ProcessImageInput) => apiFetch<{outputs: string[]}>('/api/image/process', { method: 'POST', body: JSON.stringify(data) }),

  // Scrape (591 / HouseBox listing → FB-ready post)
  scrape: (url: string, account_id: number) => apiFetch<ScrapeResponse>('/api/scrape', {
    method: 'POST', body: JSON.stringify({ url, account_id }),
  }),

  // License
  licenseStatus: () => apiFetch<LicenseStatus>('/api/license/status'),
  licenseActivate: (license_key: string) => apiFetch<LicenseStatus>('/api/license/activate', { method: 'POST', body: JSON.stringify({ license_key }) }),
  licenseTrial: (email: string) => apiFetch<{ success?: boolean; license_key?: string; error?: string; message?: string }>('/api/license/trial', { method: 'POST', body: JSON.stringify({ email }) }),
  licenseRefresh: () => apiFetch<LicenseStatus>('/api/license/refresh', { method: 'POST' }),
  licenseDeactivate: () => apiFetch<{ ok: boolean }>('/api/license/deactivate', { method: 'POST' }),
  licensePurchaseUrl: (plan: string, email?: string) => {
    const q = new URLSearchParams({ plan })
    if (email) q.set('email', email)
    return apiFetch<{ url: string }>(`/api/license/purchase_url?${q.toString()}`)
  },

  // Health
  health: () => apiFetch<{status: string; version: string}>('/api/health'),
}

export interface LicenseStatus {
  valid: boolean
  plan?: string
  expires_at?: string
  activated_at?: string
  license_key?: string
  error?: string
  last_verified_at?: number
  source?: 'remote' | 'cache' | 'none'
  device_id?: string
}

// Onboard
export const onboard = {
  startLogin: (accountId: number, platform: string = 'fb') => apiFetch<{ success: boolean; cookie_count?: number; error?: string }>(`/api/onboard/login/${accountId}?platform=${platform}`, { method: 'POST' }),
  getStatus: (accountId: number) => apiFetch<{ id: number; logged_in: boolean; last_used_at?: string }>(`/api/onboard/status/${accountId}`),
}

// Types
export interface Account {
  id: number; name: string; email: string; status: string; proxy?: string;
  logged_in?: boolean; last_used_at?: string; created_at: string
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
export interface ScrapeData {
  title: string; price?: string; priceUnit?: string; address?: string;
  description?: string; images?: string[]; area?: string; rooms?: string;
  floor?: string; totalFloors?: string; type?: string; source?: string;
  platform?: string; unitPrice?: string; mainArea?: string; subArea?: string;
  buildingType?: string; agentPhone?: string; company?: string;
  propertyId?: string; post_content: string;
}
export interface ScrapeResponse {
  success: boolean; platform?: '591' | 'housebox'; data?: ScrapeData; error?: string;
}

export interface CreateAccountInput { name: string; email: string; password: string; proxy?: string }
export interface CreateGroupInput { account_id: number; url: string; name?: string; tag?: string; platform?: string; platform_entity_id?: string }
export interface CreatePostInput { account_id: number; content: string; group_ids: number[]; interval_seconds?: number; auto_delete_days?: number; scheduled_at?: string }
export interface AIGenerateInput { product_data: Record<string, string>; style?: string; variant_count?: number; license_key?: string; device_id?: string }
export interface ProcessImageInput { paths: string[]; op: 'brand' | 'badge' | 'frame' | 'collage'; agent_name?: string; phone?: string; company?: string; label?: string; out_dir?: string }
