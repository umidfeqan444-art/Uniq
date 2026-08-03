import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, ADMIN_ID
from handlers import user_handlers, admin_handlers
from database import init_db

# Настройка логирования с временной меткой (только критичные ошибки)
logging.basicConfig(
    level=logging.WARNING,  # Уменьшаем количество логов
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# Validate token early
if not BOT_TOKEN or BOT_TOKEN.strip() == "":
    logger.critical("BOT_TOKEN missing in config.py. Please set BOT_TOKEN and restart.")
    raise SystemExit("BOT_TOKEN missing")


# Инициализация базы данных
init_db()


# Инициализация бота и диспетчера с поддержкой FSM
storage = MemoryStorage()

# Создаем бота без кастомной сессии сначала
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)


# Регистрация обработчиков
dp.include_router(user_handlers.router)
dp.include_router(admin_handlers.router)


async def main():
    """Start polling with optimized settings."""
    try:
        logger.warning("Starting optimized polling")
        
        # Оптимизированные настройки polling
        await dp.start_polling(
            bot, 
            skip_updates=True,
            allowed_updates=["message", "callback_query"],  # Только нужные типы обновлений
            timeout=20,  # Уменьшенный таймаут
            relax=0.1   # Минимальная задержка между запросами
        )
    except KeyboardInterrupt:
        logger.warning("Shutting down (KeyboardInterrupt)")
    except Exception as e:
        logger.error("Critical error in polling: %s", e)
        raise


if __name__ == "__main__":
    import asyncio

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down (KeyboardInterrupt)")
    except Exception as e:
        logger.exception("Fatal error: %s", e)
    finally:
        try:
            # Close bot session
            if hasattr(bot, 'session') and bot.session:
                asyncio.run(bot.session.close())
        except Exception as e:
            logger.error("Error closing bot session: %s", e)
