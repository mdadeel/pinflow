export type PinStatus = "pending" | "ready" | "scheduled" | "published" | "failed"

export interface Pin {
  id: number
  filename: string
  image_url: string
  status: PinStatus
  title: string | null
  description: string | null
  alt_text: string | null
  primary_keyword: string | null
  secondary_keywords: string[] | null
  tags: string[] | null
  board_name: string | null
  content_category: string | null
  file_size: number | null
  width: number | null
  height: number | null
  created_at: string
  scheduled_time: string | null
}

export interface PinListResponse {
  items: Pin[]
  total: number
  page: number
  per_page: number
}

export interface FetchPinsParams {
  status?: PinStatus
  page?: number
  per_page?: number
  q?: string
}

export interface Stats {
  total: number
  pending: number
  ready: number
  scheduled: number
  published: number
  failed: number
  impressions: number
  clicks: number
  saves: number
  outbound_clicks: number
}

export interface UploadResult {
  added: Pin[]
  duplicates: string[]
  rejected: { filename: string; reason: string }[]
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

export class ApiError extends Error {
  constructor(public readonly status: number, public readonly body: unknown, path: string) {
    super(`API ${status} on ${path}`)
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body && !(init.body instanceof FormData)
        ? { "Content-Type": "application/json" }
        : {}),
      ...init?.headers,
    },
  })
  if (!res.ok) {
    let body: unknown = null
    try { body = await res.json() } catch {}
    throw new ApiError(res.status, body, path)
  }
  return res.json() as Promise<T>
}

export function fetchPins(params: FetchPinsParams = {}): Promise<PinListResponse> {
  const search = new URLSearchParams()
  if (params.status) search.set("status", params.status)
  if (params.page != null) search.set("page", String(params.page))
  if (params.per_page != null) search.set("per_page", String(params.per_page))
  if (params.q) search.set("q", params.q)
  const qs = search.toString()
  return request<PinListResponse>(`/api/pins${qs ? `?${qs}` : ""}`)
}

export function fetchStats(): Promise<Stats> {
  return request<Stats>("/api/stats")
}

export function movePin(id: number, status: PinStatus): Promise<Pin> {
  return request<Pin>(`/api/pins/${id}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  })
}

export function uploadFiles(files: File[]): Promise<UploadResult> {
  const form = new FormData()
  for (const file of files) form.append("files", file)
  return request<UploadResult>("/api/uploads", { method: "POST", body: form })
}

export interface PinEdit {
  title?: string | null
  description?: string | null
  alt_text?: string | null
  primary_keyword?: string | null
  secondary_keywords?: string[] | null
  tags?: string[] | null
  board_name?: string | null
  content_category?: string | null
}

export function fetchPin(id: number): Promise<Pin> {
  return request<Pin>(`/api/pins/${id}`)
}

export function updatePin(id: number, body: PinEdit): Promise<Pin> {
  return request<Pin>(`/api/pins/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  })
}

export function regeneratePin(id: number): Promise<Pin> {
  return request<Pin>(`/api/pins/${id}/regenerate`, { method: "POST" })
}

export function approvePin(id: number): Promise<Pin> {
  return request<Pin>(`/api/pins/${id}/approve`, { method: "POST" })
}
