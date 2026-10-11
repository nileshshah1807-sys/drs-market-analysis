#!/usr/bin/env python3
"""
Advanced Pattern Recognition Module for DR. NILESH SHAH'S MARKET ANALYSIS
=========================================================================
Detects Chart Patterns, Candlestick Patterns, and Harmonic Patterns
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional


MAX_PATTERN_AGE = 60     # a peak/trough pattern must complete within the last ~3 months of trading days
MIN_SWING = 0.03         # tops/bottoms must be separated by at least a 3% dip/rally to count
MIN_SEPARATION = 10      # ...and at least 10 trading days apart


class PatternDetector:
    """Advanced pattern detection for technical analysis."""

    def __init__(self):
        self.patterns_found = []

    def detect_all_patterns(self, df: pd.DataFrame) -> Dict:
        """Detect all patterns in the given dataframe."""
        if df is None or len(df) < 5:
            return {'chart': [], 'candlestick': [], 'harmonic': [], 'summary': {}}

        try:
            self.hourly = bool((df.index != df.index.normalize()).any())
        except AttributeError:   # not a date index
            self.hourly = False
        chart, ignored = self.resolve_conflicts(self.detect_chart_patterns(df))
        results = {
            'chart': chart,
            'candlestick': self.detect_candlestick_patterns(df),
            'harmonic': self.detect_harmonic_patterns(df),
        }

        # Create summary
        results['summary'] = self.create_pattern_summary(results)
        results['summary']['ignored_conflicts'] = ignored

        return results

    @staticmethod
    def resolve_conflicts(patterns: List[Dict]) -> Tuple[List[Dict], List[str]]:
        """A chart can't be forming a bullish AND a bearish reversal at once.

        When chart patterns disagree, keep the side of the most convincing pattern:
        a confirmed breakout (STRONG) first, then the most recently completed one,
        then the more reliable one. Returns (kept patterns, names of ignored ones).
        """
        directional = [p for p in patterns if p.get('signal') in ('BULLISH', 'BEARISH')]
        if len({p['signal'] for p in directional}) < 2:
            return patterns, []
        best = max(directional, key=lambda p: (p.get('strength') == 'STRONG',
                                               -p.get('bars_ago', 0), p.get('reliability', 0)))
        kept = [p for p in patterns if p.get('signal') not in ('BULLISH', 'BEARISH') or p['signal'] == best['signal']]
        ignored = [p['name'] for p in directional if p['signal'] != best['signal']]
        return kept, ignored

    hourly = False   # set per chart: a new listing's patterns are found on 1-hour candles

    def _age_text(self, bars_ago: int) -> str:
        if self.hourly:
            return " (just completed)" if bars_ago == 0 else f" (completed {bars_ago} trading hours ago)"
        return " (completed today)" if bars_ago == 0 else f" (completed {bars_ago} trading days ago)"
    
    def create_pattern_summary(self, results: Dict) -> Dict:
        """Create a summary of detected patterns."""
        bullish = 0
        bearish = 0
        neutral = 0
        
        all_patterns = []
        
        for category in ['chart', 'candlestick', 'harmonic']:
            for pattern in results[category]:
                all_patterns.append(pattern)
                if pattern.get('signal') == 'BULLISH':
                    bullish += 1
                elif pattern.get('signal') == 'BEARISH':
                    bearish += 1
                else:
                    neutral += 1
        
        if bullish > bearish:
            overall = 'BULLISH'
        elif bearish > bullish:
            overall = 'BEARISH'
        else:
            overall = 'NEUTRAL'
        
        return {
            'total_patterns': len(all_patterns),
            'bullish_count': bullish,
            'bearish_count': bearish,
            'neutral_count': neutral,
            'overall_signal': overall,
            'patterns': all_patterns
        }
    
    # ============================================================
    # CHART PATTERNS
    # ============================================================
    
    def detect_chart_patterns(self, df: pd.DataFrame) -> List[Dict]:
        """Detect chart patterns like Head & Shoulders, Double Top/Bottom, etc."""
        patterns = []
        
        close = df['Close'].values
        high = df['High'].values
        low = df['Low'].values
        
        # Find local peaks and troughs
        peaks = self.find_peaks(high, window=5)
        troughs = self.find_troughs(low, window=5)
        
        # Head and Shoulders
        hs = self.detect_head_shoulders(close, high, low, peaks, troughs)
        if hs:
            patterns.append(hs)
        
        # Inverse Head and Shoulders
        ihs = self.detect_inverse_head_shoulders(close, high, low, peaks, troughs)
        if ihs:
            patterns.append(ihs)
        
        # Double Top
        dt = self.detect_double_top(close, high, peaks)
        if dt:
            patterns.append(dt)
        
        # Double Bottom
        db = self.detect_double_bottom(close, low, troughs)
        if db:
            patterns.append(db)
        
        # Triple Top
        tt = self.detect_triple_top(close, high, peaks)
        if tt:
            patterns.append(tt)
        
        # Triple Bottom
        tb = self.detect_triple_bottom(close, low, troughs)
        if tb:
            patterns.append(tb)
        
        # Ascending Triangle
        at = self.detect_ascending_triangle(close, high, low)
        if at:
            patterns.append(at)
        
        # Descending Triangle
        dt2 = self.detect_descending_triangle(close, high, low)
        if dt2:
            patterns.append(dt2)
        
        # Symmetrical Triangle
        st = self.detect_symmetrical_triangle(close, high, low)
        if st:
            patterns.append(st)
        
        # Bull Flag
        bf = self.detect_bull_flag(close, high, low)
        if bf:
            patterns.append(bf)
        
        # Bear Flag
        brf = self.detect_bear_flag(close, high, low)
        if brf:
            patterns.append(brf)
        
        # Wedge (Rising)
        rw = self.detect_rising_wedge(close, high, low)
        if rw:
            patterns.append(rw)
        
        # Wedge (Falling)
        fw = self.detect_falling_wedge(close, high, low)
        if fw:
            patterns.append(fw)
        
        return patterns
    
    def find_peaks(self, data: np.ndarray, window: int = 5) -> List[int]:
        """Find local peaks in data."""
        peaks = []
        for i in range(window, len(data) - window):
            if data[i] == max(data[i-window:i+window+1]):
                peaks.append(i)
        return peaks
    
    def find_troughs(self, data: np.ndarray, window: int = 5) -> List[int]:
        """Find local troughs in data."""
        troughs = []
        for i in range(window, len(data) - window):
            if data[i] == min(data[i-window:i+window+1]):
                troughs.append(i)
        return troughs
    
    def detect_head_shoulders(self, close, high, low, peaks, troughs) -> Optional[Dict]:
        """Detect Head and Shoulders pattern (most recent one only, right shoulder within MAX_PATTERN_AGE)."""
        if len(peaks) < 3 or len(troughs) < 2:
            return None

        n = len(close)
        # Newest candidate first; stop once the right shoulder is too old to matter
        for i in range(len(peaks) - 3, -1, -1):
            p1, p2, p3 = peaks[i], peaks[i+1], peaks[i+2]
            if n - 1 - p3 > MAX_PATTERN_AGE:
                break

            # Left shoulder, Head, Right shoulder
            ls = high[p1]
            head = high[p2]
            rs = high[p3]

            # Head should be highest; shoulders approximately equal
            if head > ls and head > rs and abs(ls - rs) / ls < 0.05:
                # Neckline: lows between the shoulders
                neckline_troughs = [t for t in troughs if p1 < t < p3]
                if not neckline_troughs:
                    continue
                neckline = min(low[t] for t in neckline_troughs)
                if (min(ls, rs) - neckline) / neckline < MIN_SWING:
                    continue
                confirmed = close[-1] < neckline
                bars_ago = n - 1 - p3
                return {
                    'name': 'Head & Shoulders',
                    'signal': 'BEARISH',
                    'strength': 'STRONG' if confirmed else 'FORMING',
                    'category': 'CHART',
                    'description': f'Bearish reversal pattern. Head at {head:.2f}, Neckline at {neckline:.2f}'
                                   + (' - neckline broken' if confirmed else '') + self._age_text(bars_ago),
                    'target': neckline - (head - neckline),
                    'stop_loss': head,
                    'reliability': 85,
                    'bars_ago': bars_ago,
                }
        return None

    def detect_inverse_head_shoulders(self, close, high, low, peaks, troughs) -> Optional[Dict]:
        """Detect Inverse Head and Shoulders pattern (most recent one only)."""
        if len(troughs) < 3 or len(peaks) < 2:
            return None

        n = len(close)
        for i in range(len(troughs) - 3, -1, -1):
            t1, t2, t3 = troughs[i], troughs[i+1], troughs[i+2]
            if n - 1 - t3 > MAX_PATTERN_AGE:
                break

            ls = low[t1]
            head = low[t2]
            rs = low[t3]

            if head < ls and head < rs and abs(ls - rs) / ls < 0.05:
                neckline_peaks = [p for p in peaks if t1 < p < t3]
                if not neckline_peaks:
                    continue
                neckline = max(high[p] for p in neckline_peaks)
                if (neckline - max(ls, rs)) / max(ls, rs) < MIN_SWING:
                    continue
                confirmed = close[-1] > neckline
                bars_ago = n - 1 - t3
                return {
                    'name': 'Inverse Head & Shoulders',
                    'signal': 'BULLISH',
                    'strength': 'STRONG' if confirmed else 'FORMING',
                    'category': 'CHART',
                    'description': f'Bullish reversal pattern. Head at {head:.2f}, Neckline at {neckline:.2f}'
                                   + (' - neckline broken' if confirmed else '') + self._age_text(bars_ago),
                    'target': neckline + (neckline - head),
                    'stop_loss': head,
                    'reliability': 85,
                    'bars_ago': bars_ago,
                }
        return None

    def detect_double_top(self, close, high, peaks) -> Optional[Dict]:
        """Detect Double Top pattern (last two peaks, recent, with a real dip between them)."""
        if len(peaks) < 2:
            return None

        n = len(close)
        p1, p2 = peaks[-2], peaks[-1]
        top1 = high[p1]
        top2 = high[p2]
        if n - 1 - p2 > MAX_PATTERN_AGE or p2 - p1 < MIN_SEPARATION:
            return None

        support = min(close[p1:p2])
        if abs(top1 - top2) / top1 < 0.03 and (min(top1, top2) - support) / support >= MIN_SWING:
            confirmed = close[-1] < support
            bars_ago = n - 1 - p2
            return {
                'name': 'Double Top',
                'signal': 'BEARISH',
                'strength': 'STRONG' if confirmed else 'FORMING',
                'category': 'CHART',
                'description': f'Bearish reversal. Two tops at {top1:.2f} and {top2:.2f}, support {support:.2f}'
                               + (' - support broken' if confirmed else '') + self._age_text(bars_ago),
                'target': support - (top1 - support),
                'stop_loss': max(top1, top2),
                'reliability': 75,
                'bars_ago': bars_ago,
            }
        return None

    def detect_double_bottom(self, close, low, troughs) -> Optional[Dict]:
        """Detect Double Bottom pattern (last two troughs, recent, with a real rally between them)."""
        if len(troughs) < 2:
            return None

        n = len(close)
        t1, t2 = troughs[-2], troughs[-1]
        bottom1 = low[t1]
        bottom2 = low[t2]
        if n - 1 - t2 > MAX_PATTERN_AGE or t2 - t1 < MIN_SEPARATION:
            return None

        resistance = max(close[t1:t2])
        if abs(bottom1 - bottom2) / bottom1 < 0.03 and (resistance - max(bottom1, bottom2)) / max(bottom1, bottom2) >= MIN_SWING:
            confirmed = close[-1] > resistance
            bars_ago = n - 1 - t2
            return {
                'name': 'Double Bottom',
                'signal': 'BULLISH',
                'strength': 'STRONG' if confirmed else 'FORMING',
                'category': 'CHART',
                'description': f'Bullish reversal. Two bottoms at {bottom1:.2f} and {bottom2:.2f}, resistance {resistance:.2f}'
                               + (' - resistance broken' if confirmed else '') + self._age_text(bars_ago),
                'target': resistance + (resistance - bottom1),
                'stop_loss': min(bottom1, bottom2),
                'reliability': 75,
                'bars_ago': bars_ago,
            }
        return None

    def detect_triple_top(self, close, high, peaks) -> Optional[Dict]:
        """Detect Triple Top pattern."""
        if len(peaks) < 3:
            return None

        n = len(close)
        p1, p2, p3 = peaks[-3], peaks[-2], peaks[-1]
        t1, t2, t3 = high[p1], high[p2], high[p3]
        if n - 1 - p3 > MAX_PATTERN_AGE or min(p2 - p1, p3 - p2) < MIN_SEPARATION:
            return None

        support = min(close[p1:p3])
        if (abs(t1 - t2) / t1 < 0.03 and abs(t2 - t3) / t2 < 0.03
                and (min(t1, t2, t3) - support) / support >= MIN_SWING):
            confirmed = close[-1] < support
            bars_ago = n - 1 - p3
            return {
                'name': 'Triple Top',
                'signal': 'BEARISH',
                'strength': 'STRONG' if confirmed else 'FORMING',
                'category': 'CHART',
                'description': f'Bearish reversal. Three tops near {t1:.2f}, support {support:.2f}'
                               + (' - support broken' if confirmed else '') + self._age_text(bars_ago),
                'target': support - (t1 - support),
                'stop_loss': max(t1, t2, t3),
                'reliability': 80,
                'bars_ago': bars_ago,
            }
        return None

    def detect_triple_bottom(self, close, low, troughs) -> Optional[Dict]:
        """Detect Triple Bottom pattern."""
        if len(troughs) < 3:
            return None

        n = len(close)
        t1, t2, t3 = troughs[-3], troughs[-2], troughs[-1]
        b1, b2, b3 = low[t1], low[t2], low[t3]
        if n - 1 - t3 > MAX_PATTERN_AGE or min(t2 - t1, t3 - t2) < MIN_SEPARATION:
            return None

        resistance = max(close[t1:t3])
        if (abs(b1 - b2) / b1 < 0.03 and abs(b2 - b3) / b2 < 0.03
                and (resistance - max(b1, b2, b3)) / max(b1, b2, b3) >= MIN_SWING):
            confirmed = close[-1] > resistance
            bars_ago = n - 1 - t3
            return {
                'name': 'Triple Bottom',
                'signal': 'BULLISH',
                'strength': 'STRONG' if confirmed else 'FORMING',
                'category': 'CHART',
                'description': f'Bullish reversal. Three bottoms near {b1:.2f}, resistance {resistance:.2f}'
                               + (' - resistance broken' if confirmed else '') + self._age_text(bars_ago),
                'target': resistance + (resistance - b1),
                'stop_loss': min(b1, b2, b3),
                'reliability': 80,
                'bars_ago': bars_ago,
            }
        return None

    def detect_ascending_triangle(self, close, high, low) -> Optional[Dict]:
        """Detect Ascending Triangle pattern."""
        if len(close) < 30:
            return None
        
        recent = close[-30:]
        highs = high[-30:]
        lows = low[-30:]
        
        # Flat resistance (top)
        resistance = max(highs[-10:])
        resistance_range = max(highs[-10:]) - min(highs[-10:])
        
        # Rising support (bottom)
        low_first = min(lows[:10])
        low_last = min(lows[-10:])
        
        if resistance_range / resistance < 0.02 and low_last > low_first * 1.01:
            return {
                'name': 'Ascending Triangle',
                'signal': 'BULLISH',
                'strength': 'FORMING',
                'category': 'CHART',
                'description': f'Bullish continuation. Resistance at {resistance:.2f}',
                'target': resistance + (resistance - low_first),
                'stop_loss': low_last,
                'reliability': 70
            }
        return None
    
    def detect_descending_triangle(self, close, high, low) -> Optional[Dict]:
        """Detect Descending Triangle pattern."""
        if len(close) < 30:
            return None
        
        highs = high[-30:]
        lows = low[-30:]
        
        support = min(lows[-10:])
        support_range = max(lows[-10:]) - min(lows[-10:])
        
        high_first = max(highs[:10])
        high_last = max(highs[-10:])
        
        if support_range / support < 0.02 and high_last < high_first * 0.99:
            return {
                'name': 'Descending Triangle',
                'signal': 'BEARISH',
                'strength': 'FORMING',
                'category': 'CHART',
                'description': f'Bearish continuation. Support at {support:.2f}',
                'target': support - (high_first - support),
                'stop_loss': high_last,
                'reliability': 70
            }
        return None
    
    def detect_symmetrical_triangle(self, close, high, low) -> Optional[Dict]:
        """Detect Symmetrical Triangle pattern."""
        if len(close) < 30:
            return None
        
        highs = high[-30:]
        lows = low[-30:]
        
        high_first = max(highs[:10])
        high_last = max(highs[-10:])
        low_first = min(lows[:10])
        low_last = min(lows[-10:])
        
        # Converging lines
        if high_last < high_first and low_last > low_first:
            return {
                'name': 'Symmetrical Triangle',
                'signal': 'NEUTRAL',
                'strength': 'FORMING',
                'category': 'CHART',
                'description': 'Continuation pattern. Wait for breakout direction.',
                'target': None,
                'stop_loss': None,
                'reliability': 65
            }
        return None
    
    def detect_bull_flag(self, close, high, low) -> Optional[Dict]:
        """Detect Bull Flag pattern."""
        if len(close) < 20:
            return None
        
        # Strong move up (pole)
        pole_start = min(close[-20:-10])
        pole_end = max(close[-10:-5])
        pole_gain = (pole_end - pole_start) / pole_start
        
        # Consolidation (flag)
        flag_high = max(close[-5:])
        flag_low = min(close[-5:])
        flag_range = (flag_high - flag_low) / flag_high
        
        if pole_gain > 0.10 and flag_range < 0.05:
            return {
                'name': 'Bull Flag',
                'signal': 'BULLISH',
                'strength': 'FORMING',
                'category': 'CHART',
                'description': f'Bullish continuation after {pole_gain*100:.1f}% rise',
                'target': flag_high + pole_gain * pole_end,
                'stop_loss': flag_low,
                'reliability': 72
            }
        return None
    
    def detect_bear_flag(self, close, high, low) -> Optional[Dict]:
        """Detect Bear Flag pattern."""
        if len(close) < 20:
            return None
        
        pole_start = max(close[-20:-10])
        pole_end = min(close[-10:-5])
        pole_drop = (pole_start - pole_end) / pole_start
        
        flag_high = max(close[-5:])
        flag_low = min(close[-5:])
        flag_range = (flag_high - flag_low) / flag_high
        
        if pole_drop > 0.10 and flag_range < 0.05:
            return {
                'name': 'Bear Flag',
                'signal': 'BEARISH',
                'strength': 'FORMING',
                'category': 'CHART',
                'description': f'Bearish continuation after {pole_drop*100:.1f}% drop',
                'target': flag_low - pole_drop * pole_end,
                'stop_loss': flag_high,
                'reliability': 72
            }
        return None
    
    def detect_rising_wedge(self, close, high, low) -> Optional[Dict]:
        """Detect Rising Wedge pattern."""
        if len(close) < 30:
            return None
        
        highs = high[-30:]
        lows = low[-30:]
        
        # Both lines rising, but converging
        high_slope = np.polyfit(range(15), highs[-15:], 1)[0]
        low_slope = np.polyfit(range(15), lows[-15:], 1)[0]
        
        if high_slope > 0 and low_slope > 0 and high_slope < low_slope:
            return {
                'name': 'Rising Wedge',
                'signal': 'BEARISH',
                'strength': 'FORMING',
                'category': 'CHART',
                'description': 'Bearish reversal pattern. Lines converging upward.',
                'target': close[-1] * 0.92,
                'stop_loss': max(highs[-5:]),
                'reliability': 68
            }
        return None
    
    def detect_falling_wedge(self, close, high, low) -> Optional[Dict]:
        """Detect Falling Wedge pattern."""
        if len(close) < 30:
            return None
        
        highs = high[-30:]
        lows = low[-30:]
        
        high_slope = np.polyfit(range(15), highs[-15:], 1)[0]
        low_slope = np.polyfit(range(15), lows[-15:], 1)[0]
        
        if high_slope < 0 and low_slope < 0 and high_slope > low_slope:
            return {
                'name': 'Falling Wedge',
                'signal': 'BULLISH',
                'strength': 'FORMING',
                'category': 'CHART',
                'description': 'Bullish reversal pattern. Lines converging downward.',
                'target': close[-1] * 1.08,
                'stop_loss': min(lows[-5:]),
                'reliability': 68
            }
        return None
    
    # ============================================================
    # CANDLESTICK PATTERNS
    # ============================================================
    
    def detect_candlestick_patterns(self, df: pd.DataFrame) -> List[Dict]:
        """Detect candlestick patterns."""
        patterns = []
        
        o = df['Open'].values
        h = df['High'].values
        l = df['Low'].values
        c = df['Close'].values
        
        if len(c) < 5:
            return patterns
        
        # Single candlestick patterns
        patterns.extend(self._single_candle_patterns(o, h, l, c))
        
        # Double candlestick patterns
        patterns.extend(self._double_candle_patterns(o, h, l, c))
        
        # Triple candlestick patterns
        patterns.extend(self._triple_candle_patterns(o, h, l, c))
        
        return patterns
    
    def _candle_body(self, o, c):
        """Calculate candle body size."""
        return abs(c - o)
    
    def _candle_shadow_upper(self, o, h, c):
        """Calculate upper shadow."""
        return h - max(o, c)
    
    def _candle_shadow_lower(self, o, l, c):
        """Calculate lower shadow."""
        return min(o, c) - l
    
    def _candle_range(self, h, l):
        """Calculate candle range."""
        return h - l
    
    def _is_bullish(self, o, c):
        """Check if candle is bullish."""
        return c > o
    
    def _is_bearish(self, o, c):
        """Check if candle is bearish."""
        return o > c
    
    @staticmethod
    def _prior_trend(c, lookback: int = 5, threshold: float = 0.01) -> str:
        """Trend over the candles BEFORE the last one: 'UP', 'DOWN' or 'FLAT'.
        Hammer/Hanging Man and Inverted Hammer/Shooting Star have the same shape -
        what tells them apart is the trend they appear after, not the candle colour."""
        if len(c) < lookback + 2 or c[-lookback - 2] == 0:
            return 'FLAT'
        change = (c[-2] - c[-lookback - 2]) / c[-lookback - 2]
        return 'UP' if change > threshold else 'DOWN' if change < -threshold else 'FLAT'
    
    def _single_candle_patterns(self, o, h, l, c) -> List[Dict]:
        """Detect single candlestick patterns."""
        patterns = []
        
        # Last candle
        i = -1
        body = self._candle_body(o[i], c[i])
        upper = self._candle_shadow_upper(o[i], h[i], c[i])
        lower = self._candle_shadow_lower(o[i], l[i], c[i])
        range_val = self._candle_range(h[i], l[i])
        
        if range_val == 0:
            return patterns
        
        body_ratio = body / range_val
        upper_ratio = upper / range_val
        lower_ratio = lower / range_val
        
        # Doji
        if body_ratio < 0.1:
            if upper_ratio > 0.3 and lower_ratio > 0.3:
                patterns.append({
                    'name': 'Long-Legged Doji',
                    'signal': 'NEUTRAL',
                    'strength': 'STRONG',
                    'category': 'CANDLESTICK',
                    'description': 'Indecision pattern. Potential reversal.',
                    'reliability': 60
                })
            elif upper_ratio > 0.6:
                patterns.append({
                    'name': 'Gravestone Doji',
                    'signal': 'BEARISH',
                    'strength': 'STRONG',
                    'category': 'CANDLESTICK',
                    'description': 'Bearish reversal at top.',
                    'reliability': 70
                })
            elif lower_ratio > 0.6:
                patterns.append({
                    'name': 'Dragonfly Doji',
                    'signal': 'BULLISH',
                    'strength': 'STRONG',
                    'category': 'CANDLESTICK',
                    'description': 'Bullish reversal at bottom.',
                    'reliability': 70
                })
            else:
                patterns.append({
                    'name': 'Doji',
                    'signal': 'NEUTRAL',
                    'strength': 'MODERATE',
                    'category': 'CANDLESTICK',
                    'description': 'Indecision pattern.',
                    'reliability': 55
                })
        
        trend = self._prior_trend(c)
        
        # Hammer (bullish) - long lower shadow after a decline
        if lower_ratio > 0.6 and body_ratio < 0.3 and upper_ratio < 0.1:
            if trend == 'DOWN':
                patterns.append({
                    'name': 'Hammer',
                    'signal': 'BULLISH',
                    'strength': 'STRONG',
                    'category': 'CANDLESTICK',
                    'description': 'Bullish reversal at bottom.',
                    'reliability': 72
                })
        
        # Hanging Man (bearish) - same shape after a rise
        if lower_ratio > 0.6 and body_ratio < 0.3 and upper_ratio < 0.1:
            if trend == 'UP':
                patterns.append({
                    'name': 'Hanging Man',
                    'signal': 'BEARISH',
                    'strength': 'STRONG',
                    'category': 'CANDLESTICK',
                    'description': 'Bearish reversal at top.',
                    'reliability': 65
                })
        
        # Inverted Hammer - long upper shadow after a decline
        if upper_ratio > 0.6 and body_ratio < 0.3 and lower_ratio < 0.1:
            if trend == 'DOWN':
                patterns.append({
                    'name': 'Inverted Hammer',
                    'signal': 'BULLISH',
                    'strength': 'MODERATE',
                    'category': 'CANDLESTICK',
                    'description': 'Potential bullish reversal.',
                    'reliability': 60
                })
        
        # Shooting Star - same shape after a rise
        if upper_ratio > 0.6 and body_ratio < 0.3 and lower_ratio < 0.1:
            if trend == 'UP':
                patterns.append({
                    'name': 'Shooting Star',
                    'signal': 'BEARISH',
                    'strength': 'STRONG',
                    'category': 'CANDLESTICK',
                    'description': 'Bearish reversal at top.',
                    'reliability': 72
                })
        
        # Marubozu (strong momentum)
        if body_ratio > 0.8:
            if self._is_bullish(o[i], c[i]):
                patterns.append({
                    'name': 'Bullish Marubozu',
                    'signal': 'BULLISH',
                    'strength': 'STRONG',
                    'category': 'CANDLESTICK',
                    'description': 'Strong bullish momentum.',
                    'reliability': 68
                })
            else:
                patterns.append({
                    'name': 'Bearish Marubozu',
                    'signal': 'BEARISH',
                    'strength': 'STRONG',
                    'category': 'CANDLESTICK',
                    'description': 'Strong bearish momentum.',
                    'reliability': 68
                })
        
        return patterns
    
    def _double_candle_patterns(self, o, h, l, c) -> List[Dict]:
        """Detect double candlestick patterns."""
        patterns = []
        
        if len(c) < 2:
            return patterns
        
        # Bullish Engulfing
        if (self._is_bearish(o[-2], c[-2]) and 
            self._is_bullish(o[-1], c[-1]) and
            o[-1] < c[-2] and c[-1] > o[-2]):
            patterns.append({
                'name': 'Bullish Engulfing',
                'signal': 'BULLISH',
                'strength': 'STRONG',
                'category': 'CANDLESTICK',
                'description': 'Strong bullish reversal pattern.',
                'reliability': 78
            })
        
        # Bearish Engulfing
        if (self._is_bullish(o[-2], c[-2]) and 
            self._is_bearish(o[-1], c[-1]) and
            o[-1] > c[-2] and c[-1] < o[-2]):
            patterns.append({
                'name': 'Bearish Engulfing',
                'signal': 'BEARISH',
                'strength': 'STRONG',
                'category': 'CANDLESTICK',
                'description': 'Strong bearish reversal pattern.',
                'reliability': 78
            })
        
        # Bullish Harami
        if (self._is_bearish(o[-2], c[-2]) and 
            self._is_bullish(o[-1], c[-1]) and
            o[-1] > c[-2] and c[-1] < o[-2]):
            patterns.append({
                'name': 'Bullish Harami',
                'signal': 'BULLISH',
                'strength': 'MODERATE',
                'category': 'CANDLESTICK',
                'description': 'Potential bullish reversal.',
                'reliability': 55
            })
        
        # Bearish Harami
        if (self._is_bullish(o[-2], c[-2]) and 
            self._is_bearish(o[-1], c[-1]) and
            o[-1] < c[-2] and c[-1] > o[-2]):
            patterns.append({
                'name': 'Bearish Harami',
                'signal': 'BEARISH',
                'strength': 'MODERATE',
                'category': 'CANDLESTICK',
                'description': 'Potential bearish reversal.',
                'reliability': 55
            })
        
        # Piercing Line
        if (self._is_bearish(o[-2], c[-2]) and 
            self._is_bullish(o[-1], c[-1]) and
            o[-1] < l[-2] and c[-1] > (o[-2] + c[-2]) / 2):
            patterns.append({
                'name': 'Piercing Line',
                'signal': 'BULLISH',
                'strength': 'STRONG',
                'category': 'CANDLESTICK',
                'description': 'Bullish reversal pattern.',
                'reliability': 70
            })
        
        # Dark Cloud Cover
        if (self._is_bullish(o[-2], c[-2]) and 
            self._is_bearish(o[-1], c[-1]) and
            o[-1] > h[-2] and c[-1] < (o[-2] + c[-2]) / 2):
            patterns.append({
                'name': 'Dark Cloud Cover',
                'signal': 'BEARISH',
                'strength': 'STRONG',
                'category': 'CANDLESTICK',
                'description': 'Bearish reversal pattern.',
                'reliability': 70
            })
        
        # Tweezer Top
        if (abs(h[-1] - h[-2]) / h[-2] < 0.005 and
            self._is_bullish(o[-2], c[-2]) and 
            self._is_bearish(o[-1], c[-1])):
            patterns.append({
                'name': 'Tweezer Top',
                'signal': 'BEARISH',
                'strength': 'MODERATE',
                'category': 'CANDLESTICK',
                'description': 'Bearish reversal at resistance.',
                'reliability': 62
            })
        
        # Tweezer Bottom
        if (abs(l[-1] - l[-2]) / l[-2] < 0.005 and
            self._is_bearish(o[-2], c[-2]) and 
            self._is_bullish(o[-1], c[-1])):
            patterns.append({
                'name': 'Tweezer Bottom',
                'signal': 'BULLISH',
                'strength': 'MODERATE',
                'category': 'CANDLESTICK',
                'description': 'Bullish reversal at support.',
                'reliability': 62
            })
        
        return patterns
    
    def _triple_candle_patterns(self, o, h, l, c) -> List[Dict]:
        """Detect triple candlestick patterns."""
        patterns = []
        
        if len(c) < 3:
            return patterns
        
        # Morning Star
        if (self._is_bearish(o[-3], c[-3]) and
            abs(c[-2] - o[-2]) < abs(c[-3] - o[-3]) * 0.3 and
            self._is_bullish(o[-1], c[-1]) and
            c[-1] > (o[-3] + c[-3]) / 2):
            patterns.append({
                'name': 'Morning Star',
                'signal': 'BULLISH',
                'strength': 'STRONG',
                'category': 'CANDLESTICK',
                'description': 'Strong bullish reversal at bottom.',
                'reliability': 82
            })
        
        # Evening Star
        if (self._is_bullish(o[-3], c[-3]) and
            abs(c[-2] - o[-2]) < abs(c[-3] - o[-3]) * 0.3 and
            self._is_bearish(o[-1], c[-1]) and
            c[-1] < (o[-3] + c[-3]) / 2):
            patterns.append({
                'name': 'Evening Star',
                'signal': 'BEARISH',
                'strength': 'STRONG',
                'category': 'CANDLESTICK',
                'description': 'Strong bearish reversal at top.',
                'reliability': 82
            })
        
        # Three White Soldiers
        if (self._is_bullish(o[-3], c[-3]) and
            self._is_bullish(o[-2], c[-2]) and
            self._is_bullish(o[-1], c[-1]) and
            c[-2] > c[-3] and c[-1] > c[-2]):
            patterns.append({
                'name': 'Three White Soldiers',
                'signal': 'BULLISH',
                'strength': 'STRONG',
                'category': 'CANDLESTICK',
                'description': 'Strong bullish continuation.',
                'reliability': 78
            })
        
        # Three Black Crows
        if (self._is_bearish(o[-3], c[-3]) and
            self._is_bearish(o[-2], c[-2]) and
            self._is_bearish(o[-1], c[-1]) and
            c[-2] < c[-3] and c[-1] < c[-2]):
            patterns.append({
                'name': 'Three Black Crows',
                'signal': 'BEARISH',
                'strength': 'STRONG',
                'category': 'CANDLESTICK',
                'description': 'Strong bearish continuation.',
                'reliability': 78
            })
        
        # Three Inside Up
        if (self._is_bearish(o[-3], c[-3]) and
            self._is_bullish(o[-2], c[-2]) and
            o[-2] > c[-3] and c[-2] < o[-3] and
            self._is_bullish(o[-1], c[-1]) and
            c[-1] > o[-3]):
            patterns.append({
                'name': 'Three Inside Up',
                'signal': 'BULLISH',
                'strength': 'STRONG',
                'category': 'CANDLESTICK',
                'description': 'Confirmed bullish reversal.',
                'reliability': 72
            })
        
        # Three Inside Down
        if (self._is_bullish(o[-3], c[-3]) and
            self._is_bearish(o[-2], c[-2]) and
            o[-2] < c[-3] and c[-2] > o[-3] and
            self._is_bearish(o[-1], c[-1]) and
            c[-1] < o[-3]):
            patterns.append({
                'name': 'Three Inside Down',
                'signal': 'BEARISH',
                'strength': 'STRONG',
                'category': 'CANDLESTICK',
                'description': 'Confirmed bearish reversal.',
                'reliability': 72
            })
        
        return patterns
    
    # ============================================================
    # HARMONIC PATTERNS
    # ============================================================
    
    def detect_harmonic_patterns(self, df: pd.DataFrame) -> List[Dict]:
        """Detect harmonic patterns (Gartley, Butterfly, Bat, Crab)."""
        patterns = []
        
        close = df['Close'].values
        high = df['High'].values
        low = df['Low'].values
        
        if len(close) < 30:
            return patterns
        
        # Find significant swing points
        swings = self.find_swing_points(high, low, window=5)
        
        if len(swings) < 5:
            return patterns
        
        # Check last 5 swings for harmonic patterns
        X, A, B, C, D = swings[-5], swings[-4], swings[-3], swings[-2], swings[-1]
        if len(close) - 1 - D['index'] > MAX_PATTERN_AGE:
            return patterns   # pattern completed too long ago to matter now
        
        xa = abs(A['price'] - X['price'])
        ab = abs(B['price'] - A['price'])
        bc = abs(C['price'] - B['price'])
        cd = abs(D['price'] - C['price'])
        
        if xa == 0:
            return patterns
        
        # Fibonacci ratios
        ab_ratio = ab / xa
        bc_ratio = bc / ab if ab > 0 else 0
        cd_ratio = cd / bc if bc > 0 else 0
        
        # Gartley Pattern (0.618 AB, 0.382-0.886 BC, 1.272-1.618 CD)
        if (0.55 < ab_ratio < 0.70 and 
            0.38 < bc_ratio < 0.89 and
            1.20 < cd_ratio < 1.70):
            signal = 'BULLISH' if X['price'] < A['price'] else 'BEARISH'
            patterns.append({
                'name': 'Gartley Pattern',
                'signal': signal,
                'strength': 'STRONG',
                'category': 'HARMONIC',
                'description': f'AB={ab_ratio:.3f}, BC={bc_ratio:.3f}, CD={cd_ratio:.3f}',
                'reliability': 75,
                'fib_levels': {'AB': ab_ratio, 'BC': bc_ratio, 'CD': cd_ratio}
            })
        
        # Butterfly Pattern (0.786 AB, 0.382-0.886 BC, 1.618-2.618 CD)
        if (0.72 < ab_ratio < 0.85 and 
            0.38 < bc_ratio < 0.89 and
            1.60 < cd_ratio < 2.70):
            signal = 'BULLISH' if X['price'] < A['price'] else 'BEARISH'
            patterns.append({
                'name': 'Butterfly Pattern',
                'signal': signal,
                'strength': 'STRONG',
                'category': 'HARMONIC',
                'description': f'AB={ab_ratio:.3f}, BC={bc_ratio:.3f}, CD={cd_ratio:.3f}',
                'reliability': 72,
                'fib_levels': {'AB': ab_ratio, 'BC': bc_ratio, 'CD': cd_ratio}
            })
        
        # Bat Pattern (0.382-0.50 AB, 0.382-0.886 BC, 1.618-2.618 CD)
        if (0.35 < ab_ratio < 0.55 and 
            0.38 < bc_ratio < 0.89 and
            1.60 < cd_ratio < 2.70):
            signal = 'BULLISH' if X['price'] < A['price'] else 'BEARISH'
            patterns.append({
                'name': 'Bat Pattern',
                'signal': signal,
                'strength': 'STRONG',
                'category': 'HARMONIC',
                'description': f'AB={ab_ratio:.3f}, BC={bc_ratio:.3f}, CD={cd_ratio:.3f}',
                'reliability': 70,
                'fib_levels': {'AB': ab_ratio, 'BC': bc_ratio, 'CD': cd_ratio}
            })
        
        # Crab Pattern (0.382-0.618 AB, 0.382-0.886 BC, 2.24-3.618 CD)
        if (0.35 < ab_ratio < 0.65 and 
            0.38 < bc_ratio < 0.89 and
            2.20 < cd_ratio < 3.70):
            signal = 'BULLISH' if X['price'] < A['price'] else 'BEARISH'
            patterns.append({
                'name': 'Crab Pattern',
                'signal': signal,
                'strength': 'STRONG',
                'category': 'HARMONIC',
                'description': f'AB={ab_ratio:.3f}, BC={bc_ratio:.3f}, CD={cd_ratio:.3f}',
                'reliability': 73,
                'fib_levels': {'AB': ab_ratio, 'BC': bc_ratio, 'CD': cd_ratio}
            })
        
        # Deep Crab Pattern (0.886 AB, 0.382-0.886 BC, 2.618-3.618 CD)
        if (0.85 < ab_ratio < 0.95 and 
            0.38 < bc_ratio < 0.89 and
            2.60 < cd_ratio < 3.70):
            signal = 'BULLISH' if X['price'] < A['price'] else 'BEARISH'
            patterns.append({
                'name': 'Deep Crab Pattern',
                'signal': signal,
                'strength': 'STRONG',
                'category': 'HARMONIC',
                'description': f'AB={ab_ratio:.3f}, BC={bc_ratio:.3f}, CD={cd_ratio:.3f}',
                'reliability': 70,
                'fib_levels': {'AB': ab_ratio, 'BC': bc_ratio, 'CD': cd_ratio}
            })
        
        # AB=CD Pattern
        if 0.95 < (ab / cd) < 1.05 if cd > 0 else False:
            signal = 'BULLISH' if X['price'] < A['price'] else 'BEARISH'
            patterns.append({
                'name': 'AB=CD Pattern',
                'signal': signal,
                'strength': 'MODERATE',
                'category': 'HARMONIC',
                'description': f'Symmetrical AB=CD pattern. AB={ab:.2f}, CD={cd:.2f}',
                'reliability': 65,
                'fib_levels': {'AB': ab_ratio, 'BC': bc_ratio, 'CD': cd_ratio}
            })
        
        return patterns
    
    def find_swing_points(self, high: np.ndarray, low: np.ndarray, window: int = 5) -> List[Dict]:
        """Find swing high and low points."""
        swings = []
        
        for i in range(window, len(high) - window):
            # Swing High
            if high[i] == max(high[i-window:i+window+1]):
                swings.append({'index': i, 'price': high[i], 'type': 'HIGH'})
            # Swing Low
            elif low[i] == min(low[i-window:i+window+1]):
                swings.append({'index': i, 'price': low[i], 'type': 'LOW'})
        
        # Sort by index
        swings.sort(key=lambda x: x['index'])
        
        # Ensure alternating high/low
        filtered = []
        for swing in swings:
            if not filtered:
                filtered.append(swing)
            elif swing['type'] != filtered[-1]['type']:
                filtered.append(swing)
            else:
                # Keep the more extreme one
                if swing['type'] == 'HIGH' and swing['price'] > filtered[-1]['price']:
                    filtered[-1] = swing
                elif swing['type'] == 'LOW' and swing['price'] < filtered[-1]['price']:
                    filtered[-1] = swing
        
        return filtered


# ============================================================
# PATTERN FORMATTER
# ============================================================

class PatternFormatter:
    """Format pattern results for display."""
    
    @staticmethod
    def format_patterns(patterns: Dict) -> str:
        """Format all patterns into readable text."""
        lines = []
        
        summary = patterns.get('summary', {})
        
        lines.append(f"PATTERN ANALYSIS SUMMARY")
        lines.append(f"=" * 40)
        lines.append(f"Total Patterns Found: {summary.get('total_patterns', 0)}")
        lines.append(f"Bullish: {summary.get('bullish_count', 0)} | Bearish: {summary.get('bearish_count', 0)} | Neutral: {summary.get('neutral_count', 0)}")
        lines.append(f"Overall Signal: {summary.get('overall_signal', 'N/A')}")
        lines.append("")
        
        # Chart Patterns
        if patterns.get('chart'):
            lines.append("CHART PATTERNS:")
            lines.append("-" * 30)
            for p in patterns['chart']:
                lines.append(f"  {p['name']}: {p['signal']} ({p.get('strength', 'N/A')})")
                lines.append(f"    {p.get('description', '')}")
                if p.get('target'):
                    lines.append(f"    Target: {p['target']:.2f}")
                lines.append("")
        
        # Candlestick Patterns
        if patterns.get('candlestick'):
            lines.append("CANDLESTICK PATTERNS:")
            lines.append("-" * 30)
            for p in patterns['candlestick']:
                lines.append(f"  {p['name']}: {p['signal']}")
                lines.append(f"    {p.get('description', '')}")
                lines.append("")
        
        # Harmonic Patterns
        if patterns.get('harmonic'):
            lines.append("HARMONIC PATTERNS:")
            lines.append("-" * 30)
            for p in patterns['harmonic']:
                lines.append(f"  {p['name']}: {p['signal']}")
                lines.append(f"    {p.get('description', '')}")
                if p.get('fib_levels'):
                    fib = p['fib_levels']
                    lines.append(f"    Fib Levels: AB={fib['AB']:.3f}, BC={fib['BC']:.3f}, CD={fib['CD']:.3f}")
                lines.append("")
        
        return "\n".join(lines)
    
    @staticmethod
    def get_pattern_signal(patterns: Dict) -> Tuple[str, int]:
        """Get overall signal and score from patterns."""
        summary = patterns.get('summary', {})
        bullish = summary.get('bullish_count', 0)
        bearish = summary.get('bearish_count', 0)
        
        if bullish > bearish + 1:
            return 'BULLISH', min(85, 50 + bullish * 5)
        elif bearish > bullish + 1:
            return 'BEARISH', max(15, 50 - bearish * 5)
        else:
            return 'NEUTRAL', 50


if __name__ == "__main__":
    # Test with sample data
    print("Pattern Recognition Module")
    print("=" * 50)
    print("This module detects:")
    print("- Chart Patterns: H&S, Double Top/Bottom, Triangles, Flags")
    print("- Candlestick Patterns: Doji, Hammer, Engulfing, Stars")
    print("- Harmonic Patterns: Gartley, Butterfly, Bat, Crab")
    print("\nImport and use in your application.")
