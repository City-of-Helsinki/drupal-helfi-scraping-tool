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
    def open_spider(self, spider):
        self.file = open('../result/scraped_data.json', 'w', encoding='utf-8')
        self.file.write('[')
        self.item_count = 0  # Initialize a counter for the items

    def close_spider(self, spider):
        # if self.item_count % 50 != 0:
        #     # This is to remove the trailing comma for the last batch if it's not exactly 50 items
        #     self.file.seek(self.file.tell() - 2, 0)
        self.file.write('\n]')
        self.file.close()

    def process_item(self, item, spider):
        line = json.dumps(dict(item), ensure_ascii=False) + ",\n"
        self.file.write(line)

        self.item_count += 1  # Increment the item counter

        # Check if the count has reached 50
        if self.item_count % 50 == 0:
            self.file.flush()  # Flush every 50 items

        return item














