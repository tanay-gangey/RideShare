FROM python
RUN pip install pandas
RUN apt-get install libpq-dev
RUN pip install Psycopg2
ADD master.py /tmp
ADD readCount /tmp
ADD slave.py /tmp
ADD model.py /tmp
ADD model_slave.py /tmp
ADD orchestrator.py /tmp
COPY requirements.txt /tmp
WORKDIR /tmp
RUN pip install -r requirements.txt