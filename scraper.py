import re
import json
import urllib.parse
from time import sleep

import httpx
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
                with Client(headers=headers, timeout=15) as client:
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

    def get_images(self, listing_key, xawc):
        images_url = 'https://www.apartments.com/services/property/mediagallery/render'

        json_payload = {"ListingKey":f"{listing_key}","HasViewFromUnit": False,"UnitNumber":""}

        with Client() as client:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
                'Content-Type': 'application/json',
                'X_AWC_TOKEN': xawc
            }
            response = client.post(headers=headers, url=images_url, json=json_payload)

        if response.status_code != 200:
            response.raise_for_status()

        return response.json()

    def parse_data(self, detail_htmls):
        for html in detail_htmls[1:2]:
            listing = {'id': '', 'name': '', 'url': '', 'phone': '', 'city': '', 'state': '', 'zip': '',
                       'address': '', 'country': '', 'DMA': '', 'latitude': '', 'longitude': ''}
            unit = {'id': '', 'key': '', }
            image = {'id': '', 'key': '', 'url': ''}
            tree = HTMLParser(html)
            # print(tree.html)
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
                    parsed_data = json.loads(json_data)
                    pretified_json = json.dumps(parsed_data, indent=2)
                    # print(pretified_json)
                    break

            listing['id'] = parsed_data['listingId']
            listing['name'] = parsed_data['listingName']
            listing['url'] = tree.css_first('div.header-switch-language-wrapper.mortar-wrapper > a').attributes.get('href', '')
            listing['phone'] = parsed_data['phoneNumber']
            listing['city'] = parsed_data['listingCity']
            listing['state'] = parsed_data['listingState']
            listing['zip'] = parsed_data['listingZip']
            listing['address'] = parsed_data['listingAddress']
            listing['country'] = parsed_data['listingCountry']
            listing['DMA'] = parsed_data['listingDMA']
            listing['latitude'] = parsed_data['location']['latitude']
            listing['longitude'] = parsed_data['location']['longitude']
            print(listing)

            rentals = parsed_data['rentals']
            for rental in rentals:
                unit['id'] = listing['id']
                unit['key'] = rental['RentalKey']
                try:
                    unit['number'] = rental['UnitNumber']
                except:
                    unit['number'] = ''
                unit['name'] = rental['Name']
                print(unit)

            for script in scripts:
                if 'antiWebCrawlerToken' in script.text(strip=True):
                    raw_data = script.text()
                    pattern = r'antiWebCrawlerToken:\s*\'([^\']*?)\''
                    match = re.search(pattern=pattern, string=raw_data)
                    xawc = match.group(1)
                    break

            json_images = self.get_images(listing_key=listing['id'], xawc=xawc)
            # print(json_images)

            image_tree = HTMLParser(json_images['Photos'])
            images = []
            images_element = image_tree.css('li')
            # print(len(images_element))
            for item in images_element:
                image['id'] = parsed_data['listingId']
                image['key'] = item.attributes.get('id')
                image['url'] = item.css_first('div.lazy.backgroundImageWrapper').attributes.get('data-img-src')
                images.append(image.copy())

            print(images)

    def main(self):
        loc = 'tucson-az'
        htmls = asyncio.run(self.get_links(loc=loc))
        links = self.parse_links(htmls)
        detail_htmls = asyncio.run(self.get_detail_htmls(links))
        self.parse_data(detail_htmls)

if __name__ == '__main__':
    scraper = ApartmentScraper()
    scraper.main()