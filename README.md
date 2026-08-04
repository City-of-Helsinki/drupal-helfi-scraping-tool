# Drupal Helfi scraping tool

For most of our needs to figure out where certain elements are being used on the website of [hel.fi](https://www.hel.fi/fi) we can use Siteimprove policies. While slow, they can potentially be seen and edited by multiple people and they keep up to date every week. They also provide a nice dashboard.

However, while Siteimprove is great to answer to questions:

* How many instances do we have of a certain element on the site?
* On what pages can this element be found on the site?

Siteimprove is still lacking when we want to get the actual contents of thousands of elements or have more flexibility in matching. In addition, not all our sites have Siteimprove subscription.

This scraping tool helps to fill that need.

## How it works

* This tool is a command line program that scrapes offline copy of hel.fi sites.
* It downloads a static copy of a site into `~/.local/share/scraping-tool/projects/<site>/`
* It scrapes the contents of the .html files
  * To make it faster, it can filter files to be scanned based on filename, filecontents
  * With the selected set of files, it performs a scrape using CSS selector
* It returns the selected fields into a `scraped_data.json` file.

## Sites

`www.hel.fi` is copied to kopio.hel.fi nightly, and provides a zip file of the
latest dump. Other sites are scraped by a github workflow that runs on the
site's repo.

```
scraping-tool sites                           # list sites and what has been downloaded
scraping-tool sites download historia.hel.fi  # from the github artifact
scraping-tool sites download www.hel.fi       # from the kopio zip
scraping-tool scrape historia.hel.fi quotes
```

Site dumps update once per day. Run `scraping-tool sites download <site>` to re-download latest version.

### Adding a new site

1. Add `.github/workflows/scraping-tool.yml` to the site's own repository. See the "Scraping tool mirror" section of [drupal-gh-actions](https://github.com/City-of-Helsinki/drupal-gh-actions#scraping-tool-mirror).
2. Run it once from **Actions > Build scraping tool artifact > Run workflow**.
3. Add the site to [app/sites.toml](app/sites.toml) and commit.

### Github access

Sites other than www.hel.fi need github credentials to download the html dump. Either
install the [github cli](https://cli.github.com/) and run `gh auth login`, or put
a token in the environment as `GITHUB_TOKEN`. Create a token at
https://github.com/settings/tokens with the `public_repo` scope, or a fine
grained token with read access to Actions.

## Usage

This tool is used to scrape data from Drupal Helfi sites. It uses the [Scrapy](https://scrapy.org/) framework to scrape the data.

### Commands

* `scraping-tool sites` lists the sites and shows which ones have been downloaded
* `scraping-tool sites download <site>` downloads the latest copy of a site
* `scraping-tool scrape <site> <scrape_module>` scrapes a downloaded site using given module rules (see below)
* `scraping-tool scrape <site> <scrape_module> --output results.json` writes somewhere other than `scraped_data.json`
* `scraping-tool list` lists available scrape modules
* `scraping-tool env` lists settings as the tool sees them, useful for debugging if the tool does not work

Add `--help` to any command to see the full set of options.

The site can be narrowed to a part of the site, e.g. `www.hel.fi/fi` only walks the Finnish pages.

### Crawl modules

Crawl command wihtout arguments lists pre-built crawl modules:

```
`scraping-tool scrape`
```

A crawl module can be given as a path to a custom file instead:

```
scraping-tool scrape www.hel.fi ./my-search.py
```

To create one:

* Copy [app/crawls/_example.py](app/crawls/_example.py) to a new file with a descriptive name
  * For example: `cp app/crawls/_example.py ./my-searches/list-of-links.py`
* Modify the new file to reduce the files to be searched as small as possible using filename and filecontents patterns
  * For example: `regex_content_include_pattern = r'component--list-of-links'`
* Create an CSS selector to match the HTML elements of interest
  * For example:  `css_selector = '.component--list-of-links a.list-of-links__item__link'`
  * This would return all list-of-links links on the site line by line
* Select which attributes to export
  * For example: `'url': url,` and `'text': match.get_text().strip(),`
  * This would print url as many times there are list-of-links on the site.
* Save the changes to the module file, then run the scrape
  * For example: `scraping-tool scrape www.hel.fi ./my-searches/list-of-links.py`

If you want to share your scrape module, move it to the folder
`app/crawls/` and commit it. It can now be run by name with `scraping-tool
scrape <site> <name>`

### Tips

* Filter to use only the language you're interested. `scraping-tool scrape www.hel.fi/fi <module>`
* Filter only path you're interested in `regex_path_include_pattern = r'\/(uutiset|nyheter|news)\/'`
* Filter out paths that you're not interested in `regex_path_exclude_pattern = r'(illustration_error_page_403_401|illustration_error_page_404)'`
* Filter only files that have certain content, for example the class that you're looking for. `regex_content_include_pattern = r'content-card--design-teaser'`
* Keep the CSS selector as simple as possible.
* Try to save only relevant data to output file so that its size stays sane.

### Notice

* The copy of a site is not perfect.
  * It's build by crawling the site and collecting urls while saving.
  * The core copy also downloads sitemap.xml files and adds those urls to be crawled.
  * It modifies the crawled HTML source, for example, it removes image source variants, basically blocking any queries related to actual image syntax.
  * It also modifies the paths to include .html suffix, which I've tried to counter with some code, but not all can be fixed (paging for example)
  * Regarding paged content, it tries to crawl them, but it adds an hex code to the end of the filename beyond first page.
