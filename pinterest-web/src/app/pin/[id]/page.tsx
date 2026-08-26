"use client"

import { useParams } from "next/navigation"
import Link from "next/link"
import { PinEditor } from "@/components/pin-editor"

export default function PinEditorPage() {
  const params = useParams<{ id: string }>()
  const idStr = params?.id
  const id = idStr ? Number(idStr) : NaN

  if (Number.isNaN(id)) {
    return (
      <main className="mx-auto max-w-2xl p-4">
        <div role="alert" className="text-sm text-destructive">
          Invalid pin id.
        </div>
      </main>
    )
  }

  return (
    <main className="mx-auto max-w-2xl space-y-4 p-4">
      <Link
        href="/queue"
        className="text-sm text-primary underline-offset-4 hover:underline"
      >
        ← Back to queue
      </Link>
      <PinEditor id={id} />
    </main>
  )
}
