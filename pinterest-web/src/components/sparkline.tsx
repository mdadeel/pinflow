"use client"

interface SparklineProps {
  data: number[]
  width?: number
  height?: number
  stroke?: string
}

export function Sparkline({
  data,
  width = 240,
  height = 48,
  stroke = "currentColor",
}: SparklineProps) {
  const pad = 2
  const min = data.length ? Math.min(...data) : 0
  const max = data.length ? Math.max(...data) : 0
  const flat = data.length < 2 || min === max

  let points: string
  if (flat) {
    const midY = height / 2
    points = `${pad},${midY} ${width - pad},${midY}`
  } else {
    const span = max - min
    const stepX = data.length > 1 ? (width - pad * 2) / (data.length - 1) : 0
    points = data
      .map((v, i) => {
        const x = pad + i * stepX
        const y = height - pad - ((v - min) / span) * (height - pad * 2)
        return `${x.toFixed(1)},${y.toFixed(1)}`
      })
      .join(" ")
  }

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-hidden="true"
      data-slot="sparkline"
    >
      <polyline
        points={points}
        fill="none"
        stroke={stroke}
        strokeWidth={2}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  )
}
