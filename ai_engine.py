#!/usr/bin/env python3
"""
AI/ML Engine for DR. NILESH SHAH'S MARKET ANALYSIS
===================================================
- AI Score Prediction (ML)
- Sentiment Analysis
- Anomaly Detection
- Pattern Recognition ML
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# ML Libraries
try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor, IsolationForest
    from sklearn.preprocessing import StandardScaler, LabelEncoder
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score
    import joblib
    SKLEARN_OK = True
except ImportError:
    SKLEARN_OK = False
    print("[WARNING] scikit-learn not installed. Run: pip install scikit-learn")


class AIScorePredictor:
    """ML model to predict future stock scores."""
    
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler() if SKLEARN_OK else None
        self.is_trained = False
        self.feature_names = [
            'rsi', 'macd_hist', 'sma20_ratio', 'sma50_ratio', 
            'adx', 'volume_change', 'price_change_5d', 'price_change_10d',
            'volatility', 'stoch_k', 'cci', 'williams_r'
        ]
    
    def prepare_features(self, df: pd.DataFrame) -> np.ndarray:
        """Extract features from stock data for ML model."""
        if df is None or len(df) < 10:
            return None
        
        try:
            close = df['Close'].values
            high = df['High'].values
            low = df['Low'].values
            volume = df['Volume'].values
            
            # Current values
            current_price = close[-1]
            
            # RSI
            try:
                import ta
                rsi = ta.momentum.RSIIndicator(df['Close'], 14).rsi().iloc[-1]
            except:
                rsi = 50.0
            
            # MACD Histogram
            try:
                macd = ta.trend.MACD(df['Close'])
                macd_hist = macd.macd_diff().iloc[-1]
            except:
                macd_hist = 0.0
            
            # Price ratios
            sma20 = np.mean(close[-20:]) if len(close) >= 20 else current_price
            sma50 = np.mean(close[-50:]) if len(close) >= 50 else current_price
            
            sma20_ratio = current_price / sma20 if sma20 > 0 else 1.0
            sma50_ratio = current_price / sma50 if sma50 > 0 else 1.0
            
            # ADX
            try:
                adx = ta.trend.ADXIndicator(df['High'], df['Low'], df['Close']).adx().iloc[-1]
            except:
                adx = 25.0
            
            # Volume change
            vol_avg = np.mean(volume[-20:]) if len(volume) >= 20 else volume[-1]
            volume_change = volume[-1] / vol_avg if vol_avg > 0 else 1.0
            
            # Price changes
            price_change_5d = (close[-1] / close[-6] - 1) * 100 if len(close) >= 6 else 0
            price_change_10d = (close[-1] / close[-11] - 1) * 100 if len(close) >= 11 else 0
            
            # Volatility (ATR ratio)
            try:
                atr = ta.volatility.AverageTrueRange(df['High'], df['Low'], df['Close'], 14).average_true_range().iloc[-1]
                volatility = atr / current_price if current_price > 0 else 0.02
            except:
                volatility = 0.02
            
            # Stochastic K
            try:
                stoch = ta.momentum.StochasticOscillator(df['High'], df['Low'], df['Close'])
                stoch_k = stoch.stoch().iloc[-1]
            except:
                stoch_k = 50.0
            
            # CCI
            try:
                cci = ta.trend.CCIIndicator(df['High'], df['Low'], df['Close']).cci().iloc[-1]
            except:
                cci = 0.0
            
            # Williams %R
            try:
                wr = ta.momentum.WilliamsRIndicator(df['High'], df['Low'], df['Close']).williams_r().iloc[-1]
            except:
                wr = -50.0
            
            features = np.array([[
                rsi if not np.isnan(rsi) else 50,
                macd_hist if not np.isnan(macd_hist) else 0,
                sma20_ratio,
                sma50_ratio,
                adx if not np.isnan(adx) else 25,
                volume_change,
                price_change_5d,
                price_change_10d,
                volatility,
                stoch_k if not np.isnan(stoch_k) else 50,
                cci if not np.isnan(cci) else 0,
                wr if not np.isnan(wr) else -50
            ]])
            
            return features
            
        except Exception as e:
            return None
    
    def train_with_synthetic(self):
        """Train model with synthetic data based on technical analysis rules."""
        if not SKLEARN_OK:
            return False
        
        try:
            # Generate synthetic training data
            np.random.seed(42)
            n_samples = 1000
            
            X = np.random.randn(n_samples, len(self.feature_names))
            
            # Generate scores based on technical rules
            y = np.zeros(n_samples)
            
            for i in range(n_samples):
                score = 50  # Base score
                
                # RSI contribution
                rsi = X[i, 0] * 15 + 50  # Denormalize
                if rsi < 30:
                    score += 20
                elif rsi < 40:
                    score += 10
                elif rsi > 70:
                    score -= 20
                elif rsi > 60:
                    score -= 10
                
                # MACD contribution
                if X[i, 1] > 0:
                    score += 10
                else:
                    score -= 10
                
                # Price above SMA
                if X[i, 2] > 1:
                    score += 10
                else:
                    score -= 10
                
                # Volume surge
                if X[i, 5] > 1.5:
                    score += 5
                
                # Momentum
                if X[i, 6] > 2:
                    score += 10
                elif X[i, 6] < -2:
                    score -= 10
                
                # Add noise
                score += np.random.randn() * 5
                
                y[i] = np.clip(score, 0, 100)
            
            # Train model
            self.model = GradientBoostingRegressor(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                random_state=42
            )
            
            X_scaled = self.scaler.fit_transform(X)
            self.model.fit(X_scaled, y)
            self.is_trained = True
            
            return True
            
        except Exception as e:
            print(f"Training error: {e}")
            return False
    
    def predict_score(self, df: pd.DataFrame) -> dict:
        """Predict future score for a stock."""
        if not SKLEARN_OK:
            return {'predicted_score': None, 'confidence': 0, 'trend': 'N/A', 'error': 'ML not available'}
        
        if not self.is_trained:
            self.train_with_synthetic()
        
        features = self.prepare_features(df)
        if features is None:
            return {'predicted_score': None, 'confidence': 0, 'trend': 'N/A', 'error': 'Insufficient data'}
        
        try:
            X_scaled = self.scaler.transform(features)
            predicted = self.model.predict(X_scaled)[0]
            predicted = np.clip(predicted, 0, 100)
            
            # Calculate confidence based on feature quality
            confidence = min(85, max(40, 70 - abs(features[0][0] - 50) * 0.5))
            
            # Determine trend
            if predicted >= 70:
                trend = 'STRONG UPTREND'
            elif predicted >= 55:
                trend = 'UPTREND'
            elif predicted >= 45:
                trend = 'NEUTRAL'
            elif predicted >= 30:
                trend = 'DOWNTREND'
            else:
                trend = 'STRONG DOWNTREND'
            
            # Prediction range
            margin = 100 - confidence
            low = max(0, predicted - margin / 2)
            high = min(100, predicted + margin / 2)
            
            return {
                'predicted_score': round(predicted, 1),
                'confidence': round(confidence, 1),
                'trend': trend,
                'range_low': round(low, 1),
                'range_high': round(high, 1),
                'features_used': len(self.feature_names)
            }
            
        except Exception as e:
            return {'predicted_score': None, 'confidence': 0, 'trend': 'N/A', 'error': str(e)}


class SentimentAnalyzer:
    """Analyze market sentiment from various sources."""
    
    def __init__(self):
        self.sentiment_keywords = {
            'bullish': ['buy', 'bull', 'bullish', 'up', 'rise', 'gain', 'profit', 'growth', 
                       'positive', 'strong', 'breakout', 'rally', 'surge', 'boom', 'outperform',
                       'upgrade', 'accumulate', 'target', 'momentum', 'high'],
            'bearish': ['sell', 'bear', 'bearish', 'down', 'fall', 'loss', 'decline', 'weak',
                       'negative', 'breakdown', 'crash', 'dump', 'slump', 'underperform',
                       'downgrade', 'reduce', 'risk', 'fear', 'low', 'correction']
        }
        
        # Common stock-related news sources sentiment
        self.market_sentiment_indicators = {
            'fear_greed_zones': {
                'extreme_fear': (0, 25),
                'fear': (25, 45),
                'neutral': (45, 55),
                'greed': (55, 75),
                'extreme_greed': (75, 100)
            }
        }
    
    def analyze_price_sentiment(self, df: pd.DataFrame) -> dict:
        """Analyze sentiment based on price action (proxy for market sentiment)."""
        if df is None or len(df) < 5:
            return {'score': 50, 'label': 'NEUTRAL', 'factors': []}
        
        close = df['Close'].values
        volume = df['Volume'].values
        
        factors = []
        score = 50
        
        # 1. Price momentum (5-day)
        if len(close) >= 6:
            momentum_5d = (close[-1] / close[-6] - 1) * 100
            if momentum_5d > 3:  # Lowered threshold
                factors.append(('5-day momentum', 'BULLISH', f'+{momentum_5d:.1f}%'))
                score += 10
            elif momentum_5d < -3:  # Lowered threshold
                factors.append(('5-day momentum', 'BEARISH', f'{momentum_5d:.1f}%'))
                score -= 10
        
        # 2. Price momentum (10-day)
        if len(close) >= 11:
            momentum_10d = (close[-1] / close[-11] - 1) * 100
            if momentum_10d > 5:
                factors.append(('10-day momentum', 'BULLISH', f'+{momentum_10d:.1f}%'))
                score += 10
            elif momentum_10d < -5:
                factors.append(('10-day momentum', 'BEARISH', f'{momentum_10d:.1f}%'))
                score -= 10
        
        # 2b. Price momentum (20-day)
        if len(close) >= 21:
            momentum_20d = (close[-1] / close[-21] - 1) * 100
            if momentum_20d > 10:
                factors.append(('20-day momentum', 'BULLISH', f'+{momentum_20d:.1f}%'))
                score += 10
            elif momentum_20d < -10:
                factors.append(('20-day momentum', 'BEARISH', f'{momentum_20d:.1f}%'))
                score -= 10
        
        # 3. Volume analysis
        if len(volume) >= 20:
            vol_avg = np.mean(volume[-20:])
            vol_ratio = volume[-1] / vol_avg if vol_avg > 0 else 1
            
            if vol_ratio > 2:
                if close[-1] > close[-2]:
                    factors.append(('Volume surge', 'BULLISH', f'{vol_ratio:.1f}x avg'))
                    score += 8
                else:
                    factors.append(('Volume surge', 'BEARISH', f'{vol_ratio:.1f}x avg'))
                    score -= 8
            elif vol_ratio < 0.5:
                factors.append(('Low volume', 'NEUTRAL', f'{vol_ratio:.1f}x avg'))
        
        # 4. Volatility
        if len(close) >= 20:
            recent_close = close[-20:]
            returns = np.diff(recent_close) / recent_close[:-1]
            volatility = np.std(returns) * 100
            if volatility > 3:
                factors.append(('High volatility', 'RISKY', f'{volatility:.1f}%'))
                score -= 5
            elif volatility < 1:
                factors.append(('Low volatility', 'STABLE', f'{volatility:.1f}%'))
                score += 3
        
        # 5. Trend strength
        if len(close) >= 50:
            sma20 = np.mean(close[-20:])
            sma50 = np.mean(close[-50:])
            
            if close[-1] > sma20 > sma50:
                factors.append(('Trend', 'BULLISH', 'Price > SMA20 > SMA50'))
                score += 10
            elif close[-1] < sma20 < sma50:
                factors.append(('Trend', 'BEARISH', 'Price < SMA20 < SMA50'))
                score -= 10
        
        # 6. Recent highs/lows
        if len(close) >= 20:
            recent_high = max(close[-20:])
            recent_low = min(close[-20:])
            position = (close[-1] - recent_low) / (recent_high - recent_low) if recent_high != recent_low else 0.5
            
            if position > 0.8:
                factors.append(('Position', 'BULLISH', f'{position*100:.0f}% of range'))
                score += 5
            elif position < 0.2:
                factors.append(('Position', 'BEARISH', f'{position*100:.0f}% of range'))
                score -= 5
        
        # Normalize score
        score = max(0, min(100, score))
        
        # Determine label
        if score >= 70:
            label = 'VERY BULLISH'
        elif score >= 55:
            label = 'BULLISH'
        elif score >= 45:
            label = 'NEUTRAL'
        elif score >= 30:
            label = 'BEARISH'
        else:
            label = 'VERY BEARISH'
        
        return {
            'score': round(score, 1),
            'label': label,
            'factors': factors
        }
    
    def analyze_keyword_sentiment(self, text: str) -> dict:
        """Analyze sentiment from text using keyword matching."""
        if not text:
            return {'score': 50, 'label': 'NEUTRAL', 'keywords_found': []}
        
        text_lower = text.lower()
        words = text_lower.split()
        
        bullish_count = 0
        bearish_count = 0
        found_keywords = []
        
        for word in words:
            if word in self.sentiment_keywords['bullish']:
                bullish_count += 1
                found_keywords.append(('BULLISH', word))
            elif word in self.sentiment_keywords['bearish']:
                bearish_count += 1
                found_keywords.append(('BEARISH', word))
        
        total = bullish_count + bearish_count
        if total == 0:
            return {'score': 50, 'label': 'NEUTRAL', 'keywords_found': []}
        
        # Calculate score
        bull_ratio = bullish_count / total
        score = 50 + (bull_ratio - 0.5) * 100
        
        score = max(0, min(100, score))
        
        if score >= 65:
            label = 'BULLISH'
        elif score >= 55:
            label = 'SLIGHTLY BULLISH'
        elif score >= 45:
            label = 'NEUTRAL'
        elif score >= 35:
            label = 'SLIGHTLY BEARISH'
        else:
            label = 'BEARISH'
        
        return {
            'score': round(score, 1),
            'label': label,
            'bullish_keywords': bullish_count,
            'bearish_keywords': bearish_count,
            'keywords_found': found_keywords[:10]
        }


class AnomalyDetector:
    """Detect unusual price/volume patterns."""
    
    def __init__(self):
        self.isolation_forest = None
        if SKLEARN_OK:
            self.isolation_forest = IsolationForest(
                n_estimators=100,
                contamination=0.1,
                random_state=42
            )
    
    def detect_anomalies(self, df: pd.DataFrame) -> dict:
        """Detect anomalies in stock data."""
        if df is None or len(df) < 5:
            return {'anomalies': [], 'anomaly_score': 0, 'status': 'Insufficient data'}
        
        anomalies = []
        
        close = df['Close'].values
        high = df['High'].values
        low = df['Low'].values
        volume = df['Volume'].values
        
        # 1. Price Gap Anomalies
        gaps = self._detect_price_gaps(close, high, low)
        anomalies.extend(gaps)
        
        # 2. Volume Anomalies
        vol_anomalies = self._detect_volume_anomalies(volume, close)
        anomalies.extend(vol_anomalies)
        
        # 3. Price Spike Anomalies
        spike_anomalies = self._detect_price_spikes(close)
        anomalies.extend(spike_anomalies)
        
        # 4. Volatility Anomalies
        vol_spike = self._detect_volatility_spikes(close, high, low)
        anomalies.extend(vol_spike)
        
        # 5. ML-based Anomaly Detection
        if SKLEARN_OK and len(df) >= 20:  # Lowered requirement
            ml_anomalies = self._ml_anomaly_detection(df)
            anomalies.extend(ml_anomalies)
        
        # Calculate overall anomaly score
        anomaly_score = min(100, len(anomalies) * 15)
        
        # Determine status
        if anomaly_score >= 70:
            status = 'HIGH ANOMALY DETECTED'
        elif anomaly_score >= 40:
            status = 'MODERATE ANOMALIES'
        elif anomaly_score >= 20:
            status = 'LOW ANOMALIES'
        else:
            status = 'NORMAL'
        
        return {
            'anomalies': anomalies,
            'anomaly_score': anomaly_score,
            'total_anomalies': len(anomalies),
            'status': status,
            'warning': anomaly_score >= 50
        }
    
    def _detect_price_gaps(self, close, high, low) -> list:
        """Detect price gaps."""
        anomalies = []
        
        for i in range(1, min(10, len(close))):
            gap_up = low[-i] > high[-i-1]
            gap_down = high[-i] < low[-i-1]
            
            if gap_up:
                gap_pct = (low[-i] - high[-i-1]) / high[-i-1] * 100
                if gap_pct > 0.5:  # Lowered threshold
                    anomalies.append({
                        'type': 'GAP UP',
                        'severity': 'HIGH' if gap_pct > 5 else 'MEDIUM',
                        'description': f'Gap up of {gap_pct:.1f}%',
                        'days_ago': i,
                        'signal': 'BULLISH'
                    })
            
            if gap_down:
                gap_pct = (low[-i-1] - high[-i]) / low[-i-1] * 100
                if gap_pct > 2:
                    anomalies.append({
                        'type': 'GAP DOWN',
                        'severity': 'HIGH' if gap_pct > 5 else 'MEDIUM',
                        'description': f'Gap down of {gap_pct:.1f}%',
                        'days_ago': i,
                        'signal': 'BEARISH'
                    })
        
        return anomalies
    
    def _detect_volume_anomalies(self, volume, close) -> list:
        """Detect volume anomalies."""
        anomalies = []
        
        if len(volume) < 20:
            return anomalies
        
        vol_avg = np.mean(volume[-20:])
        vol_std = np.std(volume[-20:])
        
        # Recent volume spikes
        for i in range(1, min(6, len(volume))):
            vol_ratio = volume[-i] / vol_avg if vol_avg > 0 else 1
            
            if vol_ratio > 2:  # Lowered threshold
                price_change = (close[-i] - close[-i-1]) / close[-i-1] * 100 if i < len(close) else 0
                anomalies.append({
                    'type': 'VOLUME SPIKE',
                    'severity': 'HIGH' if vol_ratio > 4 else 'MEDIUM',
                    'description': f'Volume {vol_ratio:.1f}x average',
                    'days_ago': i,
                    'signal': 'BULLISH' if price_change > 0 else 'BEARISH',
                    'price_change': price_change
                })
        
        return anomalies
    
    def _detect_price_spikes(self, close) -> list:
        """Detect price spikes."""
        anomalies = []
        
        if len(close) < 5:
            return anomalies
        
        for i in range(1, min(6, len(close))):
            daily_return = (close[-i] - close[-i-1]) / close[-i-1] * 100 if i < len(close) else 0
            
            if abs(daily_return) > 2:  # Lowered threshold
                anomalies.append({
                    'type': 'PRICE SPIKE',
                    'severity': 'HIGH' if abs(daily_return) > 5 else 'MEDIUM',
                    'description': f'Price moved {daily_return:+.1f}% in one day',
                    'days_ago': i,
                    'signal': 'BULLISH' if daily_return > 0 else 'BEARISH'
                })
        
        return anomalies
    
    def _detect_volatility_spikes(self, close, high, low) -> list:
        """Detect volatility spikes."""
        anomalies = []
        
        if len(close) < 20:
            return anomalies
        
        # Calculate rolling volatility (fix array size mismatch)
        recent_close = close[-20:]
        returns = np.diff(recent_close) / recent_close[:-1]
        
        if len(returns) < 10:
            return anomalies
        
        current_vol = np.std(returns[-5:]) * 100
        avg_vol = np.std(returns) * 100
        
        if avg_vol > 0 and current_vol > avg_vol * 1.5:  # Lowered threshold
            anomalies.append({
                'type': 'VOLATILITY SPIKE',
                'severity': 'HIGH' if current_vol > avg_vol * 2 else 'MEDIUM',
                'description': f'Volatility {current_vol/avg_vol:.1f}x higher than average',
                'days_ago': 0,
                'signal': 'CAUTION'
            })
        
        return anomalies
    
    def _ml_anomaly_detection(self, df: pd.DataFrame) -> list:
        """Use Isolation Forest for ML-based anomaly detection."""
        anomalies = []
        
        try:
            close = df['Close'].values
            volume = df['Volume'].values
            
            # Prepare features
            returns = np.diff(close) / close[:-1]
            vol_changes = np.diff(volume) / volume[:-1]
            
            min_len = min(len(returns), len(vol_changes))
            features = np.column_stack([
                returns[-min_len:],
                vol_changes[-min_len:],
                np.abs(returns[-min_len:]) * vol_changes[-min_len:]  # Interaction
            ])
            
            # Remove NaN/Inf
            features = np.nan_to_num(features, nan=0, posinf=0, neginf=0)
            
            # Fit and predict
            self.isolation_forest.fit(features)
            predictions = self.isolation_forest.predict(features)
            
            # Check last few points
            for i in range(1, min(4, len(predictions))):
                if predictions[-i] == -1:  # Anomaly
                    anomalies.append({
                        'type': 'ML ANOMALY',
                        'severity': 'MEDIUM',
                        'description': f'ML detected unusual pattern ({i} days ago)',
                        'days_ago': i,
                        'signal': 'UNUSUAL'
                    })
            
        except:
            pass
        
        return anomalies


class PatternML:
    """ML-based pattern recognition."""
    
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler() if SKLEARN_OK else None
        self.pattern_labels = [
            'UPTREND', 'DOWNTREND', 'SIDEWAYS',
            'BREAKOUT_UP', 'BREAKOUT_DOWN',
            'REVERSAL_BULL', 'REVERSAL_BEAR',
            'CONSOLIDATION'
        ]
        self.is_trained = False
    
    def extract_pattern_features(self, df: pd.DataFrame) -> np.ndarray:
        """Extract features for pattern classification."""
        if df is None or len(df) < 10:
            return None
        
        try:
            close = df['Close'].values
            high = df['High'].values
            low = df['Low'].values
            
            features = []
            
            # Price momentum at different periods
            for period in [5, 10, 20]:
                if len(close) > period:
                    mom = (close[-1] / close[-period-1] - 1) * 100
                    features.append(mom)
                else:
                    features.append(0)
            
            # Volatility
            if len(close) >= 20:
                returns = np.diff(close[-20:]) / close[-21:-1]
                features.append(np.std(returns) * 100)
            else:
                features.append(2)
            
            # High-Low range
            if len(close) >= 20:
                range_pct = (max(high[-20:]) - min(low[-20:])) / close[-1] * 100
                features.append(range_pct)
            else:
                features.append(10)
            
            # SMA ratios
            for period in [10, 20, 50]:
                if len(close) >= period:
                    sma = np.mean(close[-period:])
                    features.append(close[-1] / sma)
                else:
                    features.append(1)
            
            # Volume trend
            if len(df) >= 20:
                vol = df['Volume'].values
                vol_sma = np.mean(vol[-20:])
                features.append(vol[-1] / vol_sma if vol_sma > 0 else 1)
            else:
                features.append(1)
            
            # Price position in range
            if len(close) >= 20:
                h = max(high[-20:])
                l = min(low[-20:])
                pos = (close[-1] - l) / (h - l) if h != l else 0.5
                features.append(pos)
            else:
                features.append(0.5)
            
            # Consecutive up/down days
            consecutive = 0
            for i in range(-1, -min(10, len(close)), -1):
                if close[i] > close[i-1]:
                    consecutive += 1
                else:
                    break
            features.append(consecutive)
            
            consecutive = 0
            for i in range(-1, -min(10, len(close)), -1):
                if close[i] < close[i-1]:
                    consecutive += 1
                else:
                    break
            features.append(-consecutive)
            
            return np.array(features).reshape(1, -1)
            
        except:
            return None
    
    def train_pattern_model(self):
        """Train pattern recognition model with synthetic data."""
        if not SKLEARN_OK:
            return False
        
        try:
            np.random.seed(42)
            n_samples = 800
            n_features = 10
            
            X = np.random.randn(n_samples, n_features)
            y = np.random.choice(self.pattern_labels, n_samples)
            
            # Create rules for synthetic data
            for i in range(n_samples):
                if X[i, 0] > 5 and X[i, 1] > 3:  # Strong uptrend + high momentum
                    y[i] = 'UPTREND'
                elif X[i, 0] < -5 and X[i, 1] > 3:
                    y[i] = 'DOWNTREND'
                elif abs(X[i, 0]) < 2:
                    y[i] = 'SIDEWAYS'
                elif X[i, 0] > 8:
                    y[i] = 'BREAKOUT_UP'
                elif X[i, 0] < -8:
                    y[i] = 'BREAKOUT_DOWN'
            
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=8,
                random_state=42
            )
            
            X_scaled = self.scaler.fit_transform(X)
            self.model.fit(X_scaled, y)
            self.is_trained = True
            
            return True
            
        except Exception as e:
            print(f"Pattern ML training error: {e}")
            return False
    
    def predict_pattern(self, df: pd.DataFrame) -> dict:
        """Predict current market pattern."""
        if not SKLEARN_OK:
            return {'pattern': 'N/A', 'confidence': 0, 'description': 'ML not available'}
        
        if not self.is_trained:
            self.train_pattern_model()
        
        features = self.extract_pattern_features(df)
        if features is None:
            return {'pattern': 'SIDEWAYS', 'confidence': 50, 'description': 'Insufficient data for ML prediction'}
        
        try:
            X_scaled = self.scaler.transform(features)
            prediction = self.model.predict(X_scaled)[0]
            probabilities = self.model.predict_proba(X_scaled)[0]
            confidence = max(probabilities) * 100
            
            # Pattern descriptions
            descriptions = {
                'UPTREND': 'Strong bullish trend. Price making higher highs.',
                'DOWNTREND': 'Strong bearish trend. Price making lower lows.',
                'SIDEWAYS': 'Consolidation phase. No clear direction.',
                'BREAKOUT_UP': 'Bullish breakout detected. Price breaking resistance.',
                'BREAKOUT_DOWN': 'Bearish breakdown. Price breaking support.',
                'REVERSAL_BULL': 'Potential bullish reversal forming.',
                'REVERSAL_BEAR': 'Potential bearish reversal forming.',
                'CONSOLIDATION': 'Price consolidating. Await breakout direction.'
            }
            
            # Get top 3 patterns
            top_indices = np.argsort(probabilities)[-3:][::-1]
            top_patterns = [
                {'pattern': self.pattern_labels[i], 'probability': round(probabilities[i] * 100, 1)}
                for i in top_indices
            ]
            
            return {
                'pattern': prediction,
                'confidence': round(confidence, 1),
                'description': descriptions.get(prediction, 'Pattern detected'),
                'top_patterns': top_patterns
            }
            
        except Exception as e:
            return {'pattern': 'N/A', 'confidence': 0, 'description': str(e)}


class AIEngine:
    """Main AI Engine combining all AI/ML features."""
    
    def __init__(self):
        self.score_predictor = AIScorePredictor()
        self.sentiment_analyzer = SentimentAnalyzer()
        self.anomaly_detector = AnomalyDetector()
        self.pattern_ml = PatternML()
        
        # Pre-train models
        self._initialize_models()
    
    def _initialize_models(self):
        """Initialize and pre-train ML models."""
        if SKLEARN_OK:
            print("[AI] Initializing ML models...")
            self.score_predictor.train_with_synthetic()
            self.pattern_ml.train_pattern_model()
            print("[AI] ML models ready!")
    
    def full_analysis(self, df: pd.DataFrame) -> dict:
        """Run complete AI analysis on stock data."""
        results = {
            'score_prediction': {},
            'sentiment': {},
            'anomalies': {},
            'pattern_ml': {},
            'ai_score': 0,
            'ai_signal': 'N/A'
        }
        
        try:
            # 1. Score Prediction
            results['score_prediction'] = self.score_predictor.predict_score(df)
            
            # 2. Sentiment Analysis
            results['sentiment'] = self.sentiment_analyzer.analyze_price_sentiment(df)
            
            # 3. Anomaly Detection
            results['anomalies'] = self.anomaly_detector.detect_anomalies(df)
            
            # 4. Pattern ML
            results['pattern_ml'] = self.pattern_ml.predict_pattern(df)
            
            # 5. Calculate combined AI score
            scores = []
            
            pred_score = results['score_prediction'].get('predicted_score')
            if pred_score is not None and pred_score > 0:
                scores.append(pred_score)
            
            sent_score = results['sentiment'].get('score')
            if sent_score is not None and sent_score > 0:
                scores.append(sent_score)
            
            pattern = results['pattern_ml'].get('pattern')
            if pattern and pattern != 'N/A':
                if pattern in ['UPTREND', 'BREAKOUT_UP', 'REVERSAL_BULL']:
                    scores.append(70)
                elif pattern in ['DOWNTREND', 'BREAKOUT_DOWN', 'REVERSAL_BEAR']:
                    scores.append(30)
                else:
                    scores.append(50)
            
            if scores:
                results['ai_score'] = round(np.mean(scores), 1)
            else:
                results['ai_score'] = 50  # Default to neutral
            
            # Determine AI signal
            ai_score = results['ai_score']
            if ai_score >= 75:
                results['ai_signal'] = 'STRONG BUY'
            elif ai_score >= 60:
                results['ai_signal'] = 'BUY'
            elif ai_score >= 45:
                results['ai_signal'] = 'HOLD'
            elif ai_score >= 30:
                results['ai_signal'] = 'SELL'
            else:
                results['ai_signal'] = 'STRONG SELL'
            
        except Exception as e:
            results['error'] = str(e)
        
        return results


# Test
if __name__ == "__main__":
    print("AI Engine Module")
    print("=" * 50)
    print("Features:")
    print("- AI Score Prediction (ML)")
    print("- Sentiment Analysis")
    print("- Anomaly Detection")
    print("- Pattern Recognition ML")
    print(f"\nScikit-learn available: {SKLEARN_OK}")
    
    if SKLEARN_OK:
        print("\nInitializing AI Engine...")
        engine = AIEngine()
        print("AI Engine ready!")
