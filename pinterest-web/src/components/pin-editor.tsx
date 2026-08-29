"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  fetchPin,
  updatePin,
  regeneratePin,
  approvePin,
  fetchDuplicates,
  recordLearning,
  resetPin,
  retryPin,
  deletePin,
  ApiError,
  type Pin,
  type PinEdit,
  type DuplicateCandidate,
} from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function splitList(value: string): string[] | null {
  const items = value
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  return items.length ? items : null;
}

function formatScheduled(value: string | null): string | null {
  if (!value) return null;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function describeError(err: unknown): string {
  if (err instanceof ApiError) {
    const detail = (err.body as { detail?: unknown } | null)?.detail;
    if (typeof detail === "string") return detail;
    return err.message;
  }
  return err instanceof Error ? err.message : "Something went wrong.";
}

interface FormState {
  title: string;
  description: string;
  alt_text: string;
  primary_keyword: string;
  secondary_keywords: string;
  tags: string;
  board_name: string;
  content_category: string;
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
  };
}

function toEditBody(form: FormState, initial: FormState): PinEdit {
  const body: PinEdit = {};
  const strFields: (keyof FormState)[] = [
    "title",
    "description",
    "alt_text",
    "primary_keyword",
    "board_name",
    "content_category",
  ];
  for (const key of strFields) {
    if (form[key] !== initial[key]) {
      (body as Record<string, string | null>)[key] = form[key] || null;
    }
  }
  if (form.secondary_keywords !== initial.secondary_keywords) {
    body.secondary_keywords = splitList(form.secondary_keywords);
  }
  if (form.tags !== initial.tags) {
    body.tags = splitList(form.tags);
  }
  return body;
}

export function PinEditor({ id }: { id: number }) {
  const [pin, setPin] = useState<Pin | null>(null);
  const [form, setForm] = useState<FormState | null>(null);
  const [initial, setInitial] = useState<FormState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [duplicates, setDuplicates] = useState<DuplicateCandidate[] | null>(
    null,
  );
  const [deleted, setDeleted] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchPin(id)
      .then((loaded) => {
        if (cancelled) return;
        const f = toForm(loaded);
        setPin(loaded);
        setForm(f);
        setInitial(f);
        setError(null);
      })
      .catch((err) => {
        if (!cancelled) setError(describeError(err));
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  useEffect(() => {
    let cancelled = false;
    fetchDuplicates(id)
      .then((list) => {
        if (!cancelled) setDuplicates(list ?? []);
      })
      .catch(() => {
        if (!cancelled) setDuplicates(null);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  function applyPin(next: Pin) {
    const f = toForm(next);
    setPin(next);
    setForm(f);
    setInitial(f);
  }

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => (prev ? { ...prev, [key]: value } : prev));
  }

  async function handleSave() {
    if (!form || !initial) return;
    const body = toEditBody(form, initial);
    if (Object.keys(body).length === 0) return;
    setBusy(true);
    setError(null);
    try {
      const next = await updatePin(id, body);
      applyPin(next);
      recordLearning("edited", id).catch(() => {});
    } catch (err) {
      setError(describeError(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleRegenerate() {
    setBusy(true);
    setError(null);
    try {
      const next = await regeneratePin(id);
      applyPin(next);
      recordLearning("regenerated", id).catch(() => {});
    } catch (err) {
      setError(describeError(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleApprove() {
    setBusy(true);
    setError(null);
    try {
      const next = await approvePin(id);
      applyPin(next);
      recordLearning("approved", id).catch(() => {});
    } catch (err) {
      setError(describeError(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleReset() {
    setBusy(true);
    setError(null);
    try {
      applyPin(await resetPin(id));
      recordLearning("reset", id).catch(() => {});
    } catch (err) {
      setError(describeError(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleRetry() {
    setBusy(true);
    setError(null);
    try {
      applyPin(await retryPin(id));
      recordLearning("retried", id).catch(() => {});
    } catch (err) {
      setError(describeError(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete() {
    if (!confirm("Delete this pin permanently? This cannot be undone.")) return;
    setBusy(true);
    setError(null);
    try {
      await deletePin(id);
      setDeleted(true);
    } catch (err) {
      setError(describeError(err));
    } finally {
      setBusy(false);
    }
  }

  if (deleted) {
    return (
      <p className="text-sm text-muted-foreground">
        Pin deleted.{" "}
        <Link href="/queue" className="text-primary hover:underline">
          Return to queue
        </Link>
      </p>
    );
  }

  if (!pin || !form) {
    return (
      <p className="text-sm text-muted-foreground" data-testid="status">
        {error ? error : "Loading…"}
      </p>
    );
  }

  const canApprove = pin.status === "ready";
  const scheduled = formatScheduled(pin.scheduled_time);

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
            <div className="relative aspect-square w-40">
              <Image
                src={`${API_BASE}${pin.image_url}`}
                alt={pin.filename}
                fill
                className="object-cover"
                sizes="160px"
              />
            </div>
          </div>
        )}

        {scheduled && (
          <p data-testid="scheduled" className="text-sm text-muted-foreground">
            Scheduled: {scheduled}
          </p>
        )}

        <div className="rounded-lg border border-border p-4">
          <h3 className="text-sm font-medium">Possible duplicates</h3>
          {duplicates === null ? (
            <p className="mt-2 text-sm text-muted-foreground">
              Couldn&apos;t check for duplicates.
            </p>
          ) : duplicates.length === 0 ? (
            <p className="mt-2 text-sm text-muted-foreground">
              No duplicates found
            </p>
          ) : (
            <ul className="mt-2 space-y-1 text-sm">
              {duplicates.map((dup) => (
                <li key={dup.id}>
                  <Link
                    href={`/pin/${dup.id}`}
                    className="text-primary hover:underline"
                  >
                    {dup.title} ({(dup.score * 100).toFixed(0)}%)
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>

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
            <span className="text-sm font-medium">
              Secondary keywords (comma-separated)
            </span>
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

        <div className="flex flex-wrap gap-3 pt-4 border-t">
          <Button type="button" onClick={handleSave} disabled={busy} size="lg">
            {busy ? (
              <>
                <svg className="mr-2 size-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Saving...
              </>
            ) : (
              "Save Changes"
            )}
          </Button>
          <Button
            type="button"
            variant="outline"
            size="lg"
            onClick={handleRegenerate}
            disabled={busy}
          >
            <svg className="mr-2 size-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" />
            </svg>
            Regenerate AI
          </Button>
          <Button
            type="button"
            variant="secondary"
            size="lg"
            onClick={handleApprove}
            disabled={!canApprove || busy}
          >
            <svg className="mr-2 size-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Approve
          </Button>
          <Button
            type="button"
            variant="outline"
            size="lg"
            onClick={handleReset}
            disabled={busy}
          >
            <svg className="mr-2 size-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" />
            </svg>
            Reset
          </Button>
          <Button
            type="button"
            variant="outline"
            size="lg"
            onClick={handleRetry}
            disabled={busy}
          >
            <svg className="mr-2 size-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 12a9 9 0 1 0 2.5-6.6M3.75 12V6m0 6h6" />
            </svg>
            Retry
          </Button>
          <Button
            type="button"
            variant="destructive"
            size="lg"
            onClick={handleDelete}
            disabled={busy}
          >
            <svg className="mr-2 size-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
            </svg>
            Delete
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
