import codecs
import pandas as pd
import argparse
from pathlib import Path
from typing import List, Sequence
from common import utils, Card


def _parse_cmdline_args():
    format_description = '''
    
# Source Excel/CSV file columns:

- Word
- Translation
- Pronunciation
- Flags

    ''' + utils.flags_help_text()

    parser = argparse.ArgumentParser(epilog=format_description, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('in_file', metavar='INFILE', type=Path,
                        help="input file (see description below)")
    parser.add_argument('out_file', metavar='OUTFILE', type=Path,
                        help="output file (ready to be imported into an Anki deck)")
    parser.add_argument('-t', dest='tags', metavar='TAGS', default=None, type=str,
                        help="add the specified tag(s) to all cards")
    return parser.parse_args()


def read_source_file(path: Path, additional_tags: str) -> Sequence[Card]:
    cards: List[Card] = list()

    if path.suffix.lower() == '.csv':
        df = pd.read_csv(str(path))
    elif path.suffix.lower() in ['.xlsx', '.xls']:
        df = pd.read_excel(str(path))
    else:
        print(f"{str(path)}: unsupported extension")
        return cards

    core_columns = ['Word', 'Translation', 'Pronunciation']
    core_columns_count = len([c for c in df.columns if c in core_columns])
    if core_columns_count < 2:
        print(f"{str(path)}: at least two columns must be present: {','.join(core_columns)}")
        return cards

    def _field_to_str(row: pd.Series, col: str) -> str:
        if col in row.index:
            return str(row[col])
        else:
            return ''

    for i in range(df.index.size):
        r = df.iloc[i]
        cards.append(Card(word=_field_to_str(r, 'Word'),
                          translation=_field_to_str(r, 'Translation'),
                          pronunciation=_field_to_str(r, 'Pronunciation'),
                          flags=_field_to_str(r, 'Flags'),
                          tags=_field_to_str(r, 'Tags') + ' ' + additional_tags,
                          source=f"{path.name}#{i}"
                          ))

    return cards


def field_to_str(val) -> str:
    if pd.isna(val):
        return ''
    else:
        return str(val).strip()


def main():
    args = _parse_cmdline_args()

    additional_tags = ''
    if args.tags is not None:
        additional_tags = utils.cleanup(args.tags)

    print(f"reading file {str(args.in_file)}")
    all_cards = read_source_file(args.in_file, additional_tags)
    print(f"{len(all_cards)} total cards read")
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
