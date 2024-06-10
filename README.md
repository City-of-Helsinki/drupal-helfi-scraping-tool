# Drupal Helfi scraping tool

For most of our needs to figure out where certain elements are being used on the website of [hel.fi](https://www.hel.fi/fi) we can use Siteimprove policies. While slow, they can potentially be seen and edited by multiple people and they keep up to date every week. They also provide a nice dashboard.

However, while Siteimprove is great to answer to questions:

* How many instances do we have of a certain element on the site?
* On what pages can this element be found on the site?

Siteimprove is still lacking in the department when we want to get the actual contents of thousands of elements or have more flexibility in matching.

This scraping tool helps to fill that need.

## How it works

* This tool runs in a docker container that can be started and stopped with easy commands
* It downloads a zip file that contains an static copy of [hel.fi](https://www.hel.fi/fi) with paths to pages and the page html content in .html files.
* It scrapes the contents of the .html files
  * To make it faster, it can filter files to be scanned based on filename, filecontents
  * With the selected set of files, it performs a scrape using CSS selector
* It returns the selected fields into  app/scraped_data.json file, that can be previewed even while the scraping is ongoing

## Installing

### Requirements

* Docker
* Make
* ~ 3 gigs of free space for the site clone as of June 2024

### Install steps

1. Clone this repository
2. Create environment variables `cp .env.local.example .env.local`
3. Edit environment variables, at least add the DOWNLOAD_URL
4. Run `make start` to create docker container
5. Run `make download` to get the latest clone of the website.
6. Read usage instructions below

## Usage

This tool is used to scrape data from Drupal Helfi sites. It uses the [Scrapy](https://scrapy.org/) framework to scrape the data.

### Commands

* `make start` starts the container and copies potential previously downloaded files in it
* `make stop` stops the container, it does not remove files from filesystem
* `make download` downloads latest data for scraping
* `make scrape <scrape_module>` scrapes the downloaded data using given module rules (see below)
* `make list` lists available scrape modules
* `make env` lists env settings as the tool sees them, useful for debugging if the tool does not work

### Normal usage

When I want to use this tool, I normally do the following:

* Start the container if it's not already running `make start`
* If I have not run the download command for a while (data updates once per day), I run `make download`
* Copy `app/crawls/_example.ph` to a new file in the same folder with a descriptive name
  * For example: `app/crawls/list-of-links.py`
* Modify the new file to reduce the files to be searched as small as possible using filename and filecontents patterns
  * For example: `regex_content_include_pattern = r'component--list-of-links'`
* Create an CSS selector to match the HTML elements of interest
  * For example:  `css_selector = '.component--list-of-links a.list-of-links__item__link'`
  * This would return all list-of-links links on the site line by line
* Select which attributes to export
  * For example: `'url': url,` and `'text': match.get_text().strip(),`
  * This would print url as many times there are list-of-links on the site.
* Save my changes to the module file, then run the scrape
  * For example: `make scrape list-of-links`
* Check the matches from the command line and from the resulting `app/scraped_data.json` file for any bugs in my filters.

### Tips

Since scraping takes a while, remember to check the [scraped_data.json](app/scraped_data.json) when you have started your crawl to spot any problems with the output. This way you do not have to wait until the end to see problems and fix them.

To keep the scraping time sane, follow these steps.

* Filter to use only the language you're interested. `website_path = 'www.hel.fi/fi'`
* Filter only path you're interested in `regex_path_include_pattern = r'\/(uutiset|nyheter|news)\/'`
* Filter out paths that you're not interested in `regex_path_exclude_pattern = r'(illustration_error_page_403_401|illustration_error_page_404)'`
* Filter only files that have certain content, for example the class that you're looking for. `regex_content_include_pattern = r'content-card--design-teaser'`
* Keep the CSS selector as simple as possible.
* Try to save only relevant data to output file so that its size stays sane.

### Notice

* The copy of hel.fi is not perfect.
  * It's build by crawling the site and collecting urls while saving.
  * It also downloads sitemap.xml files and adds those urls to be crawled.
  * It modifies the crawled HTML source, for example, it removes image source variants, basically blocking any queries related to actual image syntax.
  * It also modifies the paths to include .html suffix, which I've tried to counter with some code, but not all can be fixed (paging for example)
  * Regarding paged content, it tries to crawl them, but it adds an hex code to the end of the filename beyond first page.

### Scrape modules

There are some ready made modules that have answered a question I have had, feel free to use them as an inspiration or as a basis for further exploration.

Here's a table of the current modules with their matches and processing time on my machine. These times and matches will probably vary between data date and computer.

| Command                           | Description                                                      |  Time  | Matches |
|-----------------------------------|------------------------------------------------------------------|:------:|:-------:|
| `make scrape all`                 | This command gets urls to all pages, including paged links.      | 20 min |   22877 |
| `make scrape all_unpaged`         | Same as above, but paging is removed before scraping.            | 14 min |   16174 |
| `make scrape alt_original`        | How the alt-texts get altered with the photographer information. |  2 min |    3752 |
| `make scrape announcements`       | All announcements and their texts                                | 14 min |     133 |
| `make scrape contact_card_img`    | Contact card image styles                                        |  5 sec |     100 |
| `make scrape contact_card`        | Contact card person descriptions                                 | 14 sec |     277 |
| `make scrape cross_lang_links`    | Internal links that point to another language in text content.   | 30 min |     961 |
| `make scrape empty_headings`      | Headings with only whitespace                                    | 16 min |      16 |
| `make scrape external_icon`       | CKEditor created links with external icon                        |  7 sec |       2 |
| `make scrape image_caption`       | Image caption text content                                       |  6 min |    9320 |
| `make scrape img`                 | Figuring out all image classes with the exclusion method         | 15 min |    1681 |
| `make scrape internal_links`      | List all internal links (helps to create vector map)             | 18 min |  334196 |
| `make scrape liftup_button`       | Liftup with image secondary elements that have button in them    |  9 sec |       0 |
| `make scrape news_2023`           | List of all news done in 2023                                    |  2 min |    2074 |
| `make scrape quotes`              | All quotes on site                                               |  9 sec |     148 |
| `make scrape rekry_query`         | All links to rekry searches                                      | 22 sec |       0 |
| `make scrape tables`              | All pages that contain tables                                    | 17 sec |     559 |
| `make scrape user_edited_content` | All spans in use inside user_edited_content                      | 23 min |   22371 |
