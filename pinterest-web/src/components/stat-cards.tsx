"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { fetchStats, type Stats } from "@/lib/api"

const EMPTY: Stats = {
  total: 0,
  pending: 0,
  ready: 0,
  scheduled: 0,
  published: 0,
  failed: 0,
  impressions: 0,
  clicks: 0,
  saves: 0,
  outbound_clicks: 0,
}

const CARDS: { key: keyof Stats; label: string }[] = [
  { key: "total", label: "Total Images" },
  { key: "pending", label: "Pending" },
  { key: "ready", label: "AI Generated" },
  { key: "scheduled", label: "Scheduled" },
  { key: "published", label: "Published" },
  { key: "failed", label: "Failed" },
  { key: "clicks", label: "Clicks" },
  { key: "saves", label: "Saves" },
  { key: "impressions", label: "Impressions" },
]

export function StatCards() {
  const [stats, setStats] = useState<Stats>(EMPTY)

  useEffect(() => {
    let active = true
    fetchStats()
      .then((data) => {
        if (active) setStats(data)
      })
      .catch(() => {})
    return () => {
      active = false
    }
  }, [])

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      {CARDS.map(({ key, label }) => (
        <Card key={key} size="sm">
          <CardHeader>
            <CardTitle className="text-muted-foreground font-normal">{label}</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold tracking-tight">
            {stats[key].toLocaleString()}
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
