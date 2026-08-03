# Drupal Helfi scraping tool

For most of our needs to figure out where certain elements are being used on the website of [hel.fi](https://www.hel.fi/fi) we can use Siteimprove policies. While slow, they can potentially be seen and edited by multiple people and they keep up to date every week. They also provide a nice dashboard.

However, while Siteimprove is great to answer to questions:

* How many instances do we have of a certain element on the site?
* On what pages can this element be found on the site?

Siteimprove is still lacking in the department when we want to get the actual contents of thousands of elements or have more flexibility in matching.

This scraping tool helps to fill that need.

## How it works

* This tool runs in a docker container that can be started and stopped with easy commands
* It downloads a static copy of a hel.fi site into `projects/<site>/`
* It scrapes the contents of the .html files
  * To make it faster, it can filter files to be scanned based on filename, filecontents
  * With the selected set of files, it performs a scrape using CSS selector
* It returns the selected fields into a `scraped_data.json` file in the working directory. The file can be previewed even while the scraping is ongoing

## Sites

Most hel.fi sites are scraped by a github workflow that runs on the site's own
repo. `www.hel.fi` is the exception: it is copied to kopio.hel.fi, and comes from
a zip file instead.

Either way the copy lands in `projects/<site>/` and is scraped the same way.

```
./scrape sites                           # what there is, and what has been downloaded
./scrape sites download historia.hel.fi  # from the github artifact
./scrape sites download www.hel.fi       # from the kopio zip
./scrape scrape historia.hel.fi quotes
```

### Adding a new site

1. Add `.github/workflows/scraping-tool.yml` to the site's own repository. See the "Scraping tool mirror" section of [drupal-gh-actions](https://github.com/City-of-Helsinki/drupal-gh-actions#scraping-tool-mirror).
2. Run it once from **Actions > Build scraping tool artifact > Run workflow**.
3. Add the site to [app/sites.toml](app/sites.toml) and commit.

## Installing

### Requirements

* Docker

### Install steps

1. Clone this repository
2. `cp .env.local.example .env.local` and fill in `GITHUB_TOKEN`, which is needed to download any site except the core one. Create one at https://github.com/settings/tokens with the `public_repo` scope, or a fine grained token with read access to Actions.
   * The core site comes from a kopio.hel.fi zip file of a token. Its address is the `url` of `www.hel.fi` in [app/sites.toml](app/sites.toml).
3. Run `./scrape sites download <site>` for the site you are interested in
4. Read usage instructions below

## Usage

This tool is used to scrape data from Drupal Helfi sites. It uses the [Scrapy](https://scrapy.org/) framework to scrape the data.

### Commands

* `./scrape sites` lists the sites and shows which ones have been downloaded
* `./scrape sites download <site>` downloads the latest copy of a site
* `./scrape scrape <site> <scrape_module>` scrapes a downloaded site using given module rules (see below)
* `./scrape scrape <site> <scrape_module> --workers 4` same, but limits how many CPU cores are used
* `./scrape scrape <site> <scrape_module> --output results.json` writes somewhere other than `scraped_data.json`
* `./scrape list` lists available scrape modules
* `./scrape env` lists settings as the tool sees them, useful for debugging if the tool does not work
* `./scrape build` re-creates docker image (e.g. when updating python dependencies).

Add `--help` to any of them to see the full set of options.

The site can be narrowed to a part of the site, e.g. `www.hel.fi/fi` only walks the Finnish pages.

### Crawl modules from a file

A crawl module can be given as a path to a file instead of a name:

```
./scrape scrape www.hel.fi ./my-search.py
```

### Running in Docker

`./scrape` is a small wrapper that runs the tool inside a container, so that Docker
is the only thing you need to have installed. The tool itself is a normal command
line program in `app/cli.py`. If you already have python and the dependencies from
`docker/requirements.txt`, you can skip the container and call it directly:

```
python app/cli.py scrape www.hel.fi quotes --workers 4
```

### Normal usage

When I want to use this tool, I normally do the following:

* If I have not run the download command for a while (data updates once per day), I run `./scrape sites download <site>`
* Copy `app/crawls/custom/_example.py` to a new file in `app/crawls/custom/` folder with a descriptive name
  * For example: `cp app/crawls/custom/_example.py app/crawls/custom/list-of-links.py`
* Modify the new file to reduce the files to be searched as small as possible using filename and filecontents patterns
  * For example: `regex_content_include_pattern = r'component--list-of-links'`
* Create an CSS selector to match the HTML elements of interest
  * For example:  `css_selector = '.component--list-of-links a.list-of-links__item__link'`
  * This would return all list-of-links links on the site line by line
* Select which attributes to export
  * For example: `'url': url,` and `'text': match.get_text().strip(),`
  * This would print url as many times there are list-of-links on the site.
* Save my changes to the module file, then run the scrape
  * For example: `./scrape scrape www.hel.fi custom/list-of-links`
* Check the matches from the command line and from the resulting `scraped_data.json` file.
* If `docker/requirements.txt` or `Dockerfile` is updated, run `./scrape build`.
* If you want to share the new `list-of-links` script, copy it to the folder `app/crawls/` and commit it. It can now be run with `./scrape scrape <site> list-of-links`

### Tips

Since scraping takes a while, remember to check the [scraped_data.json](app/scraped_data.json) when you have started your crawl to spot any problems with the output. This way you do not have to wait until the end to see problems and fix them.

To keep the scraping time sane, follow these steps.

* Filter to use only the language you're interested. `./scrape scrape www.hel.fi/fi <module>`
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
