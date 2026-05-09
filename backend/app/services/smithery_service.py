"""Smithery valuation service.

Uses Smithery's Connect API to call the Financial Modeling Prep MCP server. If
the connection or upstream FMP token is not configured yet, this module raises a
clear runtime error so the valuation agent can fall back to demo data.
"""

import json
import os
import time
from datetime import date
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

_CACHE_TTL_SECONDS = 300
_cache: dict[str, tuple[float, dict[str, Any]]] = {}

_REQUIRED_TOOLS = {
    "quote": "getQuote",
    "profile": "getCompanyProfile",
    "ratios_ttm": "getFinancialRatiosTTM",
    "metrics_ttm": "getKeyMetricsTTM",
    "price_targets": "getPriceTargetConsensus",
    "price_change": "getStockPriceChange",
}

_OPTIONAL_CONTEXT_TOOLS = {
    "ratings": "getRatingsSnapshot",
    "grade_summary": "getStockGradeSummary",
    "analyst_estimates": "getAnalystEstimates",
    "earnings": "getEarningsReports",
    "income_growth": "getIncomeStatementGrowth",
    "financial_scores": "getFinancialScores",
    "peers": "getStockPeers",
    "sector_pe": "getSectorPESnapshot",
    "industry_pe": "getIndustryPESnapshot",
}

_FMP_STABLE_BASE = "https://financialmodelingprep.com/stable"
_DEFAULT_SHIBUI_CONNECTION_ID = "finance"


class SmitheryServiceError(RuntimeError):
    pass


def _first_number(*values: Any) -> float | None:
    for value in values:
        if value is None:
            continue
        try:
            return float(str(value).replace(",", ""))
        except (TypeError, ValueError):
            continue
    return None


def _first_value(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def _as_records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        for key in ("data", "result", "results", "items"):
            nested = value.get(key)
            if isinstance(nested, list):
                return [item for item in nested if isinstance(item, dict)]
            if isinstance(nested, dict):
                return [nested]
        return [value]
    return []


def _first_record(value: Any) -> dict[str, Any]:
    records = _as_records(value)
    return records[0] if records else {}


def _parse_tool_result(payload: dict[str, Any]) -> Any:
    if payload.get("isError"):
        text = payload.get("content", [{}])[0].get("text", "Smithery tool call failed")
        raise SmitheryServiceError(str(text))

    result = payload.get("result", {})

    if "structuredContent" in result:
        return result["structuredContent"]

    content = result.get("content", payload.get("content"))
    if isinstance(content, list) and content:
        item = content[0]
        if isinstance(item, dict):
            if "json" in item:
                return item["json"]
            text = item.get("text")
            if isinstance(text, str):
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return text

    return result


def _parse_text_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, str):
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            return []
        return _as_records(parsed)
    return _as_records(payload)


async def _fmp_get(client: httpx.AsyncClient, path: str, params: dict[str, Any]) -> Any:
    token = os.getenv("FMP_ACCESS_TOKEN")
    if not token:
        raise SmitheryServiceError("FMP_ACCESS_TOKEN is missing.")

    response = await client.get(
        f"{_FMP_STABLE_BASE}/{path}",
        params={**params, "apikey": token},
    )
    response.raise_for_status()
    payload = response.json()

    if isinstance(payload, dict) and payload.get("Error Message"):
        raise SmitheryServiceError(str(payload["Error Message"]))

    return payload


def _tool_name(tools: list[dict[str, Any]], desired: str) -> str | None:
    names = [tool.get("name") for tool in tools if isinstance(tool.get("name"), str)]

    for name in names:
        if name == desired:
            return name

    # Namespace endpoints often prefix tools with a connection ID.
    for name in names:
        if name.endswith(f".{desired}") or name.endswith(f"/{desired}") or name.endswith(f"_{desired}"):
            return name

    return None


def _sector_tags(profile: dict[str, Any]) -> list[str]:
    sector = str(_first_value(profile.get("sector"), "")).strip()
    industry = str(_first_value(profile.get("industry"), "")).strip()
    description = str(_first_value(profile.get("description"), "")).lower()

    tags = [value for value in [sector, industry] if value]
    combined = " ".join([sector, industry, description]).lower()

    if any(term in combined for term in ["semiconductor", "chip", "gpu"]):
        tags.extend(["semiconductors", "AI infrastructure"])
    if any(term in combined for term in ["cloud", "software", "data center", "datacenter"]):
        tags.append("cloud")
    if any(term in combined for term in ["consumer", "electric vehicle", "automotive"]):
        tags.append("consumer tech")

    seen = set()
    unique_tags = []
    for tag in tags:
        normalized = tag.strip()
        if normalized and normalized.lower() not in seen:
            seen.add(normalized.lower())
            unique_tags.append(normalized)
    return unique_tags


def _consensus(price_target: dict[str, Any], quote: dict[str, Any]) -> str:
    explicit = _first_value(
        price_target.get("consensus"),
        price_target.get("rating"),
        price_target.get("recommendation"),
    )
    if explicit:
        return str(explicit).lower()

    target = _first_number(
        price_target.get("targetConsensus"),
        price_target.get("priceTargetConsensus"),
        price_target.get("targetMean"),
        price_target.get("targetMedian"),
    )
    price = _first_number(quote.get("price"), quote.get("currentPrice"))

    if target is None or price in (None, 0):
        return "unknown"

    upside = (target - price) / price
    if upside >= 0.15:
        return "buy"
    if upside <= -0.10:
        return "sell"
    return "hold"


def _momentum_3m(price_change: dict[str, Any]) -> float | None:
    return _first_number(
        price_change.get("3M"),
        price_change.get("3m"),
        price_change.get("threeMonth"),
        price_change.get("threeMonthChange"),
        price_change.get("threeMonthChangePercent"),
        price_change.get("quarter"),
    )


def _short_record_summary(record: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    return {key: record[key] for key in keys if record.get(key) not in (None, "", [], {})}


def _analyst_context(
    price_targets: dict[str, Any],
    ratings: dict[str, Any],
    grade_summary: dict[str, Any],
    analyst_estimate: dict[str, Any],
) -> dict[str, Any]:
    return {
        "price_target": _short_record_summary(
            price_targets,
            [
                "targetConsensus",
                "priceTargetConsensus",
                "targetMedian",
                "targetHigh",
                "targetLow",
            ],
        ),
        "ratings": _short_record_summary(
            ratings,
            ["rating", "overallRating", "DCFRecommendation", "ROERecommendation"],
        ),
        "grade_summary": _short_record_summary(
            grade_summary,
            ["strongBuy", "buy", "hold", "sell", "strongSell", "consensus"],
        ),
        "next_estimate": _short_record_summary(
            analyst_estimate,
            [
                "date",
                "period",
                "revenueAvg",
                "epsAvg",
                "numAnalystsRevenue",
                "numAnalystsEps",
                "estimatedRevenueAvg",
                "estimatedEpsAvg",
                "numberAnalystEstimatedRevenue",
            ],
        ),
    }


def _earnings_context(earnings: dict[str, Any], income_growth: dict[str, Any]) -> dict[str, Any]:
    estimated_eps = _first_number(earnings.get("epsEstimated"), earnings.get("estimatedEps"))
    actual_eps = _first_number(earnings.get("eps"), earnings.get("actualEps"))
    surprise = None
    if actual_eps is not None and estimated_eps not in (None, 0):
        surprise = round(((actual_eps - estimated_eps) / abs(estimated_eps)) * 100, 1)

    return {
        "latest_earnings": _short_record_summary(
            earnings,
            ["date", "eps", "epsEstimated", "revenue", "revenueEstimated"],
        ),
        "eps_surprise_pct": surprise,
        "growth": _short_record_summary(
            income_growth,
            [
                "period",
                "calendarYear",
                "growthRevenue",
                "growthGrossProfit",
                "growthOperatingIncome",
                "growthNetIncome",
                "growthEPS",
            ],
        ),
    }


def _quality_context(financial_scores: dict[str, Any]) -> dict[str, Any]:
    return _short_record_summary(
        financial_scores,
        ["altmanZScore", "piotroskiScore", "workingCapital", "totalAssets", "totalLiabilities"],
    )


def _peer_context(peers: Any, sector_pe: dict[str, Any], industry_pe: dict[str, Any]) -> dict[str, Any]:
    peer_records = _as_records(peers)
    peer_symbols = []
    for record in peer_records[:8]:
        symbol = _first_value(record.get("symbol"), record.get("ticker"))
        if symbol:
            peer_symbols.append(str(symbol))

    return {
        "peers": peer_symbols,
        "sector_pe": _short_record_summary(sector_pe, ["sector", "pe", "peRatio", "date"]),
        "industry_pe": _short_record_summary(industry_pe, ["industry", "pe", "peRatio", "date"]),
    }


def _normalize_fundamentals(raw: dict[str, Any], ticker: str) -> dict[str, Any]:
    quote = _first_record(raw.get("quote"))
    profile = _first_record(raw.get("profile"))
    ratios = _first_record(raw.get("ratios_ttm"))
    metrics = _first_record(raw.get("metrics_ttm"))
    price_targets = _first_record(raw.get("price_targets"))
    price_change = _first_record(raw.get("price_change"))
    ratings = _first_record(raw.get("ratings"))
    grade_summary = _first_record(raw.get("grade_summary"))
    analyst_estimate = _first_record(raw.get("analyst_estimates"))
    earnings = _first_record(raw.get("earnings"))
    income_growth = _first_record(raw.get("income_growth"))
    financial_scores = _first_record(raw.get("financial_scores"))
    sector_pe = _first_record(raw.get("sector_pe"))
    industry_pe = _first_record(raw.get("industry_pe"))

    return {
        "ticker": ticker,
        "price": _first_number(quote.get("price"), profile.get("price"), quote.get("currentPrice")),
        "pe_trailing": _first_number(
            ratios.get("priceToEarningsRatioTTM"),
            ratios.get("priceEarningsRatioTTM"),
            ratios.get("peRatioTTM"),
            ratios.get("priceEarningsRatio"),
            quote.get("pe"),
        ),
        "pe_forward": _first_number(
            quote.get("forwardPE"),
            profile.get("forwardPE"),
            metrics.get("forwardPE"),
        ),
        "eps": _first_number(
            quote.get("eps"),
            quote.get("epsTTM"),
            metrics.get("netIncomePerShareTTM"),
            metrics.get("epsTTM"),
        ),
        "market_cap": _first_number(
            profile.get("mktCap"),
            profile.get("marketCap"),
            quote.get("marketCap"),
        ),
        "beta": _first_number(profile.get("beta"), quote.get("beta")) or 1.0,
        "consensus": _consensus(price_targets, quote),
        "momentum_3m": _momentum_3m(price_change) or 0.0,
        "sector_tags": _sector_tags(profile),
        "analyst_context": _analyst_context(
            price_targets,
            ratings,
            grade_summary,
            analyst_estimate,
        ),
        "earnings_context": _earnings_context(earnings, income_growth),
        "quality_context": _quality_context(financial_scores),
        "peer_context": _peer_context(raw.get("peers"), sector_pe, industry_pe),
    }


class _SmitheryConnectClient:
    def __init__(self, connection_id: str | None = None) -> None:
        self.namespace = os.getenv("SMITHERY_NAMESPACE")
        self.connection_id = connection_id or os.getenv("SMITHERY_MARKET_CONNECTION_ID")
        self.api_key = os.getenv("SMITHERY_API_KEY")
        if not self.namespace or not self.connection_id or not self.api_key:
            raise SmitheryServiceError("Smithery namespace, connection ID, or API key is missing.")

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }

    def _connection_url(self, suffix: str) -> str:
        return (
            f"https://api.smithery.ai/connect/"
            f"{self.namespace}/{self.connection_id}{suffix}"
        )

    async def list_tools(self, client: httpx.AsyncClient) -> list[dict[str, Any]]:
        response = await client.get(self._connection_url("/.tools"), headers=self._headers)
        response.raise_for_status()
        tools = response.json().get("tools", [])
        return tools if isinstance(tools, list) else []

    async def call_tool(self, client: httpx.AsyncClient, name: str, arguments: dict[str, Any]) -> Any:
        response = await client.post(self._connection_url(f"/.tools/{name}"), headers=self._headers, json=arguments)
        response.raise_for_status()
        return _parse_tool_result(response.json())


def _tool_arguments(key: str, ticker: str, profile: dict[str, Any]) -> dict[str, Any]:
    if key == "analyst_estimates":
        return {"symbol": ticker, "period": "annual", "limit": 2}
    if key in {"earnings", "financial_scores"}:
        return {"symbol": ticker, "limit": 2}
    if key == "income_growth":
        return {"symbol": ticker, "period": "FY", "limit": 2}
    if key == "sector_pe":
        args = {"date": date.today().isoformat()}
        sector = _first_value(profile.get("sector"))
        exchange = _first_value(profile.get("exchangeShortName"), profile.get("exchange"))
        if sector:
            args["sector"] = str(sector)
        if exchange:
            args["exchange"] = str(exchange)
        return args
    if key == "industry_pe":
        args = {"date": date.today().isoformat()}
        industry = _first_value(profile.get("industry"))
        exchange = _first_value(profile.get("exchangeShortName"), profile.get("exchange"))
        if industry:
            args["industry"] = str(industry)
        if exchange:
            args["exchange"] = str(exchange)
        return args
    return {"symbol": ticker}


async def _fetch_fundamentals(ticker: str) -> dict[str, Any]:
    mcp = _SmitheryConnectClient()

    async with httpx.AsyncClient(timeout=30) as client:
        tools = await mcp.list_tools(client)
        if not tools:
            raise SmitheryServiceError("Smithery connection has no active tools.")

        tool_names = {key: _tool_name(tools, desired) for key, desired in _REQUIRED_TOOLS.items()}
        missing = [desired for key, desired in _REQUIRED_TOOLS.items() if tool_names[key] is None]
        if missing:
            raise SmitheryServiceError(f"Smithery toolbox is missing tools: {', '.join(missing)}")

        raw = {}
        for key, tool in tool_names.items():
            if tool is None:
                continue
            raw[key] = await mcp.call_tool(client, tool, {"symbol": ticker})

        profile = _first_record(raw.get("profile"))
        optional_tool_names = {
            key: _tool_name(tools, desired) for key, desired in _OPTIONAL_CONTEXT_TOOLS.items()
        }
        for key, tool in optional_tool_names.items():
            if tool is None:
                continue
            try:
                raw[key] = await mcp.call_tool(client, tool, _tool_arguments(key, ticker, profile))
            except Exception:
                # Extra report context should never block the core valuation.
                raw[key] = None

    return _normalize_fundamentals(raw, ticker)


def _shibui_symbol_query(ticker: str) -> str:
    safe_ticker = "".join(char for char in ticker.upper() if char.isalnum() or char in ".-")
    return f"""
WITH target AS (
  SELECT symbol, code, name, gics_sector, gics_industry_group, gics_industry, description
  FROM shibui.general_info
  WHERE code = '{safe_ticker}' AND type = 'Common Stock'
  ORDER BY exchange = 'NASDAQ' DESC
  LIMIT 1
), latest_price AS (
  SELECT sq.symbol, sq.date, sq.close, sq.volume,
    ROW_NUMBER() OVER (PARTITION BY sq.symbol ORDER BY sq.date DESC) AS rn
  FROM shibui.stock_quotes sq
  INNER JOIN target t ON sq.symbol = t.symbol
  WHERE sq.date >= CURRENT_DATE - INTERVAL '7 days'
), period_return AS (
  SELECT sq.symbol,
    FIRST_VALUE(sq.close) OVER (PARTITION BY sq.symbol ORDER BY sq.date ASC) AS start_price,
    sq.close AS current_price,
    ROW_NUMBER() OVER (PARTITION BY sq.symbol ORDER BY sq.date DESC) AS rn
  FROM shibui.stock_quotes sq
  INNER JOIN target t ON sq.symbol = t.symbol
  WHERE sq.date >= CURRENT_DATE - INTERVAL '92 days'
), latest_val AS (
  SELECT v.symbol, v.pe_ratio, v.market_cap,
    ROW_NUMBER() OVER (PARTITION BY v.symbol ORDER BY v.date DESC) AS rn
  FROM shibui.valuation v
  INNER JOIN target t ON v.symbol = t.symbol
  WHERE v.date >= CURRENT_DATE - INTERVAL '7 days'
), latest_q AS (
  SELECT f.symbol, f.eps, f.eps_diluted, f.revenue_growth_yoy, f.eps_growth_yoy,
    f.return_on_equity, f.profit_margin,
    ROW_NUMBER() OVER (PARTITION BY f.symbol ORDER BY f.date DESC) AS rn
  FROM shibui.fundamentals_quarterly f
  INNER JOIN target t ON f.symbol = t.symbol
  WHERE f.date >= CURRENT_DATE - INTERVAL '18 months'
)
SELECT t.code AS ticker, t.symbol, t.name, t.gics_sector, t.gics_industry_group, t.gics_industry,
  t.description, p.date, p.close AS price, p.volume, v.pe_ratio, v.market_cap,
  ROUND((r.current_price - r.start_price) / NULLIF(r.start_price, 0) * 100, 2) AS momentum_3m,
  q.eps, q.eps_diluted, q.revenue_growth_yoy, q.eps_growth_yoy, q.return_on_equity, q.profit_margin
FROM target t
LEFT JOIN latest_price p ON t.symbol = p.symbol AND p.rn = 1
LEFT JOIN latest_val v ON t.symbol = v.symbol AND v.rn = 1
LEFT JOIN period_return r ON t.symbol = r.symbol AND r.rn = 1
LEFT JOIN latest_q q ON t.symbol = q.symbol AND q.rn = 1
LIMIT 1
""".strip()


def _normalize_shibui_row(row: dict[str, Any], ticker: str) -> dict[str, Any]:
    sector = _first_value(row.get("gics_sector"), "")
    industry_group = _first_value(row.get("gics_industry_group"), "")
    industry = _first_value(row.get("gics_industry"), "")
    description = _first_value(row.get("description"), "")
    profile = {
        "sector": sector,
        "industry": industry,
        "description": description,
    }
    eps = _first_number(row.get("eps_diluted"), row.get("eps"))
    momentum = _first_number(row.get("momentum_3m")) or 0.0

    return {
        "ticker": ticker,
        "price": _first_number(row.get("price")),
        "pe_trailing": _first_number(row.get("pe_ratio")),
        "pe_forward": None,
        "eps": eps,
        "market_cap": _first_number(row.get("market_cap")),
        "beta": 1.0,
        "consensus": "unknown",
        "momentum_3m": momentum,
        "sector_tags": _sector_tags(profile),
        "analyst_context": {},
        "earnings_context": {
            "growth": _short_record_summary(
                row,
                ["revenue_growth_yoy", "eps_growth_yoy", "return_on_equity", "profit_margin"],
            )
        },
        "quality_context": _short_record_summary(row, ["return_on_equity", "profit_margin"]),
        "peer_context": {},
        "smithery_context": {
            "source": "shibui/finance",
            "connection_id": os.getenv("SMITHERY_SHIBUI_CONNECTION_ID", _DEFAULT_SHIBUI_CONNECTION_ID),
            "symbol": row.get("symbol"),
            "latest_price_date": row.get("date"),
        },
    }


async def _fetch_shibui_fundamentals(ticker: str) -> dict[str, Any]:
    connection_id = os.getenv("SMITHERY_SHIBUI_CONNECTION_ID", _DEFAULT_SHIBUI_CONNECTION_ID)
    mcp = _SmitheryConnectClient(connection_id=connection_id)
    async with httpx.AsyncClient(timeout=30) as client:
        tools = await mcp.list_tools(client)
        if not _tool_name(tools, "stock_data_query"):
            raise SmitheryServiceError("Shibui finance connection is missing stock_data_query.")

        result = await mcp.call_tool(
            client,
            "stock_data_query",
            {
                "user_prompt": f"Get valuation context for {ticker}",
                "query": _shibui_symbol_query(ticker),
            },
        )
        records = _parse_text_records(result)
        if not records:
            raise SmitheryServiceError(f"Shibui returned no rows for {ticker}.")
        return _normalize_shibui_row(records[0], ticker)


def _merge_valuation(primary: dict[str, Any], secondary: dict[str, Any]) -> dict[str, Any]:
    merged = primary.copy()
    for key, value in secondary.items():
        if key in {"analyst_context", "earnings_context", "quality_context", "peer_context"}:
            current = merged.get(key) if isinstance(merged.get(key), dict) else {}
            if isinstance(value, dict):
                merged[key] = {**value, **current}
        elif key == "beta" and merged.get(key) == 1.0 and value not in (None, "", [], {}, "unknown"):
            merged[key] = value
        elif merged.get(key) in (None, "", [], {}, "unknown", 0.0):
            merged[key] = value

    if primary.get("smithery_context"):
        merged["smithery_context"] = primary["smithery_context"]
    return merged


async def _fetch_direct_fmp_fundamentals(ticker: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30) as client:
        raw: dict[str, Any] = {
            "quote": await _fmp_get(client, "quote", {"symbol": ticker}),
            "profile": await _fmp_get(client, "profile", {"symbol": ticker}),
            "ratios_ttm": await _fmp_get(client, "ratios-ttm", {"symbol": ticker}),
            "metrics_ttm": await _fmp_get(client, "key-metrics-ttm", {"symbol": ticker}),
            "price_targets": await _fmp_get(client, "price-target-consensus", {"symbol": ticker}),
            "price_change": await _fmp_get(client, "stock-price-change", {"symbol": ticker}),
        }

        optional_requests = {
            "ratings": ("ratings-snapshot", {"symbol": ticker, "limit": 2}),
            "grade_summary": ("grades-summary", {"symbol": ticker}),
            "analyst_estimates": ("analyst-estimates", {"symbol": ticker, "period": "annual", "limit": 2}),
            "earnings": ("earnings", {"symbol": ticker, "limit": 2}),
            "income_growth": ("income-statement-growth", {"symbol": ticker, "period": "FY", "limit": 2}),
            "financial_scores": ("financial-scores", {"symbol": ticker, "limit": 2}),
            "peers": ("stock-peers", {"symbol": ticker}),
        }

        profile = _first_record(raw.get("profile"))
        sector = _first_value(profile.get("sector"))
        industry = _first_value(profile.get("industry"))
        exchange = _first_value(profile.get("exchangeShortName"), profile.get("exchange"))
        snapshot_date = date.today().isoformat()
        if sector:
            optional_requests["sector_pe"] = (
                "sector-pe-snapshot",
                {"date": snapshot_date, "sector": sector, "exchange": exchange or "NASDAQ"},
            )
        if industry:
            optional_requests["industry_pe"] = (
                "industry-pe-snapshot",
                {"date": snapshot_date, "industry": industry, "exchange": exchange or "NASDAQ"},
            )

        for key, (path, params) in optional_requests.items():
            try:
                raw[key] = await _fmp_get(client, path, params)
            except Exception:
                raw[key] = None

    return _normalize_fundamentals(raw, ticker)


async def get_fundamentals(ticker: str) -> dict[str, Any]:
    normalized_ticker = ticker.upper().strip()
    now = time.time()
    cached = _cache.get(normalized_ticker)
    if cached and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]

    try:
        shibui_result = await _fetch_shibui_fundamentals(normalized_ticker)
    except (SmitheryServiceError, httpx.HTTPStatusError, httpx.RequestError):
        shibui_result = {}

    try:
        fmp_result = await _fetch_fundamentals(normalized_ticker)
    except (SmitheryServiceError, httpx.HTTPStatusError, httpx.RequestError):
        # FMP Smithery connectors currently expose tools but do not pass FMP_ACCESS_TOKEN.
        fmp_result = await _fetch_direct_fmp_fundamentals(normalized_ticker)

    result = _merge_valuation(shibui_result, fmp_result) if shibui_result else fmp_result

    _cache[normalized_ticker] = (now, result)
    return result
