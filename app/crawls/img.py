# Website path
website_path = 'www.hel.fi' # Use when you want to search all pages

# By default all regex matching is off
regex_path_include_pattern = None # This turns off include filtering
regex_path_exclude_pattern = None # This turns off exclude filtering
regex_content_include_pattern = None # This turns off include filtering
regex_content_exclude_pattern = None # This turns off exclude filtering

# Exclude helpers
exclude_paging = '(\d[a-f\d][a-f\d][a-f\d]|[a-f\d]\d[a-f\d][a-f\d]|[a-f\d][a-f\d]\d[a-f\d]|[a-f\d][a-f\d][a-f\d]\d|e,location|adba|aeba|bdfb|ddbc|eddd|efde|fadc|fcac|fdfa|feab|ffdd|efbf|fddf|fffc|dfaa).html$'
exclude_error = '(illustration_error_page_403_401|illustration_error_page_404)'

# What files to exluce (After inclusion) based on path
regex_path_exclude_pattern =  r'('+exclude_error+'|'+exclude_paging+')'

# What files to include based on file content
regex_content_include_pattern = r'img'

# Custom beautiful soup loop function
def custom_soup_and_loop_logic(spider, response_body, url, BeautifulSoup):
    soup = BeautifulSoup(response_body, 'html.parser') # Create a BeautifulSoup object from the HTML content

    # CSS selector for matchging elements
    css_selector = '''
      :not(
        .component--image .image,
        .contact-card--with-image,
        .list-of-links__item__image,
        .component--liftup-with-image-img.component--liftup-with-image-img-on-right .image,
        .component--liftup-with-image-img.component--liftup-with-image-img-on-left .image,
        .component--liftup-with-image-bg.component--liftup-with-image-img-on-right .image,
        .component--liftup-with-image-bg.component--liftup-with-image-img-on-left .image,
        .current__content,
        .news-listing__card-teaser,
        .component--content-cards-small .content-card__image,
        .component--content-cards-large .content-card__image,
        .hero--with-image-left .hero__image-container,
        .hero--with-image-right .hero__image-container,
        .hero--with-image-bottom .hero__image-container,
        .hero--diagonal .hero__image-container,
        .unit-contact-card__image,
        .node--type-news-item.node--view-mode-full > .main-image,
        .unit--full > .main-image,
        .project__image-container,
        .content-liftup__image,
        .news-listing__item,
        .card--external,
        .card,
        .card__image
      ) > * > img
    '''

    # Find and loop through matching elements on this page
    matches = soup.select(css_selector)
    for match in matches:
        spider.matches += 1
        yield {
            'url': url,
            'src': match['src'],
        }

