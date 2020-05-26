# Python image
FROM python:3.8.2-buster

# Install locales
RUN apt-get update
RUN apt-get install -y locales
RUN sed -i -e 's/# it_IT.UTF-8 UTF-8/it_IT.UTF-8 UTF-8/' /etc/locale.gen && locale-gen

# log messages immediately dumped to the stream 
ENV PYTHONUNBUFFERED 1


RUN mkdir /app
WORKDIR /app
COPY ./app/ .

RUN pip install --upgrade pip
RUN pip install -r requirements.txt


