import os

KEYWORDS = [
    "rumor", "rumour", "leak", "leaked", "reportedly", "insider",
    "unconfirmed", "sources say", "tipster", "speculation"
]

DOMAINS = {
    "ai": [
        'https://news.google.com/rss/search?q=("AI"+OR+"artificial+intelligence")+("rumor"+OR+"leak"+OR+"reportedly"+OR+"insider")&hl=en-US&gl=US&ceid=US:en',
        'https://hnrss.org/newest?points=10'
    ],
    "finance": [
        'https://news.google.com/rss/search?q=("finance"+OR+"markets"+OR+"stocks")+("rumor"+OR+"reportedly"+OR+"leak")&hl=en-US&gl=US&ceid=US:en'
    ],
    "science": [
        'https://news.google.com/rss/search?q=("science"+OR+"research")+("rumor"+OR+"leak"+OR+"reportedly")&hl=en-US&gl=US&ceid=US:en'
    ]
}

MODEL = os.getenv("MODEL", "gpt-4o-mini")
MAX_ITEMS = int(os.getenv("MAX_ITEMS", "60"))

# --- Domain topic guards to keep picks on-theme ---
DOMAIN_KEYWORDS = {
    "ai": [
        "ai", "artificial intelligence", "machine learning", "ml",
        "llm", "model", "chatbot", "neural", "openai", "anthropic",
        "google", "meta", "deepmind", "microsoft"
    ],
    "finance": [
        "market", "stock", "equity", "bond", "fed", "yield", "rate",
        "ipo", "earnings", "investor", "stake", "mufg", "sec", "nasdaq"
    ],
    "science": [
        "research", "study", "scientists", "physics", "chemistry", "biology",
        "astronomy", "space", "materials", "superconductor", "genome",
        "neuroscience", "peer-reviewed", "preprint", "arxiv", "nature", "science", "grant", "funding", "laboratory", "peer review"
    ],
}

DOMAIN_EXCLUDES = {
    "science": ["stock", "stake", "earnings", "ipo", "investor", "nasdaq", "finance", "stocktwits", "m&a", "stake sale", "rumor mill", "artifical intelligence", "meta", "openai", "google", "microsoft", "verge"],
    "ai": [],
    "finance": [],
}
SUPPRESS_DUP_SUMMARY = True
BAD_DOMAINS = set()
