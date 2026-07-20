import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

type Kind = "ok" | "error";
interface ToastCtx {
  notify: (message: string, kind?: Kind) => void;
}
const Ctx = createContext<ToastCtx>({ notify: () => {} });

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<{ message: string; kind: Kind } | null>(null);

  const notify = useCallback((message: string, kind: Kind = "ok") => {
    setToast({ message, kind });
    window.setTimeout(() => setToast(null), 3800);
  }, []);

  return (
    <Ctx.Provider value={{ notify }}>
      {children}
      {toast && <div className={`toast ${toast.kind}`}>{toast.message}</div>}
    </Ctx.Provider>
  );
}

export const useToast = () => useContext(Ctx);
