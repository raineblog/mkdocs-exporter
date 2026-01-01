FROM python:3.12
WORKDIR /app
COPY requirements.txt .
RUN python -m pip install --upgrade pip --no-cache-dir
RUN pip install --no-cache-dir -r requirements.txt && \
    playwright install --with-deps
RUN apt-get install -y fontconfig texlive-full fonts-noto-cjk fonts-noto-cjk-extra && \
    rm -rf /var/lib/apt/lists/* && fc-cache -fv
COPY exporter/ /app/exporter/
COPY export-pdf.sh /usr/local/bin/export-pdf
RUN chmod +x /usr/local/bin/export-pdf
