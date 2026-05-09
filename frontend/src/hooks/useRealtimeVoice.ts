// Phase 5: WebSocket bridge to GPT Realtime 2 via backend WS /realtime
// Manages mic capture (getUserMedia), PCM streaming, and incoming audio playback
// Exposes: { isActive, toggle, isListening, isSpeaking }

export function useRealtimeVoice(_ticker?: string) {
  return {
    isActive: false,
    isListening: false,
    isSpeaking: false,
    toggle: () => {
      console.warn("useRealtimeVoice: not implemented — Phase 5");
    },
  };
}
