"""HTTP API умной розетки, в которую включён бойлер.

Три ручки: прочитать состояние, подать питание, снять. Больше бойлером
управлять нечем — температуру и режимы он не отдаёт.

Локально:
    TUYA_DEVICE_ID=... BOILER_API_TOKEN=... TUYA_TOKEN_FILE=token.json \\
        uvicorn app:app --host 127.0.0.1 --port 8000
"""

import logging
import os
import secrets

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from tuya import Socket, TuyaError

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

DEVICE_ID = os.environ["TUYA_DEVICE_ID"]
# Тот же токен, что и у бота: общая строка на две стороны, а не два секрета.
API_TOKEN = os.environ["BOILER_API_TOKEN"]
TOKEN_FILE = os.getenv("TUYA_TOKEN_FILE", "token.json")
CACHE_TTL = float(os.getenv("TUYA_CACHE_TTL", "3.0"))

# Сутки: столько отсчитывает таймер самой розетки, больше она не примет.
MAX_MINUTES = 24 * 60

socket = Socket(DEVICE_ID, TOKEN_FILE, cache_ttl=CACHE_TTL)


def require_token(authorization: str = Header(None)) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Нужен заголовок Authorization")
    # compare_digest, а не ==: обычное сравнение строк выходит на первом
    # несовпавшем символе и тем самым подсказывает токен по времени ответа.
    if not secrets.compare_digest(authorization[len("Bearer ") :], API_TOKEN):
        raise HTTPException(401, "Неверный токен")


app = FastAPI(title="Boiler API", dependencies=[Depends(require_token)])


# Обработчики синхронные намеренно: SDK блокирующий, и FastAPI уводит
# такие ручки в пул потоков. Объявить их async значило бы повесить
# весь сервис на время похода в облако.
@app.get("/status")
def status() -> dict:
    return _guard(socket.status)


@app.post("/on")
def turn_on(minutes: int = Query(0, ge=0, le=MAX_MINUTES)) -> dict:
    _guard(socket.turn_on, minutes)
    return {"ok": True}


@app.post("/off")
def turn_off() -> dict:
    _guard(socket.turn_off)
    return {"ok": True}


def _guard(func, *args):
    """Проблемы с облаком — это 502, а не 500.

    Для клиента это принципиально разные вещи: 502 значит «попробуйте
    ещё раз», а 500 — «сервис сломан».
    """
    try:
        return func(*args)
    except TuyaError as exc:
        logger.warning("Tuya недоступна: %s", exc)
        raise HTTPException(502, f"Tuya вернула ошибку: {exc}") from exc
