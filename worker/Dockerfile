FROM python
ADD requirements.txt /
ADD worker.py /
RUN pip install -r requirements.txt
CMD ["python3","worker.py"]