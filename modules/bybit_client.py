from pybit.unified_trading import HTTP
import asyncio
from modules.config import API_ID, API_HASH, PHONE_NUMBER, SESSION_FILE, CHANNEL_NAMES , BYBIT_API_KEY , BYBIT_API_SECRET


class BybitClient:
    def __init__(self):
        self.session = HTTP(
            testnet=False,
            api_key=BYBIT_API_KEY,
            api_secret=BYBIT_API_SECRET,
        )  
        self.pending_tp_sl = None  
        self.pending_amounts = {}  


    def get_recent_klines(self, symbol, interval='15', limit=100):
        
        try:
            response = self.session.get_kline(
                category="linear",
                symbol=symbol,
                interval=interval,
                limit=limit
            )
            if response.get('retCode') == 0:
                klines = response['result']['list']
                
                formatted_klines = [k[:6] for k in klines]
                return formatted_klines[::-1] 
            return []
        
        except Exception as e:
            print(f"Ошибка получения свечей для {symbol}: {e}")
            return []

   
    async def get_current_price(self, symbol):
        try:
            ticker = self.session.get_tickers(
                category="linear",
                symbol=symbol
            )  
            if ticker and 'result' in ticker and 'list' in ticker['result']:  
                return float(ticker['result']['list'][0]['lastPrice'])  
            
        except Exception as e:  
            print(f" Ошибка получения цены {symbol}: {e}")  
        return None  

    async def execute_spot_trade(self, signal):

        try:
            symbol = signal['symbol']  
            action = signal['action']  
            
            print(f" Получение текущей цены на {symbol}...")  
            current_price = await self.get_current_price(symbol)  

            if not current_price:  
                print(f" Не удается получить текущую цену за {symbol}")  
                return None  
            
            print(f" Текущая рыночная цена: {current_price}")  
            
            trading_params = await self.get_trading_params(symbol)  
            min_qty = trading_params['min_qty']  
            qty_step = trading_params['qty_step']  
            price_precision = trading_params['price_precision']  
            tick_size = trading_params['tick_size']  
            
            entry_price = self.adjust_price_to_tick(current_price, tick_size)  
            
            order_amount_usdt = signal.get('custom_amount', 10)
            base_quantity = order_amount_usdt / entry_price  
            
            if base_quantity < min_qty:  
                quantity = min_qty  
            else:  
                quantity = base_quantity  
            
            quantity = self.adjust_to_step(quantity, qty_step)  
            
            try:
                balance = self.session.get_wallet_balance(accountType="UNIFIED")  
                if balance and 'result' in balance and 'list' in balance['result']:  
                    usdt_balance = 0  
                    for account in balance['result']['list']:  
                        for coin in account.get('coin', []):  
                            if coin['coin'] == 'USDT':  
                                usdt_balance = float(coin['walletBalance'])  
                                break  
                    
                    order_value = quantity * entry_price  
                    if usdt_balance < order_value:  
                        print(f"Недостаточно средств! Нужно: {order_value:.2f}, Доступно: {usdt_balance:.2f}")  
                        return None  
                    
            except Exception as e:  
                print(f" Не удалось проверить баланс: {e}")  
            
            side = "Sell" if action == "SELL" else "Buy"  
            
            order = self.session.place_order(
                category="linear",
                symbol=symbol,
                side=side,
                orderType="Market",
                qty=str(quantity),
                price=str(entry_price),
                timeInForce="GTC"
            )  
            
            if order and 'retCode' in order and order['retCode'] == 0:  
                print(f" Рыночный ордер размещен ID: {order['result']['orderId']}")  
                
                await self.set_tp_sl(
                    symbol=symbol,
                    quantity=quantity,
                    signal=signal,
                    side=side
                )  
                
                return order  
            else:  
                print(f" Ордер не выполнен: {order.get('retMsg', 'Unknown error')}")  
                return None  
                
        except Exception as e:  
            print(f" Ошибка создания ордера: {e}")  
            return None  

    async def get_trading_params(self, symbol):
        try:
            instruments = self.session.get_instruments_info(
                category="linear",
                symbol=symbol
            )  
            
            if instruments and 'result' in instruments and instruments['result']['list']:  
                instrument = instruments['result']['list'][0]  
                lot_size_filter = instrument.get('lotSizeFilter', {})  
                price_filter = instrument.get('priceFilter', {})  
                
                min_qty = float(lot_size_filter.get('minOrderQty', 1.0))  
                qty_step = float(lot_size_filter.get('qtyStep', 0.1))  
                tick_size = float(price_filter.get('tickSize', 0.01))  
                price_precision = self.get_price_precision(tick_size)  
                
                return {
                    'min_qty': min_qty,  
                    'qty_step': qty_step,  
                    'price_precision': price_precision,  
                    'tick_size': tick_size  
                }
            
        except Exception as e:  
            print(f" Ошибка при получении торговых параметров: {e}")  
        
        return {'min_qty': 1.0, 'qty_step': 0.1, 'price_precision': 4, 'tick_size': 0.01}  

    def get_price_precision(self, tick_size):
        try:
            if tick_size <= 0: return 4  
            tick_str = format(tick_size, '.10f').rstrip('0')  
            if '.' in tick_str:  
                return min(len(tick_str.split('.')[1]), 8)  
            return 0  
        except:  
            return 4  

    def priceTick(self, price, tick_size):
        if tick_size <= 0: return round(price, 4)  
        return round(price / tick_size) * tick_size  

    def step(self, quantity, step):
        if step <= 0: return quantity  
        try:
            adjusted = round(quantity / step) * step  
            if step < 0.001: adjusted = round(adjusted, 8)  
            elif step < 0.01: adjusted = round(adjusted, 6)  
            elif step < 0.1: adjusted = round(adjusted, 4)  
            elif step < 1: adjusted = round(adjusted, 2)  
            else: adjusted = round(adjusted, 0)  
            
            if adjusted.is_integer(): return float(int(adjusted))  
            return float(f"{adjusted:.10f}".rstrip('0').rstrip('.'))  
        
        except Exception as e:  
            print(f"Ошибка в шаге: {e}")  
            return round(quantity, 4)  

    async def get_open_positions(self, symbol):
        try:
            positions = self.session.get_positions(category="linear", symbol=symbol)  
            if positions and 'result' in positions and positions['result']['list']:  
                return [pos for pos in positions['result']['list'] if float(pos.get('size', 0)) > 0]  
            return []  
        
        except Exception as e:  
            print(f"Ошибка при получении позиций: {e}")  
            return []  

    async def get_open_orders(self, symbol):
        try:
            orders = self.session.get_open_orders(category="linear", symbol=symbol)  
            if orders and 'result' in orders and orders['result']['list']:  
                return orders['result']['list']  
            return []  
        
        except Exception as e:  
            print(f"Ошибка открытия ордера: {e}")  
            return []  
    
    async def set_tp_sl(self, symbol, quantity, signal, side):
        try:
            tp_sl_params = {
                "category": "linear",
                "symbol": symbol,
                "positionIdx": 0,
            }  
            
            if signal.get('tp'):  
                tp_sl_params["takeProfit"] = str(signal['tp'])  
            if signal.get('sl'):  
                tp_sl_params["stopLoss"] = str(signal['sl'])  
            
            if "takeProfit" in tp_sl_params or "stopLoss" in tp_sl_params:
                result = self.session.set_trading_stop(**tp_sl_params)  
                if result and 'retCode' in result and result['retCode'] == 0:  
                    print(" TP/SL выставлены!")  
                    return True  
            return False  
        
        except Exception as e:  
            print(f" Ошибка выставления TP/SL: {e}")  
            return False  

    async def cancel_orders_symbol(self, symbol):
        try:
            result = self.session.cancel_all_orders(category="linear", symbol=symbol)  
            return result.get('retCode') == 0  
        
        except Exception as e:  
            print(f" Ошибка при отмене ордера: {e}")  
            return False  
            
    async def get_order_status(self, symbol, order_id):
        try:
            order_info = self.session.get_order_history(
                category="linear",
                symbol=symbol,
                orderId=order_id
            )  
            if order_info and 'result' in order_info and order_info['result']['list']:  
                return order_info['result']['list'][0].get('orderStatus')  
            
        except Exception as e:  
            print(f" Ошибка получения статуса ордера: {e}")  
        return None  