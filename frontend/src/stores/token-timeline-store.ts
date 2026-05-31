import { create } from "zustand";

/**
 * A single per-turn token usage entry in the timeline
 */
export interface TokenTimelineEntry {
  turn: number;
  prompt_tokens: number;
  completion_tokens: number;
  per_turn_token: number;
  context_window: number;
  is_condensed: boolean;
  condenser_prompt_tokens: number | null;
  response_id: string;
}

/**
 * Detail of a condensation event
 */
export interface CondensationDetail {
  turn: number;
  summary: string;
  forgotten_event_ids_count: number;
}

/**
 * Response from the GET /token-timeline API
 */
export interface TokenTimelineResponse {
  timeline: TokenTimelineEntry[];
  condensation_details: CondensationDetail[];
}

interface TokenTimelineState {
  entries: TokenTimelineEntry[];
  condensationDetails: CondensationDetail[];
}

interface TokenTimelineStore extends TokenTimelineState {
  addEntries: (entries: TokenTimelineEntry[]) => void;
  addCondensationDetail: (detail: CondensationDetail) => void;
  markLastEntryCondensed: (condenserPromptTokens: number | null) => void;
  setFromAPI: (response: TokenTimelineResponse) => void;
  reset: () => void;
}

const useTokenTimelineStore = create<TokenTimelineStore>((set) => ({
  entries: [],
  condensationDetails: [],

  addEntries: (newEntries) =>
    set((state) => ({
      entries: [...state.entries, ...newEntries],
    })),

  addCondensationDetail: (detail) =>
    set((state) => ({
      condensationDetails: [...state.condensationDetails, detail],
    })),

  markLastEntryCondensed: (condenserPromptTokens) =>
    set((state) => {
      if (state.entries.length === 0) return state;
      const updated = [...state.entries];
      const lastIdx = updated.length - 1;
      updated[lastIdx] = {
        ...updated[lastIdx],
        is_condensed: true,
        condenser_prompt_tokens: condenserPromptTokens,
      };
      return { entries: updated };
    }),

  setFromAPI: (response) =>
    set({
      entries: response.timeline,
      condensationDetails: response.condensation_details,
    }),

  reset: () => set({ entries: [], condensationDetails: [] }),
}));

export default useTokenTimelineStore;
