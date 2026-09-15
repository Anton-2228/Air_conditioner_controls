FROM python:3.12-slim

# PYTHONUNBUFFERED обязателен: иначе логи повиснут в буфере и docker logs будет пустым
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Отдельным слоем, чтобы правка кода не переустанавливала зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# uid 1000 — тот же, что у бота: token.json лежит на bind-mount, и файл,
# записанный контейнером, должен остаться читаемым с хоста.
RUN useradd --create-home --uid 1000 boiler \
    && mkdir -p /data \
    && chown boiler:boiler /data
USER boiler

# Слушает 0.0.0.0, но наружу порт не публикуется: сервис доступен только
# боту внутри compose-сети.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
