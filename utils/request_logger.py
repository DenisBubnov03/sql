import logging
import functools
import time
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import TimedOut, NetworkError, RetryAfter

logger = logging.getLogger(__name__)

def retry_on_timeout(max_retries=3, base_delay=1.0):
    """
    Декоратор для повторных попыток при таймаутах
    
    Args:
        max_retries: Максимальное количество попыток
        base_delay: Базовая задержка между попытками
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except (TimedOut, NetworkError, RetryAfter) as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)  # Экспоненциальная задержка
                        logger.warning(f"Попытка {attempt + 1} не удалась ({type(e).__name__}): {e}. Повтор через {delay}с")
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"Все {max_retries} попыток не удались. Последняя ошибка: {e}")
                        raise last_exception
                except Exception as e:
                    # Для других ошибок не делаем повторные попытки
                    raise e
                    
        return wrapper
    return decorator

def log_request(func_name: str = None):
    """
    Декоратор для логирования запросов к боту
    
    Args:
        func_name: Кастомное имя функции для логирования
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            # Получаем информацию о пользователе
            user = update.effective_user
            user_info = {
                'id': user.id if user else 'Unknown',
                'username': user.username if user else 'Unknown',
                'first_name': user.first_name if user else 'Unknown',
                'last_name': user.last_name if user else 'Unknown'
            }
            
            # Получаем информацию о запросе
            request_info = {
                'function': func_name or func.__name__,
                'chat_id': update.effective_chat.id if update.effective_chat else 'Unknown',
                # 'message_type': update.message.content_type if update.message else 'Unknown',
                'text': update.message.text[:100] + '...' if update.message and update.message.text and len(update.message.text) > 100 else (update.message.text if update.message else 'No text'),
                'timestamp': datetime.now().isoformat()
            }
            
            # Логируем начало запроса
            logger.info(f"🚀 ЗАПРОС НАЧАТ | Функция: {request_info['function']} | "
                       f"Пользователь: {user_info['username']} (ID: {user_info['id']}) | "
                       f"Чат: {request_info['chat_id']} | "
                       f"Текст: {request_info['text']}")
            
            start_time = time.time()
            success = False
            error = None
            
            try:
                # Выполняем функцию
                result = await func(update, context, *args, **kwargs)
                success = True
                execution_time = time.time() - start_time
                
                # Логируем успешное завершение
                logger.info(f"✅ ЗАПРОС УСПЕШЕН | Функция: {request_info['function']} | "
                           f"Пользователь: {user_info['username']} | "
                           f"Время выполнения: {execution_time:.2f}с")
                
                return result
                
            except Exception as e:
                success = False
                error = str(e)
                execution_time = time.time() - start_time
                
                # Логируем ошибку
                logger.error(f"❌ ЗАПРОС ОШИБКА | Функция: {request_info['function']} | "
                           f"Пользователь: {user_info['username']} | "
                           f"Ошибка: {error} | "
                           f"Время выполнения: {execution_time:.2f}с")
                
                # Перебрасываем ошибку дальше
                raise
                
        return wrapper
    return decorator

def log_command(command_name: str = None):
    """
    Декоратор для логирования команд бота
    
    Args:
        command_name: Кастомное имя команды для логирования
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            # Получаем информацию о пользователе
            user = update.effective_user
            user_info = {
                'id': user.id if user else 'Unknown',
                'username': user.username if user else 'Unknown',
                'first_name': user.first_name if user else 'Unknown',
                'last_name': user.last_name if user else 'Unknown'
            }
            
            # Получаем информацию о команде
            command = command_name or (update.message.text.split()[0] if update.message and update.message.text else 'Unknown')
            
            request_info = {
                'command': command,
                'function': func.__name__,
                'chat_id': update.effective_chat.id if update.effective_chat else 'Unknown',
                'timestamp': datetime.now().isoformat()
            }
            
            # Логируем начало команды
            logger.info(f"🎯 КОМАНДА НАЧАТА | Команда: {request_info['command']} | "
                       f"Функция: {request_info['function']} | "
                       f"Пользователь: {user_info['username']} (ID: {user_info['id']}) | "
                       f"Чат: {request_info['chat_id']}")
            
            start_time = time.time()
            success = False
            error = None
            
            try:
                # Выполняем функцию
                result = await func(update, context, *args, **kwargs)
                success = True
                execution_time = time.time() - start_time
                
                # Логируем успешное завершение команды
                logger.info(f"✅ КОМАНДА УСПЕШНА | Команда: {request_info['command']} | "
                           f"Функция: {request_info['function']} | "
                           f"Пользователь: {user_info['username']} | "
                           f"Время выполнения: {execution_time:.2f}с")
                
                return result
                
            except Exception as e:
                success = False
                error = str(e)
                execution_time = time.time() - start_time
                
                # Логируем ошибку команды
                logger.error(f"❌ КОМАНДА ОШИБКА | Команда: {request_info['command']} | "
                           f"Функция: {request_info['function']} | "
                           f"Пользователь: {user_info['username']} | "
                           f"Ошибка: {error} | "
                           f"Время выполнения: {execution_time:.2f}с")
                
                # Перебрасываем ошибку дальше
                raise
                
        return wrapper
    return decorator

def log_conversation_handler(handler_name: str = None):
    """
    Декоратор для логирования обработчиков разговоров
    
    Args:
        handler_name: Кастомное имя обработчика для логирования
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            # Получаем информацию о пользователе
            user = update.effective_user
            user_info = {
                'id': user.id if user else 'Unknown',
                'username': user.username if user else 'Unknown',
                'first_name': user.first_name if user else 'Unknown',
                'last_name': user.last_name if user else 'Unknown'
            }
            
            # Получаем информацию о состоянии разговора
            conversation_state = context.user_data.get('conversation_state', 'Unknown')
            
            request_info = {
                'handler': handler_name or func.__name__,
                'conversation_state': conversation_state,
                'chat_id': update.effective_chat.id if update.effective_chat else 'Unknown',
                'text': update.message.text[:100] + '...' if update.message and update.message.text and len(update.message.text) > 100 else (update.message.text if update.message else 'No text'),
                'timestamp': datetime.now().isoformat()
            }
            
            # Логируем начало обработки
            logger.info(f"💬 РАЗГОВОР ОБРАБОТКА | Обработчик: {request_info['handler']} | "
                       f"Состояние: {request_info['conversation_state']} | "
                       f"Пользователь: {user_info['username']} (ID: {user_info['id']}) | "
                       f"Текст: {request_info['text']}")
            
            start_time = time.time()
            success = False
            error = None
            
            try:
                # Выполняем функцию
                result = await func(update, context, *args, **kwargs)
                success = True
                execution_time = time.time() - start_time
                
                # Логируем успешное завершение
                logger.info(f"✅ РАЗГОВОР УСПЕШЕН | Обработчик: {request_info['handler']} | "
                           f"Состояние: {request_info['conversation_state']} | "
                           f"Пользователь: {user_info['username']} | "
                           f"Время выполнения: {execution_time:.2f}с")
                
                return result
                
            except Exception as e:
                success = False
                error = str(e)
                execution_time = time.time() - start_time
                
                # Логируем ошибку
                logger.error(f"❌ РАЗГОВОР ОШИБКА | Обработчик: {request_info['handler']} | "
                           f"Состояние: {request_info['conversation_state']} | "
                           f"Пользователь: {user_info['username']} | "
                           f"Ошибка: {error} | "
                           f"Время выполнения: {execution_time:.2f}с")
                
                # Перебрасываем ошибку дальше
                raise
                
        return wrapper
    return decorator 