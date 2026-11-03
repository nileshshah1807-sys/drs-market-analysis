#!/usr/bin/env python3
"""
Scoring for DR. NILESH SHAH'S MARKET ANALYSIS
=============================================
The indicator calculations, the 0-100 score and the stop-loss/targets - in one place.

Used by the app's scan (dr_shah_analysis.py), the backtest (backtest.py) and the daily emailed
report (daily_report.py), so all three always give a stock the same score and signal.
"""

import json
import logging

import numpy as np
import pandas as pd
import ta

from app_paths import DATA_DIR

try:
    import market_data
    MARKET_DATA_OK = True
except ImportError:
    MARKET_DATA_OK = False

logger = logging.getLogger(__name__)
WEIGHTS_FILE = DATA_DIR / "weights_config.json"


def safe_float(v, d=0.0):
    try:
        if v is None: return d
        val = float(v)
        return d if (pd.isna(val) or np.isnan(val) or np.isinf(val)) else val
    except: return d


# ============================================================
# INDICATORS
# ============================================================

def _wilder(values, period):
    """Wilder's smoothing, seeded with the average of the first `period` values."""
    out = np.empty(len(values))
    n = min(period, len(values))
    out[:n] = np.cumsum(values[:n]) / np.arange(1, n + 1)
    for i in range(n, len(values)):
        out[i] = (out[i - 1] * (period - 1) + values[i]) / period
    return out


def supertrend(high, low, close, period=10, multiplier=3.0):
    """SuperTrend line and direction (+1 bullish / -1 bearish) for every candle.
    The ATR uses Wilder's smoothing, as on TradingView and broker charts, so the signal
    flips on the same candle as theirs."""
    tr1 = high - low
    tr2 = np.abs(high - np.roll(close, 1))
    tr3 = np.abs(low - np.roll(close, 1))
    tr = np.maximum(tr1, np.maximum(tr2, tr3))
    tr[0] = tr1[0]
    atr = _wilder(tr, period)
    hl2 = (high + low) / 2
    basic_ub = hl2 + multiplier * atr
    basic_lb = hl2 - multiplier * atr
    final_ub, final_lb = basic_ub.copy(), basic_lb.copy()
    direction = np.ones(len(close))
    line = np.array(close, dtype=float)
    for i in range(1, len(close)):
        final_ub[i] = basic_ub[i] if (basic_ub[i] < final_ub[i-1] or close[i-1] > final_ub[i-1]) else final_ub[i-1]
        final_lb[i] = basic_lb[i] if (basic_lb[i] > final_lb[i-1] or close[i-1] < final_lb[i-1]) else final_lb[i-1]
        if direction[i-1] == 1:
            direction[i] = -1 if close[i] < final_lb[i] else 1
        else:
            direction[i] = 1 if close[i] > final_ub[i] else -1
        line[i] = final_lb[i] if direction[i] == 1 else final_ub[i]
    return line, direction


def indicators(df, days=None):
    """Every indicator the score uses, for the latest candle of `df`.

    `days`: a new listing's daily candles, when `df` holds its 1-hour candles (worked out
    from `df` if not given)."""
    if df is None or df.empty:
        raise ValueError("No data")

    # New listings come with 1-hour candles: every indicator below is then worked out on
    # those, but the day's change and the traded value are still per day
    hourly = MARKET_DATA_OK and market_data.is_hourly(df)
    if not hourly:
        days = df
    elif days is None:
        days = market_data.daily_bars(df)

    price = safe_float(df['Close'].iloc[-1])
    prev = safe_float(days['Close'].iloc[-2]) if len(days) > 1 else price

    # Liquidity: average daily traded value over the last 20 sessions, in Rs crore
    try: liquidity_cr = safe_float((days['Close'] * days['Volume']).tail(20).mean() / 1e7)
    except: liquidity_cr = 0.0

    # RSI
    try: rsi = safe_float(ta.momentum.RSIIndicator(df['Close'], 14).rsi().iloc[-1], 50)
    except: rsi = 50.0

    # MACD (None when there isn't enough history - ~35 days - so it scores neutral instead of bearish)
    try:
        m = ta.trend.MACD(df['Close'])
        macd = {'macd': safe_float(m.macd().iloc[-1], None), 'signal': safe_float(m.macd_signal().iloc[-1], None),
                'hist': safe_float(m.macd_diff().iloc[-1], None)}
    except: macd = {'macd': None, 'signal': None, 'hist': None}

    # Moving Averages - None when the stock is too new for that average (it's then skipped
    # by the scorer; treating it as equal to the price used to count as a bearish signal)
    try:
        ma = {
            'sma20': safe_float(ta.trend.SMAIndicator(df['Close'], 20).sma_indicator().iloc[-1], None),
            'sma50': safe_float(ta.trend.SMAIndicator(df['Close'], 50).sma_indicator().iloc[-1], None) if len(df) >= 50 else None,
            'sma200': safe_float(ta.trend.SMAIndicator(df['Close'], 200).sma_indicator().iloc[-1], None) if len(df) >= 200 else None,
            'ema12': safe_float(ta.trend.EMAIndicator(df['Close'], 12).ema_indicator().iloc[-1], None),
            'ema26': safe_float(ta.trend.EMAIndicator(df['Close'], 26).ema_indicator().iloc[-1], None)
        }
    except: ma = {'sma20': None, 'sma50': None, 'sma200': None, 'ema12': None, 'ema26': None}

    # Bollinger
    try:
        bb = ta.volatility.BollingerBands(df['Close'])
        boll = {'upper': safe_float(bb.bollinger_hband().iloc[-1]), 'lower': safe_float(bb.bollinger_lband().iloc[-1])}
    except: boll = {'upper': price * 1.02, 'lower': price * 0.98}

    # Stochastic
    try:
        s = ta.momentum.StochasticOscillator(df['High'], df['Low'], df['Close'])
        stoch = {'k': safe_float(s.stoch().iloc[-1], 50), 'd': safe_float(s.stoch_signal().iloc[-1], 50)}
    except: stoch = {'k': 50, 'd': 50}

    # ADX: how strong the trend is; +DI above -DI means the trend is up
    try:
        a = ta.trend.ADXIndicator(df['High'], df['Low'], df['Close'])
        adx, adx_pos, adx_neg = safe_float(a.adx().iloc[-1], 25), safe_float(a.adx_pos().iloc[-1], None), safe_float(a.adx_neg().iloc[-1], None)
    except: adx, adx_pos, adx_neg = 25.0, None, None

    # OBV
    try:
        obv_s = ta.volume.OnBalanceVolumeIndicator(df['Close'], df['Volume']).on_balance_volume()
        obv_curr = safe_float(obv_s.iloc[-1])
        obv_prev = safe_float(obv_s.iloc[-5]) if len(obv_s) >= 5 else obv_curr
        obv_trend = ((obv_curr - obv_prev) / abs(obv_prev) * 100) if obv_prev != 0 else 0
    except: obv_trend = 0.0

    # Williams %R
    try: wr = safe_float(ta.momentum.WilliamsRIndicator(df['High'], df['Low'], df['Close']).williams_r().iloc[-1], -50)
    except: wr = -50.0

    # CCI
    try: cci = safe_float(ta.trend.CCIIndicator(df['High'], df['Low'], df['Close']).cci().iloc[-1], 0)
    except: cci = 0.0

    # ATR
    try: atr = safe_float(ta.volatility.AverageTrueRange(df['High'], df['Low'], df['Close'], 14).average_true_range().iloc[-1])
    except: atr = price * 0.02
    if atr == 0: atr = price * 0.02

    # SuperTrend
    try:
        line, direction = supertrend(df['High'].values, df['Low'].values, df['Close'].values)
        st_sig = 'BUY' if direction[-1] == 1 else 'SELL'
        st_dir = 'BULLISH' if direction[-1] == 1 else 'BEARISH'
        st_val = round(safe_float(line[-1]), 2)
    except Exception as e:
        logger.warning(f"SuperTrend error: {e}")
        st_val, st_sig, st_dir = price, 'HOLD', 'NEUTRAL'

    # VWAP
    try:
        tp = (df['High'] + df['Low'] + df['Close']) / 3
        vwap = safe_float((tp * df['Volume']).rolling(20).sum().iloc[-1] / df['Volume'].rolling(20).sum().iloc[-1])
        if vwap == 0: vwap = price
        vwap_sig = 'BULLISH' if price > vwap * 1.02 else 'BEARISH' if price < vwap * 0.98 else 'NEUTRAL'
    except:
        vwap, vwap_sig = price, 'NEUTRAL'

    # Support and resistance (for the stop-loss and targets)
    try: levels = support_resistance(df, atr)
    except Exception as e:
        logger.warning(f"Support/resistance error: {e}")
        levels = {'support': [], 'resistance': []}

    return {
        'price': price, 'prev': prev, 'liquidity_cr': liquidity_cr, 'rsi': rsi, 'macd': macd, 'ma': ma,
        'boll': boll, 'stoch': stoch, 'adx': adx, 'adx_pos': adx_pos, 'adx_neg': adx_neg, 'obv_trend': obv_trend,
        'wr': wr, 'cci': cci, 'atr': atr,
        'supertrend': {'val': st_val, 'sig': st_sig, 'dir': st_dir},
        'vwap': {'val': vwap, 'sig': vwap_sig},
        'levels': levels, 'hourly': hourly, 'days': len(days)
    }


LEVEL_LOOKBACK = 250   # candles searched for turning points (about a year of daily candles)
LEVEL_WINDOW = 5       # a turning point is the highest / lowest candle among this many on each side


def support_resistance(df, atr):
    """Prices where the stock has turned before: {'support': [...], 'resistance': [...]}, each a
    list of (price, times tested) with the level nearest today's price first.

    A level is a swing high or low of the last LEVEL_LOOKBACK candles. Turning points within
    half an ATR of each other are one level, tested that many times. A level above today's
    price is resistance and one below it is support, whichever it was when it formed."""
    high = df['High'].values[-LEVEL_LOOKBACK:]
    low = df['Low'].values[-LEVEL_LOOKBACK:]
    price = float(df['Close'].iloc[-1])
    w = LEVEL_WINDOW
    points = []
    for i in range(w, len(high) - w):
        if high[i] == high[i - w:i + w + 1].max():
            points.append(float(high[i]))
        if low[i] == low[i - w:i + w + 1].min():
            points.append(float(low[i]))
    if len(high) > w:   # the last few candles can't be confirmed turns yet, but the price has just turned there
        points += [float(high[-w:].max()), float(low[-w:].min())]

    tol = max(atr * 0.5, price * 0.002)
    groups = []   # [sum of prices, how many]
    for p in sorted(p for p in points if p > 0):
        if groups and p - groups[-1][0] / groups[-1][1] <= tol:
            groups[-1][0] += p
            groups[-1][1] += 1
        else:
            groups.append([p, 1])
    levels = [(total / n, n) for total, n in groups]
    return {'support': [lv for lv in reversed(levels) if lv[0] < price],
            'resistance': [lv for lv in levels if lv[0] > price]}


# ============================================================
# SCORER
# ============================================================

# The score a stock needs for each signal, checked from the top down; below the last one: STRONG SELL.
# Chosen with the backtest (5 years of the user's watchlist, set on the older 60% of dates and checked
# on the newer 40%): the only set tried where strong buy > buy > hold > sell > strong sell on both
# 10- and 20-day holds. The old 75/60/45/30 gave no strong buys at all with the current weights.
CUTOFFS = (('STRONG BUY', 62), ('BUY', 56), ('HOLD', 44), ('SELL', 37))


def rec_for(total):
    """The signal for a 0-100 score."""
    return next((rec for rec, cut in CUTOFFS if total >= cut), 'STRONG SELL')


# Four indicators that all measure the same thing - a price stretched low (oversold) - so their
# weights add up to how much the score leans on that one idea
OVERSOLD = ('rsi', 'boll', 'stoch', 'mom')


def oversold_share(weights):
    """Percent of the score that comes from the "oversold" indicators."""
    return sum(weights.get(k, 0) for k in OVERSOLD)


def cutoff_ranges():
    """[(signal, lowest score, highest score)] for showing the cut-offs: STRONG BUY 62-100 ... STRONG SELL 0-36."""
    lows = [c for _, c in CUTOFFS] + [0]
    highs = [100] + [c - 1 for _, c in CUTOFFS]
    return list(zip([r for r, _ in CUTOFFS] + ['STRONG SELL'], lows, highs))


class Scorer:
    WEIGHTS = {'rsi': 20, 'macd': 5, 'ma': 5, 'boll': 20, 'stoch': 15, 'adx': 5, 'vol': 5, 'mom': 15, 'st': 5, 'vwap': 5}
    DEFAULT_WEIGHTS = dict(WEIGHTS)

    @classmethod
    def score(cls, data):
        scores = {
            'rsi': cls._rsi(data['rsi']),
            'macd': cls._macd(data['macd']),
            'ma': cls._ma(data['price'], data['ma']),
            'boll': cls._boll(data['price'], data['boll']),
            'stoch': cls._stoch(data['stoch']),
            'adx': cls._adx(data['adx'], data.get('adx_pos'), data.get('adx_neg')),
            'vol': cls._vol(data['obv_trend']),
            'mom': cls._mom(data['wr'], data['cci']),
            'st': cls._st(data['supertrend']),
            'vwap': cls._vwap(data['vwap'])
        }
        total = sum(scores[k] * cls.WEIGHTS[k] / 100 for k in scores)
        return {'total': round(total, 1), 'breakdown': scores, 'rec': rec_for(total)}

    @staticmethod
    def _rsi(v):
        v = safe_float(v, 50)
        return 90 if v < 20 else 75 if v < 30 else 60 if v < 40 else 50 if v < 50 else 45 if v < 60 else 35 if v < 70 else 20 if v < 80 else 10

    @staticmethod
    def _macd(m):
        if m.get('hist') is None or m.get('macd') is None or m.get('signal') is None:
            return 50   # not enough history for MACD - neutral
        s = 50 + (25 if safe_float(m['hist']) > 0 else -25) + (15 if safe_float(m['macd']) > safe_float(m['signal']) else -15)
        return max(0, min(100, s))

    @staticmethod
    def _ma(price, ma):
        s = 50
        for v in ma.values():
            if v is None:
                continue   # stock too new for this average - skip rather than count as bearish
            s += 10 if price > safe_float(v) else -10
        s50, s200 = ma.get('sma50'), ma.get('sma200')
        if s50 is not None and s200 is not None and s50 > 0 and s200 > 0:
            s += 10 if s50 > s200 else -10
        return max(0, min(100, s))

    @staticmethod
    def _boll(price, b):
        u, l = safe_float(b['upper']), safe_float(b['lower'])
        if u == l: return 50
        pos = (price - l) / (u - l)
        return 80 if pos < 0.1 else 65 if pos < 0.3 else 50 if pos < 0.5 else 40 if pos < 0.7 else 30 if pos < 0.9 else 15

    @staticmethod
    def _stoch(s):
        k, d = safe_float(s['k'], 50), safe_float(s['d'], 50)
        sc = 50 + (30 if k < 20 else 15 if k < 30 else -30 if k > 80 else -15 if k > 70 else 0)
        return max(0, min(100, sc + (10 if k > d else -10)))

    @staticmethod
    def _adx(v, di_pos=None, di_neg=None):
        # A strong trend scores high only when it is UP (+DI above -DI); a strong fall scores low.
        # (It used to score any strong trend high - a steep fall included.) No direction known: neutral.
        if di_pos is None or di_neg is None or di_pos != di_pos or di_neg != di_neg:
            return 50
        v = safe_float(v, 25)
        strength = 0 if v <= 20 else 10 if v <= 30 else 20 if v <= 40 else 30
        return 50 + strength if di_pos >= di_neg else 50 - strength

    @staticmethod
    def _vol(v):
        v = safe_float(v)
        return 80 if v > 10 else 65 if v > 5 else 55 if v > 0 else 45 if v > -5 else 35 if v > -10 else 20

    @staticmethod
    def _mom(wr, cci):
        s = 50
        wr = safe_float(wr, -50)
        s += 20 if wr < -80 else (-20 if wr > -20 else 0)
        cci = safe_float(cci, 0)
        s += 15 if cci < -100 else (-15 if cci > 100 else 0)
        return max(0, min(100, s))

    @staticmethod
    def _st(st):
        sig, d = st.get('sig', 'HOLD'), st.get('dir', 'NEUTRAL')
        if sig == 'BUY' and d == 'BULLISH': return 85
        elif sig == 'BUY': return 65
        elif sig == 'SELL' and d == 'BEARISH': return 15
        elif sig == 'SELL': return 35
        return 50

    @staticmethod
    def _vwap(v):
        sig = v.get('sig', 'NEUTRAL')
        return 70 if sig == 'BULLISH' else 30 if sig == 'BEARISH' else 50


def load_weights():
    """Use the scoring weights saved by the app (weights_config.json); ignored unless they're
    complete and total 100."""
    try:
        if WEIGHTS_FILE.exists():
            with open(WEIGHTS_FILE, 'r') as f:
                data = json.load(f)
            weights = {k: int(data[k]) for k in Scorer.DEFAULT_WEIGHTS}
            if sum(weights.values()) == 100 and min(weights.values()) >= 0:
                Scorer.WEIGHTS.update(weights)
    except Exception as e:
        logger.error(f"Could not load weights: {e}")


class TargetCalc:
    """Stop-loss and three targets.

    They sit at the stock's own support and resistance (data['levels']): the stop just beyond
    the nearest level behind the price, the targets at the next levels ahead of it. So the
    risk:reward differs from stock to stock - little room under a nearby resistance, plenty
    when the next one is far. Where there is no usable level, a multiple of the ATR is used
    instead (which is all the app used before, and gave every stock the same risk:reward)."""

    MIN_STOP = 0.75                   # ATRs. A stop nearer than this would be hit by ordinary daily movement
    MAX_STOP = 3.0                    # ATRs. A level further than this is too far away to be the stop
    MIN_TARGET = 0.5                  # ATRs. A level nearer than this isn't a target: the price is already at it
    STOP_PAD = 0.25                   # ATRs. The stop goes this far beyond its level, not on it
    ATR_STOP = 1.5                    # ATRs. Stop, when no level can be used
    ATR_TARGETS = (1.5, 2.5, 4.0)     # ATRs. Targets 1-3, when no level can be used

    @classmethod
    def calc(cls, data, rec):
        price = data['price']
        atr = data['atr']
        if price <= 0: return {}

        short = rec in ['SELL', 'STRONG SELL']
        pos = 'SHORT' if short else 'LONG' if rec in ['STRONG BUY', 'BUY'] else 'HOLD'
        side = -1 if short else 1     # +1: targets above the price and the stop below; -1: the reverse
        levels = data.get('levels') or {}
        behind = levels.get('resistance' if short else 'support') or []
        ahead = levels.get('support' if short else 'resistance') or []
        behind_name, ahead_name = ('resistance', 'support') if short else ('support', 'resistance')

        def floor(v):   # a price level is never zero or negative, however wild the stock
            return max(v, 0.01)

        def tested(n):
            return f", tested {n} times" if n > 1 else ""

        # Stop: beyond the nearest level behind the price that leaves the stock room to move
        sl = floor(price - side * atr * cls.ATR_STOP)
        basis = {'sl': f"{cls.ATR_STOP:g} x ATR from the price (no {behind_name} within reach)"}
        for level, n in behind:
            gap = abs(price - level) / atr + cls.STOP_PAD
            if gap < cls.MIN_STOP:
                continue
            if gap <= cls.MAX_STOP:
                sl = floor(level - side * atr * cls.STOP_PAD)
                basis['sl'] = f"just {'above' if short else 'below'} {behind_name} at {level:,.2f}{tested(n)}"
            break

        # Targets: the next levels ahead of the price, then ATR steps once those run out
        targets, notes = [], []
        for level, n in ahead:
            if abs(level - (targets[-1] if targets else price)) < atr * cls.MIN_TARGET:
                continue
            targets.append(level)
            notes.append(f"{ahead_name}{tested(n)}")
            if len(targets) == 3:
                break
        for k in cls.ATR_TARGETS[len(targets):]:
            t = price + side * atr * k
            if targets and side * (t - targets[-1]) < atr:     # keep it beyond the previous target
                t = targets[-1] + side * atr
            targets.append(floor(t))
            notes.append(f"{k:g} x ATR from the price (no {ahead_name} level there)")
        basis.update(zip(('t1', 't2', 't3'), notes))

        risk = abs(price - sl)
        reward = abs((targets[0] if pos == 'HOLD' else targets[1]) - price)   # main target: T2 (T1 for a HOLD)
        r = {'price': round(price, 2), 'atr': round(atr, 2),
             'sl': round(sl, 2), 't1': round(targets[0], 2), 't2': round(targets[1], 2), 't3': round(targets[2], 2),
             'risk': round(risk, 2), 'reward': round(reward, 2), 'pos': pos, 'basis': basis}
        r['rr'] = round(r['reward'] / r['risk'], 2) if r.get('risk', 0) > 0 else 0
        return r


# ------------------------------------------------------------
# Relative strength vs the Nifty 50
# ------------------------------------------------------------

NIFTY_SYMBOL = '^NSEI'
RS_PERIODS = {'1M': 21, '3M': 63, '6M': 126}     # trading days


def relative_strength(df, index_df, periods=RS_PERIODS):
    """Stock return minus Nifty 50 return over each period, in percentage points
    (+5.0 = the stock beat the Nifty by 5%). None where there isn't enough history."""
    out = {label: None for label in periods}
    if index_df is None or len(index_df) == 0 or df is None or len(df) < 2:
        return out
    index_close = index_df['Close']
    for label, n in periods.items():
        if len(df) <= n:
            continue
        start, end = df.index[-1 - n], df.index[-1]
        s0, s1 = safe_float(df['Close'].iloc[-1 - n]), safe_float(df['Close'].iloc[-1])
        i0, i1 = safe_float(index_close.asof(start)), safe_float(index_close.asof(end))
        if s0 > 0 and i0 > 0 and i1 > 0:
            out[label] = round((s1 / s0 - i1 / i0) * 100, 2)
    return out
