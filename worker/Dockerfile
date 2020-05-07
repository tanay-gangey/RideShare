FROM python:3.7
RUN apt-get install libpq-dev
RUN pip install Psycopg2
ADD worker.py /
ADD readCount /
ADD slavesCount /
ADD model.py /
ADD orchestrator.py /
COPY requirements.txt /
RUN pip install -r requirements.txt
