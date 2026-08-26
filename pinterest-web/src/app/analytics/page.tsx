"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Sparkline } from "@/components/sparkline"
import {
  fetchAnalytics,
  fetchLearning,
  type AnalyticsSummary,
  type LearningCounts,
} from "@/lib/api"

const STATUSES = ["pending", "ready", "scheduled", "published", "failed"] as const

const STAT_CARDS: { key: keyof AnalyticsSummary["totals"]; label: string; format?: (n: number) => string }[] = [
  { key: "pins", label: "Total Pins" },
  { key: "published", label: "Published" },
  { key: "scheduled", label: "Scheduled" },
]

export default function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsSummary | null>(null)
  const [learning, setLearning] = useState<LearningCounts | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    let active = true
    fetchAnalytics()
      .then((res) => {
        if (active) setData(res)
      })
      .catch(() => {
        if (active) setError(true)
      })
    fetchLearning()
      .then((res) => {
        if (active) setLearning(res)
      })
      .catch(() => {})
    return () => {
      active = false
    }
  }, [])

  if (error) {
    return (
      <div className="mx-auto max-w-5xl px-6 py-10" role="alert">
        Failed to load analytics.
      </div>
    )
  }

  if (!data) {
    return (
      <div className="mx-auto max-w-5xl px-6 py-10">
        <p className="text-muted-foreground">Loading analytics…</p>
      </div>
    )
  }

  const ctr = `${(data.ctr * 100).toFixed(2)}%`

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <h1 className="text-2xl font-semibold tracking-tight">Analytics</h1>
      <p className="mt-2 text-muted-foreground">
        Performance and publishing overview.
      </p>

      <section className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {STAT_CARDS.map(({ key, label }) => (
          <Card key={key} size="sm">
            <CardHeader>
              <CardTitle className="text-muted-foreground font-normal">{label}</CardTitle>
            </CardHeader>
            <CardContent className="text-2xl font-semibold tracking-tight">
              {data.totals[key].toLocaleString()}
            </CardContent>
          </Card>
        ))}
        <Card size="sm">
          <CardHeader>
            <CardTitle className="text-muted-foreground font-normal">CTR</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold tracking-tight">{ctr}</CardContent>
        </Card>
      </section>

      <section className="mt-6">
        <h2 className="text-lg font-medium">Status breakdown</h2>
        <ul className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-5">
          {STATUSES.map((status) => (
            <Card key={status} size="sm">
              <CardHeader>
                <CardTitle className="text-muted-foreground font-normal capitalize">{status}</CardTitle>
              </CardHeader>
              <CardContent className="text-2xl font-semibold tracking-tight">
                {(data.by_status[status] ?? 0).toLocaleString()}
              </CardContent>
            </Card>
          ))}
        </ul>
      </section>

      <section className="mt-6">
        <h2 className="text-lg font-medium">Learning signals</h2>
        {!learning ? (
          <p className="mt-3 text-muted-foreground">No signals yet</p>
        ) : learning.total === 0 ? (
          <p className="mt-3 text-muted-foreground">No signals yet</p>
        ) : (
          <Card size="sm" className="mt-3">
            <CardHeader>
              <CardTitle className="text-muted-foreground font-normal">
                Total signals
              </CardTitle>
            </CardHeader>
            <CardContent className="text-2xl font-semibold tracking-tight">
              {learning.total.toLocaleString()}
            </CardContent>
            <CardContent className="text-sm text-muted-foreground">
              {Object.entries(learning.counts)
                .map(([action, count]) => `${action}: ${count}`)
                .join(", ")}
            </CardContent>
          </Card>
        )}
      </section>

      <section className="mt-6">
        <h2 className="text-lg font-medium">Top pins</h2>
        {data.top_pins.length === 0 ? (
          <p className="mt-3 text-muted-foreground">No analytics yet</p>
        ) : (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted-foreground">
                  <th className="py-2 pr-4 font-medium">Title</th>
                  <th className="py-2 pr-4 font-medium">Impressions</th>
                  <th className="py-2 pr-4 font-medium">Saves</th>
                  <th className="py-2 pr-4 font-medium">Clicks</th>
                </tr>
              </thead>
              <tbody>
                {data.top_pins.map((pin) => (
                  <tr key={pin.id} className="border-t">
                    <td className="py-2 pr-4">{pin.title}</td>
                    <td className="py-2 pr-4">{pin.impressions.toLocaleString()}</td>
                    <td className="py-2 pr-4">{pin.saves.toLocaleString()}</td>
                    <td className="py-2 pr-4">{pin.clicks.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="mt-6">
        <h2 className="text-lg font-medium">Last 30 days</h2>
        <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Card size="sm">
            <CardHeader>
              <CardTitle className="text-muted-foreground font-normal">Published per day</CardTitle>
            </CardHeader>
            <CardContent>
              <Sparkline data={data.series.map((s) => s.published)} />
            </CardContent>
          </Card>
          <Card size="sm">
            <CardHeader>
              <CardTitle className="text-muted-foreground font-normal">Clicks per day</CardTitle>
            </CardHeader>
            <CardContent>
              <Sparkline data={data.series.map((s) => s.clicks)} />
            </CardContent>
          </Card>
        </div>
      </section>
    </div>
  )
}
