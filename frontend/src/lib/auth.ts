import { create } from "zustand";
import type { Me } from "./types";

interface AuthState {
  token: string | null;
  user: Me | null;
  ready: boolean;
  setSession: (token: string, user: Me) => void;
  setUser: (user: Me) => void;
  clear: () => void;
  markReady: () => void;
  can: (perm: string) => boolean;
}

// Không lưu token vào localStorage; tải lại trang sẽ gọi /auth/refresh bằng cookie HttpOnly.
export const useAuth = create<AuthState>((set, get) => ({
  token: null,
  user: null,
  ready: false,
  setSession: (token, user) => set({ token, user }),
  setUser: (user) => set({ user }),
  clear: () => set({ token: null, user: null }),
  markReady: () => set({ ready: true }),
  can: (perm) => !!get().user?.permissions.includes(perm),
}));
