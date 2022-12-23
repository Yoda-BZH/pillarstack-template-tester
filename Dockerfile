FROM debian:stable
WORKDIR /app
COPY template-tester.* /app/

RUN apt-get update > /dev/null; apt-get install --yes curl apt-transport-https > /dev/null
RUN echo "deb [signed-by=/usr/share/keyrings/salt-archive-keyring.gpg arch=amd64] https://repo.saltproject.io/py3/debian/11/amd64/3004 bullseye main" >> /etc/apt/sources.list.d/salt.list
RUN curl -fsSL -o /usr/share/keyrings/salt-archive-keyring.gpg https://repo.saltproject.io/py3/debian/11/amd64/latest/salt-archive-keyring.gpg
# RUN pip3 install pytest pytest-mock pytest-cov requests Jinja2
RUN apt-get update && \
    apt-get install --yes python3 python3-jinja2 python3-colorama python3-jsonpath-rw salt-common

