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
    <form onSubmit={handleSubmit} className="ticker-form">
      <input
        className="ticker-input"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="NVDA, TSLA, BTC"
        maxLength={10}
        disabled={loading}
      />
      <button
        type="submit"
        className="btn btn-primary"
        disabled={loading || !value.trim()}
      >
        {loading ? "Analyzing" : "Pitch me"}
      </button>
    </form>
  );
}
