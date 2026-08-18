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
    host = spider.website_path.split('/')[0]
    # www.hel.fi is also linked to without the www.
    hosts = [host]
    if host.startswith('www.'):
        hosts.append(host[len('www.'):])

    # CSS selector for matchging elements
    filetypes = ':not([href$=".pdf"])'
    starts = ['/', '../']
    for name in hosts:
        starts.append(f'https://{name}/')
        starts.append(f'http://{name}/')

    css_selector = ','.join(
        f'.layout-main-wrapper a[href^="{start}"]{filetypes}' for start in starts
    )

    # Find and loop through matching elements on this page
    matches = soup.select(css_selector)
    for match in matches:
        spider.matches += 1
        yield {
            'url': url.replace(f'https://{host}',''),
            'href': match['href'].replace('.html',''),
        }

