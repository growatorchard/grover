import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

def scrape_website(url):
    """Scrape textual content from a single webpage."""
    try:
        parsed = urlparse(url)
        if not parsed.netloc:
            return "Invalid URL"
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        r_robots = requests.get(robots_url, timeout=5)
        if r_robots.status_code == 200 and "Disallow: /" in r_robots.text:
            return "Website disallows scraping (robots.txt)."
        r_page = requests.get(url, timeout=10)
        if r_page.status_code != 200:
            return f"Failed to retrieve page (HTTP {r_page.status_code})."
        soup = BeautifulSoup(r_page.text, "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = " ".join(soup.stripped_strings)
        return text
    except Exception as e:
        return f"Error scraping site: {e}" 