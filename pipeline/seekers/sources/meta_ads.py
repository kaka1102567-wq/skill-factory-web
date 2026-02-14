"""Meta/Facebook Ads documentation URL patterns and source definitions."""


def get_sources() -> list[dict]:
    """Return list of Meta Ads documentation sources for Seekers scraping."""
    return [
        {
            "url": "https://www.facebook.com/business/help",
            "type": "help_center",
            "priority": 1,
        },
        {
            "url": "https://developers.facebook.com/docs/marketing-api",
            "type": "api_docs",
            "priority": 1,
        },
        {
            "url": "https://www.facebook.com/policies/ads/",
            "type": "policy",
            "priority": 2,
        },
        {
            "url": "https://www.facebook.com/business/help/337584869654220",
            "type": "help_center",
            "priority": 2,
        },
        {
            "url": "https://developers.facebook.com/docs/marketing-api/audiences",
            "type": "api_docs",
            "priority": 2,
        },
        {
            "url": "https://developers.facebook.com/docs/meta-pixel",
            "type": "api_docs",
            "priority": 1,
        },
        {
            "url": "https://www.facebook.com/business/help/742478679120153",
            "type": "help_center",
            "priority": 3,
        },
        {
            "url": "https://developers.facebook.com/docs/marketing-api/conversions-api",
            "type": "api_docs",
            "priority": 2,
        },
    ]
