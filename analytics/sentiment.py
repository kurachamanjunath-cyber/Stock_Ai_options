"""News sentiment analyzer for market sentiment scoring."""
import pandas as pd
import numpy as np
from textblob import TextBlob
from typing import Dict, List, Tuple
import requests
from datetime import datetime, timedelta

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
        # Try to fetch from NewsAPI if key provided
        sentiment_scores = []
        news_articles = []
        
        if api_key:
            try:
                url = "https://newsapi.org/v2/everything"
                params = {
                    "q": asset_name,
                    "sortBy": "publishedAt",
                    "language": "en",
                    "apiKey": api_key,
                    "pageSize": num_articles
                }
                response = requests.get(url, params=params, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    articles = data.get("articles", [])
                    
                    for article in articles[:num_articles]:
                        headline = article.get("title", "")
                        description = article.get("description", "")
                        text = f"{headline} {description}"
                        
                        # Simple sentiment analysis using TextBlob
                        blob = TextBlob(text)
                        polarity = blob.sentiment.polarity  # -1 to 1
                        
                        sentiment_scores.append(polarity)
                        news_articles.append({
                            "headline": headline,
                            "sentiment": polarity,
                            "source": article.get("source", {}).get("name", "Unknown"),
                            "published": article.get("publishedAt", "")
                        })
            except Exception as e:
                pass  # Fallback to local sentiment
        
        # If no articles or API failed, use sample sentiment
        if not sentiment_scores:
            sentiment_scores = [0.1]  # Neutral default
        
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
            "sentiment_scale_100": int((overall_sentiment + 1) * 50)  # Convert to 0-100
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
