FROM python:3.10-slim-buster

ENV TZ="Europe/Moscow"

ADD main.py settings.py requirements.txt /

RUN date

RUN pip install -r requirements.txt

CMD [ "python", "./main.py" ]