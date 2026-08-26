import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export default function UploadPage() {
  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <h1 className="text-2xl font-semibold tracking-tight">Upload</h1>
      <p className="mt-2 text-muted-foreground">
        Drop images and let the platform auto-describe them.
      </p>
      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Drop zone</CardTitle>
          <CardDescription>Wired up in Task 9.</CardDescription>
        </CardHeader>
        <CardContent className="text-muted-foreground">
          Multi-file upload with progress lands in Task 9.
        </CardContent>
      </Card>
    </div>
  )
}
