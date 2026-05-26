"""Tool implementations exposed to the Sales Engineer agent."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from rich.console import Console

from core.catalog import get_product_by_id, search_products
from core.config import TAVILY_API_KEY
from core.models import ToolResult

console = Console()


def _result(success: bool, data: Any, error: Optional[str] = None) -> ToolResult:
    """Build a ToolResult through Pydantic v2 validation."""
    return ToolResult.model_validate({"success": success, "data": data, "error": error})


def _normalize_location(location: str) -> str:
    location_lower = location.lower()
    if "kuala" in location_lower or location_lower == "kl":
        return "KL"
    if "johor" in location_lower:
        return "Johor"
    if "sabah" in location_lower or "kinabalu" in location_lower:
        return "Sabah"
    if "sarawak" in location_lower or "kuching" in location_lower:
        return "Sarawak"
    if "penang" in location_lower:
        return "Penang"
    if "nationwide" in location_lower:
        return "nationwide"
    return location


def _summarize(result: ToolResult) -> str:
    if not result.success:
        return result.error or "Tool failed"
    text = json.dumps(result.data, ensure_ascii=False)
    return text[:500]


def _extract_price_myr(text: str) -> Optional[float]:
    match = re.search(r"(?:RM|MYR)\s*([0-9][0-9,]*(?:\.\d{1,2})?)", text, re.IGNORECASE)
    if not match:
        return None
    return float(match.group(1).replace(",", ""))


def search_catalog(
    category: Optional[str] = None,
    max_price_myr: Optional[float] = None,
    min_price_myr: Optional[float] = None,
    specs_filter: Optional[dict[str, Any]] = None,
    in_stock_only: bool = True,
) -> ToolResult:
    """Search the local SQLite product catalog."""
    products = search_products(
        category=category,
        max_price=max_price_myr,
        min_price=min_price_myr,
        specs_filter=specs_filter,
        in_stock_only=in_stock_only,
    )
    return _result(True, [p.model_dump() for p in products[:10]])


def get_product_details(product_id: str) -> ToolResult:
    """Return one product's full catalog details."""
    product = get_product_by_id(product_id)
    if not product:
        return _result(False, None, f"Product not found: {product_id}")
    return _result(True, product.model_dump())


def check_compatibility(product_a_id: str, product_b_id: str) -> ToolResult:
    """Check pairwise compatibility by explicit relationship or same category."""
    a = get_product_by_id(product_a_id)
    b = get_product_by_id(product_b_id)
    if not a or not b:
        return _result(False, None, "One or both products were not found")
    explicit = a.id in b.compatible_with or b.id in a.compatible_with
    same_category = a.category == b.category
    compatible = explicit or same_category
    reason = (
        "Explicitly listed as compatible"
        if explicit
        else "Same category products are considered compatible"
        if same_category
        else "No explicit compatibility link and categories differ"
    )
    return _result(True, {"compatible": compatible, "reason": reason, "product_a": a.name, "product_b": b.name})


def check_delivery(product_ids: list[str], delivery_location: str) -> ToolResult:
    """Check regional delivery feasibility for selected products."""
    location = _normalize_location(delivery_location)
    unavailable: list[str] = []
    details: list[dict] = []
    for product_id in product_ids:
        product = get_product_by_id(product_id)
        if not product:
            unavailable.append(product_id)
            details.append({"product_id": product_id, "available": False, "reason": "Product not found"})
            continue
        deliverable = location in product.available_regions or "nationwide" in product.available_regions
        if not deliverable:
            unavailable.append(product.id)
        details.append(
            {
                "product_id": product.id,
                "product_name": product.name,
                "available": deliverable,
                "regions": product.available_regions,
            }
        )
    return _result(True, {"feasible": not unavailable, "unavailable_products": unavailable, "delivery_details": details})


def calculate_budget_fit(product_ids: list[str], quantities: dict[str, int], budget_myr: float) -> ToolResult:
    """Calculate quote totals against the supplied budget."""
    total = 0.0
    line_items: list[dict] = []
    for product_id in product_ids:
        product = get_product_by_id(product_id)
        if not product:
            return _result(False, None, f"Product not found: {product_id}")
        quantity = int(quantities.get(product_id, 1))
        subtotal = product.price_myr * quantity
        total += subtotal
        line_items.append(
            {
                "product_id": product.id,
                "product_name": product.name,
                "quantity": quantity,
                "unit_price_myr": product.price_myr,
                "subtotal_myr": subtotal,
            }
        )
    remaining = budget_myr - total
    utilization = (total / budget_myr * 100) if budget_myr else 0.0
    return _result(
        True,
        {
            "total_myr": total,
            "within_budget": total <= budget_myr,
            "remaining_myr": remaining,
            "utilization_pct": utilization,
            "line_items": line_items,
        },
    )


def find_alternatives(product_id: str, max_price_myr: float, same_category: bool = True) -> ToolResult:
    """Find cheaper alternative products."""
    product = get_product_by_id(product_id)
    if not product:
        return _result(False, None, f"Product not found: {product_id}")
    category = product.category if same_category else None
    alternatives = [
        p
        for p in search_products(category=category, max_price=max_price_myr)
        if p.id != product_id
    ][:5]
    return _result(True, [p.model_dump() for p in alternatives])


def search_web_products(
    query: str,
    max_price_myr: Optional[float] = None,
    location: str = "Malaysia",
) -> ToolResult:
    """Search real products using Tavily, falling back safely if unavailable."""
    if not TAVILY_API_KEY:
        console.log("[yellow]TAVILY_API_KEY missing; using SQLite catalog fallback only.[/yellow]")
        return _result(True, [], "Tavily key missing; SQLite fallback used")
    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=TAVILY_API_KEY)
        search_query = f"{query} buy {location} price"
        response = client.search(search_query, max_results=5, include_answer=False)
        results = []
        for item in response.get("results", [])[:5]:
            text = f"{item.get('title', '')} {item.get('content', '')}"
            price = _extract_price_myr(text)
            if max_price_myr is not None and price is not None and price > max_price_myr:
                continue
            url = item.get("url", "")
            host = url.lower()
            source = "Shopee" if "shopee" in host else "Lazada" if "lazada" in host else "Amazon" if "amazon" in host else "web"
            results.append(
                {
                    "name": item.get("title", query),
                    "url": url,
                    "price_myr": price,
                    "source": source,
                    "snippet": item.get("content", ""),
                }
            )
        return _result(True, results)
    except Exception as exc:  # pragma: no cover - external service
        console.log(f"[yellow]Tavily search failed; using SQLite fallback only: {exc}[/yellow]")
        return _result(True, [], f"Tavily unavailable; SQLite fallback used: {exc}")


def get_fx_rate(from_currency: str, to_currency: str = "MYR") -> ToolResult:
    """Fetch live FX rate from exchangerate.host API.

    Falls back to hardcoded rates if the API is unavailable.
    """
    FALLBACK_RATES = {
        "USD": 4.48,
        "SGD": 3.32,
        "EUR": 4.85,
        "GBP": 5.67,
        "AUD": 2.89,
        "JPY": 0.030,
        "CNY": 0.62,
    }
    from_upper = from_currency.upper()
    to_upper = to_currency.upper()
    if from_upper == to_upper:
        return _result(True, {"rate": 1.0, "from": from_upper, "to": to_upper, "source": "identity"})
    try:
        import json as _json
        import urllib.request

        url = f"https://api.exchangerate.host/latest?base={from_upper}&symbols={to_upper}"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = _json.loads(resp.read())
        rate = data["rates"].get(to_upper)
        if rate:
            return _result(
                True,
                {
                    "rate": rate,
                    "from": from_upper,
                    "to": to_upper,
                    "source": "live_api",
                    "date": data.get("date", "unknown"),
                },
            )
    except Exception as exc:
        console.log(f"[yellow]FX API unavailable; using fallback rate: {exc}[/yellow]")
    fallback_rate = FALLBACK_RATES.get(from_upper)
    if fallback_rate:
        return _result(
            True,
            {
                "rate": fallback_rate,
                "from": from_upper,
                "to": to_upper,
                "source": "fallback_hardcoded",
            },
        )
    return _result(
        False,
        None,
        f"No FX rate available for {from_upper} to {to_upper}. "
        f"Supported fallback currencies: {list(FALLBACK_RATES.keys())}",
    )


TOOL_DEFINITIONS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "search_catalog",
            "description": "Search local SQLite product catalog.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "max_price_myr": {"type": "number"},
                    "min_price_myr": {"type": "number"},
                    "specs_filter": {"type": "object"},
                    "in_stock_only": {"type": "boolean"},
                },
            },
        },
    },
    {"type": "function", "function": {"name": "get_product_details", "description": "Get full product details.", "parameters": {"type": "object", "properties": {"product_id": {"type": "string"}}, "required": ["product_id"]}}},
    {"type": "function", "function": {"name": "check_compatibility", "description": "Check if two products are compatible.", "parameters": {"type": "object", "properties": {"product_a_id": {"type": "string"}, "product_b_id": {"type": "string"}}, "required": ["product_a_id", "product_b_id"]}}},
    {"type": "function", "function": {"name": "check_delivery", "description": "Check product delivery feasibility by location.", "parameters": {"type": "object", "properties": {"product_ids": {"type": "array", "items": {"type": "string"}}, "delivery_location": {"type": "string"}}, "required": ["product_ids", "delivery_location"]}}},
    {"type": "function", "function": {"name": "calculate_budget_fit", "description": "Calculate budget fit for selected products.", "parameters": {"type": "object", "properties": {"product_ids": {"type": "array", "items": {"type": "string"}}, "quantities": {"type": "object", "additionalProperties": {"type": "integer"}}, "budget_myr": {"type": "number"}}, "required": ["product_ids", "quantities", "budget_myr"]}}},
    {"type": "function", "function": {"name": "find_alternatives", "description": "Find alternative products under a max price.", "parameters": {"type": "object", "properties": {"product_id": {"type": "string"}, "max_price_myr": {"type": "number"}, "same_category": {"type": "boolean"}}, "required": ["product_id", "max_price_myr"]}}},
    {"type": "function", "function": {"name": "search_web_products", "description": "Search real web product listings with Tavily.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "max_price_myr": {"type": "number"}, "location": {"type": "string"}}, "required": ["query"]}}},
    {
        "type": "function",
        "function": {
            "name": "get_fx_rate",
            "description": (
                "Fetch a live currency exchange rate to MYR. "
                "Use this when the client's budget is stated in a foreign currency "
                "(USD, SGD, EUR, GBP, AUD, JPY, CNY) so you can convert it to MYR "
                "before budget calculations. Falls back to reliable hardcoded rates "
                "if the live API is unavailable."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "from_currency": {
                        "type": "string",
                        "description": "The source currency code e.g. USD, SGD, EUR",
                    },
                    "to_currency": {
                        "type": "string",
                        "description": "Target currency, always MYR",
                        "default": "MYR",
                    },
                },
                "required": ["from_currency"],
            },
        },
    },
]


def dispatch_tool(tool_name: str, arguments: dict) -> str:
    """Dispatch a named tool and return JSON serialized ToolResult."""
    try:
        tools = {
            "search_catalog": search_catalog,
            "get_product_details": get_product_details,
            "check_compatibility": check_compatibility,
            "check_delivery": check_delivery,
            "calculate_budget_fit": calculate_budget_fit,
            "find_alternatives": find_alternatives,
            "search_web_products": search_web_products,
            "get_fx_rate": get_fx_rate,
        }
        if tool_name not in tools:
            result = _result(False, None, f"Unknown tool: {tool_name}")
        else:
            result = tools[tool_name](**arguments)
    except Exception as exc:
        result = _result(False, None, str(exc))
    return json.dumps(result.model_dump(), ensure_ascii=False)


def summarize_tool_json(tool_json: str) -> str:
    """Create a compact display summary for a serialized tool result."""
    try:
        return _summarize(ToolResult.model_validate(json.loads(tool_json)))
    except Exception:
        return tool_json[:500]
