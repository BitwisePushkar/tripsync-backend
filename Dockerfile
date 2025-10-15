FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /app/

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY . /app

EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "tripsync.wsgi:application"]