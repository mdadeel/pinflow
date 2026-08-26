import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export default function QueuePage() {
  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <h1 className="text-2xl font-semibold tracking-tight">Queue</h1>
      <p className="mt-2 text-muted-foreground">
        Review, reorder, and approve pins before they publish.
      </p>
      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Pending pins</CardTitle>
          <CardDescription>Wired up in Task 10.</CardDescription>
        </CardHeader>
        <CardContent className="text-muted-foreground">
          Kanban-style queue with drag/drop lands in Task 10.
        </CardContent>
      </Card>
    </div>
  )
}
