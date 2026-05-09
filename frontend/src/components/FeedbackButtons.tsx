import { useState } from "react";
import { postFeedback, type FeedbackResponse } from "../lib/api";

type Signal = "too_jargony" | "too_basic" | "nailed_it";

interface Props {
  pitchId: string | null;
  ticker?: string;
  userId?: string;
  profileSnapshot?: Record<string, unknown>;
  onFeedback?: (signal: Signal, response: FeedbackResponse) => void;
}

const SIGNALS = [
  { signal: "nailed_it" as const,   label: "Nailed it",      color: "var(--green)" },
  { signal: "too_jargony" as const, label: "Too jargon-y",   color: "var(--red)" },
  { signal: "too_basic" as const,   label: "Too basic",      color: "var(--yellow)" },
] as const;

export default function FeedbackButtons({
  pitchId,
  ticker,
  userId = "kai_demo",
  profileSnapshot,
  onFeedback,
}: Props) {
  const [sent, setSent] = useState<Signal | null>(null);
  const [note, setNote] = useState<string | null>(null);

  async function handleClick(signal: Signal) {
    if (!pitchId || sent) return;
    setSent(signal);
    setNote("Style updating");
    try {
      const response = await postFeedback(pitchId, userId, signal, {
        ticker,
        profile: profileSnapshot,
      });
      onFeedback?.(signal, response);

      const deltaPct = Math.round((response.jargon_level_delta || 0) * 100);
      if (signal === "too_jargony") {
        const flagged = response.flagged_terms_added ?? [];
        setNote(
          flagged.length
            ? `Style updated: jargon ${deltaPct}%, avoiding ${flagged.slice(0, 2).join(", ")}`
            : `Style updated: jargon ${deltaPct}%`
        );
      } else if (signal === "too_basic") {
        setNote(`Style updated: jargon +${deltaPct}%`);
      } else {
        setNote("Style locked in");
      }
    } catch (err) {
      console.error("feedback error", err);
      setNote("Couldn't update style — try again");
      setSent(null);
    }
  }

  return (
    <div className="feedback-bar">
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
      {note && <span className="feedback-note">{note}</span>}
    </div>
  );
}
