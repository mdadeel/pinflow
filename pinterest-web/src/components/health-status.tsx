"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

interface HealthStatus {
  status: string
  timestamp: string
  version: string
  checks: Record<string, string>
}

function Skeleton({ className }: { className?: string }) {
  return (
    <div className={`animate-pulse rounded-md bg-muted ${className ?? ""}`} />
  )
}

function StatusDot({ status }: { status: string }) {
  const colors: Record<string, string> = {
    ok: "bg-emerald-500",
    configured: "bg-emerald-500",
    healthy: "bg-emerald-500",
    not_configured: "bg-yellow-500",
    degraded: "bg-yellow-500",
    error: "bg-red-500",
  }

  return (
    <span className={`inline-block h-2 w-2 rounded-full ${colors[status] ?? "bg-gray-400"}`} />
  )
}

export function HealthStatus() {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    let active = true
    fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/health`)
      .then((res) => res.json())
      .then((data) => {
        if (active) setHealth(data)
      })
      .catch(() => {
        if (active) setError(true)
      })
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
          <div className="space-y-3">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-full" />
          </div>
        </CardContent>
      </Card>
    )
  }

  if (error || !health) {
    return (
      <Card className="border-destructive/20">
        <CardHeader>
          <CardTitle className="text-sm font-medium text-muted-foreground">System Status</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2">
            <StatusDot status="error" />
            <span className="text-sm text-destructive">Unable to connect</span>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium text-muted-foreground">System Status</CardTitle>
          <span className="text-xs text-muted-foreground">v{health.version}</span>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <StatusDot status={health.status} />
              <span className="text-sm font-medium capitalize">{health.status}</span>
            </div>
          </div>

          <div className="mt-3 space-y-1.5">
            {Object.entries(health.checks).map(([name, status]) => (
              <div key={name} className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground capitalize">
                  {name.replace(/_/g, " ")}
                </span>
                <div className="flex items-center gap-1.5">
                  <StatusDot status={status} />
                  <span className="text-xs text-muted-foreground capitalize">
                    {status.replace(/_/g, " ")}
                  </span>
                </div>
              </div>
            ))}
          </div>

          <p className="mt-3 text-xs text-muted-foreground">
            Last checked: {new Date(health.timestamp).toLocaleTimeString()}
          </p>
        </div>
      </CardContent>
    </Card>
  )
}
