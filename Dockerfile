FROM python:3.12-slim

# PYTHONUNBUFFERED обязателен: иначе логи повиснут в буфере и docker logs будет пустым
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Отдельным слоем, чтобы правка кода не переустанавливала зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home --uid 1000 bot \
    && mkdir -p /data \
    && chown bot:bot /data
USER bot

CMD ["python", "aiogram_handler.py"]
