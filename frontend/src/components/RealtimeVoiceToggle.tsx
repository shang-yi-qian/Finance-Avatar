// Phase 5: activates WebSocket to GPT Realtime 2 via backend WS /realtime
// User can interrupt avatar mid-pitch; handles bi-directional audio streaming
import { useRealtimeVoice } from "../hooks/useRealtimeVoice";

interface Props {
  ticker?: string;
}

export default function RealtimeVoiceToggle({ ticker }: Props) {
  const { isActive, isListening, isSpeaking, toggle } = useRealtimeVoice(ticker);

  return (
    <button
      className="btn btn-ghost realtime-toggle"
      onClick={toggle}
      title="Toggle live voice mode (Phase 5)"
      style={{
        borderColor: isActive ? "var(--accent-light)" : undefined,
        color: isActive ? "var(--accent-light)" : undefined,
      }}
    >
      {isActive ? (
        <>
          {isListening ? "Listening" : isSpeaking ? "Speaking" : "Live voice"}
        </>
      ) : (
        "Voice mode"
      )}
    </button>
  );
}
