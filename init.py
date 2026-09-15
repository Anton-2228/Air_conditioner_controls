import logging
import os
from pathlib import Path

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from dotenv import load_dotenv

from logging_config import setup_logging
from validation import parse_chat_ids

dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path)

setup_logging(os.getenv("LOG_LEVEL", "INFO"))

logger = logging.getLogger(__name__)

# Импорты ниже идут после load_dotenv и настройки логирования намеренно.
from air_conditioner import AcProtocol, AirConditioner, StateStorage  # noqa: E402
from boiler import Boiler  # noqa: E402
from middlewares import WhitelistMiddleware  # noqa: E402
from mqtt_wrapper import MqttWrapper  # noqa: E402

API_TOKEN = os.getenv("API_TOKEN")
if not API_TOKEN:
    raise RuntimeError("Не задан API_TOKEN")

ALLOWED_CHAT_IDS = parse_chat_ids(os.getenv("ALLOWED_CHAT_IDS"))
if not ALLOWED_CHAT_IDS:
    # Пустой белый список означал бы «можно всем» — лучше не подниматься.
    raise RuntimeError("Не задан ALLOWED_CHAT_IDS: без белого списка бот не запускается")

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "ac_bot")
TASMOTA_TOPIC = os.getenv("TASMOTA_TOPIC", "tasmota_A3CA74")
MQTT_ACK_TIMEOUT = float(os.getenv("MQTT_ACK_TIMEOUT", "5.0"))
MQTT_RECONNECT_DELAY = float(os.getenv("MQTT_RECONNECT_DELAY", "5.0"))
STATE_FILE_PATH = Path(os.getenv("STATE_FILE_PATH", "data/state.json"))
TELEGRAM_PROXY = os.getenv("TELEGRAM_PROXY", "").strip()

# Бойлер живёт за отдельным HTTP API на VPS и к MQTT отношения не имеет.
BOILER_API_URL = os.getenv("BOILER_API_URL", "").strip()
BOILER_API_TOKEN = os.getenv("BOILER_API_TOKEN", "").strip()
BOILER_REQUEST_TIMEOUT = float(os.getenv("BOILER_REQUEST_TIMEOUT", "10.0"))
BOILER_SYNC_DELAY = float(os.getenv("BOILER_SYNC_DELAY", "2.0"))

# Протокол кондиционера. Меняется при переезде на другой кондиционер:
# другой пульт — другой вендор, иногда другой диапазон температур.
AC_PROTOCOL = AcProtocol(
    vendor=os.getenv("AC_VENDOR", "Gree"),
    model=os.getenv("AC_MODEL", "YAW1F"),
    min_temp=int(os.getenv("AC_MIN_TEMP", "17")),
    max_temp=int(os.getenv("AC_MAX_TEMP", "30")),
    send_light=os.getenv("AC_SEND_LIGHT", "1") not in ("0", "false", "False"),
)

# С некоторых серверов api.telegram.org недоступен напрямую — тогда
# запросы к Bot API пускаем через прокси. Пустое значение — напрямую.
bot = Bot(
    token=API_TOKEN,
    session=AiohttpSession(proxy=TELEGRAM_PROXY) if TELEGRAM_PROXY else None,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

# outer_middleware, а не middleware: внешний слой отрабатывает до резолвинга
# фильтров и до подъёма FSM, поэтому чужой не проскочит даже в catch-all.
whitelist_middleware = WhitelistMiddleware(ALLOWED_CHAT_IDS)
dp.message.outer_middleware(whitelist_middleware)
dp.callback_query.outer_middleware(whitelist_middleware)

mqtt_wrapper = MqttWrapper(
    host=MQTT_HOST,
    port=MQTT_PORT,
    username=MQTT_USER,
    password=MQTT_PASSWORD,
    base_topic=TASMOTA_TOPIC,
    client_id=MQTT_CLIENT_ID,
    ack_timeout=MQTT_ACK_TIMEOUT,
    reconnect_delay=MQTT_RECONNECT_DELAY,
)

air_conditioner = AirConditioner(StateStorage(STATE_FILE_PATH), mqtt_wrapper, AC_PROTOCOL)

# Бойлер необязателен: без адреса и токена бот поднимается как раньше,
# только без команды /boiler. Ронять из-за него управление кондиционером
# было бы неправильно — это независимые устройства.
if BOILER_API_URL and BOILER_API_TOKEN:
    boiler = Boiler(
        base_url=BOILER_API_URL,
        token=BOILER_API_TOKEN,
        request_timeout=BOILER_REQUEST_TIMEOUT,
        sync_delay=BOILER_SYNC_DELAY,
    )
else:
    boiler = None
    logger.warning("BOILER_API_URL/BOILER_API_TOKEN не заданы: команда /boiler выключена")

COMMANDS = [
    BotCommand(command="menu", description="Управление кондиционером"),
    BotCommand(command="start", description="Управление кондиционером"),
]
if boiler is not None:
    COMMANDS.append(BotCommand(command="boiler", description="Управление бойлером"))

__all__ = [
    "AC_PROTOCOL",
    "ALLOWED_CHAT_IDS",
    "COMMANDS",
    "air_conditioner",
    "boiler",
    "bot",
    "dp",
    "mqtt_wrapper",
    "router",
    "storage",
]
