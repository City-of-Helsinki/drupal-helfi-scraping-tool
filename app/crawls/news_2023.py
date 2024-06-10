import re

# Website path
website_path = 'www.hel.fi' # Use when you want to search all pages

# By default all regex matching is off
regex_path_include_pattern = None # This turns off include filtering
regex_path_exclude_pattern = None # This turns off exclude filtering
regex_content_include_pattern = None # This turns off include filtering
regex_content_exclude_pattern = None # This turns off exclude filtering

# What files to include based on path
regex_path_include_pattern = r'(\/uutiset\/|\/nyheter\/|\/news\/)' # Liikenne

# Exclude helpers
exclude_paging = '(\d[a-f\d][a-f\d][a-f\d]|[a-f\d]\d[a-f\d][a-f\d]|[a-f\d][a-f\d]\d[a-f\d]|[a-f\d][a-f\d][a-f\d]\d|e,location|adba|aeba|bdfb|ddbc|eddd|efde|fadc|fcac|fdfa|feab|ffdd|efbf|fddf|fffc|dfaa).html$'
exclude_error = '(illustration_error_page_403_401|illustration_error_page_404)'

# What files to exluce (After inclusion) based on path
regex_path_exclude_pattern =  r'('+exclude_error+'|'+exclude_paging+')'


# What files to include based on file content
regex_content_include_pattern = r'<meta property="article:published_time" content="2023-'

# Custom beautiful soup loop function
def custom_soup_and_loop_logic(spider, response_body, url, BeautifulSoup):
    soup = BeautifulSoup(response_body, 'html.parser') # Create a BeautifulSoup object from the HTML content

    meta_titles = soup.select('meta[property="og:title"][content]')
    meta_title = '';
    for meta in meta_titles:
        meta_title = meta['content']

    meta_alt_langs = soup.select('link[rel="alternate"][hreflang]')
    meta_alt_lang = ', '.join([meta['hreflang'] for meta in meta_alt_langs])

    # CSS selector for matchging elements
    css_selector = 'meta[property="article:published_time"]'

    # Find and loop through matching elements on this page
    matches = soup.select(css_selector)
    for match in matches:

        spider.matches += 1
        yield {
            'url': url,
            'published': match['content'],
            'title': meta_title,
            'langs': meta_alt_lang,
        }

