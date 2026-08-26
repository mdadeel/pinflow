import { ActivityFeed } from "@/components/activity-feed"
import { StatCards } from "@/components/stat-cards"

export default function HomePage() {
  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <h1 className="text-2xl font-semibold tracking-tight">Overview</h1>
      <p className="mt-2 text-muted-foreground">
        Monitor your queue and publishing activity.
      </p>
      <section className="mt-6">
        <StatCards />
      </section>
      <section className="mt-6">
        <ActivityFeed />
      </section>
    </div>
  )
}
