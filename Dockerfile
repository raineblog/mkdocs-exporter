# syntax=docker/dockerfile:1
FROM python:alpine

RUN apk add --no-cache \
    bash tini tar zstd \
    ca-certificates openssh curl wget \
    git git-fast-import \
    fontconfig texlive-full && fc-cache -fv

RUN pip install playwright && \
    playwright install-deps chromium && \
    playwright install chromium

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY exporter/ /app/exporter/
COPY --chmod=755 mkdocs-export.sh /usr/local/bin/mkdocs-export

ENTRYPOINT ["/sbin/tini", "--"]
CMD ["/usr/local/bin/mkdocs-export"]