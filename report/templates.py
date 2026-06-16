"""
templates.py -- Report template definitions.

Each template reframes the same valuation for a different audience. The engine and
comp data are identical; only the headline, intro narrative, and emphasis change.
"""

TEMPLATES = {
    "seller": {
        "label": "Seller CMA",
        "title": "Comparative Market Analysis",
        "subtitle": "Prepared for the sale of your home",
        "intro": ("This analysis estimates the current market value of your home "
                  "based on comparable recent sales and active listings nearby. "
                  "Use it to set a competitive list price with confidence."),
        "cta": "Let's talk about a pricing and marketing strategy.",
    },
    "buyer": {
        "label": "Buyer CMA",
        "title": "Offer Strategy Analysis",
        "subtitle": "Prepared to support your offer",
        "intro": ("This analysis estimates a fair market value for the property "
                  "you're considering, based on comparable recent sales. Use it to "
                  "frame a competitive, well-supported offer."),
        "cta": "Let's decide on an offer price and terms.",
    },
    "expired": {
        "label": "Expired Listing",
        "title": "Why It Didn't Sell -- A Fresh Market Analysis",
        "subtitle": "A new look at your home's value",
        "intro": ("Your previous listing expired without a sale. This updated "
                  "analysis re-prices your home to today's comparable sales so we "
                  "can re-launch it at a number the market will respond to."),
        "cta": "Let's re-list at the right price and get it sold.",
    },
    "fsbo": {
        "label": "FSBO",
        "title": "Your Home's Market Value",
        "subtitle": "An independent market analysis",
        "intro": ("Selling on your own? Here is an objective, data-backed estimate "
                  "of your home's value from comparable sales -- so you can price "
                  "it accurately and negotiate from a position of knowledge."),
        "cta": "Happy to help, whether you list with me or not.",
    },
}


def get_template(key: str) -> dict:
    return TEMPLATES.get(key, TEMPLATES["seller"])
