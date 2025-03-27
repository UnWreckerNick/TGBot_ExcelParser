import re

import httpx
from lxml import html
from sqlalchemy import select

from app.database import get_session
from app.models import ExcelData


# Паттерн ищет в строке последовательности символов, состоящие только из цифр, возможно разделенные точкой, запятой или пробелом
PRICE_PATTERN = re.compile(r"[\d\s,.]+")

async def fetch_price(url: str, xpath: str) -> float | None:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=30)
            if response.status_code != 200:
                print(f"Ошибка {response.status_code} при запросе {url}")
                return None

        tree = html.fromstring(response.text)
        prices = tree.xpath(xpath)

        if not prices:
            print(f"XPath {xpath} не дал результатов для {url}")
            return None

        price_text = prices[0]
        if isinstance(price_text, html.HtmlElement):
            price_text = price_text.text

        if not price_text:
            print(f"Не удалось получить текст цены для {url}")
            return None

        price_text = price_text.replace(" ", "").replace(",", ".")
        price_match = PRICE_PATTERN.search(price_text)

        return float(price_match.group()) if price_match else None

    except httpx.RequestError as e:
        print(f"Ошибка запроса {url}: {e}")
        return None
    except Exception as e:
        print(f"Ошибка обработки данных с {url}: {e}")
        return None

async def parse_prices():
    async with get_session() as session:
        result = await session.execute(select(ExcelData))
        sites = result.scalars().all()

    site_prices = {}

    for site in sites:
        price = await fetch_price(site.url, site.xpath)
        if price is not None:
            if site.url not in site_prices:
                site_prices[site.url] = []
            site_prices[site.url].append(price)

    avg_prices = {url: sum(prices) / len(prices) for url, prices in site_prices.items() if prices}
    return avg_prices