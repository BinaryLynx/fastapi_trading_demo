FROM python:3.11.1

WORKDIR /app

COPY ./requirements.txt .

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY ./src ./src