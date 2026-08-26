import { describe, it, expect } from "vitest"
import { render } from "@testing-library/react"
import { Sparkline } from "@/components/sparkline"

describe("Sparkline", () => {
  it("renders an svg with a polyline of one point per data value", () => {
    const { container } = render(<Sparkline data={[1, 2, 3, 4]} />)
    const svg = container.querySelector("svg")
    expect(svg).toBeDefined()
    const polyline = container.querySelector("polyline")
    expect(polyline).toBeDefined()
    const points = polyline!.getAttribute("points") ?? ""
    expect(points.split(" ").length).toBe(4)
  })

  it("renders without crashing for empty data", () => {
    const { container } = render(<Sparkline data={[]} />)
    expect(container.querySelector("svg")).toBeDefined()
    expect(container.querySelector("polyline")).toBeDefined()
  })
})
