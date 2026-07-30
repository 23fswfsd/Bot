from config import DEFAULT_RISK_PERCENT, MIN_TRADE_AMOUNT

class RiskManager:
    def __init__(self, max_risk_per_trade=2.0):
        self.max_risk_per_trade = max_risk_per_trade
    
    def validate_signal(self, signal):
        try:
            print("Начало проверки рисков...")
            
            if not signal.get('symbol'):
                print(" Символ не найден")
                return False
            
            if not signal.get('action'):
                print(" Действие не найдено")
                return False
            
            if not signal.get('entry_range') or len(signal['entry_range']) != 2:
                print(" Недопустимый диапазон ввода")
                return False
            
            risk_percent = signal.get('risk_percent', DEFAULT_RISK_PERCENT)
            if risk_percent > self.max_risk_per_trade:
                print(f" Risk too high: {risk_percent}% (max: {self.max_risk_per_trade}%)")
                return False
            
            entry_min, entry_max = signal['entry_range']
            if entry_min <= 0 or entry_max <= 0 or entry_min >= entry_max:
                print(" Недопустимые входные цены")
                return False
            
            if signal.get('tp') and signal.get('sl'):
                if signal['action'] == 'SELL':
                    if signal['tp'] >= entry_min:
                        print(" TP должен быть ниже входа для коротких позиций")
                        return False
                    if signal['sl'] <= entry_max:
                        print(" SL должен быть выше входа для коротких")
                        return False
                else:  # BUY
                    if signal['tp'] <= entry_max:
                        print(" TP должен быть выше уровня входа для LONG")
                        return False
                    if signal['sl'] >= entry_min:
                        print(" SL должен быть ниже входа для LONG")
                        return False
            
            print(" Проверка риска пройдена")
            return True
            
        except Exception as e:
            print(f" Ошибка проверки риска: {e}")
            return False
