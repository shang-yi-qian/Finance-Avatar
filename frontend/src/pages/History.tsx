// Phase 2+: list of past pitches from Convex, grouped by ticker
// Uses useQuery(api.pitches.getPitchesByUser, { userId })

export default function History() {
  return (
    <div>
      <h1 style={{ fontSize: 24, marginBottom: 24 }}>Pitch History</h1>
      <div
        className="card"
        style={{ textAlign: "center", padding: 48, color: "var(--text-dim)" }}
      >
        <div style={{ fontSize: 36, marginBottom: 12 }}>🕑</div>
        <p>Your past pitches will appear here once Convex is wired up (Phase 2+).</p>
      </div>
    </div>
  );
}
