# By default all regex matching is off
regex_path_include_pattern = None # This turns off include filtering
regex_path_exclude_pattern = None # This turns off exclude filtering
regex_content_include_pattern = None # This turns off include filtering
regex_content_exclude_pattern = None # This turns off exclude filtering

# Exclude helpers
exclude_paging = r'(\d[a-f\d][a-f\d][a-f\d]|[a-f\d]\d[a-f\d][a-f\d]|[a-f\d][a-f\d]\d[a-f\d]|[a-f\d][a-f\d][a-f\d]\d|e,location|adba|aeba|bdfb|ddbc|eddd|efde|fadc|fcac|fdfa|feab|ffdd|efbf|fddf|fffc|dfaa).html$'

# What files to exluce (After inclusion) based on path
regex_path_exclude_pattern =  r''+exclude_paging+''

# Custom beautiful soup loop function
def custom_soup_and_loop_logic(spider, response_body, url, BeautifulSoup):
    soup = BeautifulSoup(response_body, 'html.parser') # Create a BeautifulSoup object from the HTML content

    # The site being scraped, without the language part of www.hel.fi/fi.
    hosts = [spider.website_path.split('/')[0]]
    # www.hel.fi is also linked to without the www.
    if hosts[0].startswith('www.'):
        hosts.append(hosts[0][len('www.'):])

    # A link is cross language when the page it sits on is in one language and
    # the link points into the folder of another.
    languages = ('fi', 'sv', 'en')

    # CSS selector for matchging elements
    selectors = []
    for page_language in languages:
        for language in languages:
            if language == page_language:
                continue

            links = [f'a[href^="/{language}/"]', f'a[href^="../"][href*="/{language}/"]']
            for name in hosts:
                links.append(f'a[href^="http://{name}/{language}/"]')
                links.append(f'a[href^="https://{name}/{language}/"]')

            for link in links:
                selectors.append(f'html[lang="{page_language}"] {link}:not(.language-link)')

    css_selector = ',\n'.join(selectors)

    # Find and loop through matching elements on this page
    matches = soup.select(css_selector)
    for match in matches:
        spider.matches += 1
        # class_attr = match.get('class')
        yield {
            'url': url,
            'href': match['href'],
            'text': match.get_text().strip(),
        }

