import requests
import argparse
import unicodedata
import codecs
from pathlib import Path
from bs4 import BeautifulSoup
from typing import Callable, Sequence, List, Mapping, Tuple, Optional
import re
from time import sleep
from random import randint
from common import utils, Card


def parse_cmdline_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('in_file', metavar='INFILE', type=Path,
                        help="input file (should contain one https://www.pealim.com/ URL per line)")
    parser.add_argument('out_file', metavar='OUTFILE', type=Path,
                        help="output file (ready to be imported into an Anki deck)")
    parser.add_argument('-t', dest='tags', metavar='TAGS', default=None, type=str,
                        help="add the specified tag(s) to all cards")
    return parser.parse_args()


def remove_niqqudot(word: str) -> str:
    return ''.join([c for c in word if unicodedata.category(c)[0] != 'M'])


Handler = Callable[[BeautifulSoup, str], Sequence[Card]]


def handle_id_list(soup: BeautifulSoup, url: str, ids: Mapping[str, str]) -> Sequence[Card]:
    cards: List[Card] = list()
    ids_found: List[str] = list()
    ids_not_found: List[str] = list()
    for i, flags in ids.items():
        tag = soup.find(id=i)
        if tag is not None:
            word = tag.find(attrs={"class": "menukad"})
            translation = tag.find(attrs={"class": "meaning"})
            pronunciation = tag.find(attrs={"class": "transcription"})
            if word is not None or translation is not None or pronunciation is not None:
                cards.append(Card(word=str(word).strip() if word is not None else '',
                                  translation=str(translation).strip() if translation is not None else '',
                                  pronunciation=str(pronunciation).strip() if pronunciation is not None else '',
                                  source=url + '#' + i, flags=flags))
                ids_found.append(i)
                continue
        ids_not_found.append(i)
    # if len(ids_found) > 0:
    #    print('Found: ' + ', '.join(ids_found))
    if len(ids_not_found) > 0:
        print('Not found: ' + ', '.join(ids_not_found))
    return cards


def handle_verb(soup: BeautifulSoup, url: str) -> Sequence[Card]:
    return handle_id_list(soup, url, ids={
        'INF-L': 'VI',
        'AP-ms': 'VPms', 'AP-fs': 'VPms', 'AP-mp': 'VPms', 'AP-fp': 'VPms',
        'PERF-1s': 'VS1s', 'PERF-1p': 'VS1p',
        'PERF-2ms': 'VS2ms', 'PERF-2fs': 'VS2fs', 'PERF-2mp': 'VS2mp', 'PERF-2fp': 'VS2fp',
        'PERF-3ms': 'VS3ms', 'PERF-3fs': 'VS3ms', 'PERF-3p': 'VS3p',
        'IMPF-1s': 'VF1s', 'IMPF-1p': 'VF1p',
        'IMPF-2ms': 'VF2ms', 'IMPF-2fs': 'VF2fs', 'IMPF-2mp': 'VF2mp', 'IMPF-2fp': 'VF2fp',
        'IMPF-3ms': 'VF3ms', 'IMPF-3fs': 'VF3fs', 'IMPF-3mp': 'VF3mp', 'IMPF-3fp': 'VF3fp',
        'IMP-2ms': 'V!ms', 'IMP-2fs': 'V!fs', 'IMP-2mp': 'V!mp', 'IMP-2fp': 'V!fp'
    })


def handle_noun(soup: BeautifulSoup, url: str) -> Sequence[Card]:
    return handle_id_list(soup, url, ids={
        's': 'Nsa', 'p': 'Npa', 'sc': 'Nsc', 'pc': 'Npc'
    })


def handle_adjective(soup: BeautifulSoup, url: str) -> Sequence[Card]:
    return handle_id_list(soup, url, ids={
        'ms-a': 'Ams', 'fs-a': 'Afs', 'mp-a': 'Amp', 'fp-a': 'Afp'
    })


handler_map: Sequence[Tuple[re.Pattern, Handler]] = [(re.compile(mask, flags=re.I), handler) for (mask, handler) in [
    (r'\s*Verb\s', handle_verb),
    (r'\s*Noun\s', handle_noun),
    (r'\s*Adjective\s', handle_adjective),
    (r'\s*Глагол\s', handle_verb),
    (r'\s*Существительное\s', handle_noun),
    (r'\s*Прилагательное\s', handle_adjective),
]]


def get_handler_by_description(description: str) -> Optional[Handler]:
    for (pattern, handler) in handler_map:
        if pattern.search(description):
            return handler
    return None


def process_url(session: requests.Session, url: str, additional_tags: str) -> Sequence[Card]:
    page = session.get(url)
    soup = BeautifulSoup(page.content, "html.parser")
    descriptions = soup.find_all('meta', attrs={'name': 'description'})
    if len(descriptions) > 0:
        for description in descriptions:
            if 'content' in description.attrs:
                handler = get_handler_by_description(description.attrs['content'])
                if handler is not None:
                    return [card.append_tags(additional_tags) for card in handler(soup, url)]
                else:
                    print(f"No handler found for {url}")
    return list()


def main() -> None:
    args = parse_cmdline_args()

    additional_tags = ''
    if args.tags is not None:
        additional_tags = utils.cleanup(args.tags)

    urls: List[str] = list()
    print(f"reading URLs from {str(args.in_file)}")
    with codecs.open(args.in_file, 'r', encoding='utf_8') as fh_in:
        urls += [url.strip() for url in fh_in if len(url.strip()) > 0]
    print(f"{len(urls)} URLs read")
    if len(urls) < 1:
        return

    all_cards: List[Card] = list()
    session = requests.Session()
    for url in urls:
        seconds = randint(1, 5)
        print(f"sleeping {seconds}s before reading {url}")
        sleep(seconds)
        cards = process_url(session, url, additional_tags)
        print(f"{len(cards)} cards extracted")
        all_cards += cards
    print(f"{len(all_cards)} total cards extracted")
    if len(all_cards) < 1:
        return

    print(f"writing cards to {str(args.out_file)}")
    with codecs.open(args.out_file, 'w', encoding='utf_8') as fh_out:
        Card.save_header(fh_out)
        for card in all_cards:
            card.save(fh_out)

    print('all done!')


if __name__ == "__main__":
    main()
