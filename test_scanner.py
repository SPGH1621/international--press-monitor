import unittest
from scanner import classify, parse_page

SAMPLE = '''
<div class="tgme_widget_message_wrap">
  <div class="tgme_widget_message" data-post="demagazinesharing/1234">
    <a class="tgme_widget_message_date"><time datetime="2026-11-17T05:00:00+00:00"></time></a>
    <div class="tgme_widget_message_document_title">The Economist_1711.pdf</div>
  </div>
</div>
<div class="tgme_widget_message_wrap">
  <div class="tgme_widget_message" data-post="demagazinesharing/1235">
    <div class="tgme_widget_message_document_title">FT Asia 17112026.pdf</div>
  </div>
</div>
<div class="tgme_widget_message_wrap">
  <div class="tgme_widget_message" data-post="demagazinesharing/1236">
    <div class="tgme_widget_message_document_title">Daily Mail 17 Nov.pdf</div>
  </div>
</div>
'''

class ScannerTests(unittest.TestCase):
    def test_sources(self):
        samples = {'NYT 1109.pdf': 'nyt', 'FT Asia 1109.pdf': 'ft',
                   "Barron's November 2026.pdf": 'barrons',
                   'Bloomberg Businessweek - November.pdf': 'businessweek',
                   'The Wall Street Journal - September.pdf': 'wsj',
                   'The Economist_1209.pdf': 'economist'}
        for name, key in samples.items():
            self.assertEqual(classify(name)[0], key)
        self.assertIsNone(classify('Daily Mail_1209.pdf'))
    def test_page(self):
        items, before, count = parse_page(SAMPLE)
        self.assertEqual((len(items), before, count), (2, 1234, 3))
        self.assertEqual(items[1]['post_url'], 'https://t.me/demagazinesharing/1235')

if __name__ == '__main__':
    unittest.main()
