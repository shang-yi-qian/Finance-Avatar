// Phase 4: selfie upload → 30s voice recording → quiz → GPT Image 2 → ElevenLabs clone

export default function Onboarding() {
  return (
    <div style={{ maxWidth: 540, margin: "0 auto", paddingTop: 48, textAlign: "center" }}>
      <h1 style={{ fontSize: 36, marginBottom: 12 }}>Welcome to PitchSnap</h1>
      <p style={{ color: "var(--text-dim)", marginBottom: 32 }}>
        Let's build your investment twin. You'll need 2 minutes, a selfie, and a quick voice sample.
      </p>

      <div
        className="card"
        style={{ textAlign: "left", display: "flex", flexDirection: "column", gap: 24 }}
      >
        {/* Step indicators — active in Phase 4 */}
        {[
          { step: 1, label: "Selfie upload", desc: "We'll generate a stylised avatar with AI" },
          { step: 2, label: "30s voice sample", desc: "Cloned by ElevenLabs — only done once" },
          { step: 3, label: "Quick quiz", desc: "Risk tolerance, horizon, and interests" },
        ].map(({ step, label, desc }) => (
          <div key={step} style={{ display: "flex", gap: 14, alignItems: "flex-start", opacity: 0.5 }}>
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: "50%",
                background: "var(--bg-input)",
                border: "1px solid var(--border)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 13,
                fontWeight: 600,
                color: "var(--accent-light)",
                flexShrink: 0,
              }}
            >
              {step}
            </div>
            <div>
              <div style={{ fontWeight: 600, color: "var(--text-bright)", marginBottom: 2 }}>
                {label}
              </div>
              <div style={{ fontSize: 13, color: "var(--text-dim)" }}>{desc}</div>
            </div>
          </div>
        ))}

        <p style={{ fontSize: 13, color: "var(--text-dim)", textAlign: "center" }}>
          Onboarding UI coming in Phase 4 — use the{" "}
          <a href="/dashboard" style={{ color: "var(--accent-light)" }}>
            Dashboard
          </a>{" "}
          with the kai_demo profile for now.
        </p>
      </div>
    </div>
  );
}
