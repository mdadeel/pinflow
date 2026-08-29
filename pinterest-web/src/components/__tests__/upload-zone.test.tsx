import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { UploadZone } from "@/components/upload-zone"
import { uploadFiles, fetchPins, bulkAction, runPipeline } from "@/lib/api"

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>()
  return {
    ...actual,
    uploadFiles: vi.fn(),
    fetchPins: vi.fn(),
    bulkAction: vi.fn(),
    runPipeline: vi.fn(),
  }
})

const mockedUpload = vi.mocked(uploadFiles)
const mockedFetchPins = vi.mocked(fetchPins)
const mockedBulkAction = vi.mocked(bulkAction)
const mockedRunPipeline = vi.mocked(runPipeline)

function makeFile(name: string, type = "image/png") {
  return new File([new Uint8Array([1, 2, 3])], name, { type })
}

const fakePin = {
  id: 1,
  filename: "cat.png",
  image_url: "/media/1",
  status: "pending" as const,
  title: null,
  description: null,
  alt_text: null,
  primary_keyword: null,
  secondary_keywords: null,
  tags: null,
  board_name: null,
  content_category: null,
  file_size: 2048,
  width: 100,
  height: 200,
  created_at: "2026-01-01T00:00:00Z",
  scheduled_time: null,
}

describe("UploadZone", () => {
  beforeEach(() => mockedUpload.mockReset())

  it("calls uploadFiles on drop and renders added + duplicate results", async () => {
    mockedUpload.mockResolvedValue({
      added: [fakePin],
      duplicates: ["dog.png"],
      retried: [],
      rejected: [{ filename: "bad.gif", reason: "unsupported type" }],
    })

    render(<UploadZone />)

    const zone = screen.getByTestId("dropzone")
    const files = [makeFile("cat.png"), makeFile("sky.png")]
    fireEvent.drop(zone, { dataTransfer: { files } })

    await waitFor(() => expect(mockedUpload).toHaveBeenCalled())
    expect(mockedUpload.mock.calls[0][0].map((f) => f.name)).toEqual([
      "cat.png",
      "sky.png",
    ])

    await waitFor(() => expect(screen.getByText("cat.png")).toBeDefined())
    expect(screen.getByText("dog.png")).toBeDefined()
  })

  it("triggers the hidden file input from the multi-select button", () => {
    const clickSpy = vi.spyOn(HTMLInputElement.prototype, "click")
    render(<UploadZone />)
    fireEvent.click(screen.getByRole("button", { name: /browse/i }))
    expect(clickSpy).toHaveBeenCalled()
    clickSpy.mockRestore()
  })

  it("reset failed button resets failed pins and runs the pipeline", async () => {
    mockedFetchPins.mockResolvedValue({
      items: [{ id: 1 } as unknown as import("@/lib/api").Pin],
      total: 1,
      page: 1,
      per_page: 200,
    } as unknown as import("@/lib/api").PinListResponse)
    mockedBulkAction.mockResolvedValue({} as never)
    mockedRunPipeline.mockResolvedValue({} as never)

    render(<UploadZone />)
    fireEvent.click(screen.getByRole("button", { name: /reset failed/i }))

    await waitFor(() =>
      expect(mockedFetchPins).toHaveBeenCalledWith({
        status: "failed",
        per_page: 200,
      }),
    )
    expect(mockedBulkAction).toHaveBeenCalledWith("reset", [1])
    expect(mockedRunPipeline).toHaveBeenCalled()
    expect(screen.getByTestId("reset-msg").textContent).toMatch(/Reset 1 failed/)
  })
})
