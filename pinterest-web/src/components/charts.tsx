"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { fetchAnalytics, type AnalyticsSummary } from "@/lib/api"

function Skeleton({ className }: { className?: string }) {
  return (
    <div className={`animate-pulse rounded-md bg-muted ${className ?? ""}`} />
  )
}

export function OverviewChart() {
  const [data, setData] = useState<AnalyticsSummary | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    fetchAnalytics()
      .then((res) => {
        if (active) setData(res)
      })
      .catch(() => {})
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-32" />
        </CardHeader>
        <CardContent>
          <div className="flex items-end gap-2 h-40">
            {[...Array(7)].map((_, i) => (
              <div key={i} className="flex-1">
                <Skeleton className="h-full w-full" />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    )
  }

  if (!data || data.series.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium text-muted-foreground">Last 7 Days</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <p className="text-sm text-muted-foreground">No analytics data yet</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  const recent = data.series.slice(-7)
  const maxPublished = Math.max(...recent.map((s) => s.published), 1)

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium text-muted-foreground">Last 7 Days</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-end gap-2 h-40">
          {recent.map((day, i) => {
            const height = maxPublished > 0 ? (day.published / maxPublished) * 100 : 0
            return (
              <div key={i} className="flex flex-1 flex-col items-center gap-1">
                <span className="text-xs font-medium">{day.published}</span>
                <div
                  className="w-full rounded-t-md bg-primary transition-all"
                  style={{ height: `${Math.max(height, 4)}%` }}
                />
                <span className="text-[10px] text-muted-foreground">
                  {new Date(day.date).toLocaleDateString(undefined, { weekday: "short" })}
                </span>
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}

export function PerformanceChart() {
  const [data, setData] = useState<AnalyticsSummary | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    fetchAnalytics()
      .then((res) => {
        if (active) setData(res)
      })
      .catch(() => {})
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-32" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-40 w-full" />
        </CardContent>
      </Card>
    )
  }

  if (!data || data.series.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium text-muted-foreground">Performance</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <p className="text-sm text-muted-foreground">No performance data yet</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  const recent = data.series.slice(-7)
  const maxClicks = Math.max(...recent.map((s) => s.clicks), 1)

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium text-muted-foreground">Performance</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-end gap-2 h-40">
          {recent.map((day, i) => {
            const height = maxClicks > 0 ? (day.clicks / maxClicks) * 100 : 0
            return (
              <div key={i} className="flex flex-1 flex-col items-center gap-1">
                <span className="text-xs font-medium">{day.clicks}</span>
                <div
                  className="w-full rounded-t-md bg-emerald-500 transition-all"
                  style={{ height: `${Math.max(height, 4)}%` }}
                />
                <span className="text-[10px] text-muted-foreground">
                  {new Date(day.date).toLocaleDateString(undefined, { weekday: "short" })}
                </span>
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}
