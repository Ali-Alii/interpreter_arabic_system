from app.evaluate import score


def test_deleted_word_does_not_shift_endings():
    result = score('قرأَ الطالبُ كتاباً جديداً', 'قرأَ كتاباً جديداً')
    assert result['correct_words_and_endings'] == 3
    assert result['strict_final_word_accuracy'] == .75


def test_insertions_penalized():
    result = score('قرأَ الطالبُ', 'قرأَ قرأَ الطالبُ')
    assert result['insertions'] == 1
    assert result['strict_final_word_accuracy'] == 2/3


def test_wrong_ending_and_missing_mark():
    assert score('طالبٌ', 'طالبُ')['strict_final_word_accuracy'] == 0
    assert score('طالبْ', 'طالب')['strict_final_word_accuracy'] == 0


def test_spelling_error_is_not_hidden_by_correct_ending():
    assert score('طالبٌ', 'كاتبٌ')['strict_final_word_accuracy'] == 0
