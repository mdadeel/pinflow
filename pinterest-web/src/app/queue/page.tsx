import { KanbanBoard } from "@/components/kanban-board"

export default function QueuePage() {
  return (
    <div className="mx-auto max-w-7xl px-6 py-10">
      <h1 className="text-2xl font-semibold tracking-tight">Queue</h1>
      <p className="mt-2 text-muted-foreground">
        Review, reorder, and move pins between statuses before they publish.
      </p>
      <div className="mt-6">
        <KanbanBoard />
      </div>
    </div>
  )
}
