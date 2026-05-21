"""News sentiment analyzer for market sentiment scoring."""
import os
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

import pandas as pd
import numpy as np
from textblob import TextBlob
from typing import Dict, List, Tuple
import requests
from datetime import datetime, timedelta


INDEX_NEWS_QUERIES = {
    "NIFTY": (
        "NIFTY 50 OR NSE Nifty OR Indian stock market OR India equities "
        "OR RBI OR inflation India OR FIIs India"
    ),
    "BANKNIFTY": (
        "Bank Nifty OR Nifty Bank OR Indian banking stocks OR RBI policy "
        "OR HDFC Bank OR ICICI Bank OR SBI"
    ),
    "SENSEX": (
        "Sensex OR BSE Sensex OR Indian stock market OR India equities "
        "OR RBI OR inflation India OR FIIs India"
    ),
}


def _normalize_asset_name(asset_name: str) -> str:
    return str(asset_name or "").replace("MCX", "").upper().strip()


def _build_news_query(asset_name: str) -> str:
    normalized = _normalize_asset_name(asset_name)
    return INDEX_NEWS_QUERIES.get(normalized, normalized)


def _parse_date(value: str) -> str:
    if not value:
        return ""
    try:
        return parsedate_to_datetime(value).isoformat()
    except Exception:
        return value


def _article_impact(asset_name: str, sentiment: float) -> str:
    normalized = _normalize_asset_name(asset_name)
    if normalized in INDEX_NEWS_QUERIES:
        if sentiment > 0.2:
            return "Bullish impact: may support CALL options"
        if sentiment < -0.2:
            return "Bearish impact: may support PUT options"
        return "Mixed/neutral impact: wait for price confirmation"

    if sentiment > 0.2:
        return "Bullish impact"
    if sentiment < -0.2:
        return "Bearish impact"
    return "Mixed/neutral impact"


def _sentiment_from_article(article: Dict, asset_name: str) -> Tuple[float, Dict]:
    headline = article.get("headline", "")
    description = article.get("description", "")
    text = f"{headline} {description}"
    polarity = float(TextBlob(text).sentiment.polarity)
    article["sentiment"] = polarity
    article["impact"] = _article_impact(asset_name, polarity)
    return polarity, article


def _fetch_newsapi_articles(query: str, num_articles: int, api_key: str) -> List[Dict]:
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "sortBy": "publishedAt",
        "language": "en",
        "apiKey": api_key,
        "pageSize": num_articles,
    }
    response = requests.get(url, params=params, timeout=5)
    response.raise_for_status()
    data = response.json()

    news_articles = []
    for article in data.get("articles", [])[:num_articles]:
        news_articles.append({
            "headline": article.get("title", ""),
            "description": article.get("description", ""),
            "source": article.get("source", {}).get("name", "Unknown"),
            "published": article.get("publishedAt", ""),
            "url": article.get("url", ""),
        })
    return news_articles


def _fetch_google_news_rss_articles(query: str, num_articles: int) -> List[Dict]:
    encoded_query = quote_plus(f"{query} when:1d")
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en"
    response = requests.get(
        url,
        timeout=5,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()

    root = ET.fromstring(response.content)
    news_articles = []
    for item in root.findall(".//item")[:num_articles]:
        source_node = item.find("source")
        news_articles.append({
            "headline": item.findtext("title", default=""),
            "description": item.findtext("description", default=""),
            "source": source_node.text if source_node is not None and source_node.text else "Google News",
            "published": _parse_date(item.findtext("pubDate", default="")),
            "url": item.findtext("link", default=""),
        })
    return news_articles

def analyze_news_sentiment(
    asset_name: str,
    num_articles: int = 10,
    api_key: str = None
) -> Dict:
    """
    Analyze news sentiment for a given asset.
    
    Args:
        asset_name: Name of asset to search (e.g., 'GOLD', 'NIFTY')
        num_articles: Number of articles to analyze
        api_key: NewsAPI key (optional)
    
    Returns:
        Dict with overall sentiment, trending news, confidence
    """
    
    try:
        # Try configured NewsAPI first, then public Google News RSS.
        sentiment_scores = []
        news_articles = []
        query = _build_news_query(asset_name)
        api_key = api_key or os.getenv("NEWSAPI_KEY") or os.getenv("NEWS_API_KEY")
        
        if api_key:
            try:
                news_articles = _fetch_newsapi_articles(query, num_articles, api_key)
            except Exception:
                news_articles = []

        if not news_articles:
            try:
                news_articles = _fetch_google_news_rss_articles(query, num_articles)
            except Exception:
                news_articles = []

        for article in news_articles[:num_articles]:
            polarity, scored_article = _sentiment_from_article(article, asset_name)
            sentiment_scores.append(polarity)
            article.update(scored_article)
        
        # If no articles or API failed, use sample sentiment
        if not sentiment_scores:
            sentiment_scores = [0.0]  # Neutral default when no news source is reachable
        
        # Calculate aggregate sentiment
        overall_sentiment = float(np.mean(sentiment_scores))
        sentiment_std = float(np.std(sentiment_scores)) if len(sentiment_scores) > 1 else 0.0
        confidence = min(100, (1 - (sentiment_std / 2)) * 100)  # Confidence based on consistency
        
        # Classify sentiment
        if overall_sentiment > 0.2:
            sentiment_label = "POSITIVE"
        elif overall_sentiment < -0.2:
            sentiment_label = "NEGATIVE"
        else:
            sentiment_label = "NEUTRAL"
        
        # Sort articles by sentiment strength
        top_articles = sorted(
            news_articles,
            key=lambda x: abs(x["sentiment"]),
            reverse=True
        )[:5] if news_articles else []
        
        return {
            "overall_sentiment": overall_sentiment,  # -1 to +1
            "sentiment_label": sentiment_label,
            "confidence": float(confidence),
            "num_articles_analyzed": len(news_articles),
            "sentiment_std": sentiment_std,
            "top_articles": top_articles,
            "sentiment_scale_100": int((overall_sentiment + 1) * 50),  # Convert to 0-100
            "query": query,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
    
    except Exception as e:
        return {
            "overall_sentiment": 0.0,
            "sentiment_label": "NEUTRAL",
            "confidence": 0.0,
            "num_articles_analyzed": 0,
            "sentiment_std": 0.0,
            "top_articles": [],
            "sentiment_scale_100": 50,
            "error": str(e)
        }


def sentiment_to_signal(overall_sentiment: float, threshold: float = 0.3) -> str:
    """
    Convert sentiment score to trading signal.
    
    Args:
        overall_sentiment: Sentiment score from -1 to +1
        threshold: Threshold for strong sentiment
    
    Returns:
        Signal label: 'BULLISH', 'BEARISH', 'NEUTRAL'
    """
    if overall_sentiment > threshold:
        return "BULLISH"
    elif overall_sentiment < -threshold:
        return "BEARISH"
    else:
        return "NEUTRAL"


def calculate_sentiment_weight(overall_sentiment: float) -> float:
    """Calculate weight for sentiment in multi-factor score (0-1)."""
    return (overall_sentiment + 1) / 2  # Normalize -1 to +1 → 0 to 1
