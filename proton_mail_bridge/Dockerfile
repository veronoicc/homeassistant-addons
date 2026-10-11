# Builder stage
FROM golang:1.23-alpine AS builder

ARG BRIDGE_VERSION=v3.27.0

RUN apk add --no-cache \
    git \
    make \
    gcc \
    g++ \
    musl-dev \
    pkgconf \
    libsecret-dev \
    openssl-dev \
    libcbor-dev \
    libfido2-dev

WORKDIR /build
RUN git clone --depth 1 --branch "${BRIDGE_VERSION}" https://github.com/ProtonMail/proton-bridge.git . \
    && CGO_CFLAGS="-D_LARGEFILE64_SOURCE" make build-nogui

# Runtime stage
ARG BUILD_FROM=ghcr.io/home-assistant/base:latest
FROM ${BUILD_FROM}

RUN apk add --no-cache \
    libsecret \
    pass \
    gnupg \
    socat \
    ttyd \
    nginx \
    bash \
    jq \
    openssl

RUN rm -f /etc/nginx/http.d/default.conf

COPY --from=builder /build/bridge /usr/local/bin/proton-bridge
RUN ln -sf /usr/local/bin/proton-bridge /usr/local/bin/bridge

COPY rootfs/ /

RUN chmod +x /etc/s6-overlay/s6-rc.d/00-init-bridge/up \
    && chmod +x /etc/s6-overlay/s6-rc.d/*/run \
    && chmod +x /usr/local/bin/bridge-manager

LABEL \
    io.hass.name="Proton Mail Bridge" \
    io.hass.description="Proton Mail Bridge running headless IMAP and SMTP servers with Ingress web management terminal." \
    io.hass.arch="amd64|aarch64" \
    io.hass.type="addon" \
    io.hass.version="1.0.0"
