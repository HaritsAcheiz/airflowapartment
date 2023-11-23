import re
import json
import urllib.parse
from httpx import Client, AsyncClient
from selectolax.parser import HTMLParser
from dataclasses import dataclass
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
        # urls = [urllib.parse.urljoin(url, str(page) + '/') for page in range(page_range+1) if page > 0]
        urls = [urllib.parse.urljoin(url, str(page) + '/') for page in range(2) if page > 0]
        tasks = []
        print(urls)
        for url in urls:
            task = asyncio.create_task(self.fetch(url))
            tasks.append(task)

        htmls = await asyncio.gather(*tasks)
        return htmls

    def parse_links(self, htmls):
        all_links = []
        for html in htmls:
            tree = HTMLParser(html)
            json_data = json.loads(tree.css_first('script[type="application/ld+json"]').text(strip=True))
            # pretified_data = json.dumps(json_data, indent=2)
            links = []
            for data in json_data['about']:
                links.append(data['url'])
            all_links.extend(links)

        return all_links

    async def get_detail_htmls(self, links):
        tasks = []
        for link in links:
            task = asyncio.create_task(self.fetch(link))
            tasks.append(task)

        detail_htmls = await asyncio.gather(*tasks)
        return detail_htmls

    def parse_data(self, detail_htmls):
        for html in detail_htmls[1:2]:
            print(html)
            listing = {'id': None, 'url': None, }
            tree = HTMLParser(html)
            scripts = tree.css('script')
            for script in scripts:
                if 'ProfileStartup' in script.text(strip=True):
                    raw_data = script.text()
                    pattern = r'startup\.init\(({.*?})\);'
                    match = re.search(pattern=pattern, string=raw_data, flags=re.DOTALL)
                    sub_pattern = r'(\w+): '
                    cleared_data = re.sub(sub_pattern, r'"\1": ', match.group(1).replace("'", '"').replace("geo:", "geo: ").replace("isMF:", "isMF: "))
                    pattern = r',\s*}'
                    json_data = re.sub(pattern, '}', cleared_data)
                    print(json_data)
                    parsed_data = json.loads(json_data)
                    pretified_json = json.dumps(parsed_data, indent=2)
                    print(pretified_json)
                    break

            # json_data = json.loads(tree.css_first('script[type="application/ld+json"]').text(strip=True))
            # pretified_json = json.dumps(json_data, indent=2)
            # print(pretified_json)


    def main(self):
        loc = 'tucson-az'
        htmls = asyncio.run(self.get_links(loc=loc))
        links = self.parse_links(htmls)
        detail_htmls = asyncio.run(self.get_detail_htmls(links))
        self.parse_data(detail_htmls)

if __name__ == '__main__':
    scraper = ApartmentScraper()
    scraper.main()