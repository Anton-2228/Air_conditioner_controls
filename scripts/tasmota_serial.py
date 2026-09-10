#!/usr/bin/env python3
"""Консоль Tasmota по USB.

Нужна, когда плата не в сети: переехали в другое место, сменился Wi-Fi,
остался чужой статический IP. По проводу настраивается всё то же самое,
что и через веб-интерфейс, и точка доступа для этого не требуется.

    ./scripts/tasmota_serial.py Status 5
    ./scripts/tasmota_serial.py --wifi              # спросит сеть и пароль
    ./scripts/tasmota_serial.py --mqtt-host 192.168.1.4
    ./scripts/tasmota_serial.py --watch             # просто смотреть логи

Скорость по умолчанию 115200. Порт определяется сам, если он один.
"""

import argparse
import glob
import sys
import time
from getpass import getpass

try:
    import serial
except ImportError:
    sys.exit("Нет pyserial. Поставьте: ./venv/bin/pip install pyserial")

DEFAULT_BAUD = 115200


def redact(text: str, secret: str) -> str:
    return text.replace(secret, "********") if secret else text


def find_port() -> str:
    ports = sorted(glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*"))
    if not ports:
        sys.exit("Не найдено ни одного serial-порта. Плата воткнута в USB?")
    if len(ports) > 1:
        sys.exit(f"Портов несколько: {', '.join(ports)}. Укажите нужный через --port")
    return ports[0]


class Tasmota:
    def __init__(self, port: str, baud: int = DEFAULT_BAUD) -> None:
        self.ser = serial.Serial(port=port, baudrate=baud, timeout=0.1)

    def reset(self) -> None:
        """Дёргает EN через RTS: классическая схема автосброса ESP32."""
        self.ser.rts = True
        self.ser.dtr = False
        time.sleep(0.15)
        self.ser.rts = False
        self.ser.reset_input_buffer()

    def read_for(self, seconds: float) -> str:
        data = b""
        end = time.time() + seconds
        while time.time() < end:
            data += self.ser.read(4096)
        return data.decode("utf-8", errors="replace")

    def send(self, command: str, wait: float = 2.0) -> str:
        self.ser.reset_input_buffer()
        self.ser.write((command + "\n").encode("utf-8"))
        self.ser.flush()
        return self.read_for(wait)

    def close(self) -> None:
        self.ser.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("command", nargs="*", help="команда Tasmota, например: Status 5")
    parser.add_argument("--port", help="по умолчанию определяется автоматически")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD)
    parser.add_argument(
        "--wifi", action="store_true", help="спросить сеть и пароль, прописать и включить DHCP"
    )
    parser.add_argument("--mqtt-host", help="прописать адрес брокера")
    parser.add_argument(
        "--watch", action="store_true", help="перезагрузить плату и смотреть лог загрузки"
    )
    parser.add_argument("--seconds", type=float, default=15.0, help="сколько смотреть при --watch")
    args = parser.parse_args()

    port = args.port or find_port()
    print(f"Порт {port}, {args.baud} бод\n")
    board = Tasmota(port, args.baud)

    try:
        if args.watch:
            board.reset()
            print(board.read_for(args.seconds))
            return

        # Даём плате проснуться: без сброса она может молчать в ответ на первую команду
        board.reset()
        board.read_for(3)

        if args.wifi:
            ssid = input("Имя сети (SSID): ").strip()
            password = getpass("Пароль сети (не отображается): ")
            if not ssid:
                sys.exit("SSID пустой, ничего не меняю")
            # IPAddress1 0.0.0.0 = DHCP. Без этого плата возьмёт старый
            # статический адрес и на новой сети окажется недостижимой.
            setup = f"Backlog SSID1 {ssid}; Password1 {password}; IPAddress1 0.0.0.0"
            # Tasmota возвращает пароль эхом и в подтверждении команды,
            # и в её ответе — вырезаем, иначе он окажется на экране и в логах.
            print(redact(board.send(setup, wait=3), password))
            print("\nЖду подключения к сети...\n")
            print(redact(board.read_for(20), password))
            print("\n--- итог ---")
            print(redact(board.send("Status 5", wait=3), password))
            return

        if args.mqtt_host:
            print(board.send(f"MqttHost {args.mqtt_host}", wait=3))
            print(board.send("Status 6", wait=3))
            return

        if args.command:
            print(board.send(" ".join(args.command), wait=3))
            return

        parser.print_help()
    finally:
        board.close()


if __name__ == "__main__":
    main()
