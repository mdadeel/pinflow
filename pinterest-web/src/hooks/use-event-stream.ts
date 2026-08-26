"use client"

import { useEffect, useRef, useState } from "react"

export interface StreamEvent {
  id: string
  type: string
  payload: Record<string, unknown>
  at: string
}

export function relativeTime(at: string, now: number = Date.now()): string {
  const then = new Date(at).getTime()
  if (Number.isNaN(then)) return ""
  const diff = Math.max(0, now - then)
  const sec = Math.floor(diff / 1000)
  if (sec < 60) return "just now"
  const min = Math.floor(sec / 60)
  if (min < 60) return `${min}m ago`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr}h ago`
  return new Date(at).toLocaleDateString()
}

export function formatEvent(event: { type: string; payload: Record<string, unknown> }): string {
  const p = event.payload
  const id = p.pin_id != null ? ` (#${p.pin_id})` : ""
  switch (event.type) {
    case "image.uploaded":
      return `Image uploaded: ${String(p.filename ?? p.path ?? "")}`
    case "metadata.generated":
      return `Metadata generated${id}: ${String(p.title ?? "")}`
    case "metadata.failed":
      return `Metadata failed${id}: ${String(p.error ?? "")}`
    case "pin.scheduled":
      return `Pin scheduled${id}`
    case "pin.published":
      return `Pin published${id}`
    case "publish.failed":
      return `Publish failed${id}: ${String(p.error ?? "")}`
    case "pin.updated":
      return `Pin updated${id}: ${String(p.status ?? "")}`
    default:
      return event.type
  }
}

export function prependEvent(
  list: StreamEvent[],
  event: StreamEvent,
  limit = 200
): StreamEvent[] {
  return [event, ...list].slice(0, limit)
}

const MAX_DELAY = 10_000

function toEvent(
  data: { type?: unknown; payload?: unknown; at?: unknown },
  counter: number
): StreamEvent | null {
  if (typeof data.type !== "string") return null
  const payload =
    data.payload && typeof data.payload === "object"
      ? (data.payload as Record<string, unknown>)
      : {}
  const at = typeof data.at === "string" ? data.at : new Date().toISOString()
  const id = `${at}-${data.type}-${counter}`
  return { id, type: data.type, payload, at }
}

export function useEventStream(url?: string) {
  const [events, setEvents] = useState<StreamEvent[]>([])
  const [connected, setConnected] = useState(false)
  const counterRef = useRef(0)
  const wsRef = useRef<WebSocket | null>(null)
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const delayRef = useRef(1000)
  const closedRef = useRef(false)

  useEffect(() => {
    closedRef.current = false
    const base = url ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
    const wsUrl = `${base.replace(/^http/, "ws")}/ws`

    function connect() {
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        setConnected(true)
        delayRef.current = 1000
      }

      ws.onclose = () => {
        setConnected(false)
        if (closedRef.current) return
        const delay = delayRef.current
        delayRef.current = Math.min(delay * 2, MAX_DELAY)
        retryRef.current = setTimeout(connect, delay)
      }

      ws.onmessage = (msg) => {
        let data: { type?: unknown; payload?: unknown; at?: unknown }
        try {
          data = JSON.parse(msg.data)
        } catch {
          return
        }
        if (data.type === "hello") {
          const recent = Array.isArray(data.payload) ? data.payload : (data.payload as { recent?: unknown })?.recent
          const list = Array.isArray(recent) ? recent : []
          setEvents(
            list
              .map((e) => toEvent(e as { type?: unknown; payload?: unknown; at?: unknown }, counterRef.current++))
              .filter((e): e is StreamEvent => e !== null)
          )
          return
        }
        const event = toEvent(data, counterRef.current++)
        if (event) setEvents((prev) => prependEvent(prev, event))
      }
    }

    connect()

    return () => {
      closedRef.current = true
      if (retryRef.current) clearTimeout(retryRef.current)
      wsRef.current?.close()
    }
  }, [url])

  return { events, connected }
}
