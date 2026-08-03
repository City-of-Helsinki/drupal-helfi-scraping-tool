# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html

import json


class JsonExportPipeline:
    # The cli resolves --output into SCRAPED_DATA_OUTPUT before the crawl starts.
    def __init__(self, output_path):
        self.output_path = output_path

    @classmethod
    def from_crawler(cls, crawler):
        return cls(output_path=crawler.settings.get('SCRAPED_DATA_OUTPUT'))

    def open_spider(self):
        self.file = open(self.output_path, 'w', encoding='utf-8')
        self.file.write('[')
        self.item_count = 0

    def close_spider(self):
        self.file.write('\n]')
        self.file.close()

    def process_item(self, item):
        # An aborted run can close the file while an item is still on its way here.
        if self.file.closed:
            return item

        separator = '\n' if self.item_count == 0 else ',\n'
        self.file.write(separator + json.dumps(dict(item), ensure_ascii=False))

        self.item_count += 1

        if self.item_count % 50 == 0:
            self.file.flush()  # Flush every 50 items

        return item
