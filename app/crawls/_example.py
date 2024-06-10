# Website path
website_path = 'www.hel.fi' # Use when you want to search all pages
# website_path = 'www.hel.fi/fi' # Use when you want to limit search only to Finnish pages
# website_path = 'www.hel.fi/sv' # Use when you want to limit search only to Swedish pages
# website_path = 'www.hel.fi/en' # Use when you want to limit search only to English pages

# By default all regex matching is off
regex_path_include_pattern = None # This turns off include filtering
regex_path_exclude_pattern = None # This turns off exclude filtering
regex_content_include_pattern = None # This turns off include filtering
regex_content_exclude_pattern = None # This turns off exclude filtering

# What files to include based on path
# regex_path_include_pattern = r'/kasvatus-ja-koulutus/' # Kasko
# regex_path_include_pattern = r'/kaupunkiymparisto-ja-liikenne/' # Liikenne

# Exclude helpers
exclude_paging = '(\d[a-f\d][a-f\d][a-f\d]|[a-f\d]\d[a-f\d][a-f\d]|[a-f\d][a-f\d]\d[a-f\d]|[a-f\d][a-f\d][a-f\d]\d|e,location|adba|aeba|bdfb|ddbc|eddd|efde|fadc|fcac|fdfa|feab|ffdd|efbf|fddf|fffc|dfaa).html$'
exclude_news = '(\/uutiset\/|\/nyheter\/|\/news\/)'
exclude_error = '(illustration_error_page_403_401|illustration_error_page_404)'

# What files to exluce (After inclusion) based on path
regex_path_exclude_pattern =  r''+exclude_paging+''
# regex_path_exclude_pattern =  r'('+exclude_news+'|'+exclude_paging+')'

# What files to include based on file content
# regex_content_include_pattern = r'body'

# What files to exclude based on file content
# regex_content_exclude_pattern = r'hero__container'

# Custom beautiful soup loop function
def custom_soup_and_loop_logic(spider, response_body, url, BeautifulSoup):
    soup = BeautifulSoup(response_body, 'html.parser') # Create a BeautifulSoup object from the HTML content

    # Example of how to get meta data from page head
    # metas = soup.select('meta[name="description"][content]')
    # metaContent = '';
    # for meta in metas:
    #     metaContent = meta['content']

    # CSS selector for matching elements
    css_selector = 'body'

    # Find and loop through matching elements on this page
    matches = soup.select(css_selector)
    for match in matches:
        spider.matches += 1
        # class_attr = match.get('class')
        yield {
            'url': url,
            # 'class': class_attr if class_attr is not None else '',
            # 'title': match['title'],
            # "html": str(match), # Get outer   HTML
            # "inner_html": match.encode_contents().decode('utf-8').strip(),  # Get inner HTML
            # 'href': match['href'],
            # 'text': match.get_text().strip(),
            # 'length': len(match.get_text().strip()),
            # 'meta': metaContent
        }

