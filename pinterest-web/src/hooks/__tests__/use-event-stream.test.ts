import { describe, expect, it } from "vitest"
import {
  formatEvent,
  prependEvent,
  relativeTime,
  type StreamEvent,
} from "@/hooks/use-event-stream"

describe("relativeTime", () => {
  const now = Date.parse("2026-08-26T12:00:00Z")

  it("returns 'just now' for <60s", () => {
    expect(relativeTime("2026-08-26T11:59:30Z", now)).toBe("just now")
  })

  it("returns 'Nm ago' for <60m", () => {
    expect(relativeTime("2026-08-26T11:57:00Z", now)).toBe("3m ago")
  })

  it("returns 'Nh ago' for <24h", () => {
    expect(relativeTime("2026-08-26T09:00:00Z", now)).toBe("3h ago")
  })

  it("returns a date string for >=24h", () => {
    expect(relativeTime("2026-08-25T12:00:00Z", now)).toMatch(/\d/)
  })
})

describe("formatEvent", () => {
  it("formats image.uploaded", () => {
    expect(formatEvent({ type: "image.uploaded", payload: { filename: "cat.png" } })).toBe(
      "Image uploaded: cat.png"
    )
  })

  it("formats metadata.generated with title", () => {
    expect(
      formatEvent({ type: "metadata.generated", payload: { pin_id: 12, title: "Cats" } })
    ).toBe("Metadata generated (#12): Cats")
  })

  it("formats metadata.failed with error", () => {
    expect(
      formatEvent({ type: "metadata.failed", payload: { pin_id: 12, error: "boom" } })
    ).toBe("Metadata failed (#12): boom")
  })

  it("formats pin.scheduled", () => {
    expect(formatEvent({ type: "pin.scheduled", payload: { pin_id: 7 } })).toBe(
      "Pin scheduled (#7)"
    )
  })

  it("formats metadata.edited", () => {
    expect(formatEvent({ type: "metadata.edited", payload: { pin_id: 12 } })).toBe(
      "Metadata edited (#12)"
    )
  })

  it("formats pin.published", () => {
    expect(formatEvent({ type: "pin.published", payload: { pin_id: 7 } })).toBe(
      "Pin published (#7)"
    )
  })

  it("formats publish.failed", () => {
    expect(formatEvent({ type: "publish.failed", payload: { pin_id: 7, error: "x" } })).toBe(
      "Publish failed (#7): x"
    )
  })

  it("formats pin.updated", () => {
    expect(formatEvent({ type: "pin.updated", payload: { pin_id: 7, status: "ready" } })).toBe(
      "Pin updated (#7): ready"
    )
  })
})

describe("prependEvent", () => {
  it("prepends newest first", () => {
    const a: StreamEvent = { id: "a", type: "t", payload: {}, at: "now" }
    const b: StreamEvent = { id: "b", type: "t", payload: {}, at: "later" }
    expect(prependEvent([a], b).map((e) => e.id)).toEqual(["b", "a"])
  })

  it("caps the list length", () => {
    const many = Array.from({ length: 5 }, (_, i) => ({
      id: String(i),
      type: "t",
      payload: {},
      at: "x",
    }))
    const events = many.reduce((acc, e) => prependEvent(acc, e, 3), [] as StreamEvent[])
    expect(events).toHaveLength(3)
    expect(events.map((e) => e.id)).toEqual(["4", "3", "2"])
  })
})
