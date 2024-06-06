

# config.py

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

# What files to exluce (After inclusion) based on path
# regex_path_exclude_pattern =  r''+exclude_paging+''



# What files to include based on file content
# regex_content_include_pattern = r'content-card--design-teaser'
# regex_content_include_pattern = r'form' # Filter only pages that have at least one form

# What files to exclude based on file content
# regex_content_exclude_pattern = r'(openid-connect-login-form|user-login-form|eu-cookie-compliance-block-form)' # Filter out login forms and cookie consent forms
# regex_content_exclude_pattern = r'hero__container'

# Custom beautiful soup loop function
def custom_soup_and_loop_logic(spider, response_body, url, BeautifulSoup):


    soup2 = BeautifulSoup(response_body, 'html.parser') # Create a BeautifulSoup object from the HTML content
    metas = soup2.select('meta[name="description"][content]')
    metaContent = '';
    for meta in metas:
        metaContent = meta['content']


    soup = BeautifulSoup(response_body, 'html.parser') # Create a BeautifulSoup object from the HTML content

    # CSS selector for matchging elements
    css_selector = 'body'



    # Find and loop through matching elements on this page
    matches = soup.select(css_selector)
    for match in matches:
        spider.matches += 1
        # class_attr = match.get('class')
        yield {
            # 'class': class_attr if class_attr is not None else '',
            # 'title': match['title'],
            # 'title': match['title'],
            'url': url,
            # "html": str(match), # Get outer   HTML
            # "inner_html": match.encode_contents().decode('utf-8').strip(),  # Get inner HTML
            # 'href': match['href'],
            # 'text': match.get_text().strip(),
            # 'length': len(match.get_text().strip()),
            # 'meta': metaContent
        }

