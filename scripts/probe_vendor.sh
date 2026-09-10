#!/usr/bin/env bash
# Перебирает ИК-протоколы, пока кондиционер не отзовётся.
#
# Определить протокол по марке на корпусе нельзя — его задаёт пульт,
# а пульты делают несколько ODM на весь рынок. Поэтому просто пробуем
# по очереди и смотрим, на каком кондиционер пикнет.
#
# Имена — ровно как их понимает Tasmota (release-ir 15.6.0). Полный список
# плата выдаёт сама в ответ на несуществующее имя: IRhvac {"Vendor":"x"}.
#
# Запускать из корня проекта там, где работает брокер:
#     ./scripts/probe_vendor.sh
#     ./scripts/probe_vendor.sh ELECTRA_AC COOLIX   # только эти
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

# Первыми — самые вероятные для китайских OEM-сплитов: ELECTRA_AC покрывает
# пульты AUX серии YKR-*, дальше семейства Midea, Gree, Haier, Kelon, TCL.
DEFAULT_VENDORS=(
    ELECTRA_AC COOLIX MIDEA GREE
    HAIER_AC HAIER_AC_YRW02 HAIER_AC176 HAIER_AC160
    KELON TCL112AC TEKNOPOINT AIRWELL AIRTON VESTEL_AC TECO MIRAGE
    GOODWEATHER NEOCLIMA KELVINATOR LG LG2 SAMSUNG_AC
    PANASONIC_AC PANASONIC_AC32 TOSHIBA_AC FUJITSU_AC SHARP_AC WHIRLPOOL_AC
    HITACHI_AC HITACHI_AC1 HITACHI_AC264 HITACHI_AC296 HITACHI_AC344 HITACHI_AC424
    MITSUBISHI_AC MITSUBISHI112 MITSUBISHI136 MITSUBISHI_HEAVY_88 MITSUBISHI_HEAVY_152
    DAIKIN DAIKIN2 DAIKIN64 DAIKIN128 DAIKIN152 DAIKIN160 DAIKIN176 DAIKIN216
    ARGO TROTEC TROTEC_3550 AMCOR DELONGHI_AC CARRIER_AC64 CORONA_AC
    SANYO_AC SANYO_AC88 VOLTAS TRANSCOLD TECHNIBEL_AC ECOCLIM TRUMA RHOSS
    BOSCH144 YORK EUROM
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
    printf '>>> %-22s ' "${vendor}"
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
