import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export default function HomePage() {
  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <h1 className="text-2xl font-semibold tracking-tight">Overview</h1>
      <p className="mt-2 text-muted-foreground">
        Monitor your queue and publishing activity.
      </p>
      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Queue health</CardTitle>
            <CardDescription>Live count from the API</CardDescription>
          </CardHeader>
          <CardContent className="text-muted-foreground">
            Wired up in Task 8.
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Recent activity</CardTitle>
            <CardDescription>Last 24 hours</CardDescription>
          </CardHeader>
          <CardContent className="text-muted-foreground">
            Wired up in Task 8.
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
