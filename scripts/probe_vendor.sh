#!/usr/bin/env bash
# Перебирает ИК-протоколы, пока кондиционер не отзовётся.
#
# Определить протокол по марке на корпусе нельзя — его задаёт пульт,
# а пульты делают несколько ODM на весь рынок. Поэтому просто пробуем
# по очереди и смотрим, на каком кондиционер пикнет.
#
# Запускать из корня проекта, брокер должен быть поднят:
#     ./scripts/probe_vendor.sh
#     ./scripts/probe_vendor.sh Haier Electra Airwell   # только эти
#
# Между посылками пауза: успевайте смотреть на кондиционер. Как только
# он отреагировал — Ctrl+C, последний напечатанный вендор и есть ваш.

set -euo pipefail

TOPIC="${TASMOTA_TOPIC:-tasmota_A3CA74}"
USER_NAME="${MQTT_USER:-bot}"
PAUSE="${PAUSE:-4}"

if [ -f .env ]; then
    # Пароль берём из .env, чтобы не светить его в командной строке
    PASSWORD="$(grep -E '^MQTT_PASSWORD=' .env | cut -d= -f2-)"
else
    PASSWORD="${MQTT_PASSWORD:-}"
fi

if [ -z "${PASSWORD}" ]; then
    echo "Не найден MQTT_PASSWORD — положите его в .env или задайте переменной" >&2
    exit 1
fi

# Кандидаты. Первыми — те, чьи пульты относятся к семейству YKR-*.
DEFAULT_VENDORS=(
    Electra Airwell Haier Kelon Gree Coolix Midea TCL
    Hitachi Daikin Fujitsu Panasonic Samsung LG Toshiba
    Mitsubishi Sharp Whirlpool Vestel Teco Goodweather
    Neoclima Airton Amcor Argo Carrier64 Corona Delonghi
    Ecoclim Kelvinator Mirage Sanyo Technibel Transcold
    Trotec Voltas York
)

if [ "$#" -gt 0 ]; then
    VENDORS=("$@")
else
    VENDORS=("${DEFAULT_VENDORS[@]}")
fi

echo "Смотрите на кондиционер. Как только отреагирует — Ctrl+C."
echo "Пауза между посылками: ${PAUSE} c. Топик: cmnd/${TOPIC}/IRhvac"
echo

for vendor in "${VENDORS[@]}"; do
    payload="{\"Vendor\":\"${vendor}\",\"Power\":\"On\",\"Mode\":\"Cool\",\"Temp\":24,\"FanSpeed\":\"Auto\"}"
    printf '>>> %-14s ' "${vendor}"
    if docker compose exec -T mosquitto mosquitto_pub \
        -h localhost -u "${USER_NAME}" -P "${PASSWORD}" \
        -t "cmnd/${TOPIC}/IRhvac" -m "${payload}" 2>/dev/null; then
        echo "отправлено"
    else
        echo "ОШИБКА публикации"
    fi
    sleep "${PAUSE}"
done

echo
echo "Список исчерпан. Если ни один не сработал — скорее всего нужен"
echo "ИК-приёмник, чтобы прочитать код родного пульта (см. README)."
