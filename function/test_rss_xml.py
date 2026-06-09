import json
import unittest

try:
    from function.rss_xml import rss_xml_to_feed_items
except ModuleNotFoundError:
    from rss_xml import rss_xml_to_feed_items

_SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel>
    <title>Example Feed</title>
    <item>
      <title>Article One</title>
      <link>https://example.com/1</link>
      <description><![CDATA[<p>Desc 1</p>]]></description>
      <pubDate>Tue, 10 Jun 2026 00:19:00 +0200</pubDate>
      <guid isPermaLink="true">https://example.com/1</guid>
      <category>Politik</category>
      <category>Deutschland</category>
      <dc:creator>Max Mustermann</dc:creator>
    </item>
    <item>
      <title>Article Two</title>
      <link>https://example.com/2</link>
      <description>Plain description</description>
      <pubDate>Tue, 10 Jun 2026 00:05:00 +0200</pubDate>
      <guid isPermaLink="false">id-2</guid>
      <category>Wetter</category>
      <enclosure url="https://example.com/a.mp3" length="123" type="audio/mpeg"/>
    </item>
  </channel>
</rss>
"""

_SAMPLE_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom Feed</title>
  <entry>
    <title>Atom Article</title>
    <link href="https://example.com/atom/1"/>
    <id>tag:example.com,2026:1</id>
    <updated>2026-06-10T00:19:00+02:00</updated>
    <summary>Atom summary text</summary>
  </entry>
</feed>
"""


class RssXmlToJsonTests(unittest.TestCase):
    def test_returns_json_array_with_one_object_per_item(self):
        result = rss_xml_to_feed_items(_SAMPLE_RSS)

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)

    def test_simple_text_fields_are_mapped(self):
        item = rss_xml_to_feed_items(_SAMPLE_RSS)[0]

        self.assertEqual(item["title"], "Article One")
        self.assertEqual(item["link"], "https://example.com/1")
        self.assertEqual(item["description"], "<p>Desc 1</p>")
        self.assertEqual(item["pubDate"], "Tue, 10 Jun 2026 00:19:00 +0200")

    def test_element_with_attributes_and_text(self):
        item = rss_xml_to_feed_items(_SAMPLE_RSS)[0]

        self.assertEqual(
            item["guid"],
            {
                "@isPermaLink": "true",
                "#text": "https://example.com/1",
            },
        )

    def test_repeated_tags_become_array(self):
        item = rss_xml_to_feed_items(_SAMPLE_RSS)[0]

        self.assertEqual(item["category"], ["Politik", "Deutschland"])

    def test_single_category_stays_string(self):
        item = rss_xml_to_feed_items(_SAMPLE_RSS)[1]

        self.assertEqual(item["category"], "Wetter")

    def test_namespaced_elements_keep_prefix(self):
        item = rss_xml_to_feed_items(_SAMPLE_RSS)[0]

        self.assertEqual(item["dc:creator"], "Max Mustermann")

    def test_self_closing_element_with_attributes(self):
        item = rss_xml_to_feed_items(_SAMPLE_RSS)[1]

        self.assertEqual(
            item["enclosure"],
            {
                "@url": "https://example.com/a.mp3",
                "@length": "123",
                "@type": "audio/mpeg",
            },
        )

    def test_atom_entries_are_supported(self):
        result = rss_xml_to_feed_items(_SAMPLE_ATOM)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Atom Article")
        self.assertEqual(
            result[0]["link"],
            {"@href": "https://example.com/atom/1"},
        )

    def test_empty_feed_returns_empty_array(self):
        xml = """<?xml version="1.0"?><rss version="2.0"><channel/></rss>"""
        self.assertEqual(rss_xml_to_feed_items(xml), [])

    def test_invalid_xml_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            rss_xml_to_feed_items("<rss><unclosed>")

        self.assertIn("invalid RSS XML", str(ctx.exception))

    def test_result_is_json_serializable(self):
        result = rss_xml_to_feed_items(_SAMPLE_RSS)
        encoded = json.dumps(result, ensure_ascii=False)
        decoded = json.loads(encoded)

        self.assertEqual(decoded[0]["title"], "Article One")


if __name__ == "__main__":
    unittest.main()
