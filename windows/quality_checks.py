"""Conservative diagnostics. Flags request review; they are not correctness scores."""
import os,re,unicodedata
from decimal import Decimal
from collections import Counter,OrderedDict
from difflib import SequenceMatcher

def has_repeating_ngrams(text: str) -> bool:
    text=unicodedata.normalize('NFKC',text).casefold()
    units=re.findall(r'\w+|[^\w\s]',text)
    streams=[units,list(re.sub(r'\W','',text))]
    for stream in streams:
        for size in range(1,min(12,len(stream)//3)+1):
            for start in range(len(stream)-size*3+1):
                block=stream[start:start+size]
                if block*3==stream[start:start+size*3] and size*3>=len(stream)*.6:return True
    return False

def sanitize_prompt(candidate_prompt: str, recent_transcripts: list[str]) -> str:
    """Sanitize dynamic context; history must exclude its single source utterance."""
    candidate=' '.join(candidate_prompt.split())[:300]
    normalized=lambda s:re.sub(r'\W','',unicodedata.normalize('NFKC',s).casefold())[:300]
    key=normalized(candidate)
    if not key or has_repeating_ngrams(candidate):return ''
    if key in {normalized(s) for s in ('music','background music','音楽','音樂','음악','thanks for watching','ご視聴ありがとうございました','시청해 주셔서 감사합니다')}:return ''
    if len(key)>=8 and any(SequenceMatcher(None,key,normalized(s),autojunk=False).ratio()>.85 for s in recent_transcripts[-10:]):return ''
    return candidate
WORDS=dict(zip('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety'.split(),
               list(range(20))+list(range(20,100,10))))
DIGITS=dict(zip('零〇一二兩三四五六七八九', [0,0,1,2,2,3,4,5,6,7,8,9]))
SCALES={'hundred':100,'thousand':1000,'million':1000000,'billion':1000000000}
ENGLISH_NUMBERS=re.compile(r'\b(?:'+'|'.join([*WORDS,*SCALES])+r')(?:[- ]+(?:'+'|'.join([*WORDS,*SCALES,'and'])+r'))*\b')

def english_number(match):
    parts=re.split('[- ]+',match[0])
    separate=lambda:' '.join(str(WORDS.get(p,p)) for p in parts)
    if not any(p in SCALES for p in parts):
        values=[WORDS.get(p) for p in parts]
        if len(parts)==1:return str(values[0])
        if len(parts)==2 and all(v is not None for v in values) and values[0]>=20 and 0<values[1]<10:
            return str(sum(values))
        return separate()  # "one and two" means two quantities, not three.
    total=group=0;previous_scale=float('inf')
    for index,part in enumerate(parts):
        if part=='and':
            if not index or index==len(parts)-1 or parts[index-1] not in SCALES:return separate()
        elif part=='hundred':
            # "twelve hundred" is 1200; a scale-free group of 1-99 is allowed only before any larger scale.
            if not (0<group<10 or 0<group<100 and not total and previous_scale==float('inf')):return separate()
            group*=100
        elif part in SCALES:
            scale=SCALES[part]
            if scale>=previous_scale or not group:return separate()
            total+=group*scale;group=0;previous_scale=scale
        else:
            if index and parts[index-1] in WORDS:
                previous=WORDS[parts[index-1]]
                if not (previous>=20 and previous%10==0 and 0<WORDS[part]<10):return separate()
            group+=WORDS[part]
    return str(total+group)

def canonical_number(text):
    whole,_,fraction=text.replace(',','').partition('.')
    fraction=fraction.rstrip('0')
    return (whole.lstrip('0') or '0')+('.'+fraction if fraction else '')
SMALL_UNITS={'十':10,'百':100,'千':1000}
LARGE_UNITS={'萬':10000,'万':10000,'億':100000000,'亿':100000000}
ARABIC=r'\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?'
CJK_DIGITS='零〇一二兩三四五六七八九'
# A Chinese quantity must start with a digit and contain a multiplier, so 千萬不要 or 萬一 stay text.
CJK_QUANTITY=re.compile(r'(?:'+ARABIC+'|['+CJK_DIGITS+r'])(?:'+ARABIC+'|['+CJK_DIGITS+'十百千萬万億亿])*')

def cjk_number(s):
    """Parse Chinese numerals, including Arabic digits mixed with 十百千萬億 (12萬5千, 3.5億)."""
    if not any(c in s for c in '十百千萬万億亿'):
        return int(''.join(str(DIGITS[c]) for c in s))
    total=section=Decimal(0);digit=None
    for token in re.findall(ARABIC+'|.',s):
        if token in DIGITS:digit=Decimal(DIGITS[token])
        elif token[0].isdigit():digit=Decimal(token.replace(',',''))
        elif token in SMALL_UNITS:
            section+=(Decimal(1) if digit is None else digit)*SMALL_UNITS[token];digit=None
        else:
            section+=digit or 0
            if token in '億亿':total=(total+section)*LARGE_UNITS[token]
            else:total+=section*LARGE_UNITS[token]
            section=Decimal(0);digit=None
    value=total+section+(digit or 0)
    return format(value.normalize(),'f') if value!=value.to_integral() else str(int(value))

def chinese_quantity(match):
    text=match[0]
    return cjk_number(text) if any(c in text for c in '十百千萬万億亿') else text

# Chinese numerals become digits only before a time unit or a counting measure word, so
# words such as 四周 (surroundings), 一般 or 一起 stay text. 周、成、只 are left out because
# they are often not counts (四周, 三成 = 30%, 只 = only).
CJK_COUNT_UNITS=('小時','分鐘','英寸','英尺','英里','公尺','公里','公斤','世紀','世纪','秒','分','個','个','點','点','人','次','年','月','日',
                 '名','位','枚','株','種','种','條','条','隻','本','件','項','项','頁','页','張','张','台','輛','辆','架','艘','座','場','场',
                 '連','连','倍','歲','岁','號','号','層','层','米','度','元','塊','块','週','天','代','級','级','期','章','部','首','篇','份',
                 '組','组','隊','队','局','輪','轮','시간','초')
CJK_COUNT=re.compile('[零〇一二兩三四五六七八九十百千]+(?=\\s*(?:'+'|'.join(CJK_COUNT_UNITS)+'))')

MONTHS=('January','February','March','April','May','June','July','August','September','October','November','December')
# Capitalized month names only (ASR capitalizes them), so "march on" or "may" stay words; a
# sentence-initial "May" is usually the modal verb ("May I ...") and is skipped too.
MONTH=re.compile(r'(?<![.!?]\s)(?<!^)\b('+'|'.join(MONTHS)+r')\b|^(?!May\b)('+'|'.join(MONTHS)+r')\b')

def numbers(text):
    text=unicodedata.normalize('NFKC',text).strip()
    text=MONTH.sub(lambda m:str(MONTHS.index(m[1] or m[2])+1),text).lower()
    # Adverbial 十分 ("very") is not ten; 十分鐘 and digits such as 二十分 are untouched.
    text=re.sub(r'(?<![零〇一二兩三四五六七八九十百千\d])十分(?![鐘钟])','很',text)
    # English numbers are matched as whole words; don't match "one" in someone.
    text=re.sub(r'\ba(?=[- ]+(?:hundred|thousand|million|billion)\b)','one',text)
    # "350 million" and "1.5 billion" mix digits with an English scale word.
    text=re.sub(r'('+ARABIC+r')[- ]+(hundred|thousand|million|billion)\b',
                lambda m:canonical_number(format((Decimal(m[1].replace(',',''))*SCALES[m[2]]).normalize(),'f')),text)
    text=ENGLISH_NUMBERS.sub(english_number,text)
    text=CJK_QUANTITY.sub(chinese_quantity,text)
    text=CJK_COUNT.sub(lambda m:str(cjk_number(m[0])),text)
    return Counter(canonical_number(value) for value in re.findall(r'\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?',text))

def translation_numbers(text):
    """Numbers compared across languages. The value 1 is left out: English "one"/"a" is often a
    pronoun or article ("one of", "one another") and Chinese adds or drops 一 freely (之一, 一個),
    so 1 alone produced false mismatches and needless repair passes. A changed count still shows
    up as an extra number (one bomb -> 兩枚 adds 2)."""
    found=numbers(text);found.pop('1',None)
    return found

def untranslated_english(source,translation,terms=()):
    """Flag ordinary English left in a Chinese subtitle; never delete it."""
    remaining=translation
    # Explicit glossary targets, URLs and acronyms are intentional exceptions.
    for term in sorted(terms,key=lambda t:len(t.get('zh','')),reverse=True):
        target=term.get('zh','')
        if target:remaining=re.sub(r'(?<![A-Za-z0-9_])'+re.escape(target)+r'(?![A-Za-z0-9_])',' ',remaining,flags=re.I)
    remaining=re.sub(r'https?://\S+|\b[A-Z][A-Z0-9]{1,}\b',' ',remaining)
    ordinary=set('everyone anyone someone something nothing hello thanks thank please sorry wait waiting attack seconds minutes points teammate ultimate really actually probably because gonna wanna going think know want need look watching talking doing getting should would could cannot never'.split())
    words=set(re.findall(r"[a-z]+",remaining.casefold()))
    source_words=set(re.findall(r"[a-z]+",source.casefold()))
    return bool(ordinary & words & source_words)

# Output-anomaly checks (2026-11-08). In A/B/C/E FLEURS replays about 4-6% of finals had
# visibly broken output that no existing flag caught: U+FFFD, code-like residue ('!!");'),
# CJK words split by spaces, or an ordinary source word left in ALL CAPS. The all-caps case
# slipped through because untranslated_english() treats every all-caps word as an acronym.
# Where the corruption happens (generation, streaming or post-processing) is not yet known.
CODE_RESIDUE=re.compile(r'[!?]{2,}["\'`)\]}]|["\'`][)\]}]|[)\]}]\s*;|```|</?[A-Za-z][A-Za-z0-9]*>')
CJK_SPACED=re.compile(r'[\u4e00-\u9fff]{1,3}(?: [\u4e00-\u9fff]{1,3}){3,}')
SENTENCE_START=re.compile(r'(?:^|[.!?]["\')\]]?\s+)$')

def _source_forms(source):
    """Map each casefolded source word to how it was written: 'lower', 'upper' or 'title'.
    A Title-case word at a sentence start is 'start' because it may or may not be a name."""
    forms={}
    for m in re.finditer(r"[A-Za-z][A-Za-z']*",source):
        w=m[0];key=w.casefold()
        if w.isupper() and len(w)>1:form='upper'
        elif w[0].isupper():form='start' if SENTENCE_START.search(source[:m.start()]) else 'title'
        else:form='lower'
        forms.setdefault(key,set()).add(form)
    return forms

def _match_source(word,forms):
    key=word.casefold()
    if key in forms:return forms[key]
    # Simple inflection (term/terms, tour/tours); short words must match exactly.
    for other,f in forms.items():
        if len(key)>=4 and len(other)>=4 and (key.startswith(other) or other.startswith(key)) and abs(len(key)-len(other))<=2:return f
    return None

def caps_words(source,translation):
    """Split all-caps Latin words in the translation by how the source wrote them.
    Returns (ordinary, name_like): ordinary words were lower-case in the source (EARLY for
    'early'); name_like were Title-case mid-sentence or only seen at a sentence start
    (JACKAR for 'Jackar'). Words the source itself wrote in capitals, and words absent
    from the source, are neither. Case is never changed here."""
    forms=_source_forms(source);ordinary=[];name_like=[]
    for w in re.findall(r'(?<![A-Za-z])[A-Z]{3,}(?![A-Za-z])',translation):
        f=_match_source(w,forms)
        if not f or 'upper' in f:continue
        (ordinary if 'lower' in f else name_like).append(w)
    return ordinary,name_like

def output_anomalies(source,translation):
    """Broken-output flags for diagnostics. Only REPAIR_ANOMALIES join quality_flags (and
    so trigger a repair pass) in the opt-in trial; name-like case changes are reported by
    caps_words() only."""
    flags=[]
    if '\ufffd' in translation:flags.append('replacement_character')
    if CODE_RESIDUE.search(translation):flags.append('code_residue')
    if CJK_SPACED.search(translation):flags.append('cjk_spacing')
    if caps_words(source,translation)[0]:flags.append('uppercased_source_word')
    return flags

# G trial (2026-11-08): one repair pass removed U+FFFD and code residue, but 7 of 9
# all-caps cases stayed all-caps after repair at ~+0.8 s each. All-caps words are therefore
# reported (output_anomalies / caps_words) but no longer trigger a repair pass.
REPAIR_ANOMALIES=('replacement_character','code_residue','cjk_spacing')

def output_anomaly_repair_enabled():
    """Off by default; set MOSA_OUTPUT_ANOMALY_REPAIR=1 for an explicit trial."""
    return os.environ.get('MOSA_OUTPUT_ANOMALY_REPAIR','0')=='1'

def quality_flags(source,translation,language=None,terms=(),anomalies=None):
    flags=[]
    if untranslated_english(source,translation,terms):flags.append('untranslated_english')
    if translation_numbers(source)!=translation_numbers(translation):flags.append('number_mismatch')
    patterns={'en':r"\b(?:not|never|cannot)\b|n['’]t\b",
              'ja':r'ない|ません|ずに|禁止',
              'ko':r'않|지\s*마|말[아아요세]|못\s|아니|없'}
    patterns_to_use=[patterns[language]] if language in patterns else list(patterns.values())
    if any(re.search(p,source,re.I) for p in patterns_to_use) and not re.search(r'不|沒|未|無|別|勿|禁止',translation):
        flags.append('possible_missing_negation')
    if any(t['zh'] not in translation for t in terms if t['ja'] and t['ja'].casefold() in source.casefold()):
        flags.append('missing_glossary_term')
    if output_anomaly_repair_enabled() if anomalies is None else anomalies:
        flags.extend(f for f in output_anomalies(source,translation) if f in REPAIR_ANOMALIES)
    return flags

def assess_segment(segment):
    """Keep uncertain human speech visible, but never feed it into later context."""
    probability=getattr(segment,'no_speech_prob',0)
    ratio=getattr(segment,'compression_ratio',0)
    confidence=getattr(segment,'avg_logprob',0)
    text=getattr(segment,'text','').strip()
    reject=probability>=.65 or ratio>2.4 or (confidence<-1.5 and probability>.35)
    if text and not re.search(r'\w',text):reject=True
    if text and (probability>.35 or confidence<-1.0) and not sanitize_prompt(text,[]):reject=True
    return not reject,confidence<-1.0

def livestream_translation_hint(text):
    if not re.search(r'\bchat\b',text,re.I):return ''
    return (' When chat addresses livestream viewers (for example: Chat, what do you think? or '
            'Thank you, chat), translate it as 聊天室 or 聊天室的各位, never 查德. '
            'Read the chat means 看聊天室. When chat means an ordinary conversation or the verb '
            'to chat, use 聊天. Chad is a distinct person name and must not be changed to 聊天室. '
            'Do not add Twitch or viewers unless the source meaning supports it.')

def static_prompt(terms):
    """A bounded static vocabulary, never generated recognition history."""
    clean=[]
    for term in terms[:30]:
        if isinstance(term,str):
            term=' '.join(term.split()).strip()
            if term and len(term)<=40 and term not in clean:clean.append(term)
    return ', '.join(clean)[:200] or None

class TranslationCache:
    def __init__(self,limit=16):self.items=OrderedDict();self.limit=limit
    def get(self,key):
        if key not in self.items:return None
        self.items.move_to_end(key);return self.items[key]
    def put(self,key,value):
        self.items[key]=value;self.items.move_to_end(key)
        while len(self.items)>self.limit:self.items.popitem(last=False)

def preview_has_progress(text,previous):
    """Batch small appended prefixes; corrections are always allowed through."""
    if not previous:return bool(text)
    if text==previous:return False
    if not text.startswith(previous):return True
    added=text[len(previous):].strip()
    return len(added)>=8 or bool(re.search(r'[。！？.!?]$',added))
