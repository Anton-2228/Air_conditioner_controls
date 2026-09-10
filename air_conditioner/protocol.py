from dataclasses import dataclass


@dataclass(frozen=True)
class AcProtocol:
    """Какому кондиционеру и на каком языке мы говорим.

    Живёт в настройках, а не в коде: при переезде на другой кондиционер
    меняется пульт, а значит вендор, модель и иногда диапазон температур.
    """

    vendor: str = "Gree"
    model: str = "YAW1F"
    """Пустая строка — у вендора нет вариантов модели, ключ Model не отправляем."""
    min_temp: int = 17
    max_temp: int = 30
    send_light: bool = True
    """Подсветку дисплея понимают не все протоколы; лишний ключ вызовет отказ."""

    def clamp(self, temp: int) -> int:
        return max(self.min_temp, min(self.max_temp, temp))

    def in_range(self, temp: int) -> bool:
        return self.min_temp <= temp <= self.max_temp
