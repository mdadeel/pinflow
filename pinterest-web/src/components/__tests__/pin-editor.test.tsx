import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { PinEditor } from "@/components/pin-editor"
import {
  fetchPin,
  updatePin,
  regeneratePin,
  approvePin,
  fetchDuplicates,
  recordLearning,
  ApiError,
  type Pin,
} from "@/lib/api"

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>()
  return {
    ...actual,
    fetchPin: vi.fn(),
    updatePin: vi.fn(),
    regeneratePin: vi.fn(),
    approvePin: vi.fn(),
    fetchDuplicates: vi.fn(),
    recordLearning: vi.fn(),
  }
})

vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => (
    <a href={href}>{children}</a>
  ),
}))

const mockedFetch = vi.mocked(fetchPin)
const mockedUpdate = vi.mocked(updatePin)
const mockedRegenerate = vi.mocked(regeneratePin)
const mockedApprove = vi.mocked(approvePin)
const mockedFetchDuplicates = vi.mocked(fetchDuplicates)
const mockedRecordLearning = vi.mocked(recordLearning)

function makePin(overrides: Partial<Pin> = {}): Pin {
  return {
    id: 1,
    filename: "pin-1.png",
    image_url: "/media/1",
    status: "pending",
    title: "Original",
    description: "desc",
    alt_text: "alt",
    primary_keyword: "kw",
    secondary_keywords: ["a", "b"],
    tags: ["x"],
    board_name: "travel",
    content_category: "photo",
    file_size: 2048,
    width: 100,
    height: 200,
    created_at: "2026-01-01T00:00:00Z",
    scheduled_time: null,
    ...overrides,
  }
}

describe("PinEditor", () => {
  beforeEach(() => {
    mockedFetch.mockReset()
    mockedUpdate.mockReset()
    mockedRegenerate.mockReset()
    mockedApprove.mockReset()
    mockedFetchDuplicates.mockReset()
    mockedRecordLearning.mockReset()
    mockedFetch.mockImplementation(async () => makePin())
    mockedUpdate.mockImplementation(async (_id, body) => makePin(body as Partial<Pin>))
    mockedRegenerate.mockImplementation(async () =>
      makePin({ status: "ready", title: "Regen" }),
    )
    mockedApprove.mockImplementation(async () =>
      makePin({ status: "scheduled", scheduled_time: "2026-03-01T10:00:00Z" }),
    )
    mockedFetchDuplicates.mockImplementation(async () => [])
    mockedRecordLearning.mockResolvedValue({ id: 1, action: "edited", pin_id: 1 })
  })

  it("loads the pin and renders the title in an input", async () => {
    mockedFetch.mockImplementation(async () => makePin({ title: "Original" }))
    render(<PinEditor id={1} />)
    expect(await screen.findByDisplayValue("Original")).toBeDefined()
  })

  it("edits the title and Save calls updatePin with the changed field only", async () => {
    mockedFetch.mockImplementation(async () => makePin({ title: "Original" }))
    render(<PinEditor id={1} />)

    const title = (await screen.findByLabelText("Title")) as HTMLInputElement
    fireEvent.change(title, { target: { value: "new" } })
    fireEvent.click(screen.getByRole("button", { name: "Save" }))

    await waitFor(() =>
      expect(mockedUpdate).toHaveBeenCalledWith(1, { title: "new" }),
    )
    expect((screen.getByLabelText("Title") as HTMLInputElement).value).toBe("new")
  })

  it("approves a ready pin and shows the scheduled time", async () => {
    mockedFetch.mockImplementation(async () => makePin({ status: "ready" }))
    render(<PinEditor id={1} />)

    await screen.findByDisplayValue("Original")
    const approve = screen.getByRole("button", { name: "Approve" }) as HTMLButtonElement
    expect(approve.disabled).toBe(false)
    fireEvent.click(approve)

    await waitFor(() => expect(mockedApprove).toHaveBeenCalledWith(1))
    expect(screen.getByTestId("scheduled").textContent).toContain("Mar")
  })

  it("shows an alert banner with the message when updatePin returns 409", async () => {
    mockedFetch.mockImplementation(async () => makePin({ status: "ready" }))
    mockedUpdate.mockRejectedValueOnce(
      new ApiError(409, { detail: "Cannot edit scheduled pin" }, "/api/pins/1"),
    )
    render(<PinEditor id={1} />)

    const title = await screen.findByLabelText("Title")
    fireEvent.change(title, { target: { value: "new" } })
    fireEvent.click(screen.getByRole("button", { name: "Save" }))

    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toContain(
        "Cannot edit scheduled pin",
      ),
    )
  })

  it("renders the Possible duplicates panel with a link to the duplicate", async () => {
    mockedFetch.mockImplementation(async () => makePin({ id: 1 }))
    mockedFetchDuplicates.mockImplementation(async () => [
      { id: 99, title: "Dup", score: 0.95, status: "ready" },
    ])
    render(<PinEditor id={1} />)

    expect(await screen.findByText("Possible duplicates")).toBeDefined()
    const link = screen.getByRole("link", { name: /Dup/ })
    expect(link.getAttribute("href")).toBe("/pin/99")
    expect(link.textContent).toContain("95%")
  })

  it("records an 'edited' learning signal after a successful Save", async () => {
    mockedFetch.mockImplementation(async () => makePin({ title: "Original" }))
    render(<PinEditor id={1} />)

    const title = await screen.findByLabelText("Title")
    fireEvent.change(title, { target: { value: "new" } })
    fireEvent.click(screen.getByRole("button", { name: "Save" }))

    await waitFor(() =>
      expect(mockedRecordLearning).toHaveBeenCalledWith("edited", 1),
    )
  })

  it("records an 'approved' learning signal after a successful Approve", async () => {
    mockedFetch.mockImplementation(async () => makePin({ status: "ready" }))
    render(<PinEditor id={1} />)

    await screen.findByDisplayValue("Original")
    fireEvent.click(screen.getByRole("button", { name: "Approve" }))

    await waitFor(() =>
      expect(mockedRecordLearning).toHaveBeenCalledWith("approved", 1),
    )
  })

  it("records a 'regenerated' learning signal after a successful Regenerate", async () => {
    mockedFetch.mockImplementation(async () => makePin({ status: "ready" }))
    render(<PinEditor id={1} />)

    await screen.findByDisplayValue("Original")
    fireEvent.click(screen.getByRole("button", { name: "Regenerate" }))

    await waitFor(() =>
      expect(mockedRecordLearning).toHaveBeenCalledWith("regenerated", 1),
    )
  })
})
