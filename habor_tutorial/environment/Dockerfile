FROM ubuntu:24.04

# Install or copy over any environment dependencies here.

WORKDIR /app

RUN apt-get update && apt-get install -y openssh-client && rm -rf /var/lib/apt/lists/*

