"""
M&A Target Scanner - Monitors multiple signals for potential acquisition targets
Tracks SEC filings, undervalued stocks, unusual activity, and M&A news
"""

import requests
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any
import yfinance as yf
from bs4 import BeautifulSoup
import pandas as pd
from collections import defaultdict

class AcquisitionScanner:
    def __init__(self, discord_webhook_url: str):
        self.discord_webhook = discord_webhook_url
        self.headers = {
            'User-Agent': 'Investment Research Bot mitch@example.com'
        }
        self.alert_threshold = 5  # Minimum score to trigger alert
        self.alert_threshold = 5
   print(f"🎯 Alert threshold set to: {self.alert_threshold}")  # Debug line   
    def send_discord_alert(self, title: str, description: str, color: int = 3447003, 
                          fields: List[Dict[str, Any]] = None):
        """Send formatted alert to Discord"""
        embed = {
            "title": title,
            "description": description,
            "color": color,
            "timestamp": datetime.utcnow().isoformat(),
            "fields": fields or []
        }
        
        payload = {"embeds": [embed]}
        
        try:
            response = requests.post(self.discord_webhook, json=payload)
            if response.status_code == 204:
                print(f"✓ Alert sent: {title}")
            else:
                print(f"✗ Discord alert failed: {response.status_code}")
        except Exception as e:
            print(f"✗ Error sending Discord alert: {e}")
    
    def check_sec_filings(self) -> List[Dict[str, Any]]:
        """Monitor SEC EDGAR for relevant M&A filings"""
        print("\n🔍 Checking SEC filings...")
        signals = []
        
        # Key filing types that signal M&A activity
        filing_types = ['SC 13D', 'SC 13G', '8-K', 'SC TO-T', 'SC TO-I', 'DEFM14A']
        
        try:
            # SEC EDGAR RSS feed for recent filings
            url = "https://www.sec.gov/cgi-bin/browse-edgar"
            params = {
                'action': 'getcurrent',
                'output': 'atom',
                'count': 100
            }
            
            response = requests.get(url, params=params, headers=self.headers)
            
            if response.status_code == 200:
                # Parse RSS feed
                soup = BeautifulSoup(response.content, 'xml')
                entries = soup.find_all('entry')[:50]  # Check recent 50 filings
                
                for entry in entries:
                    title = entry.find('title').text if entry.find('title') else ''
                    
                    # Check if it's a relevant filing type
                    for filing_type in filing_types:
                        if filing_type in title:
                            ticker = self._extract_ticker(title)
                            company = self._extract_company_name(title)
                            
                            signal = {
                                'ticker': ticker,
                                'company': company,
                                'signal_type': 'SEC_FILING',
                                'filing_type': filing_type,
                                'description': title[:200],
                                'score': self._score_filing(filing_type),
                                'timestamp': datetime.now().isoformat()
                            }
                            signals.append(signal)
                            print(f"  ✓ Found: {filing_type} - {ticker or company}")
                            break
            
            print(f"  Found {len(signals)} relevant SEC filings")
            
        except Exception as e:
            print(f"  ✗ SEC filing check error: {e}")
        
        return signals
    
    def _score_filing(self, filing_type: str) -> int:
        """Score filing types by M&A relevance"""
        scores = {
            'SC 13D': 40,      # Activist investor with intent to influence
            'SC 13G': 25,      # Passive 5%+ ownership
            '8-K': 30,         # Material events (could be M&A)
            'SC TO-T': 80,     # Tender offer - highest signal
            'SC TO-I': 80,     # Tender offer issuer
            'DEFM14A': 90      # Definitive merger proxy - deal announced
        }
        return scores.get(filing_type, 20)
    
    def _extract_ticker(self, text: str) -> str:
        """Extract ticker symbol from SEC filing title"""
        import re
        # Look for patterns like (TICKER) or [TICKER]
        match = re.search(r'\(([A-Z]{1,5})\)', text)
        if match:
            return match.group(1)
        return None
    
    def _extract_company_name(self, text: str) -> str:
        """Extract company name from SEC filing title"""
        # Usually format is "Company Name (TICKER) - Filing Type"
        parts = text.split(' - ')
        if parts:
            company = parts[0].split('(')[0].strip()
            return company[:50]  # Truncate long names
        return "Unknown"
    
    def scan_undervalued_targets(self) -> List[Dict[str, Any]]:
        """Screen for undervalued small-caps that could be acquisition targets"""
        print("\n🔍 Scanning for undervalued targets...")
        signals = []
        
        try:
            # Use yfinance to get screener data
            # Focus on small/mid caps with attractive valuations
            
            # Sample tickers - in production, use a broader screener
            # These are just examples of small-cap hotel/REIT stocks similar to SOHO
            sample_tickers = [
                'RHP', 'PEB', 'SHO', 'XHR', 'INN', 'DRH', 'AHT', 'CLDT',
                'ALEX', 'SABR', 'APLE', 'STAY', 'BHR', 'CHSP'
            ]
            
            for ticker in sample_tickers:
                try:
                    stock = yf.Ticker(ticker)
                    info = stock.info
                    
                    # Skip if missing key data
                    if not info.get('marketCap') or not info.get('bookValue'):
                        continue
                    
                    market_cap = info.get('marketCap', 0)
                    
                    # Focus on small-caps under $1B
                    if market_cap > 1_000_000_000:
                        continue
                    
                    # Calculate key metrics
                    pb_ratio = info.get('priceToBook', 999)
                    pe_ratio = info.get('trailingPE', 999)
                    current_price = info.get('currentPrice', 0)
                    book_value = info.get('bookValue', 0)
                    
                    # Acquisition target criteria
                    score = 0
                    reasons = []
                    
                    # Below book value - strong signal
                    if pb_ratio < 1.0:
                        score += 40
                        reasons.append(f"Trading below book (P/B: {pb_ratio:.2f})")
                    elif pb_ratio < 1.5:
                        score += 20
                        reasons.append(f"Low P/B ratio: {pb_ratio:.2f}")
                    
                    # Small market cap
                    if market_cap < 100_000_000:
                        score += 30
                        reasons.append(f"Micro-cap: ${market_cap/1e6:.1f}M")
                    elif market_cap < 500_000_000:
                        score += 20
                        reasons.append(f"Small-cap: ${market_cap/1e6:.1f}M")
                    
                    # Low PE could indicate value
                    if 0 < pe_ratio < 10:
                        score += 15
                        reasons.append(f"Low P/E: {pe_ratio:.1f}")
                    
                    # High short interest indicates potential squeeze on acquisition
                    short_ratio = info.get('shortRatio', 0)
                    if short_ratio > 10:
                        score += 20
                        reasons.append(f"High short interest: {short_ratio:.1f} days")
                    
                    if score >= 40:  # Minimum threshold
                        signal = {
                            'ticker': ticker,
                            'company': info.get('longName', ticker),
                            'signal_type': 'UNDERVALUED',
                            'score': score,
                            'market_cap': market_cap,
                            'current_price': current_price,
                            'pb_ratio': pb_ratio,
                            'reasons': reasons,
                            'timestamp': datetime.now().isoformat()
                        }
                        signals.append(signal)
                        print(f"  ✓ Found target: {ticker} (Score: {score})")
                    
                    time.sleep(2)  # Rate limiting
                    
                except Exception as e:
                    print(f"  ✗ Error checking {ticker}: {e}")
                    continue
            
            print(f"  Found {len(signals)} undervalued targets")
            
        except Exception as e:
            print(f"  ✗ Screening error: {e}")
        
        return signals
    
    def check_price_anomalies(self, tickers: List[str] = None) -> List[Dict[str, Any]]:
        """Detect unusual price/volume activity"""
        print("\n🔍 Checking for price anomalies...")
        signals = []
        
        if not tickers:
            # Use same sample tickers as screening
            tickers = ['RHP', 'PEB', 'SHO', 'XHR', 'INN', 'DRH', 'AHT', 'CLDT']
        
        try:
            for ticker in tickers:
                try:
                    stock = yf.Ticker(ticker)
                    
                    # Get recent price data
                    hist = stock.history(period='5d', interval='1d')
                    if len(hist) < 2:
                        continue
                    
                    latest = hist.iloc[-1]
                    previous = hist.iloc[-2]
                    
                    # Calculate changes
                    price_change_pct = ((latest['Close'] - previous['Close']) / previous['Close']) * 100
                    volume_ratio = latest['Volume'] / hist['Volume'].mean()
                    
                    score = 0
                    reasons = []
                    
                    # Unusual price movement
                    if price_change_pct > 5:
                        score += 30
                        reasons.append(f"Price surge: +{price_change_pct:.1f}%")
                    elif price_change_pct > 3:
                        score += 15
                        reasons.append(f"Price up: +{price_change_pct:.1f}%")
                    
                    # Volume spike
                    if volume_ratio > 3:
                        score += 35
                        reasons.append(f"Volume spike: {volume_ratio:.1f}x average")
                    elif volume_ratio > 2:
                        score += 20
                        reasons.append(f"High volume: {volume_ratio:.1f}x average")
                    
                    if score >= 30:
                        signal = {
                            'ticker': ticker,
                            'signal_type': 'PRICE_ANOMALY',
                            'score': score,
                            'price_change': price_change_pct,
                            'volume_ratio': volume_ratio,
                            'current_price': latest['Close'],
                            'reasons': reasons,
                            'timestamp': datetime.now().isoformat()
                        }
                        signals.append(signal)
                        print(f"  ✓ Anomaly detected: {ticker} (Score: {score})")
                    
                    time.sleep(2)
                    
                except Exception as e:
                    continue
            
            print(f"  Found {len(signals)} price anomalies")
            
        except Exception as e:
            print(f"  ✗ Price anomaly check error: {e}")
        
        return signals
    
    def check_ma_news(self) -> List[Dict[str, Any]]:
        """Monitor news for M&A keywords and rumors"""
        print("\n🔍 Checking M&A news...")
        signals = []
        
        # M&A related keywords
        ma_keywords = [
            'acquisition', 'merger', 'buyout', 'takeover', 'tender offer',
            'strategic alternatives', 'exploring sale', 'buyer interest',
            'activist investor', 'go private'
        ]
        
        try:
            # Use free news API (example with Google News RSS)
            # In production, use proper news API with API key
            
            url = "https://news.google.com/rss/search"
            params = {
                'q': 'acquisition OR merger OR buyout stock',
                'hl': 'en-US',
                'gl': 'US',
                'ceid': 'US:en'
            }
            
            response = requests.get(url, params=params, headers=self.headers)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'xml')
                items = soup.find_all('item')[:20]
                
                for item in items:
                    title = item.find('title').text if item.find('title') else ''
                    description = item.find('description').text if item.find('description') else ''
                    link = item.find('link').text if item.find('link') else ''
                    
                    # Check for M&A keywords
                    text = f"{title} {description}".lower()
                    matched_keywords = [kw for kw in ma_keywords if kw in text]
                    
                    if matched_keywords:
                        # Try to extract ticker
                        ticker = self._extract_ticker_from_news(title)
                        
                        signal = {
                            'ticker': ticker,
                            'signal_type': 'MA_NEWS',
                            'score': len(matched_keywords) * 15,
                            'title': title[:150],
                            'keywords': matched_keywords,
                            'link': link,
                            'timestamp': datetime.now().isoformat()
                        }
                        signals.append(signal)
                        print(f"  ✓ M&A news found: {title[:60]}...")
            
            print(f"  Found {len(signals)} M&A news items")
            
        except Exception as e:
            print(f"  ✗ News check error: {e}")
        
        return signals
    
    def _extract_ticker_from_news(self, text: str) -> str:
        """Extract ticker from news headline"""
        import re
        # Look for patterns like (NASDAQ:TICKER) or (NYSE:TICKER) or just (TICKER)
        match = re.search(r'\((?:NASDAQ:|NYSE:|)([A-Z]{1,5})\)', text)
        if match:
            return match.group(1)
        return None
    
    def aggregate_and_score(self, all_signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Combine signals by ticker and calculate total score"""
        print("\n📊 Aggregating signals...")
        
        ticker_signals = defaultdict(list)
        
        for signal in all_signals:
            ticker = signal.get('ticker')
            if ticker:
                ticker_signals[ticker].append(signal)
        
        aggregated = []
        
        for ticker, signals in ticker_signals.items():
            total_score = sum(s.get('score', 0) for s in signals)
            
            # Only keep high-scoring opportunities
            if total_score >= self.alert_threshold:
                agg = {
                    'ticker': ticker,
                    'total_score': total_score,
                    'signal_count': len(signals),
                    'signals': signals,
                    'timestamp': datetime.now().isoformat()
                }
                aggregated.append(agg)
        
        # Sort by score
        aggregated.sort(key=lambda x: x['total_score'], reverse=True)
        
        print(f"  {len(aggregated)} high-priority targets identified")
        
        return aggregated
    
    def send_summary_alerts(self, aggregated_signals: List[Dict[str, Any]]):
        """Send Discord alerts for high-priority targets"""
        print("\n📢 Sending alerts...")
        
        if not aggregated_signals:
            print("  No alerts to send (no high-priority targets)")
            return
        
        # Send alert for each high-priority target
        for target in aggregated_signals[:5]:  # Top 5 only
            ticker = target['ticker']
            score = target['total_score']
            signals = target['signals']
            
            # Build description
            signal_types = [s.get('signal_type') for s in signals]
            description = f"**Multiple acquisition signals detected**\n"
            description += f"Total Score: **{score}**/100\n"
            description += f"Signal Count: {len(signals)}\n\n"
            
            # Add details for each signal
            fields = []
            for signal in signals[:5]:  # Max 5 signals
                signal_type = signal.get('signal_type', 'UNKNOWN')
                signal_score = signal.get('score', 0)
                
                if signal_type == 'SEC_FILING':
                    fields.append({
                        "name": f"📄 {signal.get('filing_type')} Filing",
                        "value": f"Score: {signal_score}\n{signal.get('description', '')[:100]}",
                        "inline": False
                    })
                elif signal_type == 'UNDERVALUED':
                    reasons = '\n'.join(signal.get('reasons', [])[:3])
                    fields.append({
                        "name": f"💰 Undervalued Target",
                        "value": f"Score: {signal_score}\n{reasons}",
                        "inline": False
                    })
                elif signal_type == 'PRICE_ANOMALY':
                    reasons = '\n'.join(signal.get('reasons', []))
                    fields.append({
                        "name": f"📈 Unusual Activity",
                        "value": f"Score: {signal_score}\n{reasons}",
                        "inline": False
                    })
                elif signal_type == 'MA_NEWS':
                    keywords = ', '.join(signal.get('keywords', [])[:3])
                    fields.append({
                        "name": f"📰 M&A News",
                        "value": f"Score: {signal_score}\nKeywords: {keywords}",
                        "inline": False
                    })
            
            # Color based on score
            if score >= 80:
                color = 15158332  # Red - High priority
            elif score >= 60:
                color = 16776960  # Yellow - Medium priority
            else:
                color = 3447003   # Blue - Low priority
            
            self.send_discord_alert(
                title=f"🎯 ACQUISITION TARGET: ${ticker}",
                description=description,
                color=color,
                fields=fields
            )
            
            time.sleep(1)  # Rate limit Discord webhooks
    
    def run_scan(self):
        """Execute full scan across all sources"""
        print(f"\n{'='*60}")
        print(f"🚀 Starting M&A Target Scan")
        print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        
        all_signals = []
        
        # 1. Check SEC filings
        sec_signals = self.check_sec_filings()
        all_signals.extend(sec_signals)
        
        # 2. Screen for undervalued targets
        undervalued = self.scan_undervalued_targets()
        all_signals.extend(undervalued)
        
        # 3. Check price anomalies
        anomalies = self.check_price_anomalies()
        all_signals.extend(anomalies)
        
        # 4. Check M&A news
        news = self.check_ma_news()
        all_signals.extend(news)
        
        # 5. Aggregate and score
        high_priority = self.aggregate_and_score(all_signals)
        
        # 6. Send alerts
        self.send_summary_alerts(high_priority)
        
        print(f"\n{'='*60}")
        print(f"✅ Scan complete")
        print(f"📊 Total signals: {len(all_signals)}")
        print(f"🎯 High-priority targets: {len(high_priority)}")
        print(f"{'='*60}\n")
        
        return high_priority


def main():
    """Main entry point"""
    import os
    
    # Get Discord webhook from environment variable
    webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
    
    if not webhook_url:
        print("❌ ERROR: DISCORD_WEBHOOK_URL environment variable not set")
        print("Please set it in GitHub Secrets")
        return
    
    # Initialize scanner
    scanner = AcquisitionScanner(webhook_url)
    
    # Run scan
    scanner.run_scan()


if __name__ == "__main__":
    main()
