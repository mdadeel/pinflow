"use client"

import { useCallback, useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { CalendarGrid } from "@/components/calendar-grid"
import {
  fetchPins,
  reschedulePin,
  ApiError,
  type Pin,
} from "@/lib/api"

function describeError(err: unknown): string {
  if (err instanceof ApiError) {
    const detail = (err.body as { detail?: unknown } | null)?.detail
    if (typeof detail === "string") return detail
    return err.message
  }
  return err instanceof Error ? err.message : "Reschedule failed. Try again."
}

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
]

export default function CalendarPage() {
  const router = useRouter()
  const now = new Date()
  const [pins, setPins] = useState<Pin[]>([])
  const [year, setYear] = useState(now.getUTCFullYear())
  const [month, setMonth] = useState(now.getUTCMonth() + 1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    Promise.all([
      fetchPins({ status: "scheduled", per_page: 200 }),
      fetchPins({ status: "published", per_page: 200 }),
    ])
      .then(([scheduled, published]) => {
        if (cancelled) return
        setPins([...scheduled.items, ...published.items])
      })
      .catch((err) => {
        if (!cancelled) setError(describeError(err))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [year, month])

  const changeMonth = useCallback((delta: number) => {
    setMonth((prevMonth) => {
      const next = prevMonth + delta
      if (next < 1) {
        setYear((y) => y - 1)
        return 12
      }
      if (next > 12) {
        setYear((y) => y + 1)
        return 1
      }
      return next
    })
  }, [])

  const handleReschedule = useCallback(
    async (pinId: number, day: number) => {
      const iso = `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}T12:00:00`
      const original = pins.find((p) => p.id === pinId)?.scheduled_time ?? null
      setPins((prev) =>
        prev.map((p) => (p.id === pinId ? { ...p, scheduled_time: iso } : p)),
      )
      setError(null)
      try {
        await reschedulePin(pinId, iso)
      } catch (err) {
        setPins((prev) =>
          prev.map((p) => (p.id === pinId ? { ...p, scheduled_time: original } : p)),
        )
        setError(describeError(err))
      }
    },
    [year, month, pins],
  )

  const handleSelect = useCallback(
    (pinId: number) => {
      router.push(`/pin/${pinId}`)
    },
    [router],
  )

  return (
    <div className="mx-auto max-w-7xl px-6 py-10">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Calendar</h1>
          <p className="mt-2 text-muted-foreground">
            Drag a scheduled pin onto another day to reschedule it. Click a pin to edit.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => changeMonth(-1)}
            className="rounded-md border border-border bg-card px-3 py-1.5 text-sm hover:bg-muted"
          >
            Prev
          </button>
          <span className="min-w-[120px] text-center text-sm font-medium">
            {MONTH_NAMES[month - 1]} {year}
          </span>
          <button
            type="button"
            onClick={() => changeMonth(1)}
            className="rounded-md border border-border bg-card px-3 py-1.5 text-sm hover:bg-muted"
          >
            Next
          </button>
        </div>
      </div>

      {error && (
        <div
          role="alert"
          className="mt-4 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive"
        >
          {error}
        </div>
      )}

      <div className="mt-6">
        {loading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : pins.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No scheduled or published pins to display.
          </p>
        ) : (
          <CalendarGrid
            pins={pins}
            year={year}
            month={month}
            onReschedule={handleReschedule}
            onSelect={handleSelect}
          />
        )}
      </div>
    </div>
  )
}
