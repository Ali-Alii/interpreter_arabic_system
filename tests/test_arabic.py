import unicodedata
import pytest
from app.arabic import final_only


@pytest.mark.parametrize('source, expected', [
    ('ذَهَبَ الطَّالِبُ إِلَى الْمَدْرَسَةِ.', 'ذهبَ الطالبُ إلى المدرسةِ.'),
    ('كِتَابٌ قَلَمٍ', 'كتابٌ قلمٍ'),
    ('كِتَابًا كِتَاباً', 'كتاباً كتاباً'),
    ('حَقٌّ', 'حقٌّ'),
    ('قُلْ، قُلْ!', 'قلْ، قلْ!'),
    ('أَحْمَد إِيمَان', 'أحمد إيمان'),
    ('ذهب الطالب', 'ذهب الطالب'),
    ('جَاءَ الطَّالِبِ', 'جاءَ الطالبِ'), # Incorrect grammar must survive.
])
def test_display_only(source, expected):
    assert final_only(source) == unicodedata.normalize('NFC', expected)


def test_normalization_and_idempotence():
    source = unicodedata.normalize('NFD', 'إِيمَانٌ')
    assert final_only(source) == 'إيمانٌ'
    assert final_only(final_only(source)) == final_only(source)
