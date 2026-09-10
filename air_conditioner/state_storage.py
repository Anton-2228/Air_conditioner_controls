import json
import logging
import os
import tempfile
from pathlib import Path

from .models import AcState

logger = logging.getLogger(__name__)


class StateStorage:
    """Состояние кондиционера в JSON-файле.

    Состояние одно на всё устройство: кондиционер физически один,
    у пользователей общая картинка.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def load(self) -> AcState:
        """Читает состояние. Любая проблема с файлом даёт дефолты, но не исключение.

        Файл при этом не трогается: если он битый, лучше сохранить его
        как есть для разбора, чем затереть на старте.
        """
        if not self.path.exists():
            logger.info("Файла состояния %s нет, начинаю с дефолтов", self.path)
            return AcState()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.exception("Не читается файл состояния %s, беру дефолты", self.path)
            return AcState()
        if not isinstance(raw, dict):
            logger.warning("В %s не объект, а %s. Беру дефолты", self.path, type(raw).__name__)
            return AcState()
        return AcState.from_dict(raw)

    def save(self, state: AcState) -> None:
        """Атомарная запись: временный файл рядом, fsync, затем os.replace.

        fsync обязателен — без него внезапная перезагрузка сервера может
        оставить переименованный, но пустой файл.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as tmp:
                tmp_path = Path(tmp.name)
                json.dump(state.to_dict(), tmp, ensure_ascii=False, indent=2)
                tmp.flush()
                os.fsync(tmp.fileno())
            os.replace(tmp_path, self.path)
            tmp_path = None
        finally:
            if tmp_path is not None and tmp_path.exists():
                tmp_path.unlink()
