#!/usr/bin/env python3
"""
Link Resolver — Route market links through /go/ redirects.

Encapsulates the logic for selecting the best eligible partner based on:
  - Partner enabled status
  - User's country
  - Payout tier (affects CTA label)
  - Platform priority ranking
"""

import json
import os

def load_partners_config():
    """Load partners.json configuration."""
    config_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "config",
        "partners.json"
    )
    try:
        with open(config_path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"partners": []}


def is_country_allowed(partner, user_country):
    """Check if user's country is allowed for this partner."""
    if not user_country:
        return True  # No country data = allow

    blocked = partner.get("blocked_countries", [])
    if blocked and user_country.upper() in blocked:
        return False

    allowed = partner.get("allowed_countries", "all")
    if allowed == "all":
        return True

    if isinstance(allowed, list):
        return user_country.upper() in allowed

    return True


def resolve_market_destination(market_id, user_country=None, market_category=None, requested_platform=None):
    """
    Resolve a market to the best eligible partner and construct destination URL.

    Args:
        market_id: The market ticker/ID (e.g., "KXGROK-GROK5-26JUL01")
        user_country: Two-letter ISO country code (e.g., "US", "GB")
        market_category: The market's category (for future filtering)
        requested_platform: Force a specific platform slug (e.g., "kalshi")

    Returns:
        {
            "eligible": bool,
            "platform": str or None,
            "destination_url": str or None,
            "cta_label": str,
            "disclaimer_required": bool,
            "reason": str
        }
    """
    config = load_partners_config()
    partners_list = config.get("partners", [])

    # If requesting a specific platform, try it first
    if requested_platform:
        for partner in partners_list:
            if partner.get("slug") == requested_platform:
                if not partner.get("enabled"):
                    return {
                        "eligible": False,
                        "platform": requested_platform,
                        "destination_url": None,
                        "cta_label": "unavailable",
                        "disclaimer_required": False,
                        "reason": f"{requested_platform} is disabled"
                    }
                if not is_country_allowed(partner, user_country):
                    return {
                        "eligible": False,
                        "platform": requested_platform,
                        "destination_url": None,
                        "cta_label": "unavailable",
                        "disclaimer_required": False,
                        "reason": f"{requested_platform} is not available in your region"
                    }
                # Build URL for requested platform
                url = _build_partner_url(partner, market_id)
                return {
                    "eligible": bool(url),
                    "platform": requested_platform,
                    "destination_url": url,
                    "cta_label": _cta_label_for_partner(partner),
                    "disclaimer_required": partner.get("requires_disclaimer", False),
                    "reason": "requested platform" if url else "could not construct URL"
                }

        return {
            "eligible": False,
            "platform": requested_platform,
            "destination_url": None,
            "cta_label": "unavailable",
            "disclaimer_required": False,
            "reason": f"platform {requested_platform} not found"
        }

    # Otherwise, find best eligible partner by priority
    eligible_partners = []
    for partner in partners_list:
        if not partner.get("enabled"):
            continue
        if not is_country_allowed(partner, user_country):
            continue
        eligible_partners.append(partner)

    if not eligible_partners:
        return {
            "eligible": False,
            "platform": None,
            "destination_url": None,
            "cta_label": "unavailable",
            "disclaimer_required": False,
            "reason": "no eligible partners for your region"
        }

    # Sort by priority rank (lower = higher priority)
    eligible_partners.sort(key=lambda p: p.get("priority_rank", 999))
    best_partner = eligible_partners[0]

    url = _build_partner_url(best_partner, market_id)
    if not url:
        return {
            "eligible": False,
            "platform": best_partner.get("slug"),
            "destination_url": None,
            "cta_label": "unavailable",
            "disclaimer_required": False,
            "reason": f"could not construct URL for {best_partner.get('slug')}"
        }

    return {
        "eligible": True,
        "platform": best_partner.get("slug"),
        "destination_url": url,
        "cta_label": _cta_label_for_partner(best_partner),
        "disclaimer_required": best_partner.get("requires_disclaimer", False),
        "reason": "resolved to best eligible partner"
    }


def _build_partner_url(partner, market_id):
    """Build the final destination URL for a partner."""
    affiliate_id = partner.get("affiliate_id", "")
    tracking_param = partner.get("tracking_param_name", "ref")

    # Kalshi: uses ticker directly in URL
    if partner.get("slug") == "kalshi":
        base = partner.get("base_url", "https://kalshi.com/markets")
        if affiliate_id:
            return f"{base}/{market_id}?{tracking_param}={affiliate_id}"
        else:
            return f"{base}/{market_id}"

    # Other platforms: construct via market URL format (stub for now)
    # In future, could look up market_id in sources array to find platform-specific ID
    base = partner.get("base_url", "")
    if affiliate_id:
        return f"{base}/{market_id}?{tracking_param}={affiliate_id}"
    else:
        return f"{base}/{market_id}"


def _cta_label_for_partner(partner):
    """Determine the CTA label for a partner (safe, neutral language)."""
    slug = partner.get("slug", "")

    # Use generic, safe labels
    safe_labels = {
        "kalshi": "view market",
        "polymarket": "see odds",
        "coinbase": "open market",
        "sportsbook": "view contract"
    }

    return safe_labels.get(slug, "view market")
