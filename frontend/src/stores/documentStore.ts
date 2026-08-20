import { create } from "zustand";

interface DocumentState {
  keyword: string;
  setKeyword: (keyword: string) => void;
}

export const useDocumentStore = create<DocumentState>((set) => ({
  keyword: "",
  setKeyword: (keyword) => set({ keyword }),
}));
