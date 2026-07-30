import asyncio
import logging
from telethon import TelegramClient, events
from modules.config import API_ID, API_HASH, BOT_TOKEN, TELEGRAM_USERNAME, PHONE_NUMBER, CHANNEL_NAMES 
from modules.telegram_parser import TelegramParser
from modules.bybit_client import BybitClient

try:
    from ml.ml_filter import MLSignalFilter
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    print(" ML-фильтр не найден. Бот будет работать без фильтрации сигналов.")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class UnifiedTradingBot:
    def __init__(self):
        self.command_bot = None   
        self.parser = TelegramParser()   
        self.bybit = BybitClient()   
        self.allowed_usernames = [TELEGRAM_USERNAME.strip('@').lower()] if TELEGRAM_USERNAME else []   
        self.pending_confirmations = {}   
        self.pending_amounts = {}   
        self.is_parser_ready = False   
        self.parser_task = None
        
        self.ml_filter = MLSignalFilter() if ML_AVAILABLE else None
        
    async def start(self):
        logger.info("Запуск торгового бота...")
        await self.start_command_bot()
        
    async def start_command_bot(self):
        self.command_bot = TelegramClient('command_session', API_ID, API_HASH)
        await self.command_bot.start(bot_token=BOT_TOKEN)
    
        me = await self.command_bot.get_me()
        logger.info(f"Бот запущен: @{me.username}")
        
        self.parser_task = asyncio.create_task(self.start_parser_background())
        
        @self.command_bot.on(events.NewMessage)
        async def all_messages_handler(event):
            await self.handle_all_messages(event)
        
        await self.command_bot.run_until_disconnected()
    
    async def all_messages(self, event):
        user = await event.get_sender()   
        user_id = user.id if user else None   
        username = getattr(user, 'username', '').lower() if user else ''   
          
        
        text = event.text.strip()   
        
        if text.startswith('/'):   
            await self.handle_command(event, text[1:].lower()) 

        elif user_id in self.pending_confirmations or user_id in self.pending_amounts:   
            await self.handle_user_response(event)   
    
    async def user_response(self, event):
        user = await event.get_sender()   
        user_id = user.id if user else None   
        text = event.text.strip().lower()   
        
        if user_id in self.pending_amounts:   
            await self.handle_amount_input(event)   
            return   
        
        if user_id in self.pending_confirmations:   
            if any(word in text for word in ['да', 'yes', 'da']):   
                confirmation = self.pending_confirmations[user_id]   
                await self.ask_order_amount(event, confirmation)  

            elif any(word in text for word in ['нет', 'no', 'net']):   
                await event.reply(" Ордер отменен")   
                del self.pending_confirmations[user_id]   
    
    async def order_amount(self, event, signal_info):
        user = await event.get_sender()   
        user_id = user.id if user else None   
        self.pending_amounts[user_id] = signal_info   
        
        await event.reply(
            f"**Создание ордера для {signal_info['signal']['symbol']}**\n\n"   
            f"• Цена входа: {signal_info['signal'].get('entry_price', signal_info['signal'].get('entry_range', 'N/A'))}\n"   
            f"• Действие: {signal_info['signal']['action']}\n\n"   
            f"**На какую сумму открыть ордер?**\n(Минимум: 10 USDT)\n\nНапишите сумму:"   
        )   
    
    async def amount_input(self, event):
        user = await event.get_sender()   
        user_id = user.id if user else None   
        
        if user_id not in self.pending_amounts:   
            return   
        
        signal_info = self.pending_amounts[user_id]   
        amount_text = event.text.strip()   
        
        try:
            amount = float(amount_text)   
            if amount < 10:   
                await event.reply("Минимальная сумма: 10 USDT\nПопробуйте снова:")   
                return   
            
            signal = signal_info['signal']   
            signal['custom_amount'] = amount   
            
            await event.reply(f"Сумма ордера: {amount} USDT\nСоздаю ордер...")   
            result = await self.bybit.execute_spot_trade(signal)   
            
            if result:   
                await event.reply(f"**Ордер создан!**\n• Символ: {signal['symbol']}\n• Сумма: {amount} USDT")   
            else:   
                await event.reply("Не удалось создать ордер")   
            
        except ValueError:   
            await event.reply(f"Неверный формат суммы: '{amount_text}'\nВведите число:")   
            return   
        
        if user_id in self.pending_amounts: del self.pending_amounts[user_id]   
        if user_id in self.pending_confirmations: del self.pending_confirmations[user_id]   
    
    async def start_parser(self):
        
        logger.info("Запуск парсера каналов (авто-режим)...")   
        await self.parser.client.start(phone=PHONE_NUMBER)   
        
        self.parser.monitored_chats = await self.parser.find_channels_by_name()   
        logger.info(f"Найдено каналов: {len(self.parser.monitored_chats)}")   
        
        await self.setup_auto_handlers()   
        self.is_parser_ready = True   
        logger.info("Парсер запущен в АВТО-РЕЖИМЕ")   
        
        await self.parser.client.run_until_disconnected()   
           
    
    async def setup_handlers(self):
        @self.parser.client.on(events.NewMessage(chats=self.parser.monitored_chats))   
        async def channel_handler(event):   
            try:
                chat_title = getattr(event.chat, 'title', 'Unknown Chat')   
                message = event.message.text   
                signal = self.parser.parse_signal(message)   
                
                if signal:   
                    logger.info(f"Найден сигнал в {chat_title}: {signal['symbol']}")   
                    await self.process_signal_auto(signal, chat_title)   
                    
            except Exception as e:   
                logger.error(f"Ошибка обработки сообщения: {e}")   
    
    async def process_signal(self, signal, chat_title):
        try:
            if self.ml_filter:
                logger.info(f"Запрос исторических данных Bybit для валидации {signal['symbol']}...")
                klines = self.bybit.get_recent_klines(symbol=signal['symbol'], interval='15', limit=100)
                
                if not self.ml_filter.is_signal_valid(klines):
                    logger.warning(f" Сигнал {signal['symbol']} ОТКЛОНЕН.")
                    await self.send_notification(f" сигнал сомнительный отмена:\n• {signal['symbol']} из {chat_title}")
                    return 
                
                logger.info(f" Сигнал {signal['symbol']} ОДОБРЕН.")

            signal['custom_amount'] = 10   
            result = await self.bybit.execute_spot_trade(signal)   
            
            if result:   
                await self.send_notification(
                    f"**Авто-ордер создан!**\n• Из канала: {chat_title}\n"   
                    f"• Символ: {signal['symbol']}\n• Действие: {signal['action']}\n"   
                    f"• Сумма: 10 USDT (авто)\n"   
                )   
            else:   
                logger.error("Ошибка исполнения авто-ордера на бирже.")
        except Exception as e:   
            logger.error(f"Ошибка создания авто-ордера: {e}")   
    
    async def command(self, event, command):
        user = await event.get_sender()   
        username = getattr(user, 'username', '').lower() if user else ''   
        user_id = user.id if user else None   
        
        logger.info(f"Команда /{command} от @{username}")   
        
        if command == 'start':   
            await event.reply("Торговый бот активирован! Ожидаю сигналы...")   
        elif command == 'status':   
            parser_status = "ГОТОВ" if self.is_parser_ready else "ЗАГРУЗКА"   
            ml_status = "РАБОТАЕТ" if self.ml_filter else "ВЫКЛЮЧЕН"
            await event.reply(f"**Статус бота:**\n• Парсер: {parser_status}\n• ML-фильтр: {ml_status}\n• Режим: АВТО-ТОРГОВЛЯ")   

        elif command in ['last', 'prev']:
            if not self.is_parser_ready:
                await event.reply(" Парсер еще загружается, подождите...")
                return
            
            
            if not self.parser.monitored_chats:
                await event.reply(" Ошибка: В памяти бота нет отслеживаемых каналов.")
                return

            channel = self.parser.monitored_chats[0]
            channel_title = getattr(channel, 'title', 'Канал')

            message_index = 0 if command == 'last' else 1
            post_label = "последнем" if command == 'last' else "предыдущем"

            messages = []
            async for message in self.parser.client.iter_messages(channel, limit=2):
                if message.text:
                    messages.append(message)



            target_message = messages[message_index]
            post_text = target_message.text
            logger.info(f"Анализирую текст в {post_label} посте:\n{post_text}")

            signal = self.parser.parse_signal(post_text) 

            if not signal:
                await event.reply(
                    f" В {post_label} посте текст прочитан, но торговый сигнал не обнаружен:\n\n`{post_text[:200]}...`"
                )
                return

            symbol = signal.get('symbol', 'UNKNOWN')
            side = signal.get('side', 'BUY')
            entry = signal.get('entry', 'Рынок')
            tp = signal.get('tp', 'Не указан')
            sl = signal.get('sl', 'Не указан')

            response_text = (
                f" **Найден сигнал в {post_label} посте:**\n"
                f"• Канал: {channel_title}\n"
                f"• Символ: {symbol}\n"
                f"• Действие: {side}\n"
                f"• Цена входа: {entry}\n"
                f"• TP: {tp}\n"
                f"• SL: {sl}\n\n"
                f"**Создать ордер?**"
            )

            await event.reply(response_text)
        

        elif command == 'help':  
            await event.reply("Команды: /start, /status, /last, /prev, /help")

        elif command == 'help':   
            await event.reply("Команды: /start, /status, /help")   

    async def send_notification(self, message):
        if self.command_bot and self.allowed_usernames:   
            try:   
                for username in self.allowed_usernames:   
                    user = await self.command_bot.get_entity(username)   
                    await self.command_bot.send_message(user, message)   
            except Exception as e:   
                logger.error(f"Ошибка отправки уведомления: {e}")   

async def main():   
    bot = UnifiedTradingBot()   
    await bot.start()   

if __name__ == "__main__":   
    asyncio.run(main())   