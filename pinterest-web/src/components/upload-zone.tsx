"use client";

import { useEffect, useRef, useCallback, useState } from "react"
import Image from "next/image";
import { Button } from "@/components/ui/button";
import { useUploadStore } from "@/stores/upload-store";
import { uploadFiles, fetchPins, bulkAction, runPipeline, type Pin } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const ACCEPTED = [".png", ".jpg", ".jpeg", ".webp"];

function formatBytes(bytes: number | null): string {
  if (bytes == null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i++;
  }
  return `${value.toFixed(1)} ${units[i]}`;
}

function hasAcceptedExt(name: string): boolean {
  const lower = name.toLowerCase();
  return ACCEPTED.some((ext) => lower.endsWith(ext));
}

function readEntry(entry: FileSystemEntry): Promise<File[]> {
  return new Promise((resolve) => {
    if (entry.isFile) {
      (entry as FileSystemFileEntry).file((file) => resolve([file]));
      return;
    }
    if (entry.isDirectory) {
      const reader = (entry as FileSystemDirectoryEntry).createReader();
      const collected: File[] = [];
      const readBatch = () => {
        reader.readEntries((entries) => {
          if (!entries.length) {
            resolve(collected);
            return;
          }
          Promise.all(entries.map(readEntry)).then((nested) => {
            nested.forEach((f) => collected.push(...f));
            readBatch();
          });
        });
      };
      readBatch();
      return;
    }
    resolve([]);
  });
}

async function gatherFromItems(items: DataTransferItemList): Promise<File[]> {
  const entries: FileSystemEntry[] = [];
  for (let i = 0; i < items.length; i++) {
    const entry = items[i].webkitGetAsEntry?.();
    if (entry) entries.push(entry);
  }
  if (!entries.length) return [];
  const nested = await Promise.all(entries.map(readEntry));
  return nested.flat();
}

function Thumbnail({ pin }: { pin: Pin }) {
  const src = `${API_BASE}${pin.image_url}`;
  return (
      <div
        data-testid="thumb"
        className="overflow-hidden rounded-lg border border-border bg-muted"
      >
        <div className="relative aspect-square w-full">
          <Image
            src={src}
            alt={pin.filename}
            fill
            className="object-cover"
            sizes="(max-width: 640px) 50vw, 25vw"
          />
        </div>
        <div className="space-y-0.5 p-2 text-xs">
        <p className="truncate font-medium" title={pin.filename}>
          {pin.filename}
        </p>
        <p className="text-muted-foreground">
          {pin.width && pin.height ? `${pin.width}×${pin.height}` : "—"} ·{" "}
          {formatBytes(pin.file_size)}
        </p>
      </div>
    </div>
  );
}

export function UploadZone() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [resetting, setResetting] = useState(false);
  const [resetMsg, setResetMsg] = useState<string | null>(null);
  const {
    dragHighlight,
    uploading,
    lastResult,
    error,
    setDragHighlight,
    setUploading,
    setResult,
    setError,
  } = useUploadStore();

  const handleResetFailed = useCallback(async () => {
    setResetting(true);
    setResetMsg(null);
    setError(null);
    try {
      const res = await fetchPins({ status: "failed", per_page: 200 });
      const ids = res.items.map((p) => p.id);
      if (ids.length === 0) {
        setResetMsg("No failed uploads to reset.");
        return;
      }
      await bulkAction("reset", ids);
      await runPipeline();
      setResetMsg(`Reset ${ids.length} failed upload(s) and re-queued for processing.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reset failed.");
    } finally {
      setResetting(false);
    }
  }, [setError]);

  const process = useCallback(
    async (files: File[]) => {
      const accepted = files.filter((f) => hasAcceptedExt(f.name));
      const rejectedCount = files.length - accepted.length;
      if (accepted.length === 0) {
        if (rejectedCount > 0)
          setError(
            "No supported images found (accepted: .png .jpg .jpeg .webp).",
          );
        return;
      }
      setUploading(true);
      setError(null);
      try {
        const result = await uploadFiles(accepted);
        setResult(result);
        if (rejectedCount > 0)
          setError(`${rejectedCount} file(s) skipped: unsupported type.`);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Upload failed.");
      } finally {
        setUploading(false);
      }
    },
    [setError, setResult, setUploading],
  );

  const onDrop = useCallback(
    async (e: React.DragEvent) => {
      e.preventDefault();
      setDragHighlight(false);
      const dt = e.dataTransfer;
      let files: File[] = [];
      if (
        dt.items &&
        dt.items.length &&
        typeof dt.items[0].webkitGetAsEntry === "function"
      ) {
        files = await gatherFromItems(dt.items);
      } else {
        files = Array.from(dt.files);
      }
      await process(files);
    },
    [process, setDragHighlight],
  );

  const onPaste = useCallback(
    (e: ClipboardEvent) => {
      const files = e.clipboardData ? Array.from(e.clipboardData.files) : [];
      if (files.length) void process(files);
    },
    [process],
  );

  useEffect(() => {
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, [onPaste]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={handleResetFailed}
          disabled={resetting}
        >
          {resetting ? "Resetting…" : "Reset failed uploads"}
        </Button>
        {resetMsg && (
          <span className="text-sm text-muted-foreground" data-testid="reset-msg">
            {resetMsg}
          </span>
        )}
      </div>

      <div
        data-testid="dropzone"
        onDragOver={(e) => {
          e.preventDefault();
          setDragHighlight(true);
        }}
        onDragLeave={() => setDragHighlight(false)}
        onDrop={onDrop}
        className={`flex min-h-[40vh] flex-col items-center justify-center rounded-xl border-2 border-dashed p-10 text-center transition-colors ${
          dragHighlight
            ? "border-primary bg-primary/5"
            : "border-border bg-muted/30"
        }`}
      >
        <p className="text-lg font-medium">
          {dragHighlight ? "Drop to upload" : "Drag & drop images here"}
        </p>
        <p className="mt-1 text-sm text-muted-foreground">
          or paste image files, or
        </p>
        <Button
          type="button"
          variant="secondary"
          size="lg"
          className="mt-4"
          onClick={() => inputRef.current?.click()}
        >
          <svg className="mr-2 size-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
          </svg>
          Browse files
        </Button>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED.join(",")}
          multiple
          className="hidden"
          onChange={(e) => {
            const files = Array.from(e.target.files ?? []);
            if (files.length) void process(files);
            e.target.value = "";
          }}
        />
        <p className="mt-3 text-xs text-muted-foreground">
          Accepted: {ACCEPTED.join(" ")}
        </p>
      </div>

      {uploading && (
        <p className="text-sm text-muted-foreground" data-testid="uploading">
          Uploading…
        </p>
      )}

      {error && (
        <div
          role="alert"
          className="rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive"
        >
          {error}
        </div>
      )}

      {lastResult && lastResult.added.length > 0 && (
        <section>
          <h2 className="mb-2 text-sm font-semibold">Uploaded</h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
            {lastResult.added.map((pin) => (
              <Thumbnail key={pin.id} pin={pin} />
            ))}
          </div>
        </section>
      )}

      {lastResult && (lastResult.retried?.length ?? 0) > 0 && (
        <section>
          <h2 className="mb-2 text-sm font-semibold">Retried failed (re-uploading)</h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
            {lastResult.retried?.map((pin) => (
              <Thumbnail key={pin.id} pin={pin} />
            ))}
          </div>
        </section>
      )}

      {lastResult && lastResult.duplicates.length > 0 && (
        <section>
          <h2 className="mb-2 text-sm font-semibold">Duplicates (skipped)</h2>
          <ul className="list-inside list-disc text-sm text-muted-foreground">
            {lastResult.duplicates.map((name) => (
              <li key={name}>{name}</li>
            ))}
          </ul>
        </section>
      )}

      {lastResult && lastResult.rejected.length > 0 && (
        <section>
          <h2 className="mb-2 text-sm font-semibold">Rejected</h2>
          <ul className="list-inside list-disc text-sm text-muted-foreground">
            {lastResult.rejected.map((r) => (
              <li key={r.filename}>
                {r.filename} — {r.reason}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
