import unicodedata
from typing import List, Optional, Sequence
import re
from hashlib import sha256
import codecs
import uuid
from bs4 import BeautifulSoup


class utils:

    @staticmethod
    def flags_help_text() -> str:
        return '''
Available flags
---------------

[Gender] m: masculine, f: feminine
[Number] p: plural, s: single
[Person] 1: 1st, 2: 2nd, 3: 3rd
[Tense & other verb-specific] I: infinitive, P: present, S: past, F: future, !: imperative 
[Noun-specific] a: absolute state, c: construct state
[Parts of speech] V: verb, N: noun, A: adjective, B: adverb
[Special handling during manual import] . (dot) - don't remove nekudot
        '''

    @staticmethod
    def annotate_flags(flags: str) -> str:
        annotations: List[str] = []
        # gender
        if 'm' in flags and 'f' in flags:
            pass
        elif 'm' in flags:
            annotations.append('masculine')
        elif 'f' in flags:
            annotations.append('feminine')
        # person
        if '1' in flags and '2' in flags and '3' in flags:
            pass
        elif '1' in flags and '2' in flags:
            annotations.append('1st/2nd person')
        elif '1' in flags and '3' in flags:
            annotations.append('1st/3rd person')
        elif '2' in flags and '3' in flags:
            annotations.append('2nd/3rd person')
        elif '1' in flags:
            annotations.append('1st person')
        elif '2' in flags:
            annotations.append('2nd person')
        elif '3' in flags:
            annotations.append('3rd person')
        # number
        if 's' in flags and 'p' in flags:
            pass
        elif 's' in flags:
            annotations.append('single')
        elif 'p' in flags:
            annotations.append('plural')
        # tense
        if 'I' in flags:
            annotations.append('infinitive')
        elif 'P' in flags:
            annotations.append('present')
        elif 'S' in flags:
            annotations.append('past')
        elif 'F' in flags:
            annotations.append('future')
        # absolute vs construct
        if 'a' in flags and 'c' in flags:
            pass
        elif 'a' in flags:
            annotations.append('absolute')
        elif 'c' in flags:
            annotations.append('construct')
        # put all together
        if len(annotations) > 0:
            return ' '.join(annotations)
        else:
            return ''

    @staticmethod
    def cleanup(s: Optional[str]) -> str:
        if s is not None:
            return s.replace('\t', ' ').strip()
        else:
            return ''

    @staticmethod
    def remove_html(content: str) -> str:
        soup = BeautifulSoup(content, "html.parser")
        return utils.cleanup(str(soup.string))

    @staticmethod
    def remove_nekudot(word: Optional[str], flags: Optional[str] = None) -> str:
        word = utils.remove_html(word)
        # Start by leaving only letters and markings
        word = ''.join([c for c in word if unicodedata.category(c)[0] in ['L', 'M']])
        if flags is not None:
            # If flags explicitly require leaving nekudot in place, do nothing.
            if '.' not in flags:
                naked_word = ''.join([c for c in word if unicodedata.category(c)[0] == 'L'])
                # Now a very Hebrew-specific stuff. For 2nd person past tense verbs,
                # leave the very last marking in place.
                if '2' in flags and 'V' in flags and 'S' in flags:
                    if len(word) > 0:
                        last_char = word[-1]
                        if unicodedata.category(last_char)[0] == 'M':
                            word = naked_word + last_char
                        else:
                            word = naked_word
                # Otherwise, leave only the letters.
                else:
                    word = naked_word
        return word

    @staticmethod
    def dress_word(word: Optional[str], flags: str) -> str:
        word = utils.remove_nekudot(word, flags)
        if len(word) == 0:
            return word
        style = 'font-size:24pt;'
        if 'm' in flags:
            style += 'color:blue;'
        elif 'f' in flags:
            style += 'color:red;'
        return f"<span style=\"{style}\">{word}</span>"

    @staticmethod
    def dress_translation(translation: Optional[str], flags: str) -> str:
        translation = utils.cleanup(translation)
        if len(translation) == 0:
            return translation
        text = f"<span style=\"font-size:18pt;\">{translation}</span>"
        annotation = utils.annotate_flags(flags)
        if len(annotation) > 0:
            text += f"<span style=\"font-size:12pt;\"><br />({annotation})</span>"
        return text

    # noinspection PyUnusedLocal
    @staticmethod
    def dress_pronunciation(pronunciation: Optional[str], flags: str) -> str:
        # replace all commas, so we don't bother about comma-separated CSV
        pronunciation = utils.cleanup(pronunciation)
        if len(pronunciation) == 0:
            return pronunciation
        mo = re.search(r'^([^*]*)\*([^*]+)\*([^*]*)$', pronunciation)
        if mo:
            return (f"<span style=\"font-size:18pt\">{mo[1]}<span style=\"color:red;font-weight:bold;\">{mo[2]}" +
                    f"</span>{mo[3]}</span>")
        else:
            return f"<span style=\"font-size:18pt\">{pronunciation}</span>"


class Card:

    def __init__(self, *,
                 word: Optional[str], translation: Optional[str], pronunciation: Optional[str],
                 flags: Optional[str] = None, tags: Optional[str] = None, source: Optional[str] = None,
                 uuid_prefix: str = 'PGMS'):
        self._word = utils.cleanup(word)
        self._translation = utils.cleanup(translation)
        self._pronunciation = utils.cleanup(pronunciation)
        self._flags = utils.cleanup(flags)
        self._tags = utils.cleanup(tags)
        self._source = utils.cleanup(source)
        self._uuid_prefix = uuid_prefix

    @property
    def word(self) -> str:
        return self._word

    @property
    def translation(self) -> str:
        return self._translation

    @property
    def pronunciation(self) -> str:
        return self._pronunciation

    @property
    def flags(self) -> str:
        return self._flags

    @property
    def tags(self) -> str:
        return self._tags

    def append_tags(self, tags: str) -> "Card":
        self._tags += ' ' + utils.cleanup(tags)
        return self

    def append_flags(self, flags: str) -> "Card":
        self._flags += ' ' + utils.cleanup(flags)
        return self

    def has_all_flags(self, flags: str) -> bool:
        flags = utils.cleanup(flags)
        if len(flags) < 1:
            return False
        for c in flags:
            if c not in self._flags:
                return False
        return True

    def has_some_flags(self, flags: str) -> bool:
        flags = utils.cleanup(flags)
        if len(flags) < 1:
            return False
        for c in flags:
            if c in self._flags:
                return True
        return False

    def has_flags(self, flags: Sequence[str]) -> bool:
        if len(flags) < 1:
            return False
        for f in flags:
            if self.has_all_flags(f):
                return True
        return False

    def should_be_saved(self, include_flags: Sequence[str], exclude_flags: Sequence[str]) -> bool:
        include_given = len(include_flags) > 0
        exclude_given = len(exclude_flags) > 0
        # No restrictions
        if not include_given and not exclude_given:
            return True
        # If only inclusion is specified, only save this card if it has any included flags.
        elif include_given and not exclude_given:
            return self.has_flags(include_flags)
        # If only exclusion is specified, save this card unless it has any excluded flags.
        elif not include_given and exclude_given:
            return not self.has_flags(exclude_flags)
        # Both inclusion and exclusion is specified. Inclusion has priority.
        elif self.has_flags(include_flags):
            return True
        else:
            return not self.has_flags(exclude_flags)

    def calc_uuid_stem(self) -> str:
        rep = utils.remove_nekudot(self._word, self._flags + '.')
        if len(self._source) > 0:
            rep += '|' + self._source
        if len(rep) > 0:
            return sha256(codecs.encode(rep, encoding='utf-8')).hexdigest()
        else:
            return uuid.uuid1().hex

    @staticmethod
    def save_header(fh) -> None:
        fh.write("#html:true\n#separator:tab\n#columns:UUID\tFront\tBack\tTags\n#tags column:4\n")

    def save(self, fh) -> None:
        dressed_word = utils.dress_word(self._word, self._flags)
        dressed_translation = utils.dress_translation(self._translation, self._flags)
        dressed_pronunciation = utils.dress_pronunciation(self._pronunciation, self._flags)
        ask_pronunciation = "<em style=\"font-size:14pt\">Pronounce:</em>"
        ask_translation = "<em style=\"font-size:14pt\">Translate:</em>"
        ask_spelling = "<em style=\"font-size:14pt\">Spell:</em>"

        non_empty_count = len([w for w in [dressed_word, dressed_translation, dressed_pronunciation] if len(w) > 0])
        if non_empty_count == 0:
            return

        uuid_stem = self.calc_uuid_stem()

        if len(dressed_word) > 0 and len(dressed_translation) > 0:
            fh.write(f"{self._uuid_prefix}WT{uuid_stem}\t" +
                     f"{ask_translation}<br /><br />{dressed_word}\t" +
                     f"{ask_translation}<br /><br />{dressed_translation}\t" +
                     self._tags + '\n')
        if len(dressed_word) > 0 and len(dressed_pronunciation) > 0:
            fh.write(f"{self._uuid_prefix}WP{uuid_stem}\t" +
                     f"{ask_pronunciation}<br /><br />{dressed_word}\t" +
                     f"{ask_spelling}<br /><br />{dressed_pronunciation}\t" +
                     self._tags + '\n')
        if len(dressed_pronunciation) > 0 and len(dressed_translation) > 0:
            fh.write(f"{self._uuid_prefix}PT{uuid_stem}\t" +
                     f"{ask_translation}<br /><br />{dressed_pronunciation}\t" +
                     f"{ask_pronunciation}<br /><br />{dressed_translation}\t" +
                     self._tags + '\n')



