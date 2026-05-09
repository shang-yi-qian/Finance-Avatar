import { useState, type FormEvent } from "react";

interface Props {
  onSubmit: (ticker: string) => void;
  loading?: boolean;
}

export default function TickerInput({ onSubmit, loading = false }: Props) {
  const [value, setValue] = useState("");

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const ticker = value.trim().toUpperCase();
    if (ticker) onSubmit(ticker);
  }

  return (
    <form
      onSubmit={handleSubmit}
      style={{ display: "flex", gap: 8, marginBottom: 24 }}
    >
      <input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Enter ticker — NVDA, TSLA, AAPL…"
        maxLength={10}
        disabled={loading}
        style={{
          flex: 1,
          padding: "12px 16px",
          background: "var(--bg-input)",
          border: "1px solid var(--border)",
          borderRadius: 8,
          color: "var(--text-bright)",
          fontSize: 16,
          outline: "none",
        }}
      />
      <button
        type="submit"
        className="btn btn-primary"
        disabled={loading || !value.trim()}
      >
        {loading ? "Analyzing…" : "Pitch me →"}
      </button>
    </form>
  );
}
