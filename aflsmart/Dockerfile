FROM zjuchenyuan/aflsmart

USER root

RUN rm -f /etc/apt/sources.list.d/*.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        libxml2-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /work