# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html

import json
from pathlib import Path

# Where the results end up unless SCRAPED_DATA_OUTPUT says otherwise. Anchored to
# this file so the output does not move with the working directory.
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / 'scraped_data.json'


class JsonExportPipeline:
    def __init__(self, output_path=None):
        self.output_path = Path(output_path) if output_path else DEFAULT_OUTPUT

    @classmethod
    def from_crawler(cls, crawler):
        return cls(output_path=crawler.settings.get('SCRAPED_DATA_OUTPUT'))

    def open_spider(self, spider):
        self.file = open(self.output_path, 'w', encoding='utf-8')
        self.file.write('[')
        self.item_count = 0

    def close_spider(self, spider):
        self.file.write('\n]')
        self.file.close()

    def process_item(self, item, spider):
        # An aborted run can close the file while an item is still on its way here.
        if self.file.closed:
            return item

        separator = '\n' if self.item_count == 0 else ',\n'
        self.file.write(separator + json.dumps(dict(item), ensure_ascii=False))

        self.item_count += 1

        if self.item_count % 50 == 0:
            self.file.flush()  # Flush every 50 items

        return item
