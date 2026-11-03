#!/usr/bin/env python3
"""
Strategy Backtester for DR. NILESH SHAH'S MARKET ANALYSIS
=========================================================
Answers: "Does the 0-100 score actually predict returns?"

For every stock and every past trading day it rebuilds the app's indicator scores
(RS rating, MACD, MAs, Bollinger, Stochastic, ADX, OBV, Momentum, SuperTrend, VWAP) using
only data available on that day, then measures what the stock did over the next
5 / 10 / 20 trading days.

Reported:
- Average forward return and win rate for each recommendation (STRONG BUY ... STRONG SELL)
- Each indicator's predictive power (rank correlation "IC" with forward return)
- Suggested weights learned on the older 60% of history and checked on the newer 40%
  (out-of-sample), so they aren't just fitted to the same data they're judged on

The component scoring functions are taken from the app's Scorer class, so the backtest
scores stocks exactly the way the live scan does.
"""

import numpy as np
import pandas as pd
import ta

from scoring import supertrend, rs_rating_series

WARMUP = 200                # rows needed before the first score (so the 200-day SMA exists, as in live scans)
HORIZONS = (5, 10, 20)       # forward return horizons, in trading days
TRAIN_FRACTION = 0.6         # older 60% of dates = "train", newer 40% = "test"
MIN_STOCKS_FOR_EXCESS = 5    # with fewer stocks, raw returns are used instead of returns vs. the group

COMPONENT_NAMES = {
    'rs': 'RS Rating', 'macd': 'MACD', 'ma': 'Moving Avg', 'boll': 'Bollinger',
    'stoch': 'Stochastic', 'adx': 'ADX', 'vol': 'Volume (OBV)', 'mom': 'Momentum',
    'st': 'SuperTrend', 'vwap': 'VWAP',
}
REC_ORDER = ['STRONG BUY', 'BUY', 'HOLD', 'SELL', 'STRONG SELL']


def rec_from_total(total: float) -> str:
    """Same thresholds as Scorer.score()."""
    return ('STRONG BUY' if total >= 75 else 'BUY' if total >= 60 else 'HOLD' if total >= 45
            else 'SELL' if total >= 30 else 'STRONG SELL')


# ------------------------------------------------------------
# Indicators (vectorised versions of Analyzer.analyze)
# ------------------------------------------------------------

def indicator_frame(df: pd.DataFrame, index_df: pd.DataFrame = None) -> pd.DataFrame:
    """All indicator values for every row, with the same NaN fallbacks the live scan uses.
    `index_df`: Nifty 50 history, for the RS rating (without it the RS rating scores neutral)."""
    close, high, low, vol = df['Close'], df['High'], df['Low'], df['Volume'].fillna(0)
    price = close
    out = pd.DataFrame(index=df.index)
    out['price'] = price
    out['liquidity_cr'] = (close * vol).rolling(20).mean() / 1e7   # avg daily traded value, Rs crore
    out['rs_rating'] = (rs_rating_series(close, index_df['Close']) if index_df is not None and len(index_df)
                        else pd.Series(np.nan, index=df.index))
    # MACD and moving averages stay NaN while there isn't enough history; the scorer skips them
    m = ta.trend.MACD(close)
    out['macd'] = m.macd()
    out['macd_signal'] = m.macd_signal()
    out['macd_hist'] = m.macd_diff()
    out['sma20'] = ta.trend.SMAIndicator(close, 20).sma_indicator()
    out['sma50'] = ta.trend.SMAIndicator(close, 50).sma_indicator()
    out['sma200'] = ta.trend.SMAIndicator(close, 200).sma_indicator()
    out['ema12'] = ta.trend.EMAIndicator(close, 12).ema_indicator()
    out['ema26'] = ta.trend.EMAIndicator(close, 26).ema_indicator()
    bb = ta.volatility.BollingerBands(close)
    out['bb_upper'] = bb.bollinger_hband().fillna(0)
    out['bb_lower'] = bb.bollinger_lband().fillna(0)
    s = ta.momentum.StochasticOscillator(high, low, close)
    out['stoch_k'] = s.stoch().fillna(50)
    out['stoch_d'] = s.stoch_signal().fillna(50)
    out['adx'] = ta.trend.ADXIndicator(high, low, close).adx().fillna(25)
    obv = ta.volume.OnBalanceVolumeIndicator(close, vol).on_balance_volume()
    obv_prev = obv.shift(4)   # live scan compares with obv.iloc[-5]
    trend = (obv - obv_prev) / obv_prev.abs() * 100
    out['obv_trend'] = trend.where(obv_prev != 0, 0).replace([np.inf, -np.inf], 0).fillna(0)
    out['wr'] = ta.momentum.WilliamsRIndicator(high, low, close).williams_r().fillna(-50)
    out['cci'] = ta.trend.CCIIndicator(high, low, close).cci().fillna(0)
    out['st_dir'] = supertrend(high.values, low.values, close.values)[1]   # the scan's own SuperTrend
    tp = (high + low + close) / 3
    vwap = (tp * vol).rolling(20).sum() / vol.rolling(20).sum()
    vwap = vwap.replace([np.inf, -np.inf], np.nan).fillna(0)
    out['vwap'] = vwap.where(vwap != 0, price)
    return out


def component_scores(ind: pd.DataFrame, scorer) -> pd.DataFrame:
    """Score each indicator (0-100) for every row using the app's Scorer rules."""
    def opt(v):   # NaN -> None, like Analyzer.analyze for indicators without enough history
        return None if v != v else v

    rows = []
    for r in ind.itertuples(index=False):
        p = r.price
        vwap_sig = 'BULLISH' if p > r.vwap * 1.02 else 'BEARISH' if p < r.vwap * 0.98 else 'NEUTRAL'
        st = {'sig': 'BUY', 'dir': 'BULLISH'} if r.st_dir == 1 else {'sig': 'SELL', 'dir': 'BEARISH'}
        rows.append((
            scorer._rs(opt(r.rs_rating)),
            scorer._macd({'macd': opt(r.macd), 'signal': opt(r.macd_signal), 'hist': opt(r.macd_hist)}),
            scorer._ma(p, {'sma20': opt(r.sma20), 'sma50': opt(r.sma50), 'sma200': opt(r.sma200),
                           'ema12': opt(r.ema12), 'ema26': opt(r.ema26)}),
            scorer._boll(p, {'upper': r.bb_upper, 'lower': r.bb_lower}),
            scorer._stoch({'k': r.stoch_k, 'd': r.stoch_d}),
            scorer._adx(r.adx),
            scorer._vol(r.obv_trend),
            scorer._mom(r.wr, r.cci),
            scorer._st(st),
            scorer._vwap({'sig': vwap_sig}),
        ))
    return pd.DataFrame(rows, index=ind.index, columns=list(COMPONENT_NAMES))


# ------------------------------------------------------------
# Statistics
# ------------------------------------------------------------

def _ic(a: pd.Series, b: pd.Series) -> float:
    """Spearman rank correlation (information coefficient)."""
    if len(a) < 30 or a.nunique() < 2:
        return float('nan')
    # Spearman = Pearson correlation of the ranks. Computed directly because pandas'
    # corr(method='spearman') needs SciPy, which the packaged .exe doesn't include.
    return float(a.rank().corr(b.rank()))


def _total(samples: pd.DataFrame, weights: dict) -> pd.Series:
    return sum(samples[k] * weights.get(k, 0) / 100 for k in COMPONENT_NAMES)


def _evaluate(samples: pd.DataFrame, weights: dict, target: str, raw: str) -> dict:
    """IC, top-vs-bottom spread and per-recommendation stats for one weight set."""
    total = _total(samples, weights)
    recs = total.apply(rec_from_total)
    pct = total.rank(pct=True)
    top, bottom = samples.loc[pct >= 0.8, target], samples.loc[pct <= 0.2, target]
    buckets = []
    for rec in REC_ORDER:
        sel = samples.loc[recs == rec]
        if len(sel):
            buckets.append({'rec': rec, 'n': len(sel), 'avg_return': sel[raw].mean() * 100,
                            'win_rate': (sel[raw] > 0).mean() * 100,
                            'vs_avg': sel[target].mean() * 100})
        else:
            buckets.append({'rec': rec, 'n': 0, 'avg_return': None, 'win_rate': None, 'vs_avg': None})
    return {
        'ic': _ic(total, samples[target]),
        # average return of the 20% best-scored samples minus the 20% worst-scored
        'spread': (top.mean() - bottom.mean()) * 100 if len(top) and len(bottom) else float('nan'),
        'buckets': buckets,
    }


def suggest_weights(ics: dict) -> dict:
    """Integer weights summing to 100, proportional to each indicator's positive IC."""
    pos = {k: max(v, 0) if v == v else 0 for k, v in ics.items()}
    total = sum(pos.values())
    if total <= 0:
        return None
    raw = {k: v / total * 100 for k, v in pos.items()}
    weights = {k: int(v) for k, v in raw.items()}
    # hand out the remaining points by largest remainder
    for k in sorted(raw, key=lambda k: raw[k] - weights[k], reverse=True)[:100 - sum(weights.values())]:
        weights[k] += 1
    return weights


# ------------------------------------------------------------
# Main entry point
# ------------------------------------------------------------

def build_samples(data: dict, scorer, progress=None, index_df: pd.DataFrame = None) -> tuple:
    """One row per (stock, day): indicator scores + forward returns.
    `index_df`: Nifty 50 history, for the RS rating."""
    frames, skipped = [], []
    need = WARMUP + max(HORIZONS) + 30
    for i, (sym, df) in enumerate(data.items()):
        if progress:
            progress(f"Scoring history of {sym} ({i+1}/{len(data)})...", 5 + 80 * i / max(len(data), 1))
        if df is None or len(df) < need:
            skipped.append(sym)
            continue
        try:
            ind = indicator_frame(df, index_df)
            comp = component_scores(ind, scorer)
            comp['liquidity_cr'] = ind['liquidity_cr']
            for h in HORIZONS:
                comp[f'fwd{h}'] = df['Close'].shift(-h) / df['Close'] - 1
            comp = comp.iloc[WARMUP:]
            comp['symbol'] = sym
            comp['date'] = comp.index
            frames.append(comp.reset_index(drop=True))
        except Exception:
            skipped.append(sym)
    if not frames:
        return pd.DataFrame(), skipped
    return pd.concat(frames, ignore_index=True), skipped


def _add_excess_returns(samples: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Return relative to the average of the stocks in the sample that day (removes market-wide moves)."""
    samples = samples.copy()
    raw = f'fwd{horizon}'
    if samples['symbol'].nunique() >= MIN_STOCKS_FOR_EXCESS:
        samples[f'{raw}_ex'] = samples[raw] - samples.groupby('date')[raw].transform('mean')
    else:
        samples[f'{raw}_ex'] = samples[raw]
    return samples


def run_backtest(data: dict, scorer, weights: dict, horizon: int = 10, progress=None,
                 samples: pd.DataFrame = None, skipped=None, min_liquidity_cr: float = 0,
                 index_df: pd.DataFrame = None) -> dict:
    """Backtest the scoring system on {symbol: price DataFrame}.

    scorer:  the app's Scorer class (provides the per-indicator scoring rules)
    weights: current indicator weights, e.g. Scorer.WEIGHTS
    samples: pass the result of build_samples() to re-run with another horizon without rescoring
    min_liquidity_cr: only count days when the stock's 20-day average traded value was at least
                      this many Rs crore (0 = all days)
    index_df: Nifty 50 history, for the RS rating
    """
    if samples is None:
        samples, skipped = build_samples(data, scorer, progress, index_df)
    if samples.empty:
        return {'error': 'Not enough price history to backtest '
                         f'(need at least {WARMUP + max(HORIZONS) + 30} trading days per stock).',
                'skipped': skipped or []}

    if progress:
        progress("Calculating statistics...", 90)
    raw, target = f'fwd{horizon}', f'fwd{horizon}_ex'
    usable = samples.dropna(subset=[raw])
    n_all = len(usable)
    if min_liquidity_cr > 0:
        usable = usable[usable['liquidity_cr'] >= min_liquidity_cr]
        if usable['date'].nunique() < 100:
            return {'error': f'Too few days with average traded value above Rs {min_liquidity_cr:g} Cr '
                             'to backtest - lower the threshold or untick "Liquid stocks only".',
                    'skipped': skipped or []}
    usable = _add_excess_returns(usable, horizon).dropna(subset=[target])
    dates = np.sort(usable['date'].unique())
    split = int(len(dates) * TRAIN_FRACTION)
    split_date = dates[split]
    # The last `horizon` days before the split aren't learned from: their forward returns run
    # into the test period, which would let the test results leak into the suggested weights
    train_end = dates[max(split - horizon, 0)]
    train, test = usable[usable['date'] < train_end], usable[usable['date'] >= split_date]

    ics_train = {k: _ic(train[k], train[target]) for k in COMPONENT_NAMES}
    ics_test = {k: _ic(test[k], test[target]) for k in COMPONENT_NAMES}
    suggested = suggest_weights(ics_train)

    current_eval = _evaluate(test, weights, target, raw)
    suggested_eval = _evaluate(test, suggested, target, raw) if suggested else None

    components = [{
        'key': k, 'name': COMPONENT_NAMES[k], 'weight': weights.get(k, 0),
        'ic_train': ics_train[k], 'ic_test': ics_test[k],
        'suggested': suggested.get(k) if suggested else None,
    } for k in COMPONENT_NAMES]

    return {
        'horizon': horizon,
        'n_stocks': usable['symbol'].nunique(),
        'n_samples': len(usable),
        'n_test': len(test),
        'start': pd.Timestamp(dates[0]).strftime('%Y-%m-%d'),
        'end': pd.Timestamp(dates[-1]).strftime('%Y-%m-%d'),
        'split_date': pd.Timestamp(split_date).strftime('%Y-%m-%d'),
        'baseline_return': test[raw].mean() * 100,
        'baseline_win': (test[raw] > 0).mean() * 100,
        'relative': usable['symbol'].nunique() >= MIN_STOCKS_FOR_EXCESS,
        'min_liquidity_cr': min_liquidity_cr,
        'excluded_illiquid': n_all - len(usable),
        'components': components,
        'current': current_eval,
        'suggested_weights': suggested,
        'suggested': suggested_eval,
        'skipped': skipped or [],
        'samples': samples,
    }


def compare_weights(samples: pd.DataFrame, weights_a: dict, weights_b: dict, horizon: int = 10,
                    recent_days: int = 126, min_liquidity_cr: float = 0) -> dict:
    """Compare two weight sets on the most recent `recent_days` trading days (default ~6 months).

    Used by the monthly re-check of weights applied from the Backtest tab: as time passes,
    this window moves onto data the weights were never fitted to.
    Returns {'a': {'ic', 'spread'}, 'b': {...}, 'since', 'until', 'n_samples'} or {'error': ...}.
    """
    raw, target = f'fwd{horizon}', f'fwd{horizon}_ex'
    if samples is None or samples.empty:
        return {'error': 'no price history'}
    usable = samples.dropna(subset=[raw])
    if min_liquidity_cr > 0:
        usable = usable[usable['liquidity_cr'] >= min_liquidity_cr]
    usable = _add_excess_returns(usable, horizon).dropna(subset=[target])
    dates = np.sort(usable['date'].unique())
    if len(dates) < 40:
        return {'error': 'not enough recent history to compare'}
    since = dates[max(0, len(dates) - recent_days)]
    recent = usable[usable['date'] >= since]
    a, b = _evaluate(recent, weights_a, target, raw), _evaluate(recent, weights_b, target, raw)
    return {
        'a': {'ic': a['ic'], 'spread': a['spread']},
        'b': {'ic': b['ic'], 'spread': b['spread']},
        'since': pd.Timestamp(since).strftime('%Y-%m-%d'),
        'until': pd.Timestamp(dates[-1]).strftime('%Y-%m-%d'),
        'n_samples': len(recent),
        'horizon': horizon,
    }
