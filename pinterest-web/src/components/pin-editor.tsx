"use client"

import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  fetchPin,
  updatePin,
  regeneratePin,
  approvePin,
  ApiError,
  type Pin,
  type PinEdit,
} from "@/lib/api"

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

function splitList(value: string): string[] | null {
  const items = value
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean)
  return items.length ? items : null
}

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

function describeError(err: unknown): string {
  if (err instanceof ApiError) {
    const detail = (err.body as { detail?: unknown } | null)?.detail
    if (typeof detail === "string") return detail
    return err.message
  }
  return err instanceof Error ? err.message : "Something went wrong."
}

interface FormState {
  title: string
  description: string
  alt_text: string
  primary_keyword: string
  secondary_keywords: string
  tags: string
  board_name: string
  content_category: string
}

function toForm(pin: Pin): FormState {
  return {
    title: pin.title ?? "",
    description: pin.description ?? "",
    alt_text: pin.alt_text ?? "",
    primary_keyword: pin.primary_keyword ?? "",
    secondary_keywords: (pin.secondary_keywords ?? []).join(", "),
    tags: (pin.tags ?? []).join(", "),
    board_name: pin.board_name ?? "",
    content_category: pin.content_category ?? "",
  }
}

function toEditBody(form: FormState, initial: FormState): PinEdit {
  const body: PinEdit = {}
  const strFields: (keyof FormState)[] = [
    "title",
    "description",
    "alt_text",
    "primary_keyword",
    "board_name",
    "content_category",
  ]
  for (const key of strFields) {
    if (form[key] !== initial[key]) {
      ;(body as Record<string, string | null>)[key] = form[key] || null
    }
  }
  if (form.secondary_keywords !== initial.secondary_keywords) {
    body.secondary_keywords = splitList(form.secondary_keywords)
  }
  if (form.tags !== initial.tags) {
    body.tags = splitList(form.tags)
  }
  return body
}

export function PinEditor({ id }: { id: number }) {
  const [pin, setPin] = useState<Pin | null>(null)
  const [form, setForm] = useState<FormState | null>(null)
  const [initial, setInitial] = useState<FormState | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let cancelled = false
    setError(null)
    fetchPin(id)
      .then((loaded) => {
        if (cancelled) return
        const f = toForm(loaded)
        setPin(loaded)
        setForm(f)
        setInitial(f)
      })
      .catch((err) => {
        if (!cancelled) setError(describeError(err))
      })
    return () => {
      cancelled = true
    }
  }, [id])

  function applyPin(next: Pin) {
    const f = toForm(next)
    setPin(next)
    setForm(f)
    setInitial(f)
  }

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => (prev ? { ...prev, [key]: value } : prev))
  }

  async function handleSave() {
    if (!form || !initial) return
    const body = toEditBody(form, initial)
    if (Object.keys(body).length === 0) return
    setBusy(true)
    setError(null)
    try {
      const next = await updatePin(id, body)
      applyPin(next)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleRegenerate() {
    setBusy(true)
    setError(null)
    try {
      const next = await regeneratePin(id)
      applyPin(next)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleApprove() {
    setBusy(true)
    setError(null)
    try {
      const next = await approvePin(id)
      applyPin(next)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setBusy(false)
    }
  }

  if (!pin || !form) {
    return (
      <p className="text-sm text-muted-foreground" data-testid="status">
        {error ? error : "Loading…"}
      </p>
    )
  }

  const canApprove = pin.status === "ready"
  const scheduled = formatScheduled(pin.scheduled_time)

  return (
    <Card>
      <CardHeader>
        <CardTitle>Edit pin #{pin.id}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && (
          <div
            role="alert"
            className="rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive"
          >
            {error}
          </div>
        )}

        {pin.image_url && (
          <div className="overflow-hidden rounded-lg border border-border bg-muted">
            <img
              src={`${API_BASE}${pin.image_url}`}
              alt={pin.filename}
              className="aspect-square w-40 object-cover"
            />
          </div>
        )}

        {scheduled && (
          <p data-testid="scheduled" className="text-sm text-muted-foreground">
            Scheduled: {scheduled}
          </p>
        )}

        <div className="space-y-3">
          <label className="block space-y-1">
            <span className="text-sm font-medium">Title</span>
            <input
              aria-label="Title"
              value={form.title}
              onChange={(e) => update("title", e.target.value)}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            />
          </label>

          <label className="block space-y-1">
            <span className="text-sm font-medium">Description</span>
            <textarea
              aria-label="Description"
              value={form.description}
              onChange={(e) => update("description", e.target.value)}
              rows={4}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            />
          </label>

          <label className="block space-y-1">
            <span className="text-sm font-medium">Alt text</span>
            <input
              aria-label="Alt text"
              value={form.alt_text}
              onChange={(e) => update("alt_text", e.target.value)}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            />
          </label>

          <label className="block space-y-1">
            <span className="text-sm font-medium">Primary keyword</span>
            <input
              aria-label="Primary keyword"
              value={form.primary_keyword}
              onChange={(e) => update("primary_keyword", e.target.value)}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            />
          </label>

          <label className="block space-y-1">
            <span className="text-sm font-medium">Secondary keywords (comma-separated)</span>
            <input
              aria-label="Secondary keywords"
              value={form.secondary_keywords}
              onChange={(e) => update("secondary_keywords", e.target.value)}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            />
          </label>

          <label className="block space-y-1">
            <span className="text-sm font-medium">Tags (comma-separated)</span>
            <input
              aria-label="Tags"
              value={form.tags}
              onChange={(e) => update("tags", e.target.value)}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            />
          </label>

          <label className="block space-y-1">
            <span className="text-sm font-medium">Board name</span>
            <input
              aria-label="Board name"
              value={form.board_name}
              onChange={(e) => update("board_name", e.target.value)}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            />
          </label>

          <label className="block space-y-1">
            <span className="text-sm font-medium">Content category</span>
            <input
              aria-label="Content category"
              value={form.content_category}
              onChange={(e) => update("content_category", e.target.value)}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            />
          </label>
        </div>

        <div className="flex flex-wrap gap-2 pt-2">
          <Button type="button" onClick={handleSave} disabled={busy}>
            Save
          </Button>
          <Button type="button" variant="outline" onClick={handleRegenerate} disabled={busy}>
            Regenerate
          </Button>
          <Button
            type="button"
            variant="secondary"
            onClick={handleApprove}
            disabled={!canApprove || busy}
          >
            Approve
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
