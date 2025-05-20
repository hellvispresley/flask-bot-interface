FROM mcr.microsoft.com/playwright/python:v1.42.0-focal

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .


CMD ["gunicorn", "-b", "0.0.0.0:10000", "--timeout", "90", "app:app"]