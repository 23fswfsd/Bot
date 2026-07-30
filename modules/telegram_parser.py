import re
import time
import asyncio
from telethon import TelegramClient, events
from telethon.tl.types import Channel, Chat
from modules.config import API_ID, API_HASH, PHONE_NUMBER, SESSION_FILE, CHANNEL_NAMES
class TelegramParser:
    def __init__(self):
        self.client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
        self.monitored_chats = []
        
    async def send_notification(self, message):
        print(f" (Заглушка уведомления): {message}")
        pass

    async def find_channels_by_name(self):
        print(" Поиск каналов по названию...")
        
        
        dialogs = await self.client.get_dialogs()
        found_channels = []
        
        for dialog in dialogs:
            entity = dialog.entity
            
            if isinstance(entity, (Channel, Chat)):
                chat_title = getattr(entity, 'title', '')
                
                for channel_name in CHANNEL_NAMES:
                    if channel_name.lower() in chat_title.lower():
                        found_channels.append(entity)
                        print(f" Канал найден: {chat_title} (ID: {entity.id})")
                        break
        
        return found_channels      

    def parse_signal(self, message):
        try:
            lines = [line.strip() for line in message.split('\n') if line.strip()]
            
            if len(lines) < 3:
                print(" Not enough lines for valid signal")
                return None
            
            signal = {
                'action': None,
                'symbol': None,
                'entry_range': [],
                'entry_price': None,
                'tp': None,
                'sl': None,
                'risk_percent': 1.0
            }
            
            first_line = lines[0]
            print(f" First line: {first_line}")
            
            clean_line = first_line.replace('**', '')
            print(f" Clean line: {clean_line}")
            
            symbol_match = re.search(r'#([A-Za-z0-9]+)/USDT\.?', clean_line, re.IGNORECASE)
            if not symbol_match:
                symbol_match = re.search(r'\$([A-Za-z0-9]+)/USDT\.?', clean_line, re.IGNORECASE)
            
            if symbol_match:
                symbol_name = symbol_match.group(1).upper()
                signal['symbol'] = f"{symbol_name}USDT"
                print(f" Symbol found: {signal['symbol']}")
            else:
                symbol_match = re.search(r'([A-Za-z0-9]+)/USDT\.?', clean_line, re.IGNORECASE)
                if symbol_match:
                    symbol_name = symbol_match.group(1).upper()
                    signal['symbol'] = f"{symbol_name}USDT"
                    print(f" Symbol found (without # or $): {signal['symbol']}")
                else:
                    print(" Symbol not found in first line")
                    return None
            
            clean_line_upper = clean_line.upper()
            if 'SHORT' in clean_line_upper or 'ШОРТ' in clean_line_upper:
                signal['action'] = 'SELL'
            elif 'LONG' in clean_line_upper or 'ЛОНГ' in clean_line_upper or 'BUY' in clean_line_upper:
                signal['action'] = 'BUY'
            
            print(f" Action: {signal['action']}")
            
            entry_found = False
            full_text = ' '.join(lines).upper()  
            
            print(f" Полный текст для поиска входа: {full_text[:200]}...")
            
            entry_patterns = [
                r'ЛИМИТНАЯ ТОЧКА ВХОДА:\s*([\d.]+)\$?\s*-\s*([\d.]+)\$?',
                r'ДИАПАЗОН ВХОДА:\s*([\d.]+)\$?\s*-\s*([\d.]+)\$?',
                r'ВХОД:\s*([\d.]+)\$?\s*-\s*([\d.]+)\$?',
                r'ENTRY:\s*([\d.]+)\$?\s*-\s*([\d.]+)\$?',
                r'([\d.]+)\$?\s*-\s*([\d.]+)\$?\s*\(вход\)',
            ]
            
            for pattern in entry_patterns:
                entry_match = re.search(pattern, full_text, re.IGNORECASE)
                if entry_match:
                    signal['entry_range'] = [
                        float(entry_match.group(1)),
                        float(entry_match.group(2))
                    ]
                    entry_found = True
                    print(f" Диапазон входа, найденный '{pattern}': {signal['entry_range']}")
                    break
            
            if not entry_found:
                single_patterns = [
                    r'ЛИМИТНАЯ ТОЧКА ВХОДА:\s*\$?\s*([\d.]+)',
                    r'ВХОД:\s*\$?\s*([\d.]+)\$?\s*\(лимит\)',
                    r'ВХОД:\s*\$?\s*([\d.]+)',
                    r'ENTRY:\s*\$?\s*([\d.]+)',
                ]
                
                for pattern in single_patterns:
                    single_match = re.search(pattern, full_text, re.IGNORECASE)
                    if single_match:
                        entry_price = float(single_match.group(1))
                        signal['entry_price'] = entry_price
                        signal['entry_range'] = [
                            entry_price * 0.99,
                            entry_price * 1.01
                        ]
                        entry_found = True
                        print(f" Цена за один вход '{pattern}': {entry_price}")
                        break
            
            if not entry_found:
                any_range_match = re.search(r'(\d+\.?\d*)\$?\s*-\s*(\d+\.?\d*)\$?', full_text)
                if any_range_match:
                    signal['entry_range'] = [
                        float(any_range_match.group(1)),
                        float(any_range_match.group(2))
                    ]
                    entry_found = True
                    print(f" Найден диапазон входа: {signal['entry_range']}")
            
            for line in lines[1:]:
                clean_line = line.replace('**', '')
                
                if 'TP:' in clean_line.upper():
                    tp_matches = re.findall(r'(\d+\.?\d*)\$?', clean_line)
                    if tp_matches:
                        signal['tp'] = float(tp_matches[0])
                        print(f" TP: {signal['tp']}")
                
                elif 'SL:' in clean_line.upper():
                    sl_match = re.search(r'SL:\s*\$?\s*([\d.]+)', clean_line, re.IGNORECASE)
                    if sl_match:
                        signal['sl'] = float(sl_match.group(1))
                        print(f" SL: {signal['sl']}")
                
                elif 'РИСК:' in clean_line.upper():
                    risk_match = re.search(r'РИСК:\s*([\d.]+)', clean_line, re.IGNORECASE)
                    if risk_match:
                        signal['risk_percent'] = float(risk_match.group(1))
                        print(f" Risk: {signal['risk_percent']}%")
            
            if signal['symbol'] and signal['action'] and (signal['entry_range'] or signal['entry_price']):
                print(f" сигнал подтвержден : {signal}")
                return signal
            else:
                missing = []
                if not signal['symbol']: missing.append('symbol')
                if not signal['action']: missing.append('action')
                if not signal['entry_range'] and not signal['entry_price']: 
                    missing.append('entry')
                    print(f" Entry patterns tried: {entry_patterns}")
                    print(f" Single patterns tried: {single_patterns}")
                    print(f" Full text: {full_text}")
                print(f" Missing data: {', '.join(missing)}")
                return None
                
        except Exception as e:
            print(f" Error signal: {e}")
            import traceback
            traceback.print_exc()
            return None
        
    async def process_signal(self, signal):

        try:
            from bybit_client import BybitClient
            
            bybit_client = BybitClient()
            
            print(f" Обрабатывающий сигнал: {signal}")
            
            symbol = signal['symbol']
            
            existing_positions = await bybit_client.get_open_positions(symbol)
            if existing_positions:
                await self.send_notification(
                    f" **Позиция уже открыта**\n"
                    f"• Символ: {symbol}\n"
                    f"• Пропускаю создание ордера"
                )
                print(f" Position already exists for {symbol}, skipping order")
                return 
                
            existing_orders = await bybit_client.get_open_orders(symbol)
            if existing_orders:
                await self.send_notification(
                    f"**Ордер уже существует**\n"
                    f"• Символ: {symbol}\n"
                    f"• Пропускаю создание дубликата"
                )
                print(f" Ордер на {symbol} уже существуеют")
                return  
            
            await self.send_notification(
                f" **Новый сигнал обнаружен!**\n"
                f"• Символ: {signal['symbol']}\n"
                f"• Действие: {signal['action']}\n"
                f"• Диапазон входа: {signal['entry_range']}\n"
                f"• TP: {signal.get('tp', 'Не указан')}\n"
                f"• SL: {signal.get('sl', 'Не указан')}"
            )
            
            result = await bybit_client.execute_spot_trade(signal)
            
            if result:
                order_info = result.get('result', {})
                await self.send_notification(
                    f" **Ордер размещен!**\n"
                    f"• Символ: {signal['symbol']}\n"
                    f"• Тип: {signal['action']}\n"
                    f"• Количество: {order_info.get('qty', 'N/A')}\n"
                    f"• Цена: {order_info.get('price', 'N/A')}\n"
                    f"• ID: {order_info.get('orderId', 'N/A')}"
                )
                
                print(f" Лимитный ордер размещен")
                
                
        except Exception as e:
            error_msg = f" **Ошибка обработки сигнала:** {e}"
            print(error_msg)
            await self.send_notification(error_msg)
    
