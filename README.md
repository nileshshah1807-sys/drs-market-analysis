# Indian Stock Technical Scanner & Recommender

A powerful desktop application for technical analysis of Indian stocks (NSE/BSE) that scans your watchlist, calculates technical indicators, scores stocks 0-100, and provides buy/sell recommendations.

## Quick Start

### Windows
1. Double-click `run_app.bat`
2. Or open Command Prompt and run:
   ```
   pip install -r requirements.txt
   python stock_scanner.py
   ```

### Linux/Mac
1. Open Terminal in this folder
2. Run:
   ```bash
   chmod +x run_app.sh
   ./run_app.sh
   ```
   Or manually:
   ```bash
   pip3 install -r requirements.txt
   python3 stock_scanner.py
   ```

## Features

- **Technical Analysis Engine** with 10+ indicators
- **Scoring System** (0-100) based on weighted parameters
- **Recommendations**: Strong Buy, Buy, Hold, Sell, Strong Sell
- **Watchlist Management**: Add, delete, import, export
- **Import Support**: JSON, CSV, TXT, Excel (.xlsx, .xls), PDF
- **Export Results**: Excel with formatting, CSV
- **Color-coded Results** for quick decision making

## Technical Indicators Used

| Indicator | Weight | Description |
|-----------|--------|-------------|
| RSI (14) | 15% | Relative Strength Index |
| MACD | 15% | Moving Average Convergence Divergence |
| Moving Averages | 20% | SMA 20, 50, 200 & EMA 12, 26 |
| Bollinger Bands | 10% | Price volatility bands |
| Stochastic | 10% | Stochastic Oscillator |
| ADX | 10% | Average Directional Index |
| Volume (OBV) | 10% | On Balance Volume |
| Momentum | 10% | Williams %R & CCI |

## Scoring System

| Score | Recommendation | Meaning |
|-------|----------------|---------|
| 75-100 | STRONG BUY | High confidence buy signal |
| 60-74 | BUY | Moderate buy signal |
| 45-59 | HOLD | Neutral position |
| 30-44 | SELL | Consider selling |
| 0-29 | STRONG SELL | High confidence sell signal |

## How to Use

1. **Add stocks** to watchlist (e.g., RELIANCE, TCS, INFY, HDFCBANK)
2. Click **"Scan All Stocks"**
3. View results in Scan Results tab
4. Double-click any stock for detailed breakdown
5. Export results as needed

## Popular Indian Stock Symbols

```
RELIANCE    - Reliance Industries
TCS         - Tata Consultancy Services
INFY        - Infosys
HDFCBANK    - HDFC Bank
ICICIBANK   - ICICI Bank
SBIN        - State Bank of India
WIPRO       - Wipro
TATAMOTORS  - Tata Motors
TATASTEEL   - Tata Steel
ADANIENT    - Adani Enterprises
BHARTIARTL  - Bharti Airtel
ITC         - ITC Limited
KOTAKBANK   - Kotak Mahindra Bank
LT          - Larsen & Toubro
MARUTI      - Maruti Suzuki
```

## Troubleshooting

### "tkinter not available" error
- **Windows**: Reinstall Python and check "tcl/tk and IDLE" option
- **Linux**: `sudo apt-get install python3-tk`
- **Mac**: `brew install python-tk`

### "No module named..." error
Run: `pip install -r requirements.txt`

### Application doesn't start
1. Check Python version (3.7+ required)
2. Run `python test_app.py` to verify dependencies
3. Check error message for specific issue

## Files

- `stock_scanner.py` - Main application
- `requirements.txt` - Python dependencies
- `run_app.bat` - Windows launcher
- `run_app.sh` - Linux/Mac launcher
- `test_app.py` - Test script for dependencies
- `sample_watchlist.json` - Sample watchlist
- `watchlist.json` - Your saved watchlist (auto-created)

## Disclaimer

This application is for **educational and informational purposes only**. The recommendations are based on technical analysis and should NOT be considered as financial advice. Always do your own research and consult a financial advisor before investing.
