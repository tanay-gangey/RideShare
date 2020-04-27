FROM python
RUN pip install pandas
ADD master.py /
COPY requirements.txt /tmp
WORKDIR /tmp
RUN pip install -r requirements.txt
CMD ["python3","master.py"]
