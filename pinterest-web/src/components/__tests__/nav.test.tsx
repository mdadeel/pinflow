import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import { Nav } from "@/components/nav"

describe("Nav", () => {
  it("renders brand and all section links", () => {
    render(<Nav />)
    expect(screen.getByText("Pinterest Automation")).toBeDefined()
    expect(screen.getByRole("link", { name: "Overview" }).getAttribute("href")).toBe("/")
    expect(screen.getByRole("link", { name: "Upload" }).getAttribute("href")).toBe("/upload")
    expect(screen.getByRole("link", { name: "Queue" }).getAttribute("href")).toBe("/queue")
  })
})
