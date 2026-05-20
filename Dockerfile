FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    default-jdk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY . .

ENV CHROME_BIN=/usr/bin/chromium
ENV JAVA_HOME=/usr/lib/jvm/default-java

CMD gunicorn app:app --bind 0.0.0.0:$PORT