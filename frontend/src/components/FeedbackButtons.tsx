import { useState } from "react";
import { postFeedback } from "../lib/api";

interface Props {
  pitchId: string | null;
  userId?: string;
  onFeedback?: (signal: "too_jargony" | "too_basic" | "nailed_it") => void;
}

const SIGNALS = [
  { signal: "nailed_it" as const,   label: "👍 Nailed it",      color: "var(--green)" },
  { signal: "too_jargony" as const, label: "👎 Too jargon-y",   color: "var(--red)" },
  { signal: "too_basic" as const,   label: "👎 Too basic",       color: "var(--yellow)" },
] as const;

export default function FeedbackButtons({ pitchId, userId = "kai_demo", onFeedback }: Props) {
  const [sent, setSent] = useState<string | null>(null);

  async function handleClick(signal: "too_jargony" | "too_basic" | "nailed_it") {
    if (!pitchId || sent) return;
    setSent(signal);
    // Phase 3: this actually calls adaption_service via backend; for now just fires the request
    try {
      await postFeedback(pitchId, userId, signal);
      onFeedback?.(signal);
    } catch (err) {
      console.error("feedback error", err);
    }
  }

  return (
    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
      {SIGNALS.map(({ signal, label, color }) => (
        <button
          key={signal}
          className="btn btn-ghost"
          disabled={!pitchId || !!sent}
          onClick={() => handleClick(signal)}
          style={{
            borderColor: sent === signal ? color : undefined,
            color: sent === signal ? color : undefined,
            opacity: sent && sent !== signal ? 0.4 : 1,
          }}
        >
          {label}
        </button>
      ))}
      {sent && (
        <span style={{ color: "var(--text-dim)", fontSize: 13, alignSelf: "center" }}>
          Style updating…
        </span>
      )}
    </div>
  );
}
