"use client"

import { useCallback, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { useQueueStore } from "@/stores/queue-store"
import { fetchPins, movePin, ApiError, type Pin, type PinStatus } from "@/lib/api"

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

const COLUMNS: { status: PinStatus; label: string }[] = [
  { status: "pending", label: "Uploaded" },
  { status: "ready", label: "Ready" },
  { status: "scheduled", label: "Scheduled" },
  { status: "published", label: "Published" },
  { status: "failed", label: "Failed" },
]

function formatScheduled(value: string | null): string | null {
  if (!value) return null
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return null
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

function PinCard({ pin }: { pin: Pin }) {
  const setDragging = useQueueStore((s) => s.setDragging)
  const draggingId = useQueueStore((s) => s.draggingId)
  const src = `${API_BASE}${pin.image_url}`
  const scheduled = formatScheduled(pin.scheduled_time)

  return (
    <div
      data-testid={`card-${pin.id}`}
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData("text/plain", String(pin.id))
        e.dataTransfer.effectAllowed = "move"
        setDragging(pin.id)
      }}
      onDragEnd={() => setDragging(null)}
      className={`rounded-lg border border-border bg-card p-2 shadow-sm transition-opacity ${
        draggingId === pin.id ? "opacity-40" : "opacity-100"
      }`}
    >
      <div className="overflow-hidden rounded-md border border-border bg-muted">
        <img src={src} alt={pin.filename} className="aspect-square w-full object-cover" />
      </div>
      <div className="mt-2 space-y-0.5">
        <div className="flex items-center gap-1.5">
          <span
            data-testid={`chip-${pin.id}`}
            className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground"
          >
            {pin.status}
          </span>
        </div>
        <p className="truncate text-xs font-medium" title={pin.filename}>
          {pin.filename}
        </p>
        {pin.content_category && (
          <p className="truncate text-xs text-muted-foreground">{pin.content_category}</p>
        )}
        {pin.board_name && (
          <p className="truncate text-xs text-muted-foreground">#{pin.board_name}</p>
        )}
        {scheduled && (
          <p className="truncate text-xs text-muted-foreground">{scheduled}</p>
        )}
      </div>
    </div>
  )
}

export function KanbanBoard() {
  const pins = useQueueStore((s) => s.pins)
  const error = useQueueStore((s) => s.error)
  const setPins = useQueueStore((s) => s.setPins)
  const setDragging = useQueueStore((s) => s.setDragging)
  const setError = useQueueStore((s) => s.setError)
  const clearError = useQueueStore((s) => s.clearError)
  const moveOptimistic = useQueueStore((s) => s.moveOptimistic)
  const revert = useQueueStore((s) => s.revert)

  const loadAll = useCallback(async () => {
    const results = await Promise.all(
      COLUMNS.map((c) => fetchPins({ status: c.status, per_page: 200 })),
    )
    setPins(results.flatMap((r) => r.items))
  }, [setPins])

  useEffect(() => {
    void loadAll()
    const timer = setInterval(() => void loadAll(), 30_000)
    return () => clearInterval(timer)
  }, [loadAll])

  const handleDrop = useCallback(
    async (e: React.DragEvent, status: PinStatus) => {
      e.preventDefault()
      const idStr = e.dataTransfer.getData("text/plain")
      setDragging(null)
      if (!idStr) return
      const id = Number(idStr)
      const pin = useQueueStore.getState().pins.find((p) => p.id === id)
      if (!pin || pin.status === status) return

      const prevStatus = pin.status
      clearError()
      moveOptimistic(id, status)
      try {
        await movePin(id, status)
      } catch (err) {
        revert(id, prevStatus)
        setError(
          err instanceof ApiError
            ? "Move not allowed — that status transition is locked."
            : "Move failed. Try again.",
        )
      }
    },
    [clearError, moveOptimistic, revert, setDragging, setError],
  )

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Drag a pin between columns to change its status.
        </p>
        <Button variant="outline" size="sm" onClick={() => void loadAll()}>
          Refresh
        </Button>
      </div>

      {error && (
        <div
          role="alert"
          className="rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive"
        >
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {COLUMNS.map((col) => {
          const columnPins = pins.filter((p) => p.status === col.status)
          return (
            <div
              key={col.status}
              data-testid={`column-${col.status}`}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => void handleDrop(e, col.status)}
              className="flex min-h-[50vh] flex-col rounded-xl border border-border bg-muted/30 p-2"
            >
              <div className="mb-2 flex items-center justify-between px-1">
                <h2 className="text-sm font-semibold">{col.label}</h2>
                <span className="text-xs text-muted-foreground">{columnPins.length}</span>
              </div>
              <div className="flex flex-col gap-2">
                {columnPins.map((pin) => (
                  <PinCard key={pin.id} pin={pin} />
                ))}
                {columnPins.length === 0 && (
                  <p className="px-1 py-6 text-center text-xs text-muted-foreground">
                    Drop here
                  </p>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
