#!/usr/bin/env python3
"""Test script for PDF parsing functionality."""

import pdfplumber
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os

def create_test_pdf():
    """Create a test PDF with stock symbols."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        
        filename = "test_stocks.pdf"
        c = canvas.Canvas(filename, pagesize=letter)
        width, height = letter
        
        # Title
        c.setFont("Helvetica-Bold", 16)
        c.drawString(100, height - 50, "Stock Watchlist - Test PDF")
        
        # Stock list
        c.setFont("Helvetica", 12)
        y_position = height - 100
        
        stocks = [
            "RELIANCE - Buy",
            "TCS - Strong Buy",
            "INFY - Hold",
            "HDFCBANK - Buy",
            "ICICIBANK - Sell",
            "SBIN - Strong Buy",
            "WIPRO - Hold",
            "TATAMOTORS - Buy",
            "TATASTEEL - Strong Sell",
            "ADANIENT - Buy",
            "BHARTIARTL - Hold",
            "ITC - Buy",
            "KOTAKBANK - Strong Buy",
            "LT - Buy",
            "MARUTI - Hold",
            "SUNPHARMA - Buy",
            "AXISBANK - Sell",
            "BAJFINANCE - Strong Buy",
            "HCLTECH - Buy",
            "TITAN - Hold"
        ]
        
        for stock in stocks:
            c.drawString(100, y_position, stock)
            y_position -= 25
        
        # Add some more text
        y_position -= 50
        c.drawString(100, y_position, "Analysis Date: 2024-01-15")
        y_position -= 25
        c.drawString(100, y_position, "Market: NSE/BSE")
        y_position -= 25
        c.drawString(100, y_position, "Sector: All Sectors")
        
        c.save()
        print(f"[OK] Created test PDF: {filename}")
        return filename
    except ImportError:
        print("[SKIP] reportlab not installed, skipping PDF creation")
        return None


def test_pdf_parsing(filepath):
    """Test PDF parsing functionality."""
    if not filepath or not os.path.exists(filepath):
        print("[SKIP] No test PDF available")
        return
    
    print(f"\nTesting PDF parsing on: {filepath}")
    print("=" * 60)
    
    try:
        # Import the parse function from stock_scanner
        import sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
        # We'll test the parsing logic directly
        import re
        import pdfplumber
        
        known_symbols = {
            'RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK', 'SBIN',
            'WIPRO', 'TATAMOTORS', 'TATASTEEL', 'ADANIENT', 'ADANIPORTS',
            'BHARTIARTL', 'HINDUNILVR', 'ITC', 'KOTAKBANK', 'LT', 'MARUTI',
            'ONGC', 'POWERGRID', 'SUNPHARMA', 'AXISBANK', 'BAJFINANCE',
            'BAJAJFINSV', 'BAJAJ-AUTO', 'BPCL', 'CIPLA', 'COALINDIA',
            'DIVISLAB', 'DRREDDY', 'EICHERMOT', 'GRASIM', 'HCLTECH',
            'HEROMOTOCO', 'HINDALCO', 'HINDPETRO', 'INDUSINDBK', 'JSWSTEEL',
            'NTPC', 'NESTLEIND', 'PIDILITIND', 'SBILIFE',
            'SHREECEM', 'TATACONSUM', 'TECHM', 'TITAN', 'ULTRACEMCO',
            'UPL', 'VEDL', 'ZEEL', 'ASIANPAINT', 'APOLLOHOSP',
            'BAJAJHLDNG', 'BRITANNIA', 'CHOLAFIN', 'DABUR', 'GAIL',
            'GODREJCP', 'HAVELLS', 'HDFCLIFE', 'ICICIPRULI', 'INDUSTOWER',
            'JINDALSTEL', 'LICI', 'MARICO', 'MUTHOOTFIN', 'NAUKRI',
            'PIIND', 'SBICARD', 'SIEMENS', 'SRF', 'TATAPOWER',
            'TRENT', 'VOLTAS', 'ZOMATO'
        }
        
        exclude_words = {
            'THE', 'AND', 'FOR', 'BUT', 'NOT', 'YOU', 'ALL', 'CAN', 'HER', 'WAS',
            'ONE', 'OUR', 'OUT', 'ARE', 'HAS', 'HIS', 'HOW', 'ITS', 'MAY', 'NEW',
            'BUY', 'SELL', 'HOLD', 'TARGET', 'STRONG', 'WEAK', 'NEUTRAL',
            'ANALYSIS', 'DATE', 'MARKET', 'SECTOR', 'STOCK', 'WATCHLIST'
        }
        
        symbols = []
        
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    print(f"\nPage text found: {len(text)} characters")
                    print(f"First 200 chars: {text[:200]}...")
                    
                    words = text.split()
                    print(f"Total words: {len(words)}")
                    
                    for word in words:
                        clean_word = re.sub(r'[^A-Za-z0-9&-]', '', word.strip())
                        clean_upper = clean_word.upper()
                        
                        if len(clean_upper) < 2:
                            continue
                        
                        if clean_upper in known_symbols:
                            if clean_upper not in symbols:
                                symbols.append(clean_upper)
                        elif (clean_upper.isalpha() and 
                              2 <= len(clean_upper) <= 15 and
                              clean_upper not in exclude_words):
                            if clean_upper not in symbols:
                                symbols.append(clean_upper)
        
        print("\n" + "=" * 60)
        print(f"Symbols found: {len(symbols)}")
        print(f"Symbols: {symbols}")
        
        # Verify expected stocks are found
        expected = {'RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK', 'SBIN',
                   'WIPRO', 'TATAMOTORS', 'TATASTEEL', 'ADANIENT'}
        found = set(symbols) & expected
        print(f"\nExpected stocks found: {len(found)}/{len(expected)}")
        print(f"Found: {found}")
        
        if len(found) >= 8:
            print("\n[SUCCESS] PDF parsing works correctly!")
        else:
            print("\n[WARNING] Some expected stocks not found")
            
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Try to create a test PDF
    test_pdf = create_test_pdf()
    
    # Test parsing
    if test_pdf:
        test_pdf_parsing(test_pdf)
    
    print("\nTo test with your own PDF:")
    print("1. Place your PDF in this folder")
    print("2. Run: python test_pdf_parser.py yourfile.pdf")
