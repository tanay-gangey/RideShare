FROM python:3.7-slim-stretch
ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

RUN pip install pandas
ADD worker.py /tmp
ADD readCount /tmp
ADD model.py /tmp
ADD orchestrator.py /tmp
COPY requirements.txt /tmp
WORKDIR /tmp
RUN pip install -r requirements.txt