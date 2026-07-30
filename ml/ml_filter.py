# ml_filter.py
import pandas as pd
import pandas_ta as ta
import joblib

class MLSignalFilter:
    def __init__(self, model_path='signal_filter_model.joblib'):
        self.model = joblib.load(model_path)
        
    def prepareFeatures(self, klines_data):
        
        df = pd.DataFrame(klines_data, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        df.ta.rsi(length=14, append=True)
        df.ta.macd(append=True)
        df.ta.bbands(append=True)
        df.ta.atr(append=True)
        df['close_pct_change'] = df['close'].pct_change()
        
        latest_features = df.dropna().iloc[-1:]
        
        feature_cols = [col for col in latest_features.columns if col not in ['time', 'open', 'high', 'low', 'close', 'target']]
        return latest_features[feature_cols]

    def is_signal_valid(self, klines_data) -> bool:
        try:
            features = self.prepare_features(klines_data)
            if features.empty:
                return False
            
            prediction = self.model.predict(features)[0]
            
            
            return bool(prediction == 1)
        except Exception as e:
            print(f"Ошибка ML фильтра: {e}")
            return False