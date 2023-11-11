import urllib.parse
from httpx import Client, AsyncClient
from selectolax.parser import HTMLParser
from dataclasses import dataclass
import re
import asyncio

@dataclass
class ApartmentScraper:
    base_url: str = 'https://www.apartments.com/'
    user_agent: str = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'

    async def fetch(self, url):
        headers = {
            'user-agent': self.user_agent
        }

        async with AsyncClient(headers=headers) as aclient:
            response = await aclient.get(url)
            if response.status_code != 200:
                response.raise_for_status()

            return response.text

    def get_page_range(self, url):
        print('Getting page range')

        # fetcher
        headers = {
            'user-agent': self.user_agent
        }
        retry = 0
        while retry < 3:
            try:
                with Client(headers=headers) as client:
                    response = client.get(url)
                if response.status_code != 200:
                    response.raise_for_status()
                else:
                    break
            except Exception as e:
                print(f'{retry} retry due to {e}!')
                retry += 1

        # parser
        tree = HTMLParser(response.text)
        page_range = int(tree.css_first('span.pageRange').text().rsplit(maxsplit=1)[1])

        return page_range

    async def get_links(self, loc):
        url = urllib.parse.urljoin(self.base_url, loc + '/')
        page_range = self.get_page_range(url)
        urls = [urllib.parse.urljoin(url, str(page) + '/') for page in range(page_range+1) if page > 0]
        tasks = []
        for i, url in enumerate(urls):
            task = asyncio.create_task(self.fetch(url))
            tasks.append(task)

        htmls = await asyncio.gather(*tasks)
        return htmls

    def main(self):
        loc = 'tucson-az'
        results = asyncio.run(self.get_links(loc=loc))
        print(results[0])

if __name__ == '__main__':
    scraper = ApartmentScraper()
    scraper.main()