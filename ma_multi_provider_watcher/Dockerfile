ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache \
    docker-cli \
    bash \
    curl \
    git \
    jq \
    python3 \
    tar

WORKDIR /app

COPY run.py /app/run.py
RUN chmod +x /app/run.py

ENTRYPOINT ["python3", "-u", "/app/run.py"]
