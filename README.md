

# Standard Method

This scrape method builds state by searching through each category, subcategory, and series, so that when each publication hover link is clicked, the Series and Department code are populated.  The scrape looks like this:

- Build the category list
- Build the subcategory list
- Build the series list
- Browse to each series and scrape each publication in detail, clicking through tabs

This method has several downsides:
- After refreshing the url and wiping state, up to 250 publications have to be scraped in the largest categories, leaving plenty of opportunity for jQuery state to go sideways

# Search Method

This scrape method bypasses edge cases with hover links, by searching for each pub and clicking the (hopefully) single hover link that results.  We inherit Series Code from the series list scrape, so we no longer need to build series state by clicking into each series. The scrape looks like this:

- Build the category list
- Build the subcategory list
- Build the series list
- Browse to each series and scrape the title of each publication only, clicking hrough tabs
- Search for each publication, and scrape all metadata

This method has several benefits:
- Once we have a list of publications (thousands), we can run the larger scrape in parallel (running previous steps in parallel might save a few minutes, but not hours)
- We can erase state by reloading the base url in between each search
- Fewer edge cases and handling exceptions, which slows the traditional method down significantly

## TODO
- [x] Feature: strip quotes, double whitespace etc from Product Titles
- [x] Bug: still writing empty details to detailslist
- [x] Bug: inheriting last serieslist codes for all details
- [ ] Finish get-document module
- [ ] Finish document network module
- [ ] Package into containers for parallel deployment of multiple scrapers
- [ ] Add UML diagram