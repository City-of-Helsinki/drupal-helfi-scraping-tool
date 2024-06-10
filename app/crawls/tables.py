# Website path
website_path = 'www.hel.fi' # Use when you want to search all pages

# By default all regex matching is off
regex_path_include_pattern = None # This turns off include filtering
regex_path_exclude_pattern = None # This turns off exclude filtering
regex_content_include_pattern = None # This turns off include filtering
regex_content_exclude_pattern = None # This turns off exclude filtering

# Exclude helpers
exclude_paging = '(\d[a-f\d][a-f\d][a-f\d]|[a-f\d]\d[a-f\d][a-f\d]|[a-f\d][a-f\d]\d[a-f\d]|[a-f\d][a-f\d][a-f\d]\d|e,location|adba|aeba|bdfb|ddbc|eddd|efde|fadc|fcac|fdfa|feab|ffdd|efbf|fddf|fffc|dfaa).html$'

# What files to exluce (After inclusion) based on path
regex_path_exclude_pattern =  r''+exclude_paging+''

# What files to include based on file content
regex_content_include_pattern = r'<table' # Filter only pages that have at least one table

# What files to exclude based on file content
regex_content_exclude_pattern = r'id="helFiErrorPage"'

# Custom beautiful soup loop function
def custom_soup_and_loop_logic(spider, response_body, url, BeautifulSoup):
    soup = BeautifulSoup(response_body, 'html.parser') # Create a BeautifulSoup object from the HTML content

    # CSS selector for matchging elements
    css_selector = 'table'

    # Find and loop through matching elements on this page
    matches = soup.select(css_selector)
    for match in matches:
        inner_html = match.encode_contents().decode('utf-8')
        stripped_html = inner_html.replace('&nbsp;','') # Remove nbsp
        stripped_html = ''.join(stripped_html.split()) # Strip whitespace and linebreaks

        spider.matches += 1

        yield {
            'url': url,
        }

