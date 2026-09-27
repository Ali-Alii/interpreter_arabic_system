from app.merge import merge_pair, merge_segments


def join(left, right):
    return merge_pair(left, right, 25, 25, 5)


def test_shared_phrase_merged_and_incorrect_ending_preserved():
    text, info = join('ذهبِ الطالبَ إلى المدرسةُ في الصباحَ', 'إلى المدرسةُ في الصباحَ ثم عادَ')
    assert text == 'ذهبِ الطالبَ إلى المدرسةُ في الصباحَ ثم عادَ'
    assert info['status'] == 'merged'


def test_ending_conflict_reported_not_grammatically_fixed():
    text, info = join('ذهبِ الطالبَ إلى المدرسةُ في الصباحَ', 'إلى المدرسةِ في الصباحَ ثم عادَ')
    assert 'المدرسةُ' in text
    assert info['ending_conflicts'] == 1


def test_inserted_word_inside_overlap_still_aligns():
    text, info = join('قالَ ذهبِ الطالبَ إلى المدرسةُ في الصباحَ اليومَ',
                      'ذهبِ الطالبَ إلى المدرسةُ مبكراً في الصباحَ اليومَ ثم عادَ')
    assert info['status'] == 'merged'
    assert text.count('المدرسةُ') == 1
    assert text.endswith('ثم عادَ')


def test_unrelated_text_is_not_deleted():
    left, right = 'قرأَ الطفلُ كتاباً', 'سافرَ الرجلُ بعيداً'
    text, info = join(left, right)
    assert info['status'] == 'unresolved'
    assert left in text and right in text


def test_repeated_phrase_is_not_silently_removed():
    phrase = 'قالَ الطالبُ نعمْ'
    text, info = join(phrase+' '+phrase, phrase+' '+phrase+' ثم ذهبَ')
    assert info['status'] == 'unresolved'
    assert text.count(phrase) == 4


def test_non_overlapping_chunks_preserve_intentional_repetition():
    raw, joins = merge_segments([{'start':0,'end':10,'raw':'نعمْ نعمْ'},
                                 {'start':10,'end':20,'raw':'نعمْ نعمْ'}])
    assert raw == 'نعمْ نعمْ نعمْ نعمْ'
    assert joins == []


def test_three_chunks_merge_in_order():
    raw, joins = merge_segments([
        {'start':0,'end':25,'raw':'بدأَ ذهبِ الطالبَ إلى المدرسةُ في الصباحَ'},
        {'start':20,'end':45,'raw':'إلى المدرسةُ في الصباحَ ثم قرأَ قصةً قصيرةً أمامَ زملائهِ'},
        {'start':40,'end':60,'raw':'قصةً قصيرةً أمامَ زملائهِ وعادَ إلى البيتِ'},
    ])
    assert all(j['status'] == 'merged' for j in joins)
    assert raw == 'بدأَ ذهبِ الطالبَ إلى المدرسةُ في الصباحَ ثم قرأَ قصةً قصيرةً أمامَ زملائهِ وعادَ إلى البيتِ'
