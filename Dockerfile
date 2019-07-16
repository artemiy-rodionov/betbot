FROM python:3.7
RUN apt-get update && apt-get upgrade -y && apt-get autoremove && apt-get autoclean
RUN apt-get install -y libsqlite3-dev
RUN mkdir /code
WORKDIR /code
RUN mkdir /code/instance
COPY requirements.txt .
RUN pip install -r requirements.txt
ADD betbot /code/betbot
ADD run.py /code
ENTRYPOINT ["python3", "run.py"]
