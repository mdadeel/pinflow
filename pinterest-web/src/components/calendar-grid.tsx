"use client"

import type { Pin } from "@/lib/api"

interface CalendarGridProps {
  pins: Pin[]
  year: number
  month: number
  onReschedule: (pinId: number, day: number) => void
  onSelect: (pinId: number) => void
}

function utcParts(iso: string): { year: number; month: number; day: number } | null {
  const hasTimezone = iso.includes("Z") || (iso.includes("T") && (iso.split("T")[1].includes("+") || iso.split("T")[1].includes("-")))
  const d = new Date(hasTimezone ? iso : iso + "Z")
  if (Number.isNaN(d.getTime())) return null
  return {
    year: d.getUTCFullYear(),
    month: d.getUTCMonth() + 1,
    day: d.getUTCDate(),
  }
}

function pinDay(pin: Pin, year: number, month: number): number | null {
  const iso = pin.scheduled_time ?? pin.published_time
  if (!iso) return null
  const parts = utcParts(iso)
  if (!parts) return null
  if (parts.year !== year || parts.month !== month) return null
  return parts.day
}

const STATUS_DOT: Record<Pin["status"], string> = {
  pending: "bg-zinc-400",
  ready: "bg-amber-400",
  scheduled: "bg-sky-500",
  published: "bg-emerald-500",
  failed: "bg-red-500",
}

function Chip({ pin, onSelect }: { pin: Pin; onSelect: (id: number) => void }) {
  return (
    <button
      type="button"
      data-testid={`pin-${pin.id}`}
      draggable={pin.status === "scheduled"}
      onDragStart={(e) => {
        e.dataTransfer.setData("text/plain", String(pin.id))
        e.dataTransfer.effectAllowed = "move"
      }}
      onClick={() => onSelect(pin.id)}
      title={`#${pin.id} ${pin.filename}`}
      className="flex w-full items-center gap-1.5 truncate rounded-md border border-border bg-card px-1.5 py-1 text-left text-[11px] shadow-sm hover:bg-muted"
    >
      <span
        data-testid={`dot-${pin.id}`}
        className={`h-1.5 w-1.5 shrink-0 rounded-full ${STATUS_DOT[pin.status]}`}
      />
      <span className="truncate">{pin.filename}</span>
    </button>
  )
}

export function CalendarGrid({ pins, year, month, onReschedule, onSelect }: CalendarGridProps) {
  const first = new Date(Date.UTC(year, month - 1, 1))
  const startWeekday = first.getUTCDay()
  const daysInMonth = new Date(Date.UTC(year, month, 0)).getUTCDate()
  const cells: (number | null)[] = []
  for (let i = 0; i < startWeekday; i++) cells.push(null)
  for (let d = 1; d <= daysInMonth; d++) cells.push(d)
  while (cells.length % 7 !== 0) cells.push(null)

  const pinsByDay = new Map<number, Pin[]>()
  for (const pin of pins) {
    const day = pinDay(pin, year, month)
    if (day == null) continue
    const list = pinsByDay.get(day) ?? []
    list.push(pin)
    pinsByDay.set(day, list)
  }

  const weekdays = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

  return (
    <div className="overflow-hidden rounded-xl border border-border">
      <div className="grid grid-cols-7 border-b border-border bg-muted/40">
        {weekdays.map((w) => (
          <div key={w} className="px-2 py-1.5 text-center text-xs font-medium text-muted-foreground">
            {w}
          </div>
        ))}
      </div>
      <div className="grid grid-cols-7">
        {cells.map((day, idx) => {
          if (day == null) {
            return <div key={`empty-${idx}`} className="min-h-[88px] border-b border-r border-border/60 bg-muted/20" />
          }
          const dayPins = pinsByDay.get(day) ?? []
          return (
            <div
              key={`day-${day}`}
              data-testid={`day-${day}`}
              data-day={day}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault()
                const idStr = e.dataTransfer.getData("text/plain")
                if (!idStr) return
                onReschedule(Number(idStr), day)
              }}
              className="min-h-[88px] space-y-1 border-b border-r border-border/60 p-1.5"
            >
              <div className="text-[11px] font-medium text-muted-foreground">{day}</div>
              {dayPins.map((pin) => (
                <Chip key={pin.id} pin={pin} onSelect={onSelect} />
              ))}
            </div>
          )
        })}
      </div>
    </div>
  )
}
