"use client"

import { useEffect, useState } from "react"
import { Card, CardContent } from "@/components/ui/card"
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

function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-md bg-muted ${className ?? ""}`}
    />
  )
}

function StatCardSkeleton() {
  return (
    <Card>
      <CardContent className="pt-6">
        <Skeleton className="h-4 w-20" />
        <Skeleton className="mt-3 h-8 w-16" />
      </CardContent>
    </Card>
  )
}

function HeroCardSkeleton() {
  return (
    <Card className="col-span-2 md:col-span-1 bg-primary/10">
      <CardContent className="pt-6">
        <Skeleton className="h-4 w-20 bg-primary/20" />
        <Skeleton className="mt-3 h-10 w-24 bg-primary/20" />
        <Skeleton className="mt-2 h-3 w-28 bg-primary/20" />
      </CardContent>
    </Card>
  )
}

function PipelineCardSkeleton() {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center justify-between">
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-2 w-2 rounded-full" />
        </div>
        <div className="mt-3 space-y-2">
          <div className="flex items-center justify-between">
            <Skeleton className="h-3 w-16" />
            <Skeleton className="h-4 w-8" />
          </div>
          <div className="flex items-center justify-between">
            <Skeleton className="h-3 w-16" />
            <Skeleton className="h-4 w-8" />
          </div>
          <div className="flex items-center justify-between">
            <Skeleton className="h-3 w-16" />
            <Skeleton className="h-4 w-8" />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export function StatCards() {
  const [stats, setStats] = useState<Stats>(EMPTY)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    fetchStats()
      .then((data) => {
        if (active) setStats(data)
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
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <HeroCardSkeleton />
        <PipelineCardSkeleton />
        <StatCardSkeleton />
        <StatCardSkeleton />
      </div>
    )
  }

  const successRate = stats.total > 0
    ? Math.round(((stats.published + stats.scheduled) / stats.total) * 100)
    : 0

  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
      {/* Hero metric - Total pins */}
      <Card className="col-span-2 md:col-span-1 bg-primary text-primary-foreground">
        <CardContent className="pt-6">
          <p className="text-sm font-medium opacity-80">Total Pins</p>
          <p className="mt-1 text-4xl font-bold tracking-tight">
            {stats.total.toLocaleString()}
          </p>
          <p className="mt-2 text-xs opacity-70">
            {successRate}% success rate
          </p>
        </CardContent>
      </Card>

      {/* Pipeline status */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium text-muted-foreground">Pipeline</p>
            <span className="flex h-2 w-2 rounded-full bg-emerald-500" />
          </div>
          <div className="mt-3 space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Scheduled</span>
              <span className="font-semibold">{stats.scheduled}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Published</span>
              <span className="font-semibold">{stats.published}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Pending</span>
              <span className="font-semibold">{stats.pending}</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Performance */}
      <Card>
        <CardContent className="pt-6">
          <p className="text-sm font-medium text-muted-foreground">Performance</p>
          <div className="mt-3 space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Impressions</span>
              <span className="font-semibold">{stats.impressions.toLocaleString()}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Clicks</span>
              <span className="font-semibold">{stats.clicks.toLocaleString()}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Saves</span>
              <span className="font-semibold">{stats.saves.toLocaleString()}</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* AI Status */}
      <Card className="border-dashed">
        <CardContent className="pt-6">
          <p className="text-sm font-medium text-muted-foreground">AI Analysis</p>
          <div className="mt-3">
            <div className="flex items-end gap-1">
              <span className="text-3xl font-bold tracking-tight text-primary">
                {stats.ready}
              </span>
              <span className="mb-0.5 text-sm text-muted-foreground">ready</span>
            </div>
            {stats.failed > 0 && (
              <p className="mt-2 text-xs text-destructive">
                {stats.failed} failed
              </p>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
