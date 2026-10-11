ARG BUILD_ARCH=aarch64

# Builder stage
FROM golang:1.26-alpine AS builder

ENV GOTOOLCHAIN=auto

ARG BRIDGE_VERSION=v3.27.0
RUN apk add --no-cache \
    bash \
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

FROM ghcr.io/home-assistant/${BUILD_ARCH}-base:latest

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

RUN chmod +x /usr/local/bin/init-bridge \
    && chmod +x /usr/local/bin/bridge-manager \
    && chmod +x /etc/s6-overlay/s6-rc.d/*/run

LABEL \
    io.hass.name="Proton Mail Bridge" \
    io.hass.description="Proton Mail Bridge running headless IMAP and SMTP servers with Ingress web management terminal." \
    io.hass.arch="amd64|aarch64" \
    io.hass.type="addon" \
    io.hass.version="1.0.0"
