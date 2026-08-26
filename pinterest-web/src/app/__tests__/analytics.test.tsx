import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import AnalyticsPage from "@/app/analytics/page"
import * as api from "@/lib/api"

const sample = {
  totals: { pins: 12, published: 5, scheduled: 3, pending: 2, ready: 2, failed: 0 },
  by_status: { pending: 2, ready: 2, scheduled: 3, published: 5, failed: 0 },
  top_pins: [{ id: 7, title: "Sunset Beach", impressions: 1234, saves: 20, clicks: 5 }],
  series: [{ date: "2026-08-20", published: 1, clicks: 3, impressions: 100 }],
  ctr: 0.0123,
}

describe("AnalyticsPage", () => {
  it("renders totals, top pins, status breakdown, and sparklines", async () => {
    vi.spyOn(api, "fetchAnalytics").mockResolvedValue(sample as api.AnalyticsSummary)

    const { container } = render(<AnalyticsPage />)

    expect(await screen.findByText("12")).toBeDefined()
    expect(await screen.findByText("1.23%")).toBeDefined()
    expect(screen.getByText("Sunset Beach")).toBeDefined()
    expect(screen.getByText("pending")).toBeDefined()

    expect(container.querySelectorAll("svg").length).toBe(2)
  })

  it("shows an empty state when there are no top pins", async () => {
    vi.spyOn(api, "fetchAnalytics").mockResolvedValue({
      ...sample,
      top_pins: [],
    } as api.AnalyticsSummary)

    render(<AnalyticsPage />)
    expect(await screen.findByText("No analytics yet")).toBeDefined()
  })
})
