import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent, within } from "@testing-library/react"
import { CalendarGrid } from "@/components/calendar-grid"
import type { Pin } from "@/lib/api"

function makePin(
  id: number,
  opts: { status: Pin["status"]; scheduled_time?: string | null; published_time?: string | null },
): Pin {
  return {
    id,
    filename: `pin-${id}.png`,
    image_url: `/media/${id}`,
    status: opts.status,
    title: null,
    description: null,
    alt_text: null,
    primary_keyword: null,
    secondary_keywords: null,
    tags: null,
    board_name: "travel",
    content_category: "photo",
    file_size: 2048,
    width: 100,
    height: 200,
    created_at: "2026-01-01T00:00:00Z",
    scheduled_time: opts.scheduled_time ?? null,
    published_time: opts.published_time ?? null,
  }
}

function makeDataTransfer() {
  const store: Record<string, string> = {}
  return {
    setData: (k: string, v: string) => {
      store[k] = v
    },
    getData: (k: string) => store[k] ?? "",
    effectAllowed: "",
    dropEffect: "",
  }
}

const YEAR = 2026
const MONTH = 9

describe("CalendarGrid", () => {
  it("places scheduled and published pins in the correct day cells", () => {
    const pins = [
      makePin(15, { status: "scheduled", scheduled_time: "2026-09-15T12:00:00" }),
      makePin(3, { status: "published", published_time: "2026-09-03T08:00:00" }),
    ]

    render(
      <CalendarGrid
        pins={pins}
        year={YEAR}
        month={MONTH}
        onReschedule={() => {}}
        onSelect={() => {}}
      />,
    )

    const day15 = screen.getByTestId("day-15")
    expect(within(day15).getByTestId("pin-15")).toBeDefined()
    const day3 = screen.getByTestId("day-3")
    expect(within(day3).getByTestId("pin-3")).toBeDefined()
  })

  it("calls onReschedule with the dropped pin id and target day", () => {
    const onReschedule = vi.fn()
    const pins = [
      makePin(15, { status: "scheduled", scheduled_time: "2026-09-15T12:00:00" }),
    ]

    render(
      <CalendarGrid
        pins={pins}
        year={YEAR}
        month={MONTH}
        onReschedule={onReschedule}
        onSelect={() => {}}
      />,
    )

    const chip = screen.getByTestId("pin-15")
    const day20 = screen.getByTestId("day-20")

    const dt = makeDataTransfer()
    fireEvent.dragStart(chip, { dataTransfer: dt })
    fireEvent.drop(day20, { dataTransfer: dt })

    expect(onReschedule).toHaveBeenCalledWith(15, 20)
  })
})
