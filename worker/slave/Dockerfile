FROM python
RUN pip install pandas
RUN apt-get install libpq-dev
RUN pip install Psycopg2
ADD slave.py /tmp
ADD model.py /tmp
COPY requirements.txt /tmp
WORKDIR /tmp
RUN pip install -r requirements.txt
CMD ["python3","slave.py"]
