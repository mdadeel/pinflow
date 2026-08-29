"use client"

import { useState } from "react"

import { Button } from "@/components/ui/button"
import { runPipeline } from "@/lib/api"

export function RunPipelineButton() {
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)

  async function onClick() {
    setBusy(true)
    setMsg(null)
    try {
      const r = await runPipeline()
      setMsg(
        `analyzed ${r.analyzed} · scheduled ${r.scheduled} · ` +
          `published ${r.published} · failed ${r.failed}`,
      )
      setTimeout(() => window.location.reload(), 800)
    } catch {
      setMsg("failed to run pipeline")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex items-center gap-3">
      <Button onClick={onClick} disabled={busy} size="lg">
        {busy ? (
          <>
            <svg
              className="mr-2 h-4 w-4 animate-spin"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
            Running...
          </>
        ) : (
          "Run Pipeline"
        )}
      </Button>
      {msg && (
        <span className="rounded-md bg-muted px-3 py-1.5 text-sm text-muted-foreground">
          {msg}
        </span>
      )}
    </div>
  )
}
