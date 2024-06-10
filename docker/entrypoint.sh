#!/bin/bash

SCRAPE_MODULE=${SCRAPE_MODULE:-all}

case "$1" in
  download)
    wget "$DOWNLOAD_URL" -O /tmp/downloaded.zip && \
    rm -rf /usr/src/app/downloaded && \
    unzip /tmp/downloaded.zip -d /usr/src/app/downloaded && \
    find /usr/src/app/downloaded/ -type f ! -name "*.html" -exec rm -f {} +  && \
    rm /tmp/downloaded.zip
    ;;
  scrape)
    scrapy crawl -L ERROR helficopy
    ;;
  *)
    echo "Next options:"
    echo "  * 'make download' to get the latest copy of the data to be scraped"
    echo "  * 'make scrape <scrape_module>' to scrape the data using selected scrape_module"
    echo "  * 'make list' to list all available scrape_modules"
    echo "  * 'make env' to check env variables"
    echo "  * 'make stop' to stop the container"
    exit 1
    ;;
esac
