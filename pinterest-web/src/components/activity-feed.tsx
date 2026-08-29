"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { formatEvent, relativeTime, useEventStream } from "@/hooks/use-event-stream"

export function ActivityFeed() {
  const { events, connected } = useEventStream()

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <span
            className={`size-2 rounded-full ${connected ? "bg-emerald-500" : "bg-muted-foreground/40"}`}
            aria-hidden
          />
          Live activity
        </CardTitle>
      </CardHeader>
      <CardContent>
        {events.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted">
              <svg
                className="h-6 w-6 text-muted-foreground"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={1.5}
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z"
                />
              </svg>
            </div>
            <p className="mt-4 text-sm font-medium">No activity yet</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Run the pipeline to start processing pins
            </p>
          </div>
        ) : (
          <ul className="max-h-96 divide-y overflow-y-auto">
            {events.map((event) => (
              <li key={event.id} className="flex items-start justify-between gap-3 py-3 text-sm">
                <span className="text-foreground">{formatEvent(event)}</span>
                <time
                  dateTime={event.at}
                  className="shrink-0 text-xs text-muted-foreground"
                  title={new Date(event.at).toLocaleString()}
                >
                  {relativeTime(event.at)}
                </time>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}
