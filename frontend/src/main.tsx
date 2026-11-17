import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { refreshSession } from "./lib/api";
import { useAuth } from "./lib/auth";
import "./styles.css";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: (n, e: unknown) => n < 1 && (e as { status?: number })?.status !== 404, refetchOnWindowFocus: false } },
});

// Khôi phục phiên từ cookie HttpOnly (nếu có) trước khi hiển thị các trang cần đăng nhập.
refreshSession().finally(() => useAuth.getState().markReady());

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
