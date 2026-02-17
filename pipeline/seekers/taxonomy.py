"""Domain-specific category taxonomies for Knowledge Atom tagging."""

TAXONOMIES = {
    "fb_ads": {
        "name": "Facebook Ads",
        "categories": [
            {"id": "campaign_management", "name": "Campaign Management",
             "subcategories": ["campaign_creation", "campaign_types", "objectives", "campaign_budget"]},
            {"id": "audience_targeting", "name": "Audience & Targeting",
             "subcategories": ["custom_audience", "lookalike", "interest_targeting", "retargeting"]},
            {"id": "ad_creative", "name": "Ad Creative",
             "subcategories": ["ad_formats", "copywriting", "images_video", "cta"]},
            {"id": "pixel_tracking", "name": "Pixel & Tracking",
             "subcategories": ["pixel_setup", "events", "conversions", "attribution"]},
            {"id": "optimization", "name": "Optimization & Scaling",
             "subcategories": ["ab_testing", "scaling", "budget_optimization", "performance"]},
            {"id": "policy_compliance", "name": "Policies & Compliance",
             "subcategories": ["ad_policies", "account_health", "review_process", "restricted"]},
        ]
    },
    "google_ads": {
        "name": "Google Ads",
        "categories": [
            {"id": "search_ads", "name": "Search Ads", "subcategories": ["keywords", "match_types", "quality_score"]},
            {"id": "display_ads", "name": "Display Network", "subcategories": ["placements", "audiences", "creative"]},
            {"id": "shopping", "name": "Shopping Ads", "subcategories": ["feed", "merchant_center", "campaigns"]},
            {"id": "bidding", "name": "Bidding Strategies", "subcategories": ["smart_bidding", "manual", "target_roas"]},
            {"id": "analytics", "name": "Analytics & Tracking", "subcategories": ["conversion", "ga4", "attribution"]},
            {"id": "optimization", "name": "Optimization", "subcategories": ["testing", "scripts", "automation"]},
        ]
    },
    "custom": {
        "name": "Custom",
        "categories": [
            {"id": "fundamentals", "name": "Fundamentals", "subcategories": ["concepts", "terminology", "principles"]},
            {"id": "procedures", "name": "Procedures", "subcategories": ["workflows", "steps", "best_practices"]},
            {"id": "tools", "name": "Tools & Technology", "subcategories": ["setup", "configuration", "integration"]},
            {"id": "strategy", "name": "Strategy", "subcategories": ["planning", "analysis", "decision_making"]},
            {"id": "advanced", "name": "Advanced Topics", "subcategories": ["optimization", "troubleshooting", "edge_cases"]},
            {"id": "compliance", "name": "Compliance & Rules", "subcategories": ["regulations", "guidelines", "safety"]},
        ]
    }
}


_DOMAIN_ALIASES = {
    "facebook-ads": "fb_ads",
    "facebook_ads": "fb_ads",
    "fb-ads": "fb_ads",
    "meta-ads": "fb_ads",
    "google-ads": "google_ads",
    "googleads": "google_ads",
}


def get_taxonomy(domain: str) -> dict:
    key = _DOMAIN_ALIASES.get(domain, domain)
    return TAXONOMIES.get(key, TAXONOMIES["custom"])


def get_all_categories(domain: str) -> list[str]:
    tax = get_taxonomy(domain)
    return [c["id"] for c in tax.get("categories", [])]


def get_all_subcategories(domain: str) -> list[str]:
    tax = get_taxonomy(domain)
    result = []
    for cat in tax.get("categories", []):
        result.extend(cat.get("subcategories", []))
    return result
