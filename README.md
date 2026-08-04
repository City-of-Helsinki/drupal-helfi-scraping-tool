# Drupal Helfi scraping tool

For most of our needs to figure out where certain elements are being used on the website of [hel.fi](https://www.hel.fi/fi) we can use Siteimprove policies. While slow, they can potentially be seen and edited by multiple people and they keep up to date every week. They also provide a nice dashboard.

However, while Siteimprove is great to answer to questions:

* How many instances do we have of a certain element on the site?
* On what pages can this element be found on the site?

Siteimprove is still lacking in the department when we want to get the actual contents of thousands of elements or have more flexibility in matching.

This scraping tool helps to fill that need.

## How it works

* This tool is a command line program, installed with pipx or run in a docker container
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
scraping-tool sites                           # what there is, and what has been downloaded
scraping-tool sites download historia.hel.fi  # from the github artifact
scraping-tool sites download www.hel.fi       # from the kopio zip
scraping-tool scrape historia.hel.fi quotes
```

### Adding a new site

1. Add `.github/workflows/scraping-tool.yml` to the site's own repository. See the "Scraping tool mirror" section of [drupal-gh-actions](https://github.com/City-of-Helsinki/drupal-gh-actions#scraping-tool-mirror).
2. Run it once from **Actions > Build scraping tool artifact > Run workflow**.
3. Add the site to [app/sites.toml](app/sites.toml) and commit.

## Installing

There are two ways to install the tool. Pick pipx if you have python, or docker
if you would rather not install anything else.

### With pipx

Needs python 3.11 or newer and [pipx](https://pipx.pypa.io/).

```
pipx install git+https://github.com/City-of-Helsinki/drupal-helfi-scraping-tool.git
```

That puts a `scraping-tool` command on your path. Later, `pipx upgrade scraping-tool`
gets the latest version. Your site copies and your own crawl modules live in your
own directories, so an upgrade does not touch them; run `scraping-tool env` to see
where they are.

### With docker

Needs Docker, and a clone of this repository. `./scraping-tool` in the clone is a
small wrapper that runs the same command inside a container, so nothing else has
to be installed:

```
./scraping-tool sites
```

Everywhere below where the instructions say `scraping-tool`, use
`./scraping-tool` instead if this is how you installed it.

### Github access

The tool needs to reach github to download any site except www.hel.fi. Either
install the [github cli](https://cli.github.com/) and run `gh auth login`, or put
a token in the environment as `GITHUB_TOKEN`. Create a token at
https://github.com/settings/tokens with the `public_repo` scope, or a fine
grained token with read access to Actions.

With docker you can also `cp .env.local.example .env.local` and fill in the token
there; the compose file reads it. A pipx install does not, so export the variable
or use `gh` instead.

The core site is the exception: it comes from a kopio.hel.fi zip file that needs
no token. Its address is the `url` of `www.hel.fi` in
[app/sites.toml](app/sites.toml).

Once that works, run `scraping-tool sites download <site>` for the site you are
interested in and read the usage instructions below.

## Usage

This tool is used to scrape data from Drupal Helfi sites. It uses the [Scrapy](https://scrapy.org/) framework to scrape the data.

### Commands

* `scraping-tool sites` lists the sites and shows which ones have been downloaded
* `scraping-tool sites download <site>` downloads the latest copy of a site
* `scraping-tool scrape <site> <scrape_module>` scrapes a downloaded site using given module rules (see below)
* `scraping-tool scrape <site> <scrape_module> --workers 4` same, but limits how many CPU cores are used
* `scraping-tool scrape <site> <scrape_module> --output results.json` writes somewhere other than `scraped_data.json`
* `scraping-tool list` lists available scrape modules
* `scraping-tool env` lists settings as the tool sees them, useful for debugging if the tool does not work
* `./scraping-tool build` re-creates the docker image (docker only, e.g. when updating python dependencies).

Add `--help` to any of them to see the full set of options.

The site can be narrowed to a part of the site, e.g. `www.hel.fi/fi` only walks the Finnish pages.

### Crawl modules from a file

A crawl module can be given as a path to a file instead of a name:

```
scraping-tool scrape www.hel.fi ./my-search.py
```

The names in `scraping-tool list` are the modules in
[app/crawls/](app/crawls) that ship with the tool. Everything
else is a file path, so a module of your own can sit anywhere.

### Running from a clone

The tool is a normal python package. In a clone with the dependencies installed
you can run it without installing anything:

```
python -m app.cli scrape www.hel.fi quotes --workers 4
```

### Normal usage

When I want to use this tool, I normally do the following:

* If I have not run the download command for a while (data updates once per day), I run `scraping-tool sites download <site>`
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
* Save my changes to the module file, then run the scrape
  * For example: `scraping-tool scrape www.hel.fi ./my-searches/list-of-links.py`
* Check the matches from the command line and from the resulting `scraped_data.json` file.
* If `pyproject.toml` or `Dockerfile` is updated, run `./scraping-tool build` (docker only).
* If you want to share the new `list-of-links` script, move it to the folder `app/crawls/` and commit it. It can now be run by name with `scraping-tool scrape <site> list-of-links`

### Tips

Since scraping takes a while, remember to check the `scraped_data.json` it writes into the directory you started it from when you have started your crawl, to spot any problems with the output. This way you do not have to wait until the end to see problems and fix them.

To keep the scraping time sane, follow these steps.

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
