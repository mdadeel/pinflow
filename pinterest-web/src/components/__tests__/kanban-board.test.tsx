import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react"
import { KanbanBoard } from "@/components/kanban-board"
import { fetchPins, movePin, ApiError, type Pin } from "@/lib/api"

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>()
  return {
    ...actual,
    fetchPins: vi.fn(),
    movePin: vi.fn(),
  }
})

const mockedFetch = vi.mocked(fetchPins)
const mockedMove = vi.mocked(movePin)

function makePin(id: number, status: Pin["status"], filename = `pin-${id}.png`): Pin {
  return {
    id,
    filename,
    image_url: `/media/${id}`,
    status,
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
    scheduled_time: status === "scheduled" ? "2026-02-01T10:00:00Z" : null,
  }
}

const allPins = [
  makePin(1, "pending"),
  makePin(2, "ready"),
  makePin(3, "scheduled"),
  makePin(4, "published"),
  makePin(5, "failed"),
]

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

describe("KanbanBoard", () => {
  beforeEach(() => {
    mockedFetch.mockReset()
    mockedMove.mockReset()
    mockedFetch.mockImplementation(async (params) => {
      const items = allPins.filter((p) => p.status === params?.status)
      return { items, total: items.length, page: 1, per_page: 200 }
    })
  })

  it("moves a pending card to the Ready column via drag/drop", async () => {
    mockedMove.mockResolvedValue({ ...allPins[0], status: "ready" })

    render(<KanbanBoard />)

    await waitFor(() => expect(mockedFetch).toHaveBeenCalled())
    const card = screen.getByTestId(`card-${allPins[0].id}`)
    const readyCol = screen.getByTestId("column-ready")

    const dt = makeDataTransfer()
    fireEvent.dragStart(card, { dataTransfer: dt })
    fireEvent.drop(readyCol, { dataTransfer: dt })

    await waitFor(() =>
      expect(mockedMove).toHaveBeenCalledWith(allPins[0].id, "ready"),
    )
    await waitFor(() =>
      expect(within(readyCol).getByTestId(`card-${allPins[0].id}`)).toBeDefined(),
    )
  })

  it("reverts and shows an error banner when movePin returns 409", async () => {
    mockedMove.mockRejectedValueOnce(
      new ApiError(409, { detail: "status locked" }, "/api/pins/1/status"),
    )

    render(<KanbanBoard />)

    await waitFor(() => expect(mockedFetch).toHaveBeenCalled())
    const card = screen.getByTestId(`card-${allPins[0].id}`)
    const pendingCol = screen.getByTestId("column-pending")
    const readyCol = screen.getByTestId("column-ready")

    const dt = makeDataTransfer()
    fireEvent.dragStart(card, { dataTransfer: dt })
    fireEvent.drop(readyCol, { dataTransfer: dt })

    await waitFor(() => expect(mockedMove).toHaveBeenCalled())
    await waitFor(() =>
      expect(within(readyCol).queryByTestId(`card-${allPins[0].id}`)).toBeNull(),
    )
    expect(within(pendingCol).getByTestId(`card-${allPins[0].id}`)).toBeDefined()
    expect(screen.getByRole("alert")).toBeDefined()
  })
})
