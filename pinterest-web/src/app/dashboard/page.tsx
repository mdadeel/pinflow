import { ActivityFeed } from "@/components/activity-feed"
import { RunPipelineButton } from "@/components/run-pipeline-button"
import { StatCards } from "@/components/stat-cards"
import { OverviewChart, PerformanceChart } from "@/components/charts"
import { RecentPins } from "@/components/recent-pins"
import { HealthStatus } from "@/components/health-status"

export default function DashboardPage() {
  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="mt-1 text-muted-foreground">
            Monitor your pin queue and publishing activity.
          </p>
        </div>
        <RunPipelineButton />
      </div>

      <section className="mt-8">
        <StatCards />
      </section>

      <section className="mt-8 grid gap-6 md:grid-cols-2">
        <OverviewChart />
        <PerformanceChart />
      </section>

      <section className="mt-8 grid gap-6 md:grid-cols-2">
        <RecentPins />
        <ActivityFeed />
      </section>

      <section className="mt-8">
        <HealthStatus />
      </section>
    </div>
  )
}
