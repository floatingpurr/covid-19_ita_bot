# Python image
FROM python:3.8.2-buster

# Install locales
RUN apt-get update
RUN apt-get install -y locales
RUN sed -i -e 's/# it_IT.UTF-8 UTF-8/it_IT.UTF-8 UTF-8/' /etc/locale.gen && locale-gen

# log messages immediately dumped to the stream 
ENV PYTHONUNBUFFERED 1

# prepare requirements dir
RUN mkdir /packaging
WORKDIR /packaging

# Copy requieremnts file
COPY ./requirements.txt /packaging

WORKDIR /packaging

RUN pip install -r requirements.txt
