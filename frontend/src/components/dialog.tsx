import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

// In-app replacements for window.confirm / window.prompt — styled dialogs with
// an imperative, promise-based API so any handler can `await confirmDialog(...)`.
type ConfirmOpts = { title?: string; message: string; confirmLabel?: string; cancelLabel?: string; danger?: boolean };
type PromptOpts = {
  title?: string;
  message: string;
  confirmLabel?: string;
  placeholder?: string;
  defaultValue?: string;
  password?: boolean;
  minLength?: number;
};
type State = ({ kind: "confirm" } & ConfirmOpts) | ({ kind: "prompt" } & PromptOpts) | null;

let show: ((s: NonNullable<State>) => void) | null = null;
let resolveFn: ((v: unknown) => void) | null = null;

export function confirmDialog(opts: ConfirmOpts): Promise<boolean> {
  return new Promise((resolve) => {
    resolveFn = resolve as (v: unknown) => void;
    if (show) show({ kind: "confirm", ...opts });
    else resolve(false);
  });
}

export function promptDialog(opts: PromptOpts): Promise<string | null> {
  return new Promise((resolve) => {
    resolveFn = resolve as (v: unknown) => void;
    if (show) show({ kind: "prompt", ...opts });
    else resolve(null);
  });
}

export function DialogHost() {
  const [state, setState] = useState<State>(null);
  const [value, setValue] = useState("");
  const [err, setErr] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    show = (s) => {
      setState(s);
      setValue(s.kind === "prompt" ? s.defaultValue ?? "" : "");
      setErr("");
    };
    return () => {
      show = null;
    };
  }, []);

  useEffect(() => {
    if (!state) return;
    document.body.style.overflow = "hidden";
    if (state.kind === "prompt") window.setTimeout(() => inputRef.current?.focus(), 30);
    return () => {
      document.body.style.overflow = "";
    };
  }, [state]);

  if (!state) return null;

  const finish = (result: unknown) => {
    setState(null);
    resolveFn?.(result);
    resolveFn = null;
  };
  const cancel = () => finish(state.kind === "confirm" ? false : null);
  const accept = () => {
    if (state.kind === "prompt") {
      const min = state.minLength ?? 0;
      if (value.length < min) {
        setErr(`Must be at least ${min} characters.`);
        return;
      }
      finish(value);
    } else {
      finish(true);
    }
  };
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      accept();
    } else if (e.key === "Escape") {
      e.preventDefault();
      cancel();
    }
  };

  const danger = state.kind === "confirm" && state.danger;

  return createPortal(
    <div className="modal-back" onClick={cancel} onKeyDown={onKey}>
      <div className="dialog" onClick={(e) => e.stopPropagation()} role="alertdialog" aria-modal="true">
        <h3 className="dialog-title">{state.title ?? (state.kind === "confirm" ? "Please confirm" : "Enter a value")}</h3>
        <p className="dialog-msg">{state.message}</p>
        {state.kind === "prompt" && (
          <>
            <input
              ref={inputRef}
              type={state.password ? "password" : "text"}
              value={value}
              placeholder={state.placeholder}
              autoComplete={state.password ? "new-password" : "off"}
              onChange={(e) => {
                setValue(e.target.value);
                setErr("");
              }}
              onKeyDown={onKey}
              style={{ marginTop: 14 }}
            />
            {err && <div className="err">{err}</div>}
          </>
        )}
        <div className="btn-row" style={{ justifyContent: "flex-end", marginTop: 20 }}>
          <button className="btn" onClick={cancel}>
            {state.kind === "confirm" ? state.cancelLabel ?? "Cancel" : "Cancel"}
          </button>
          <button className={`btn ${danger ? "danger-solid" : "primary"}`} onClick={accept} autoFocus>
            {state.confirmLabel ?? "OK"}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
