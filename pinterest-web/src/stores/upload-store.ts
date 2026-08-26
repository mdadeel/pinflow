import { create } from "zustand"
import type { UploadResult } from "@/lib/api"

interface UploadState {
  dragHighlight: boolean
  uploading: boolean
  lastResult: UploadResult | null
  error: string | null
  setDragHighlight: (v: boolean) => void
  setUploading: (v: boolean) => void
  setResult: (r: UploadResult | null) => void
  setError: (e: string | null) => void
  reset: () => void
}

export const useUploadStore = create<UploadState>((set) => ({
  dragHighlight: false,
  uploading: false,
  lastResult: null,
  error: null,
  setDragHighlight: (v) => set({ dragHighlight: v }),
  setUploading: (v) => set({ uploading: v }),
  setResult: (r) => set({ lastResult: r }),
  setError: (e) => set({ error: e }),
  reset: () =>
    set({ dragHighlight: false, uploading: false, lastResult: null, error: null }),
}))
