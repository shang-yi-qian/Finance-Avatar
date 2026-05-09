Compute fit score: total = 0.40*risk_fit + 0.25*style_fit + 0.15*horizon_fit + 0.20*conviction

- risk_fit: stock beta vs user risk tolerance → (1 - |user_tolerance - stock_volatility_norm|) * 10
- style_fit: sector vs user thematic_interests → thematic overlap score
- horizon_fit: growth/value profile vs user horizon
- conviction: from research conviction_signal (0–1 scaled to 0–10)

Return breakdown JSON with score (0–10) + one-line reason per component.
