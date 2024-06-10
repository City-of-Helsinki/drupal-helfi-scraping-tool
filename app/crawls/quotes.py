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
regex_content_include_pattern = r'blockquote'

# Custom beautiful soup loop function
def custom_soup_and_loop_logic(spider, response_body, url, BeautifulSoup):
    soup = BeautifulSoup(response_body, 'html.parser') # Create a BeautifulSoup object from the HTML content

    # CSS selector for matchging elements
    css_selector = 'blockquote'

    # Find and loop through matching elements on this page
    matches = soup.select(css_selector)
    for match in matches:
        spider.matches += 1
        yield {
            'url': url,
            'text': match.get_text().strip(),
        }

