import pandas as pd
from pybit.unified_trading import HTTP

def get_bybit_data(symbol="BTCUSDT", interval="60", limit=1000):
    
    print(f"Скачиваем данные для {symbol}...")
    
    session = HTTP(testnet=False)
    
    response = session.get_kline(
        category="linear",
        symbol=symbol,
        interval=interval,
        limit=limit
    )
    
    if response.get('retCode') == 0:
        klines = response['result']['list']
        
        df = pd.DataFrame(klines, columns=['time', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
        
        df = df.drop(columns=['turnover'])
        
        df['time'] = pd.to_numeric(df['time'])
        df['time'] = pd.to_datetime(df['time'], unit='ms')
        
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
            
        df = df.sort_values('time').reset_index(drop=True)
        
        return df
    else:
        print(f"Ошибка API: {response}")
        return None

if __name__ == "__main__":
    df = get_bybit_data(symbol="BTCUSDT", interval="60", limit=1000)
    
    if df is not None:
        filename = 'btc_usdt_1h.csv'
        df.to_csv(filename, index=False)
        print(f"Готово! Данные успешно сохранены в файл: {filename}")
        print(df.head())