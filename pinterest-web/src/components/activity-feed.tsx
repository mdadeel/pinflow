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
          <p className="text-sm text-muted-foreground">Waiting for activity…</p>
        ) : (
          <ul className="max-h-96 divide-y overflow-y-auto">
            {events.map((event) => (
              <li key={event.id} className="flex items-start justify-between gap-3 py-2 text-sm">
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
