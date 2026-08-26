import { create } from "zustand"
import type { Pin, PinStatus } from "@/lib/api"

interface QueueState {
  pins: Pin[]
  draggingId: number | null
  error: string | null
  setPins: (pins: Pin[]) => void
  setDragging: (id: number | null) => void
  setError: (error: string | null) => void
  clearError: () => void
  moveOptimistic: (id: number, status: PinStatus) => void
  revert: (id: number, prevStatus: PinStatus) => void
}

export const useQueueStore = create<QueueState>((set) => ({
  pins: [],
  draggingId: null,
  error: null,
  setPins: (pins) => set({ pins }),
  setDragging: (id) => set({ draggingId: id }),
  setError: (error) => set({ error }),
  clearError: () => set({ error: null }),
  moveOptimistic: (id, status) =>
    set((s) => ({
      pins: s.pins.map((p) => (p.id === id ? { ...p, status } : p)),
    })),
  revert: (id, prevStatus) =>
    set((s) => ({
      pins: s.pins.map((p) => (p.id === id ? { ...p, status: prevStatus } : p)),
    })),
}))
