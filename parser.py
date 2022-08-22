import math
import os
import signal
import argparse
import enum
import re
import sys
from bs4 import BeautifulSoup
import requests
from progress.bar import FillingSquaresBar


class Target(enum.Enum):
    artist = 0
    album = 1
    song = 2
    artist_album = 2


class Parser:
    def __init__(self) -> None:
        self.HOST = 'https://musify.club'
        self.page = None
        self.directory = os.getcwd()
        self.message = ''
        self.count = -1

    def download_song(self, url: str, filename: str):
        response = requests.get(url, allow_redirects=False)
        location = response.headers['Location']
        response = requests.get(location, stream=True)
        base = os.path.basename(filename)
        bar = FillingSquaresBar(max=int(response.headers['Content-Length']))
        bar.message = ''
        bar.suffix += ' ' + base
        with open(filename, 'ba') as file:
            for chunk in response.iter_content(1024):
                bar.index += len(chunk)
                file.write(chunk)
                bar.next()
        bar.finish()

    def parse_page(self, page: str, save_path: str):
        while page and self.count:
            response = requests.get(page)
            soup = BeautifulSoup(response.text, 'html.parser')
            for playlist_item in soup.find_all('div', class_='playlist__item'):
                if not playlist_item.find('span', string='Недоступен'):
                    audio = playlist_item.find(
                        'a', attrs={'itemprop': 'audio'})
                    filename = save_path + os.path.sep + \
                        re.sub(r'[\/*?<>"]', '-', audio['download'])
                    self.download_song(self.HOST + audio['href'], filename)
                    self.count -= 1
                    if not self.count:
                        return
            page = soup.find('li', 'pagination-next')
            if page:
                page = page.a['href']
                page = page and (self.HOST + page)

    def find(self, target: Target, search_text: str, error_msg: str):
        response = requests.get(self.HOST + '/search?searchText=' +
                                search_text)
        soup = BeautifulSoup(response.text, 'html.parser')
        page = None
        if target == Target.artist_album:
            disintegration = search_text.split()
            artist, album = disintegration[0], ' '.join(disintegration[1:])
            target_text = soup.find('a', id='albums')
            if target_text:
                album = soup.find('a', attrs={'title': album.title()})
                artist_text = album.find('small').text.strip()
                if album and (artist == artist_text):
                    page = self.HOST + album['href']
                    self.message = 'Скачивание альбома ' + album['title']
        elif target == Target.artist or target == Target.album:
            if target == Target.artist:
                target_text = soup.find('a', id='artists')
                self.message = 'Скачивание песен исполнителя ' + search_text
            else:
                target_text = soup.find('a', id='album')
                self.message = 'Скачивание альбома ' + search_text
            if target_text:
                result = target_text.find_next(
                    'a', attrs={'title': search_text.title()})
                if result:
                    page = self.HOST + result['href']
        if not page:
            print(error_msg)
            return
        self.page = page

    def run(self):
        signal.signal(signal.SIGINT, self.exit_handler)
        arg_parser = argparse.ArgumentParser()
        arg_parser.add_argument(
            '-p', '--page', dest='page', help='страница скачивания')
        arg_parser.add_argument(
            '-a', '--artist', dest='artist', help='исполнитель')
        arg_parser.add_argument(
            '-r', '--release', dest='release', help='альбом')
        arg_parser.add_argument(
            '-c', '--count', dest='count', type=int, help='количество скачиваемых песен')
        arg_parser.add_argument('-d', '--directory',
                                dest='directory', help='директория сохранения')

        args = arg_parser.parse_args()
        if args.page:
            self.page = args.page
        if args.artist and args.release:
            self.find(Target.artist_album, args.artist + ' ' +
                      args.release, '[!!!] Альбом указанного артиста не найден')
        elif args.artist:
            self.find(Target.artist, args.artist,
                      '[!!!] Исполнитель не найден')
        elif args.release:
            self.find(Target.album, args.release, '[!!!] Альбом не найден')

        if args.directory:
            self.directory = args.directory
        if args.count:
            self.count = abs(args.count)

        if self.page:
            print(self.message)
            self.parse_page(self.page, self.directory)

    def exit_handler(sig, frame):
        print('\nЗавершение работы парсера...')
        sys.exit(0)


if __name__ == '__main__':
    parser = Parser()
    parser.run()
