import asyncio
import logging

import aiohttp

from .models import BoilerError, BoilerStatus

logger = logging.getLogger(__name__)


class Boiler:
    """Клиент HTTP API умной розетки, в которую включён бойлер.

    Бот не знает ничего о Tuya: только адрес API, статический токен
    и четыре ручки. Если розетку когда-нибудь перепрошьют и облако
    уйдёт из цепочки, здесь не должно поменяться ничего.
    """

    def __init__(
        self,
        base_url: str,
        token: str,
        request_timeout: float = 10.0,
        sync_delay: float = 2.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"}
        self._timeout = aiohttp.ClientTimeout(total=request_timeout)
        self._sync_delay = sync_delay
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        # Сессия создаётся лениво: aiohttp привязывает её к текущему циклу
        # событий, а в момент сборки объекта в init.py цикла ещё нет.
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self._timeout, headers=self._headers)
        return self._session

    async def get_status(self) -> BoilerStatus:
        return BoilerStatus.from_dict(await self._request("GET", "/status"))

    async def turn_on(self, minutes: int = 0) -> None:
        """Подаёт питание. minutes=0 — без таймера.

        Таймер отсчитывает сама розетка, поэтому он сработает, даже если
        упадёт сервер или пропадёт интернет.
        """
        params = {"minutes": str(minutes)} if minutes > 0 else None
        await self._request("POST", "/on", params=params)

    async def turn_off(self) -> None:
        await self._request("POST", "/off")

    async def status_after_command(self) -> BoilerStatus:
        """Состояние после команды: сначала пауза, потом запрос.

        Команда идёт через облако, реле переключается не мгновенно.
        Запрос сразу после /on вернул бы старое значение.
        """
        await asyncio.sleep(self._sync_delay)
        return await self.get_status()

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()

    async def _request(self, method: str, path: str, params: dict | None = None) -> dict:
        session = await self._get_session()
        url = self._base_url + path
        try:
            async with session.request(method, url, params=params) as response:
                body = await response.json(content_type=None)
                if response.status == 401:
                    raise BoilerError("auth", self._detail(body, "сервер не принял токен"))
                if response.status != 200:
                    raise BoilerError(
                        "unavailable" if response.status == 502 else "network",
                        self._detail(body, f"HTTP {response.status}"),
                    )
                if not isinstance(body, dict):
                    raise BoilerError("network", f"{path} вернул не JSON-объект")
                return body
        except TimeoutError as exc:
            raise BoilerError("unavailable", f"{path}: таймаут запроса") from exc
        except aiohttp.ClientError as exc:
            raise BoilerError("network", f"{path}: {exc}") from exc
        except ValueError as exc:
            # Невалидный JSON: чаще всего это страница ошибки от прокси.
            raise BoilerError("network", f"{path}: ответ не разобрать ({exc})") from exc

    @staticmethod
    def _detail(body: object, fallback: str) -> str:
        if isinstance(body, dict) and body.get("detail"):
            return str(body["detail"])
        return fallback
