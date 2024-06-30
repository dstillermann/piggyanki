from requests import Session, RequestException
from copy import copy
import argparse
import codecs
from pathlib import Path
from bs4 import BeautifulSoup, PageElement
from typing import Callable, List, Dict, Tuple, Optional
import re
from time import sleep
from random import randint
from common import utils, Card


def parse_flags(s: str) -> List[str]:
    result: List[str] = list()
    for field in utils.cleanup(s).split(sep=','):
        flags = utils.cleanup(field)
        if len(flags) > 0:
            result.append(flags)
    return result


def parse_cmdline_args():
    format_description = '''

#Source file format

Source text file should contain one https://www.pealim.com/ URL per line, 
optionally followed by one or two of the following flags:

-x/--exclude FLAGS\texclude cards with these flags
-i/--include FLAGS\tinclude cards with these flags

Inclusion has priority.

        ''' + utils.flags_help_text()

    parser = argparse.ArgumentParser(epilog=format_description, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('in_file', metavar='INFILE', type=Path,
                        help="input file (see below)")
    parser.add_argument('out_file', metavar='OUTFILE', type=Path,
                        help="output file (ready to be imported into an Anki deck)")
    parser.add_argument('-t', '--tags', dest='tags', metavar='TAGS', default=None, type=str,
                        help="add the specified tag(s) to all cards")
    parser.add_argument('-i', '--include', dest='include_flags', metavar='FLAGS',
                        default=list(), type=parse_flags,
                        help="include cards with the specified flags (comma-separated list)")
    parser.add_argument('-x', '--exclude', dest='exclude_flags', metavar='FLAGS',
                        default=list(), type=parse_flags,
                        help="exclude cards with the specified flags (comma-separated list)")
    return parser.parse_args()


Handler = Callable[[BeautifulSoup, str], List[Card]]


def handle_id_list(soup: BeautifulSoup, url: str, ids: Dict[str, str]) -> List[Card]:
    cards: List[Card] = list()
    entries_not_found: List[str] = list()
    for i, flags in ids.items():
        e_root = soup.find(id=i)
        if e_root is not None:
            e_word = e_root.find('span', attrs={"class": "menukad"})
            e_translation = e_root.find(attrs={"class": "meaning"})
            e_pronunciation = e_root.find(attrs={"class": "transcription"})
            n_found_elements = len([e for e in [e_word, e_translation, e_pronunciation] if e is not None])
            if n_found_elements > 1:
                cards.append(Card(word=str(e_word).strip() if e_word is not None else '',
                                  translation=str(e_translation).strip() if e_translation is not None else '',
                                  pronunciation=str(e_pronunciation).strip() if e_pronunciation is not None else '',
                                  source=url, flags=flags))
                continue
        entries_not_found.append(flags)
    if len(entries_not_found) > 0:
        print('Not found: ' + ', '.join(entries_not_found))
    return cards


def handle_verb(soup: BeautifulSoup, url: str) -> List[Card]:
    return handle_id_list(soup, url, ids={
        'INF-L': 'VI',
        'AP-ms': 'VPms', 'AP-fs': 'VPfs', 'AP-mp': 'VPms', 'AP-fp': 'VPfs',
        'PERF-1s': 'VS1s', 'PERF-1p': 'VS1p',
        'PERF-2ms': 'VS2ms', 'PERF-2fs': 'VS2fs', 'PERF-2mp': 'VS2mp', 'PERF-2fp': 'VS2fp',
        'PERF-3ms': 'VS3ms', 'PERF-3fs': 'VS3ms', 'PERF-3p': 'VS3p',
        'IMPF-1s': 'VF1s', 'IMPF-1p': 'VF1p',
        'IMPF-2ms': 'VF2ms', 'IMPF-2fs': 'VF2fs', 'IMPF-2mp': 'VF2mp', 'IMPF-2fp': 'VF2fp',
        'IMPF-3ms': 'VF3ms', 'IMPF-3fs': 'VF3fs', 'IMPF-3mp': 'VF3mp', 'IMPF-3fp': 'VF3fp',
        'IMP-2ms': 'V!ms', 'IMP-2fs': 'V!fs', 'IMP-2mp': 'V!mp', 'IMP-2fp': 'V!fp'
    })


def handle_noun(soup: BeautifulSoup, url: str) -> List[Card]:
    return handle_id_list(soup, url, ids={
        's': 'Nsa', 'p': 'Npa', 'sc': 'Nsc', 'pc': 'Npc'
    })


def handle_adjective(soup: BeautifulSoup, url: str) -> List[Card]:
    return handle_id_list(soup, url, ids={
        'ms-a': 'Ams', 'fs-a': 'Afs', 'mp-a': 'Amp', 'fp-a': 'Afp'
    })


def handle_adverb(soup: BeautifulSoup, url: str) -> List[Card]:
    cards: List[Card] = list()
    e_translation_headers: List[PageElement] = list()
    for text in ['Meaning', 'Перевод']:
        e_translation_headers += soup.find_all('h3', string=text)
    for e_translation_header in e_translation_headers:
        e_translation = e_translation_header.next_sibling
        e_root = e_translation_header.parent
        e_word = e_root.find('span', attrs={"class": "menukad"})
        e_pronunciation = e_root.find(attrs={"class": "transcription"})
        n_found_elements = len([e for e in [e_word, e_translation, e_pronunciation] if e is not None])
        if n_found_elements > 1:
            cards.append(Card(word=str(e_word).strip() if e_word is not None else '',
                              translation=str(e_translation_header).strip() if e_translation_header is not None else '',
                              pronunciation=str(e_pronunciation).strip() if e_pronunciation is not None else '',
                              source=url, flags='B'))
    return cards


handler_map: List[Tuple[re.Pattern, Handler]] = [(re.compile(mask, flags=re.I), handler) for (mask, handler) in [
    (r'^\s*Verb\s', handle_verb),
    (r'^\s*Noun\s', handle_noun),
    (r'^\s*Adjective\s', handle_adjective),
    (r'^\s*Adverb\s', handle_adverb),
    (r'^\s*Глагол\s', handle_verb),
    (r'^\s*Существительное\s', handle_noun),
    (r'^\s*Прилагательное\s', handle_adjective),
    (r'^\s*Наречие\s', handle_adverb)
]]


def get_handler_by_description(description: str) -> Optional[Handler]:
    for (pattern, handler) in handler_map:
        if pattern.search(description):
            return handler
    return None


def process_url(session: Session, url: str, *,
                additional_tags: str) -> List[Card]:
    try:
        page = session.get(url)
    except RequestException as e:
        print(f"Error reading {url}: {str(e)}")
        return list()
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


def build_file_line_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='*', exit_on_error=False, add_help=False)
    parser.add_argument('-i', '--include', dest='include_flags',
                        default=list(), type=parse_flags)
    parser.add_argument('-x', '--exclude', dest='exclude_flags',
                        default=list(), type=parse_flags)
    return parser


def process_file(in_file: Path, session: Session, *, additional_tags: str,
                 global_include_flags: List[str],
                 global_exclude_flags: List[str]) -> List[Card]:
    parser = build_file_line_parser()
    all_cards: List[Card] = list()
    with codecs.open(str(in_file), 'r', encoding='utf_8') as fh_in:
        for line in fh_in:
            try:
                args = line.split()
                if len(args) < 1:
                    continue
                url = args[0]
                include_flags = copy(global_include_flags)
                exclude_flags = copy(global_exclude_flags)
                if len(args) > 1:
                    parsed_options, _ = parser.parse_known_args(args=args[1:])
                    include_flags += parsed_options.include_flags
                    exclude_flags += parsed_options.exclude_flags
                seconds = randint(1, 5)
                print(f"sleeping {seconds}s before reading {url}")
                sleep(seconds)
                cards = process_url(session, url, additional_tags=additional_tags)
                print(f"{len(cards)} cards loaded from {url}")
                cards_to_add: List[Card] = list()
                for card in cards:
                    if card.should_be_saved(include_flags=include_flags, exclude_flags=exclude_flags):
                        cards_to_add.append(card)
                print(f"{len(cards_to_add)} cards added")
                all_cards += cards_to_add
            except argparse.ArgumentError:
                pass
    return all_cards


def main() -> None:
    args = parse_cmdline_args()

    session = Session()

    print(f"reading URLs from {str(args.in_file)}")
    all_cards = process_file(args.in_file, session,
                             additional_tags=utils.cleanup(args.tags),
                             global_include_flags=args.include_flags,
                             global_exclude_flags=args.exclude_flags)
    print(f"{len(all_cards)} total cards loaded")

    if len(all_cards) > 0:
        print(f"writing cards to {str(args.out_file)}")
        with codecs.open(args.out_file, 'w', encoding='utf_8') as fh_out:
            Card.save_header(fh_out)
            for card in all_cards:
                card.save(fh_out)
    else:
        print('No cards loaded, nothing to write!')

    print('all done!')


if __name__ == "__main__":
    main()
