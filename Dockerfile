FROM alpine:3.11
COPY requirements.txt /requirements.txt
COPY requirements-dev.txt /requirements-dev.txt
RUN apk --update --no-cache add \
        openssl \
        ca-certificates \
        python3 \
        python2 \
        git \
        make \
        musl-dev \
        linux-headers \
        python3-dev \
        python2-dev \
        py2-pip \
        openssl-dev \
        libffi-dev \
        gcc \
        g++ && \
    pip2 --no-cache-dir install -r /requirements.txt && \
    pip2 --no-cache-dir install -r /requirements-dev.txt && \
    python3 -m pip --no-cache-dir install -r /requirements.txt && \
    python3 -m pip --no-cache-dir install -r /requirements-dev.txt
