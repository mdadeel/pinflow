import { describe, it, expect, vi, beforeEach } from "vitest"
import { fetchPins, fetchStats, movePin, uploadFiles } from "../api"

beforeEach(() => {
  global.fetch = vi.fn()
})

function mockFetch(body: unknown, ok = true) {
  ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
    ok,
    status: ok ? 200 : 400,
    statusText: ok ? "OK" : "Bad Request",
    json: () => Promise.resolve(body),
  } as unknown as Response)
}

describe("fetchPins", () => {
  it("returns PinListResponse with items", async () => {
    mockFetch({ items: [], total: 0, page: 1, per_page: 50 })
    const r = await fetchPins()
    expect(r.total).toBe(0)
    expect(r.items).toHaveLength(0)
  })

  it("passes status and pagination params", async () => {
    mockFetch({ items: [], total: 0, page: 2, per_page: 10 })
    await fetchPins({ status: "ready", page: 2, per_page: 10 })
    const url = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string
    expect(url).toContain("status=ready")
    expect(url).toContain("page=2")
    expect(url).toContain("per_page=10")
  })

  it("encodes search query", async () => {
    mockFetch({ items: [], total: 0, page: 1, per_page: 50 })
    await fetchPins({ q: "anime wallpaper" })
    const url = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string
    expect(url).toContain("q=anime+wallpaper")
  })
})

describe("fetchStats", () => {
  it("returns Stats shape", async () => {
    mockFetch({ total: 10, pending: 3, ready: 2, scheduled: 1, published: 3, failed: 1,
                 impressions: 5000, clicks: 200, saves: 40, outbound_clicks: 30 })
    const s = await fetchStats()
    expect(s.total).toBe(10)
    expect(s.ready).toBe(2)
    expect(s.impressions).toBe(5000)
  })
})

describe("movePin", () => {
  it("PATCHes status and returns Pin", async () => {
    mockFetch({ id: 5, status: "ready", image_url: "/media/5", filename: "a.png",
                 title: null, description: null, alt_text: null, primary_keyword: null,
                 secondary_keywords: null, tags: null, board_name: null, content_category: null,
                 file_size: null, width: null, height: null, created_at: "2026-08-25T00:00:00" })
    const p = await movePin(5, "ready")
    expect(p.id).toBe(5)
    expect(p.status).toBe("ready")
    const [url, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0] as [string, RequestInit]
    expect(url).toContain("/api/pins/5/status")
    expect(init.method).toBe("PATCH")
    expect(JSON.parse(init.body as string)).toEqual({ status: "ready" })
  })
})

describe("uploadFiles", () => {
  it("POSTs FormData and returns UploadResult", async () => {
    mockFetch({ added: [], duplicates: ["a.png"], rejected: [] })
    const f = [new File([""], "a.png", { type: "image/png" })]
    const r = await uploadFiles(f)
    expect(r.duplicates).toContain("a.png")
    const [url, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0] as [string, RequestInit]
    expect(url).toContain("/api/uploads")
    expect(init.method).toBe("POST")
  })
})
