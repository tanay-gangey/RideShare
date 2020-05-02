FROM python
RUN pip install pandas
RUN apt-get install libpq-dev
RUN pip install Psycopg2
ADD worker.py /tmp
ADD readCount /tmp
ADD model.py /tmp
ADD orchestrator.py /tmp
COPY requirements.txt /tmp
WORKDIR /tmp
RUN pip install -r requirements.txt