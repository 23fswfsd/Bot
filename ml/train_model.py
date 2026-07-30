import pandas as pd
import pandas_ta as ta
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import joblib


df = pd.read_csv('btc_usdt_1h.csv') 

def createFeatures(data):
    df = data.copy()
    df.ta.rsi(length=14, append=True)          
    df.ta.macd(append=True)                    
    df.ta.bbands(append=True)                  
    df.ta.atr(append=True)                     
    
    df['close_pct_change'] = df['close'].pct_change()
    
    return df.dropna()

df_features = createFeatures(df)


df_features['target'] = (df_features['close'].shift(-1) > df_features['close']).astype(int)
df_features = df_features.dropna()


feature_cols = [col for col in df_features.columns if col not in ['time', 'open', 'high', 'low', 'close', 'target']]

X = df_features[feature_cols]
y = df_features['target']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

model = xgb.XGBClassifier(n_estimators=100, learning_rate=0.05, random_state=42)
model.fit(X_train, y_train)

preds = model.predict(X_test)
print(classification_report(y_test, preds))

joblib.dump(model, 'signal_filter_model.joblib')
print("Модель сохранена как signal_filter_model.joblib")