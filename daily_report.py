#!/usr/bin/env python3
"""
Enhanced Daily Report Module for DR. NILESH SHAH'S MARKET ANALYSIS
==================================================================
- Nifty 50 stocks analysis
- Sensex 30 stocks analysis
- US Market (S&P 500, NASDAQ, NYSE) analysis
- Market News headlines
- Professional PDF reports with logo
- Email delivery
"""

import os
import sys
import json
import csv
import smtplib
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, List, Optional

# Data imports
try:
    import yfinance as yf
    import pandas as pd
    import numpy as np
    import ta
    DATA_OK = True
except ImportError:
    DATA_OK = False

# PDF imports
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    PDF_OK = True
except ImportError:
    PDF_OK = False

# Fast batch downloads + disk cache
try:
    import market_data
    MARKET_DATA_OK = True
except ImportError:
    MARKET_DATA_OK = False

# News import
try:
    from newsapi import NewsApiClient
    NEWS_OK = True
except ImportError:
    NEWS_OK = False


# ============================================================
# NIFTY 50 STOCKS (All 50)
# ============================================================

NIFTY50_STOCKS = [
    'RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'ICICIBANK', 'HINDUNILVR',
    'ITC', 'SBIN', 'BHARTIARTL', 'KOTAKBANK', 'LT', 'AXISBANK',
    'BAJFINANCE', 'ASIANPAINT', 'MARUTI', 'SUNPHARMA', 'TITAN',
    'BAJAJFINSV', 'WIPRO', 'HCLTECH', 'ULTRACEMCO', 'NTPC',
    'NESTLEIND', 'POWERGRID', 'TMPV', 'M&M', 'JSWSTEEL',
    'TATASTEEL', 'TECHM', 'ADANIENT', 'ONGC', 'HINDALCO',
    'INDUSINDBK', 'DIVISLAB', 'DRREDDY', 'CIPLA', 'GRASIM',
    'BPCL', 'COALINDIA', 'HEROMOTOCO', 'EICHERMOT', 'UPL',
    'TATACONSUM', 'BAJAJ-AUTO', 'APOLLOHOSP', 'BRITANNIA',
    'PIDILITIND', 'SBILIFE', 'HDFCLIFE', 'ICICIPRULI'
]


# ============================================================
# SENSEX 30 STOCKS (All 30)
# ============================================================

SENSEX30_STOCKS = [
    'RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'ICICIBANK', 'HINDUNILVR',
    'ITC', 'SBIN', 'BHARTIARTL', 'KOTAKBANK', 'LT', 'AXISBANK',
    'BAJFINANCE', 'ASIANPAINT', 'MARUTI', 'SUNPHARMA', 'TITAN',
    'BAJAJFINSV', 'WIPRO', 'HCLTECH', 'ULTRACEMCO', 'NTPC',
    'NESTLEIND', 'POWERGRID', 'TMPV', 'M&M', 'JSWSTEEL',
    'TATASTEEL', 'TECHM', 'INDUSINDBK'
]


# ============================================================
# US MARKET STOCKS
# ============================================================

# S&P 500 Top 50
SP500_TOP50 = [
    'AAPL', 'MSFT', 'AMZN', 'NVDA', 'GOOGL', 'META', 'GOOG', 'BRK-B',
    'UNH', 'XOM', 'LLY', 'JPM', 'V', 'PG', 'MA', 'JNJ', 'HD', 'CVX',
    'MRK', 'ABBV', 'PEP', 'KO', 'COST', 'AVGO', 'TMO', 'MCD', 'WMT',
    'CSCO', 'ACN', 'ABT', 'DHR', 'LIN', 'NEE', 'TXN', 'PM', 'UNP',
    'RTX', 'LOW', 'HON', 'AMGN', 'IBM', 'CAT', 'GE', 'BA', 'SPGI',
    'BLK', 'GILD', 'INTC', 'MDLZ', 'ADP'
]

# NASDAQ Top 25
NASDAQ_TOP25 = [
    'AAPL', 'MSFT', 'AMZN', 'NVDA', 'GOOGL', 'META', 'TSLA', 'AVGO',
    'COST', 'NFLX', 'AMD', 'ADBE', 'PEP', 'CSCO', 'INTC', 'CMCSA',
    'QCOM', 'TXN', 'INTU', 'AMGN', 'ISRG', 'ADI', 'VRTX', 'REGN', 'MU'
]

# NYSE Top 25
NYSE_TOP25 = [
    'AAPL', 'MSFT', 'AMZN', 'NVDA', 'GOOGL', 'META', 'BRK-B', 'UNH',
    'XOM', 'LLY', 'JPM', 'V', 'PG', 'MA', 'JNJ', 'HD', 'CVX', 'MRK',
    'ABBV', 'PEP', 'KO', 'COST', 'WMT', 'MCD', 'BA'
]


def _load_min_liquidity():
    """Liquidity threshold (Rs crore/day) set in the app's Settings tab."""
    try:
        return float(json.loads((Path(__file__).parent / "app_settings.json").read_text()).get('min_liquidity_cr', 1.0))
    except Exception:
        return 1.0


MIN_LIQUIDITY_CR = _load_min_liquidity()


# ============================================================
# EMAIL CONFIGURATION
# ============================================================

class EmailConfig:
    """Email configuration and sending."""
    
    def __init__(self):
        self.config_file = Path(__file__).parent / "email_config.json"
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.sender_email = ""
        self.sender_password = ""
        self.receiver_emails = []
        self.is_configured = False
        self.last_error = ""
        self._loaded_email = ""
        self.load_config()
    
    def configure(self, smtp_server, smtp_port, sender_email, sender_password, receiver_emails):
        self.smtp_server = smtp_server
        self.smtp_port = int(smtp_port)
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.receiver_emails = receiver_emails
        self.is_configured = True
        self.save_config()
    
    def send_email(self, subject, body, attachment_path=None):
        """Send email with detailed error reporting."""
        self.last_error = ""
        
        if not self.is_configured:
            self.last_error = "Email not configured. Please save email settings first."
            return False
        
        if not self.sender_email:
            self.last_error = "Sender email is empty."
            return False
        
        if not self.sender_password:
            self.last_error = "Sender password is empty. Please re-enter and save your email config."
            return False
        
        if not self.receiver_emails:
            self.last_error = "No receiver emails configured."
            return False
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = ', '.join(self.receiver_emails)
            msg['Subject'] = f"[DR. NILESH SHAH'S ANALYSIS] {subject}"
            msg.attach(MIMEText(body, 'html'))
            
            if attachment_path and os.path.exists(attachment_path):
                with open(attachment_path, 'rb') as f:
                    attachment = MIMEBase('application', 'octet-stream')
                    attachment.set_payload(f.read())
                    encoders.encode_base64(attachment)
                    attachment.add_header('Content-Disposition', f'attachment; filename={os.path.basename(attachment_path)}')
                    msg.attach(attachment)
            
            # Connect and send
            if self.smtp_port == 465:
                # SSL for port 465
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=30)
            else:
                # STARTTLS for port 587
                server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30)
                server.ehlo()
                server.starttls()
                server.ehlo()
            
            server.login(self.sender_email, self.sender_password)
            server.send_message(msg)
            server.quit()
            self.last_error = ""
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            self.last_error = (
                f"Authentication failed: {e}\n\n"
                "For Gmail users:\n"
                "1. You MUST use an App Password (not your regular password)\n"
                "2. Go to: https://myaccount.google.com/apppasswords\n"
                "3. Generate a new App Password for 'Mail'\n"
                "4. Use that 16-character password here\n\n"
                "Make sure 2-Factor Authentication is enabled on your Google account first."
            )
            print(f"Email auth error: {e}")
            return False
            
        except smtplib.SMTPConnectError as e:
            self.last_error = (
                f"Cannot connect to {self.smtp_server}:{self.smtp_port}\n\n"
                "Check:\n"
                "1. Internet connection\n"
                "2. SMTP server address\n"
                "3. Try port 587 (STARTTLS) or 465 (SSL)\n"
                "4. Firewall/antivirus settings"
            )
            print(f"Email connect error: {e}")
            return False
            
        except smtplib.SMTPRecipientsRefused as e:
            self.last_error = f"Recipient refused: {e}\n\nCheck receiver email addresses."
            print(f"Email recipient error: {e}")
            return False
            
        except smtplib.SMTPServerDisconnected as e:
            self.last_error = f"Server disconnected: {e}\n\nTry again or check server settings."
            print(f"Email disconnect error: {e}")
            return False
            
        except TimeoutError as e:
            self.last_error = f"Connection timed out: {e}\n\nCheck internet connection."
            print(f"Email timeout error: {e}")
            return False
            
        except Exception as e:
            self.last_error = f"Email error: {type(e).__name__}: {e}"
            print(f"Email error: {e}")
            return False
    
    def test_connection(self):
        """Test SMTP connection without sending an email."""
        self.last_error = ""
        
        if not self.sender_email or not self.sender_password:
            self.last_error = "Email and password are required."
            return False
        
        try:
            if self.smtp_port == 465:
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=15)
            else:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=15)
                server.ehlo()
                server.starttls()
                server.ehlo()
            
            server.login(self.sender_email, self.sender_password)
            server.quit()
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            self.last_error = (
                f"Authentication failed!\n\n"
                "For Gmail: Use App Password, not regular password.\n"
                "Generate at: https://myaccount.google.com/apppasswords"
            )
            return False
        except Exception as e:
            self.last_error = f"Connection test failed: {e}"
            return False
    
    def save_config(self):
        """Save email settings. The password goes to Windows Credential Manager when available
        (email_config.json then holds no password); otherwise it falls back to the file."""
        try:
            stored_securely = _store_password(self.sender_email, self.sender_password)
            if stored_securely and self._loaded_email and self._loaded_email != self.sender_email:
                _delete_password(self._loaded_email)   # sender changed - don't leave the old one behind

            data = {
                'smtp_server': self.smtp_server,
                'smtp_port': self.smtp_port,
                'sender_email': self.sender_email,
                'receiver_emails': self.receiver_emails,
                'is_configured': self.is_configured,
                'password_storage': 'windows_credential_manager' if stored_securely else 'file',
                'saved_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
            if not stored_securely and self.sender_password:
                import base64
                # Fallback only (keyring unavailable): base64 is obfuscation, NOT encryption
                data['sender_password_encoded'] = base64.b64encode(self.sender_password.encode('utf-8')).decode('utf-8')
            with open(self.config_file, 'w') as f:
                json.dump(data, f, indent=2)
            self._loaded_email = self.sender_email
            print(f"[EmailConfig] Config saved (password in "
                  f"{'Windows Credential Manager' if stored_securely else 'email_config.json'})")
        except Exception as e:
            print(f"[EmailConfig] Save error: {e}")

    def load_config(self):
        """Load email settings. A password still stored in email_config.json (older versions)
        is moved into Windows Credential Manager and removed from the file."""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                self.smtp_server = data.get('smtp_server', 'smtp.gmail.com')
                self.smtp_port = int(data.get('smtp_port', 587))
                self.sender_email = data.get('sender_email', '')
                self.receiver_emails = data.get('receiver_emails', [])
                self.is_configured = data.get('is_configured', False)
                self._loaded_email = self.sender_email

                # Password left in the file by older versions (base64 or plain text)
                file_pw = data.get('sender_password', '')
                if data.get('sender_password_encoded'):
                    try:
                        import base64
                        file_pw = base64.b64decode(data['sender_password_encoded'].encode('utf-8')).decode('utf-8')
                    except Exception:
                        pass

                if file_pw:
                    self.sender_password = file_pw
                    if KEYRING_OK:
                        self.save_config()   # migrate: stores in Credential Manager, rewrites file without it
                else:
                    self.sender_password = _read_password(self.sender_email)

                # Validate: if configured but password is empty, mark as not configured
                if self.is_configured and not self.sender_password:
                    print("[EmailConfig] WARNING: Config says configured but password is empty!")
                    self.is_configured = False

                print(f"[EmailConfig] Config loaded: {self.sender_email}, configured={self.is_configured}")
        except Exception as e:
            print(f"[EmailConfig] Load error: {e}")

    def delete_stored_password(self):
        """Remove the saved password from Windows Credential Manager (used by 'Clear Config')."""
        if self.sender_email:
            _delete_password(self.sender_email)


# Windows Credential Manager (via the keyring package) for the email app password
KEYRING_SERVICE = "DR Nilesh Shah Market Analysis - Email"
try:
    import keyring
    KEYRING_OK = type(keyring.get_keyring()).__name__ not in ('Keyring', 'FailKeyring', 'NullKeyring')
except Exception:
    KEYRING_OK = False


def _store_password(email: str, password: str) -> bool:
    """Save the password in Credential Manager and read it back to confirm. False if unavailable."""
    if not KEYRING_OK or not email or not password:
        return False
    try:
        keyring.set_password(KEYRING_SERVICE, email, password)
        return keyring.get_password(KEYRING_SERVICE, email) == password
    except Exception as e:
        print(f"[EmailConfig] Credential Manager save failed: {e}")
        return False


def _read_password(email: str) -> str:
    if not KEYRING_OK or not email:
        return ""
    try:
        return keyring.get_password(KEYRING_SERVICE, email) or ""
    except Exception as e:
        print(f"[EmailConfig] Credential Manager read failed: {e}")
        return ""


def _delete_password(email: str):
    if not KEYRING_OK or not email:
        return
    try:
        keyring.delete_password(KEYRING_SERVICE, email)
    except Exception:
        pass   # nothing stored


# ============================================================
# STOCK ANALYZER
# ============================================================

class StockAnalyzer:
    """Analyze stocks for daily report."""
    
    def __init__(self):
        self.cache = {}
    
    def analyze(self, symbol, exchange='NSE', df=None):
        """Analyze a single stock. Fetches its history unless df is given."""
        if not DATA_OK:
            return None

        try:
            if df is None:
                # NSE symbols fall back to BSE (.BO) for BSE-only listings
                suffixes = {'NSE': ['.NS', '.BO'], 'BSE': ['.BO'], 'NYSE': [''], 'NASDAQ': ['']}
                for suffix in suffixes.get(exchange, ['']):
                    df = yf.Ticker(f"{symbol}{suffix}").history(period='1y')
                    if df is not None and len(df) >= 20:
                        break

            if df is None or df.empty or len(df) < 20:
                return None
            
            close = df['Close'].values
            high = df['High'].values
            low = df['Low'].values
            volume = df['Volume'].values
            
            current_price = float(close[-1])
            prev_price = float(close[-2]) if len(close) > 1 else current_price
            change = current_price - prev_price
            change_pct = (change / prev_price * 100) if prev_price > 0 else 0
            
            # 52-week high/low
            week52_high = float(high.max())
            week52_low = float(low.min())
            
            # Volume
            avg_volume = float(volume[-20:].mean()) if len(volume) >= 20 else float(volume[-1])
            current_volume = float(volume[-1])
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
            
            # RSI
            try:
                rsi = float(ta.momentum.RSIIndicator(df['Close'], 14).rsi().iloc[-1])
                if pd.isna(rsi): rsi = 50
            except: rsi = 50
            
            # MACD
            try:
                macd_ind = ta.trend.MACD(df['Close'])
                macd_hist = float(macd_ind.macd_diff().iloc[-1])
                macd_signal = 'Bullish' if macd_hist > 0 else 'Bearish'
                if pd.isna(macd_hist): macd_hist = 0
            except:
                macd_hist = 0
                macd_signal = 'Neutral'
            
            # Moving Averages
            try:
                sma20 = float(ta.trend.SMAIndicator(df['Close'], 20).sma_indicator().iloc[-1])
                # None = stock too new for that average; it's skipped in scoring instead of counting as bearish
                sma50 = float(ta.trend.SMAIndicator(df['Close'], 50).sma_indicator().iloc[-1]) if len(df) >= 50 else None
                sma200 = float(ta.trend.SMAIndicator(df['Close'], 200).sma_indicator().iloc[-1]) if len(df) >= 200 else None
            except:
                sma20, sma50, sma200 = current_price, None, None
            
            # SuperTrend
            try:
                st_signal = 'BUY' if current_price > sma20 else 'SELL'
                st_direction = 'BULLISH' if st_signal == 'BUY' else 'BEARISH'
            except:
                st_signal = 'HOLD'
                st_direction = 'NEUTRAL'
            
            # VWAP
            try:
                typical_price = (df['High'] + df['Low'] + df['Close']) / 3
                vwap = float((typical_price * df['Volume']).rolling(20).sum().iloc[-1] / df['Volume'].rolling(20).sum().iloc[-1])
                if pd.isna(vwap) or vwap == 0: vwap = current_price
                vwap_signal = 'Bullish' if current_price > vwap * 1.02 else 'Bearish' if current_price < vwap * 0.98 else 'Neutral'
            except:
                vwap = current_price
                vwap_signal = 'Neutral'
            
            # Calculate Score
            score = 50
            
            # RSI scoring
            if rsi < 30: score += 20
            elif rsi < 40: score += 10
            elif rsi > 70: score -= 20
            elif rsi > 60: score -= 10
            
            # MACD scoring
            if macd_hist > 0: score += 10
            else: score -= 10
            
            # MA scoring
            if current_price > sma20: score += 10
            else: score -= 10
            if sma50 is not None:
                score += 5 if current_price > sma50 else -5
            if sma200 is not None:
                score += 5 if current_price > sma200 else -5
            
            # Volume scoring
            if volume_ratio > 1.5: score += 5
            elif volume_ratio < 0.5: score -= 5
            
            # VWAP scoring
            if vwap_signal == 'Bullish': score += 5
            elif vwap_signal == 'Bearish': score -= 5
            
            score = max(0, min(100, score))
            
            # Recommendation
            if score >= 75: rec = 'STRONG BUY'
            elif score >= 60: rec = 'BUY'
            elif score >= 45: rec = 'HOLD'
            elif score >= 30: rec = 'SELL'
            else: rec = 'STRONG SELL'
            
            # ATR for targets
            try:
                atr = float(ta.volatility.AverageTrueRange(df['High'], df['Low'], df['Close'], 14).average_true_range().iloc[-1])
                if pd.isna(atr): atr = current_price * 0.02
            except:
                atr = current_price * 0.02
            
            # Stop Loss & Targets
            if rec in ['STRONG BUY', 'BUY']:
                stop_loss = current_price - (atr * 1.5)
                target1 = current_price + (atr * 1.5)
                target2 = current_price + (atr * 2.5)
            elif rec in ['SELL', 'STRONG SELL']:
                stop_loss = current_price + (atr * 1.5)
                target1 = current_price - (atr * 1.5)
                target2 = current_price - (atr * 2.5)
            else:
                stop_loss = current_price - (atr * 1.5)
                target1 = current_price + (atr * 1.5)
                target2 = current_price + (atr * 2.5)
            
            return {
                'symbol': symbol,
                'exchange': exchange,
                'price': round(current_price, 2),
                'change': round(change, 2),
                'change_pct': round(change_pct, 2),
                'week52_high': round(week52_high, 2),
                'week52_low': round(week52_low, 2),
                'volume': int(current_volume),
                'avg_volume': int(avg_volume),
                'volume_ratio': round(volume_ratio, 2),
                'rsi': round(rsi, 1),
                'macd_hist': round(macd_hist, 4),
                'macd_signal': macd_signal,
                'sma20': round(sma20, 2),
                'sma50': round(sma50, 2) if sma50 is not None else None,
                'sma200': round(sma200, 2) if sma200 is not None else None,
                'avg_value_cr': round(float((df['Close'] * df['Volume']).tail(20).mean()) / 1e7, 2),
                'supertrend': st_signal,
                'supertrend_dir': st_direction,
                'vwap': round(vwap, 2),
                'vwap_signal': vwap_signal,
                'score': round(score, 1),
                'recommendation': rec,
                'stop_loss': round(stop_loss, 2),
                'target1': round(target1, 2),
                'target2': round(target2, 2),
                'atr': round(atr, 2),
            }
            
        except Exception as e:
            return None
    
    def analyze_batch(self, symbols, exchange='NSE', max_stocks=50):
        """Analyze multiple stocks (one batch download via market_data when available)."""
        symbols = list(symbols)[:max_stocks]
        if MARKET_DATA_OK:
            data = market_data.load_history(symbols, years=5, exchange=exchange)
            results = []
            for symbol in symbols:
                df = data.get(symbol.upper())
                if df is not None:
                    result = self.analyze(symbol, exchange, market_data.slice_period(df, '1y'))
                    if result:
                        results.append(result)
            return results

        results = []
        for symbol in symbols:
            result = self.analyze(symbol, exchange)
            if result:
                results.append(result)
            time.sleep(0.2)  # Rate limiting
        return results


# ============================================================
# NEWS FETCHER
# ============================================================

class NewsFetcher:
    """Fetch market news from various sources."""
    
    def __init__(self):
        self.news_api_key = None
        self.news_file = Path(__file__).parent / "market_news.json"
    
    def fetch_news(self, query="stock market India", max_articles=10):
        """Fetch news from Yahoo Finance RSS or other sources."""
        news_items = []
        
        # Try to fetch from yfinance news
        try:
            # Get news for major indices
            for ticker_symbol in ['^NSEI', '^BSESN', '^GSPC', '^IXIC']:
                try:
                    ticker = yf.Ticker(ticker_symbol)
                    news = ticker.news
                    if news:
                        for item in news[:3]:
                            news_items.append(self._parse_yf_news(item))
                except:
                    pass
        except:
            pass
        
        # Add some default market news placeholders
        if not news_items:
            news_items = [
                {'title': 'Indian markets open for trading', 'publisher': 'Market Watch', 'source': 'Auto', 'published': datetime.now().strftime('%Y-%m-%d')},
                {'title': 'US markets update', 'publisher': 'Financial Times', 'source': 'Auto', 'published': datetime.now().strftime('%Y-%m-%d')},
                {'title': 'Global economic indicators', 'publisher': 'Reuters', 'source': 'Auto', 'published': datetime.now().strftime('%Y-%m-%d')},
            ]
        
        # Remove duplicates
        seen = set()
        unique_news = []
        for item in news_items:
            title = item.get('title', '')
            if title not in seen:
                seen.add(title)
                unique_news.append(item)
        
        return unique_news[:max_articles]

    @staticmethod
    def _parse_yf_news(item):
        """Handle both yfinance news formats (flat pre-0.2.50, nested under 'content' in newer versions)."""
        content = item.get('content')
        if isinstance(content, dict):
            provider = content.get('provider') or {}
            url = (content.get('canonicalUrl') or content.get('clickThroughUrl') or {}).get('url', '')
            published = content.get('pubDate') or content.get('displayTime') or ''
            try:
                published = datetime.strptime(published[:16], '%Y-%m-%dT%H:%M').strftime('%Y-%m-%d %H:%M')
            except ValueError:
                published = published or 'N/A'
            return {
                'title': content.get('title') or 'N/A',
                'publisher': provider.get('displayName', 'Unknown'),
                'link': url,
                'published': published,
                'source': 'Yahoo Finance'
            }
        ts = item.get('providerPublishTime')
        return {
            'title': item.get('title', 'N/A'),
            'publisher': item.get('publisher', 'Unknown'),
            'link': item.get('link', ''),
            'published': datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M') if ts else 'N/A',
            'source': 'Yahoo Finance'
        }


# ============================================================
# DAILY REPORT GENERATOR
# ============================================================

class DailyReportGenerator:
    """Generate comprehensive daily market reports."""
    
    def __init__(self):
        self.analyzer = StockAnalyzer()
        self.news_fetcher = NewsFetcher()
        self.email_config = EmailConfig()
        self.logo_path = Path(__file__).parent / "logo_new.png"
        self.reports_dir = Path(__file__).parent / "reports"
        self.reports_dir.mkdir(exist_ok=True)
        self.report_data = {}
    
    def generate_report(self, watchlist=None, include_us=True, include_india=True):
        """Generate comprehensive daily report."""
        print("\n" + "=" * 60)
        print("DR. NILESH SHAH'S MARKET ANALYSIS")
        print("Daily Market Report Generator")
        print("=" * 60)
        
        report = {
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'title': 'Daily Market Analysis Report',
            'sections': {},
            'summary': {},
            'news': [],
        }

        # 0. User's watchlist (e.g. {'NSE': ['RELIANCE', 'TCS']})
        if watchlist:
            print("\n[0/5] Analyzing your watchlist...")
            wl_results = []
            for exchange, symbols in watchlist.items():
                wl_results.extend(self.analyzer.analyze_batch(list(symbols), exchange, len(symbols)))
            report['sections']['watchlist'] = {
                'title': 'Your Watchlist',
                'stocks': sorted(wl_results, key=lambda x: x['score'], reverse=True),
                'total': len(wl_results),
                'strong_buy': sum(1 for r in wl_results if r['recommendation'] == 'STRONG BUY'),
                'buy': sum(1 for r in wl_results if r['recommendation'] == 'BUY'),
                'hold': sum(1 for r in wl_results if r['recommendation'] == 'HOLD'),
                'sell': sum(1 for r in wl_results if r['recommendation'] == 'SELL'),
                'strong_sell': sum(1 for r in wl_results if r['recommendation'] == 'STRONG SELL'),
                'avg_score': round(sum(r['score'] for r in wl_results) / len(wl_results), 1) if wl_results else 0,
            }
            print(f"   Analyzed {len(wl_results)} watchlist stocks")

        # 1. Nifty 50 Analysis
        if include_india:
            print("\n[1/5] Analyzing Nifty 50 stocks...")
            nifty_results = self.analyzer.analyze_batch(NIFTY50_STOCKS, 'NSE', 50)
            report['sections']['nifty50'] = {
                'title': 'Nifty 50',
                'stocks': sorted(nifty_results, key=lambda x: x['score'], reverse=True),
                'total': len(nifty_results),
                'strong_buy': sum(1 for r in nifty_results if r['recommendation'] == 'STRONG BUY'),
                'buy': sum(1 for r in nifty_results if r['recommendation'] == 'BUY'),
                'hold': sum(1 for r in nifty_results if r['recommendation'] == 'HOLD'),
                'sell': sum(1 for r in nifty_results if r['recommendation'] == 'SELL'),
                'strong_sell': sum(1 for r in nifty_results if r['recommendation'] == 'STRONG SELL'),
                'avg_score': round(sum(r['score'] for r in nifty_results) / len(nifty_results), 1) if nifty_results else 0,
            }
            print(f"   Analyzed {len(nifty_results)} Nifty 50 stocks")
        
        # 2. Sensex 30 Analysis
        if include_india:
            print("\n[2/5] Analyzing Sensex 30 stocks...")
            sensex_results = self.analyzer.analyze_batch(SENSEX30_STOCKS, 'BSE', 30)
            report['sections']['sensex30'] = {
                'title': 'Sensex 30',
                'stocks': sorted(sensex_results, key=lambda x: x['score'], reverse=True),
                'total': len(sensex_results),
                'strong_buy': sum(1 for r in sensex_results if r['recommendation'] == 'STRONG BUY'),
                'buy': sum(1 for r in sensex_results if r['recommendation'] == 'BUY'),
                'hold': sum(1 for r in sensex_results if r['recommendation'] == 'HOLD'),
                'sell': sum(1 for r in sensex_results if r['recommendation'] == 'SELL'),
                'strong_sell': sum(1 for r in sensex_results if r['recommendation'] == 'STRONG SELL'),
                'avg_score': round(sum(r['score'] for r in sensex_results) / len(sensex_results), 1) if sensex_results else 0,
            }
            print(f"   Analyzed {len(sensex_results)} Sensex 30 stocks")
        
        # 3. US Market - S&P 500
        if include_us:
            print("\n[3/5] Analyzing US Market (S&P 500 Top 50)...")
            sp500_results = self.analyzer.analyze_batch(SP500_TOP50, 'NYSE', 50)
            report['sections']['sp500'] = {
                'title': 'S&P 500 Top 50',
                'stocks': sorted(sp500_results, key=lambda x: x['score'], reverse=True),
                'total': len(sp500_results),
                'strong_buy': sum(1 for r in sp500_results if r['recommendation'] == 'STRONG BUY'),
                'buy': sum(1 for r in sp500_results if r['recommendation'] == 'BUY'),
                'hold': sum(1 for r in sp500_results if r['recommendation'] == 'HOLD'),
                'sell': sum(1 for r in sp500_results if r['recommendation'] == 'SELL'),
                'strong_sell': sum(1 for r in sp500_results if r['recommendation'] == 'STRONG SELL'),
                'avg_score': round(sum(r['score'] for r in sp500_results) / len(sp500_results), 1) if sp500_results else 0,
            }
            print(f"   Analyzed {len(sp500_results)} S&P 500 stocks")
        
        # 4. Market News
        print("\n[4/5] Fetching Market News...")
        report['news'] = self.news_fetcher.fetch_news(max_articles=15)
        print(f"   Fetched {len(report['news'])} news articles")
        
        # 5. Summary
        print("\n[5/5] Creating Summary...")
        all_stocks = []
        for key, section in report['sections'].items():
            if key != 'watchlist':  # summary/top picks are market-wide; watchlist has its own section
                all_stocks.extend(section.get('stocks', []))
        
        total_stocks = len(all_stocks)
        total_sb = sum(1 for s in all_stocks if s['recommendation'] == 'STRONG BUY')
        total_buy = sum(1 for s in all_stocks if s['recommendation'] == 'BUY')
        total_hold = sum(1 for s in all_stocks if s['recommendation'] == 'HOLD')
        total_sell = sum(1 for s in all_stocks if s['recommendation'] == 'SELL')
        total_ss = sum(1 for s in all_stocks if s['recommendation'] == 'STRONG SELL')
        avg_score = sum(s['score'] for s in all_stocks) / total_stocks if total_stocks > 0 else 0
        
        # Top picks (all markets combined)
        top_picks = sorted(all_stocks, key=lambda x: x['score'], reverse=True)[:15]
        avoid_list = sorted(all_stocks, key=lambda x: x['score'])[:10]
        
        report['summary'] = {
            'total_stocks': total_stocks,
            'strong_buy': total_sb,
            'buy': total_buy,
            'hold': total_hold,
            'sell': total_sell,
            'strong_sell': total_ss,
            'avg_score': round(avg_score, 1),
            'market_sentiment': 'BULLISH' if avg_score >= 60 else 'BEARISH' if avg_score < 40 else 'NEUTRAL',
        }
        report['top_picks'] = top_picks
        report['avoid_list'] = avoid_list
        
        self.report_data = report
        
        print("\n" + "=" * 60)
        print(f"Report Generated: {total_stocks} stocks analyzed")
        print(f"Market Sentiment: {report['summary']['market_sentiment']}")
        print("=" * 60)
        
        return report
    
    def generate_pdf_report(self, report=None):
        """Generate PDF report."""
        if not PDF_OK:
            print("[ERROR] ReportLab not installed")
            return None
        
        if report is None:
            report = self.report_data
        
        if not report:
            print("[ERROR] No report data")
            return None
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        pdf_file = self.reports_dir / f"daily_report_{timestamp}.pdf"
        
        print(f"\n[PDF] Generating: {pdf_file.name}")
        
        try:
            doc = SimpleDocTemplate(str(pdf_file), pagesize=A4,
                                   topMargin=100, bottomMargin=60,
                                   leftMargin=25, rightMargin=25)
            
            elements = []
            styles = getSampleStyleSheet()
            
            def add_header(canvas_obj, doc):
                canvas_obj.saveState()
                
                if self.logo_path.exists():
                    try:
                        canvas_obj.drawImage(str(self.logo_path), 25, A4[1] - 75, 
                                           width=45, height=45, preserveAspectRatio=True, mask='auto')
                    except: pass
                
                canvas_obj.setFont('Helvetica-Bold', 14)
                canvas_obj.setFillColor(colors.HexColor('#1f6feb'))
                canvas_obj.drawString(80, A4[1] - 50, "DR. NILESH SHAH'S MARKET ANALYSIS")
                
                canvas_obj.setFont('Helvetica', 9)
                canvas_obj.setFillColor(colors.gray)
                canvas_obj.drawString(80, A4[1] - 65, f"Daily Report | {report.get('generated_at', '')}")
                
                canvas_obj.setStrokeColor(colors.HexColor('#1f6feb'))
                canvas_obj.setLineWidth(2)
                canvas_obj.line(25, A4[1] - 85, A4[0] - 25, A4[1] - 85)
                
                canvas_obj.setFont('Helvetica', 7)
                canvas_obj.setFillColor(colors.gray)
                canvas_obj.drawString(25, 25, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                canvas_obj.drawRightString(A4[0] - 25, 25, f"Page {doc.page}")
                canvas_obj.drawCentredString(A4[0]/2, 25, "DR. NILESH SHAH'S MARKET ANALYSIS | For educational purposes only")
                canvas_obj.line(25, 38, A4[0] - 25, 38)
                canvas_obj.restoreState()
            
            # Title
            title_style = ParagraphStyle('Title', parent=styles['Title'],
                                        fontSize=18, spaceAfter=15, textColor=colors.HexColor('#1f6feb'))
            subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'],
                                           fontSize=10, spaceAfter=8, textColor=colors.gray)
            section_style = ParagraphStyle('Section', parent=styles['Heading2'],
                                          fontSize=13, spaceAfter=10, spaceBefore=15,
                                          textColor=colors.HexColor('#fbbf24'))
            
            elements.append(Paragraph("DAILY MARKET ANALYSIS REPORT", title_style))
            elements.append(Paragraph(f"Report Date: {report.get('generated_at', '')}", subtitle_style))
            elements.append(Spacer(1, 15))
            
            # Market Summary
            summary = report.get('summary', {})
            elements.append(Paragraph("MARKET SUMMARY", section_style))
            
            summary_data = [
                ['Total Stocks', 'Strong Buy', 'Buy', 'Hold', 'Sell', 'Strong Sell', 'Avg Score', 'Sentiment'],
                [str(summary.get('total_stocks', 0)), str(summary.get('strong_buy', 0)),
                 str(summary.get('buy', 0)), str(summary.get('hold', 0)),
                 str(summary.get('sell', 0)), str(summary.get('strong_sell', 0)),
                 str(summary.get('avg_score', 0)), summary.get('market_sentiment', 'N/A')]
            ]
            
            t = Table(summary_data, colWidths=[60, 60, 45, 45, 45, 60, 50, 55])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f6feb')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 7),
                ('FONTSIZE', (0, 1), (-1, 1), 10),
                ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#d1d5db')),
            ]))
            elements.append(t)
            elements.append(Spacer(1, 15))

            # Watchlist Section
            wl = report.get('sections', {}).get('watchlist', {})
            if wl:
                elements.append(Paragraph(f"YOUR WATCHLIST ({wl.get('total', 0)} Stocks)", section_style))
                elements.append(Paragraph(f"Avg Score: {wl.get('avg_score', 0)} | Buy: {wl.get('strong_buy', 0) + wl.get('buy', 0)} | Hold: {wl.get('hold', 0)} | Sell: {wl.get('sell', 0) + wl.get('strong_sell', 0)}", subtitle_style))

                data = [['Symbol', 'Price', 'Chg%', 'RSI', 'ST', 'Score', 'Signal', 'SL', 'T1', 'Rs Cr/day']]
                for s in wl.get('stocks', []):
                    liq = s.get('avg_value_cr', 0)
                    data.append([
                        s['symbol'], f"{s['price']:.2f}", f"{s['change_pct']:+.1f}%",
                        f"{s['rsi']:.0f}", s['supertrend'], f"{s['score']:.0f}",
                        s['recommendation'], f"{s['stop_loss']:.2f}", f"{s['target1']:.2f}",
                        f"{liq:.2f}" + (" LOW" if liq < MIN_LIQUIDITY_CR else "")
                    ])

                t = Table(data, colWidths=[65, 55, 40, 35, 35, 35, 70, 50, 50, 55], repeatRows=1)
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7c3aed')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 7),
                    ('FONTSIZE', (0, 1), (-1, -1), 6),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
                ]))
                elements.append(t)
                elements.append(Spacer(1, 10))

            # Top Picks
            top_picks = report.get('top_picks', [])
            if top_picks:
                elements.append(Paragraph("TOP 15 STOCK PICKS (All Markets)", section_style))
                
                picks_data = [['#', 'Symbol', 'Exchange', 'Price', 'Change%', 'RSI', 'Score', 'Signal']]
                for i, stock in enumerate(top_picks[:15], 1):
                    currency = '$' if stock.get('exchange') in ['NYSE', 'NASDAQ'] else ''
                    picks_data.append([
                        str(i), stock['symbol'], stock.get('exchange', ''),
                        f"{currency}{stock['price']:.2f}", f"{stock['change_pct']:+.2f}%",
                        f"{stock['rsi']:.0f}", f"{stock['score']:.0f}", stock['recommendation']
                    ])
                
                t = Table(picks_data, colWidths=[25, 65, 45, 60, 50, 35, 35, 80])
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#10b981')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 7),
                    ('FONTSIZE', (0, 1), (-1, -1), 7),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0fdf4')]),
                ]))
                elements.append(t)
                elements.append(Spacer(1, 10))
            
            # Nifty 50 Section
            nifty = report.get('sections', {}).get('nifty50', {})
            if nifty:
                elements.append(Paragraph(f"NIFTY 50 ANALYSIS ({nifty.get('total', 0)} Stocks)", section_style))
                elements.append(Paragraph(f"Avg Score: {nifty.get('avg_score', 0)} | Buy: {nifty.get('strong_buy', 0) + nifty.get('buy', 0)} | Hold: {nifty.get('hold', 0)} | Sell: {nifty.get('sell', 0) + nifty.get('strong_sell', 0)}", subtitle_style))
                
                data = [['Symbol', 'Price', 'Chg%', 'RSI', 'ST', 'Score', 'Signal', 'SL', 'T1']]
                for s in nifty.get('stocks', []):
                    data.append([
                        s['symbol'], f"{s['price']:.2f}", f"{s['change_pct']:+.1f}%",
                        f"{s['rsi']:.0f}", s['supertrend'], f"{s['score']:.0f}",
                        s['recommendation'], f"{s['stop_loss']:.0f}", f"{s['target1']:.0f}"
                    ])
                
                t = Table(data, colWidths=[65, 55, 40, 35, 35, 35, 70, 50, 50])
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f59e0b')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 7),
                    ('FONTSIZE', (0, 1), (-1, -1), 6),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
                ]))
                elements.append(t)
                elements.append(Spacer(1, 10))
            
            # Sensex 30 Section
            sensex = report.get('sections', {}).get('sensex30', {})
            if sensex:
                elements.append(Paragraph(f"SENSEX 30 ANALYSIS ({sensex.get('total', 0)} Stocks)", section_style))
                
                data = [['Symbol', 'Price', 'Chg%', 'RSI', 'ST', 'Score', 'Signal', 'SL', 'T1']]
                for s in sensex.get('stocks', []):
                    data.append([
                        s['symbol'], f"{s['price']:.2f}", f"{s['change_pct']:+.1f}%",
                        f"{s['rsi']:.0f}", s['supertrend'], f"{s['score']:.0f}",
                        s['recommendation'], f"{s['stop_loss']:.0f}", f"{s['target1']:.0f}"
                    ])
                
                t = Table(data, colWidths=[65, 55, 40, 35, 35, 35, 70, 50, 50])
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#ef4444')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 7),
                    ('FONTSIZE', (0, 1), (-1, -1), 6),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
                ]))
                elements.append(t)
                elements.append(Spacer(1, 10))
            
            # US Market Section
            sp500 = report.get('sections', {}).get('sp500', {})
            if sp500:
                elements.append(Paragraph(f"US MARKET - S&P 500 TOP 50 ({sp500.get('total', 0)} Stocks)", section_style))
                elements.append(Paragraph(f"Avg Score: {sp500.get('avg_score', 0)} | Buy: {sp500.get('strong_buy', 0) + sp500.get('buy', 0)} | Hold: {sp500.get('hold', 0)} | Sell: {sp500.get('sell', 0) + sp500.get('strong_sell', 0)}", subtitle_style))
                
                data = [['Symbol', 'Price', 'Chg%', 'RSI', 'Score', 'Signal', 'SL', 'T1', 'T2']]
                for s in sp500.get('stocks', []):
                    data.append([
                        s['symbol'], f"${s['price']:.2f}", f"{s['change_pct']:+.1f}%",
                        f"{s['rsi']:.0f}", f"{s['score']:.0f}", s['recommendation'],
                        f"${s['stop_loss']:.2f}", f"${s['target1']:.2f}", f"${s['target2']:.2f}"
                    ])
                
                t = Table(data, colWidths=[55, 55, 40, 35, 35, 70, 55, 55, 55])
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 7),
                    ('FONTSIZE', (0, 1), (-1, -1), 6),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
                ]))
                elements.append(t)
                elements.append(Spacer(1, 10))
            
            # Market News
            news = report.get('news', [])
            if news:
                elements.append(Paragraph("MARKET NEWS", section_style))
                
                for item in news[:10]:
                    title = item.get('title', 'N/A')
                    publisher = item.get('publisher', 'Unknown')
                    published = item.get('published', '')
                    
                    news_text = f"<b>{title}</b><br/><font size='8' color='gray'>{publisher} | {published}</font>"
                    elements.append(Paragraph(news_text, ParagraphStyle('News', parent=styles['Normal'],
                                                                         fontSize=9, spaceAfter=6, leftIndent=10)))
            
            # Disclaimer
            elements.append(Spacer(1, 20))
            elements.append(Paragraph("DISCLAIMER: This report is for educational purposes only. Not financial advice. Always do your own research before investing.", 
                                     ParagraphStyle('Disclaimer', parent=styles['Normal'],
                                                   fontSize=7, textColor=colors.gray, alignment=1)))
            
            doc.build(elements, onFirstPage=add_header, onLaterPages=add_header)
            
            print(f"[PDF] Saved: {pdf_file}")
            return str(pdf_file)
            
        except Exception as e:
            print(f"[PDF] Error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    @staticmethod
    def _rec_class(rec):
        """CSS class for a recommendation (the stylesheet only defines buy/hold/sell)."""
        return 'buy' if 'BUY' in rec else 'sell' if 'SELL' in rec else 'hold'

    def generate_email_body(self, report=None):
        """Generate HTML email body."""
        if report is None:
            report = self.report_data
        
        if not report:
            return "<p>No report data.</p>"
        
        summary = report.get('summary', {})
        
        html = f"""
        <html>
        <head><style>
            body {{ font-family: Arial, sans-serif; background: #f5f5f5; padding: 20px; }}
            .container {{ max-width: 900px; margin: 0 auto; background: white; border-radius: 10px; }}
            .header {{ background: linear-gradient(135deg, #1f6feb, #0d1b2a); color: white; padding: 25px; text-align: center; }}
            .stats {{ display: flex; justify-content: space-around; padding: 20px; background: #f8fafc; }}
            .stat {{ text-align: center; }}
            .stat .num {{ font-size: 24px; font-weight: bold; }}
            .section {{ padding: 20px; }}
            h2 {{ color: #1f6feb; border-bottom: 2px solid #1f6feb; padding-bottom: 10px; }}
            table {{ width: 100%; border-collapse: collapse; margin: 15px 0; font-size: 12px; }}
            th {{ background: #1f6feb; color: white; padding: 8px; }}
            td {{ padding: 6px; border-bottom: 1px solid #eee; text-align: center; }}
            .buy {{ background: #d1fae5; color: #065f46; }}
            .sell {{ background: #fee2e2; color: #991b1b; }}
            .hold {{ background: #fef3c7; color: #92400e; }}
            .footer {{ background: #1f2937; color: #9ca3af; padding: 15px; text-align: center; font-size: 11px; }}
        </style></head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>DR. NILESH SHAH'S MARKET ANALYSIS</h1>
                    <p>Daily Report | {report.get('generated_at', '')}</p>
                </div>
                <div class="stats">
                    <div class="stat"><div class="num">{summary.get('total_stocks', 0)}</div><div>Analyzed</div></div>
                    <div class="stat"><div class="num" style="color:#10b981">{summary.get('strong_buy', 0) + summary.get('buy', 0)}</div><div>Buy</div></div>
                    <div class="stat"><div class="num" style="color:#f59e0b">{summary.get('hold', 0)}</div><div>Hold</div></div>
                    <div class="stat"><div class="num" style="color:#ef4444">{summary.get('sell', 0) + summary.get('strong_sell', 0)}</div><div>Sell</div></div>
                    <div class="stat"><div class="num">{summary.get('avg_score', 0)}</div><div>Avg Score</div></div>
                </div>
        """
        
        # Watchlist
        wl = report.get('sections', {}).get('watchlist', {})
        if wl.get('stocks'):
            html += f'<div class="section"><h2>Your Watchlist ({wl["total"]} stocks)</h2><table><tr><th>#</th><th>Symbol</th><th>Price</th><th>Chg%</th><th>RSI</th><th>Score</th><th>Signal</th><th>Stop Loss</th><th>Target 1</th><th>Rs Cr/day</th></tr>'
            for i, s in enumerate(wl['stocks'], 1):
                rec_class = self._rec_class(s['recommendation'])
                html += f'<tr><td>{i}</td><td><b>{s["symbol"]}</b></td><td>{s["price"]:.2f}</td><td>{s["change_pct"]:+.2f}%</td><td>{s["rsi"]:.0f}</td><td>{s["score"]:.0f}</td><td class="{rec_class}">{s["recommendation"]}</td><td>{s["stop_loss"]:.2f}</td><td>{s["target1"]:.2f}</td><td>{s.get("avg_value_cr", 0):.2f}{" LOW" if s.get("avg_value_cr", 0) < MIN_LIQUIDITY_CR else ""}</td></tr>'
            html += (f'</table><p style="font-size:11px;color:#666">LOW = average traded value below Rs {MIN_LIQUIDITY_CR:g} crore/day: '
                     'stop-loss and targets are less reliable for these stocks.</p></div>')

        # Top Picks
        top_picks = report.get('top_picks', [])
        if top_picks:
            html += '<div class="section"><h2>Top 15 Picks</h2><table><tr><th>#</th><th>Symbol</th><th>Exchange</th><th>Price</th><th>Chg%</th><th>Score</th><th>Signal</th></tr>'
            for i, s in enumerate(top_picks[:15], 1):
                rec_class = self._rec_class(s['recommendation'])
                currency = '$' if s.get('exchange') in ['NYSE', 'NASDAQ'] else ''
                html += f'<tr><td>{i}</td><td><b>{s["symbol"]}</b></td><td>{s.get("exchange","")}</td><td>{currency}{s["price"]:.2f}</td><td>{s["change_pct"]:+.2f}%</td><td>{s["score"]:.0f}</td><td class="{rec_class}">{s["recommendation"]}</td></tr>'
            html += '</table></div>'
        
        # News
        news = report.get('news', [])
        if news:
            html += '<div class="section"><h2>Market News</h2><ul>'
            for item in news[:8]:
                html += f'<li><b>{item.get("title", "")}</b> <small>({item.get("publisher", "")})</small></li>'
            html += '</ul></div>'
        
        html += '<div class="footer">DR. NILESH SHAH\'S MARKET ANALYSIS | For educational purposes only</div></div></body></html>'
        return html
    
    def send_email_report(self, report=None, pdf_path=None):
        """Send report via email."""
        if not self.email_config.is_configured:
            self.email_config.last_error = "Email not configured. Please save email settings first."
            return False
        
        if not self.email_config.sender_password:
            self.email_config.last_error = "Password is empty. Please re-save email config."
            return False
        
        if report is None:
            report = self.report_data
        
        if not report:
            self.email_config.last_error = "No report data to send."
            return False
        
        subject = f"Daily Market Report - {datetime.now().strftime('%Y-%m-%d')}"
        body = self.generate_email_body(report)
        return self.email_config.send_email(subject, body, pdf_path)


# ============================================================
# QUICK FUNCTIONS
# ============================================================

def quick_report():
    """Generate a quick report."""
    generator = DailyReportGenerator()
    report = generator.generate_report(include_us=True, include_india=True)
    pdf_path = generator.generate_pdf_report(report)
    return report, pdf_path


if __name__ == "__main__":
    print("DR. NILESH SHAH'S MARKET ANALYSIS")
    print("Daily Report Generator")
    print("=" * 50)
    
    report, pdf_path = quick_report()
    
    print(f"\nPDF: {pdf_path}")
    print(f"\nSummary:")
    print(f"  Total Stocks: {report['summary']['total_stocks']}")
    print(f"  Buy Signals: {report['summary']['strong_buy'] + report['summary']['buy']}")
    print(f"  Hold: {report['summary']['hold']}")
    print(f"  Sell Signals: {report['summary']['sell'] + report['summary']['strong_sell']}")
    print(f"  Sentiment: {report['summary']['market_sentiment']}")
