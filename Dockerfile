# syntax=docker/dockerfile:1
FROM python:alpine

RUN apk add --no-cache \
    bash tini tar zstd \
    ca-certificates openssh curl wget \
    git git-fast-import \
    chromium chromium-chromedriver \
    fontconfig texlive-full && fc-cache -fv

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY exporter/ /app/exporter/
COPY --chmod=755 mkdocs-export.sh /usr/local/bin/mkdocs-export

ENTRYPOINT ["/sbin/tini", "--"]
CMD ["/usr/local/bin/mkdocs-export"]