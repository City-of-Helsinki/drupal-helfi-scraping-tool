# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter


# class WebcrawlerPipeline:
#     def process_item(self, item, spider):
#         return item

import json

class JsonExportPipeline:
    def open_spider(self):
        self.file = open('scraped_data.json', 'w', encoding='utf-8')
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














