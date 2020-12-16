"""Данный скрипт предназначен для выгрузки информации о товарах заданной
категории с сайта https://www.lamoda.ru. Сохраняются почти все характеристики
товара вместе с его основным изображением.

При запуске скрипта следует ввести адрес первой страницы категории товаров, и
дальнейший процесс автоматически получит доступ остальным страницам, обработав
таким образом все товары в категории.

Результат работы с характеристиками товаров будет сохранён в файл .csv, а
скачанные изображения - в отдельную папку img.
"""
import os
import os.path
import re
import csv
import sys
import time

import requests
from bs4 import BeautifulSoup

# Время ожидания ответа от веб-сервера (секунды)
TIMEOUT = 5

# Число попыток выполнить http-запрос при возникновении сбоя
MAX_RETRIES = 3

# Задержка после выполнения http-запроса (секунды)
SLEEP_TIME = 1

# Адрес страницы категории товаров по умолчанию
DEFAULT_URL = 'https://www.lamoda.ru/c/5374/accs_ns-elektrchasymuj/'

# Адрес интернет-магазина
HOST = 'https://www.lamoda.ru'

# URL субдомена, где хранятся изображения товаров на сервере
IMAGE_HOST = 'https://a.lmcdn.ru/img600x866'

# Заголовки http-запроса
HEADERS = {
    'user-agent': ('Mozilla/5.0 (Windows NT 6.1; rv:82.0) Gecko/20100101 '
                   'Firefox/82.0'),
    'accept': '*/*',
}

# Имя файла по умолчанию для сохранения полученных данных
DEFAULT_FILENAME = 'lamoda.csv'

# Имя каталога для сохранения полученных изображений товаров
IMAGE_DIR = 'img'

# Регулярные выражения, используемые в парсинге сайта
PAGE_RE = re.compile(r'pagination:\{current:(\d+),total:(\d+),')
IMAGE_RE = re.compile(r'\["([^"]+)"')

# Получить ответ сервера при GET-запросе
def get_response(url: str, params: dict=None) -> requests.Response:
    for attempt in range(0, MAX_RETRIES):
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT,
                             params=params)
        except requests.exceptions.RequestException:
            time.sleep(SLEEP_TIME)
        else:
            time.sleep(SLEEP_TIME)
            return r

    return False

# Получить текст html-страницы
def get_html(url: str) -> str:
    r = get_response(url)

    if not r:
        print('Ошибка: не удалось выполнить http-запрос.\n')
        return False

    if r.status_code != requests.codes.ok:
        print(f'Ошибка {r.status_code} при обращении к web-странице.\n')
        return False

    return r.text

# Сохранить в файл изображение по адресу URL
def save_image(url: str, filename: str) -> bool:
    r = get_response(url)

    if not r:
        print('Ошибка: не удалось выполнить http-запрос '
              'для получения изображения.\n'
              'Ссылка на изображение: ' + url)
        return False

    if r.status_code != requests.codes.ok:
        print(f'Ошибка {r.status_code} при обращении файлу изображения.\n'
              'Ссылка на изображение: ' + url)
        return False

    try:
        with open(filename, 'wb') as f:
            f.write(r.content)
    except OSError:
        print('Ошибка: не удалось сохранить изображение.')
        return False
    else:
        return True

# Получить URL следующей страницы категории товаров
def get_next_page(html: str, base_url: str) -> str:
    """Входные параметры:
    html: str - текст исходной html-страницы;
    base_url: str - базовый URL страницы категории товаров, к которому будет
    присоединён параметр с номером следующей страницы.
    """
    search_results = re.findall(PAGE_RE, ''.join(html.split()))
    if search_results:
        current = int(search_results[0][0])
        total = int(search_results[0][1])
        if current < total:
            print(f'Обрабатывается страница {current + 1} из {total}...')
            if '?' in base_url:
                return f'{base_url}&page={current + 1}'
            else:
                return f'{base_url}?page={current + 1}'
        else:
            return False
    else:
        return False

# Получить адреса страниц всех товаров для заданной страницы категории
def get_item_urls(html: str) -> list:
    """Входные параметры:
    html: str - текст html-страницы категории товаров.
    """
    soup = BeautifulSoup(html, 'html.parser')
    items = soup.find_all('a', class_='products-list-item__link link')
    return [HOST + item.get('href') for item in items]

# Заменить все пробельные символы и их повторы на обычный пробел
def clean_text(text: str) -> str:
    return ' '.join(text.split())

# Получить информацию о товаре по адресу его страницы, сохранив также
# соответствующее ему изображение в файле
def get_item(item_url: str) -> dict:
    html = get_html(item_url)

    if not html:
        print('Нет доступа к странице товара.\n'
              'Ссылка на страницу: ' + item_url)
        return False

    item = {'url': item_url}
    soup = BeautifulSoup(html, 'html.parser')

    model_name = soup.find('div', class_='product-title__model-name')
    if model_name:
        item['model_name'] = clean_text(model_name.get_text(strip=True))

    brand_name = soup.find('h1', class_='product-title__brand-name')
    if brand_name:
        item['brand_name'] = clean_text(brand_name.get_text(strip=True))

    price_current = soup.find('span', class_='product-prices__price_current')
    if price_current:
        item['price_current'] = price_current.get_text(strip=True)[:-1] + 'RUB'

    description = soup.find('pre', itemprop='description')
    if description:
        item['description'] = clean_text(description.get_text(strip=True))

    attributes = soup.find_all('span', class_='ii-product__attribute-label')
    for attribute in attributes:
        label_text = attribute.get_text(strip=True)
        value_text = clean_text(attribute.next_sibling.get_text(strip=True))

        if label_text == 'Состав:':
            item['compound'] = value_text
        elif label_text == 'Ширина:':
            item['width'] = clean_text(value_text)
        elif label_text == 'Диаметр циферблата:':
            item['diameter'] = clean_text(value_text)
        elif label_text == 'Сезон:':
            item['season'] = value_text
        elif label_text == 'Цвет:':
            item['color'] = value_text
        elif label_text == 'Механизм часов:':
            item['machinery'] = value_text
        elif label_text == 'Водозащита:':
            item['waterproof'] = value_text
        elif label_text == 'Цвет фурнитуры:':
            item['furniture_color'] = value_text
        elif label_text == 'Гарантийный период:':
            item['duration_of_cover'] = value_text
        elif label_text == 'Страна производства:':
            item['country'] = value_text
        elif label_text == 'Артикул':
            item['marking'] = value_text

    image = soup.find('d-gallery-widget')
    if image:
        search_results = re.findall(IMAGE_RE, image.get(':gallery') or '')
        if search_results:
            image_url = IMAGE_HOST + search_results[0]
            image_filename = os.path.join(
                os.getcwd(), IMAGE_DIR, search_results[0].split('/')[-1])
            if save_image(image_url, image_filename):
                item['image'] = 'file:///' + image_filename

    return item

# Обработать полностью всю категорию и возвратить информацию обо всех найденных
# в ней товарах
def get_all_items(category_url: str) -> list:
    """Входные параметры:
    category_url: str - адрес первой страницы категории товаров.
    """
    print('Обрабатывается начальная страница...')
    items = []
    base_url = category_url
    while category_url:
        html = get_html(category_url)
        if not html:
            print('Нет доступа к странице со списком товаров.\n'
                  'Ссылка на страницу: ' + category_url)
            return items

        for item_url in get_item_urls(html):
            item = get_item(item_url)
            if item:
                items.append(item)

        category_url = get_next_page(html, base_url)

    print(f'Итого товаров получено: {len(items)}')
    return items

# Сохранить в csv-файл информацию о товарах, полученную ранее с помощью
# функции get_all_items(). Изображения при этом уже не сохраняются, т.к. при
# штатной работе они должны быть сохранены при вызове упомянутой функции
def save_items(items: str, filename: str) -> bool:
    keys = ['model_name', 'marking', 'url', 'image', 'brand_name',
            'price_current', 'compound', 'width', 'diameter', 'season',
            'color', 'furniture_color', 'machinery', 'waterproof',
            'duration_of_cover', 'country', 'description']

    titles = ['Название модели', 'Артикул', 'Web-страница', 'Изображение',
              'Брэнд', 'Цена', 'Состав', 'Ширина', 'Диаметр циферблата',
              'Сезон', 'Цвет', 'Цвет фурнитуры', 'Механизм часов',
              'Водозащита', 'Гарантийный период', 'Страна производства',
              'Описание']
    try:
        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(titles)
            for item in items:
                writer.writerow([item.get(key, '') for key in keys])
    except OSError:
        print('Ошибка: не удалось записать данные в файл.')
        return False
    else:
        print('Данные успешно записаны.')
        return True

if __name__ == '__main__':
    if not os.path.exists(IMAGE_DIR):
        try:
            os.mkdir(IMAGE_DIR)
        except OSError:
            print ('Не удалось создать директорию с изображениями.\n'
                   'Работа программы завершена.')
            sys.exit()

    print('Введите адрес первой страницы категории товаров\n'
          '(Enter - ввод значения по умолчанию):')
    url = input().strip() or DEFAULT_URL

    print('Процесс сбора данных запущен.\n'
          'Адрес начальной страницы: ' + url)

    items = get_all_items(url)

    if items:
        print('Введите имя файла для сохранения данных\n'
              '(Enter - ввод имени по умолчанию):')
        filename = input().strip() or DEFAULT_FILENAME
        if save_items(items, filename):
            os.startfile(filename)
    else:
        print('Товары не найдены, работа программы завершена.')
