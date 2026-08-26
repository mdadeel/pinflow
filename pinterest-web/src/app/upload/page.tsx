import { UploadZone } from "@/components/upload-zone"

export default function UploadPage() {
  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <h1 className="text-2xl font-semibold tracking-tight">Upload</h1>
      <p className="mt-2 text-muted-foreground">
        Drop images and let the platform auto-describe them.
      </p>
      <div className="mt-6">
        <UploadZone />
      </div>
    </div>
  )
}
