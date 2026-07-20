import asyncio
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

try:
    import function.main as main
except ModuleNotFoundError:
    import main  # noqa: F401

_MAIN = main.__name__
_BERLIN = ZoneInfo("Europe/Berlin")

_SAMPLE_RSS_BYTES = b"""<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Test Article</title>
      <link>https://example.com/test</link>
    </item>
  </channel>
</rss>
"""


class DatetimeOutputTests(unittest.TestCase):
    def test_module_timezone_is_europe_berlin(self):
        self.assertEqual(str(main._TZ), "Europe/Berlin")

    def test_date_prefix_follows_berlin_at_utc_day_boundary(self):
        """22:00 UTC am 8.6. = 00:00 Berlin am 9.6. (CEST) — nicht UTC-Datum 08-06."""
        utc_time = datetime(2026, 6, 8, 22, 0, tzinfo=timezone.utc)
        berlin_time = utc_time.astimezone(_BERLIN)

        self.assertEqual(berlin_time.strftime("%d-%m-%Y"), "09-06-2026")
        self.assertNotEqual(utc_time.strftime("%d-%m-%Y"), "09-06-2026")

    def test_date_prefix_follows_berlin_in_winter_time(self):
        utc_time = datetime(2026, 1, 15, 23, 30, tzinfo=timezone.utc)
        berlin_time = utc_time.astimezone(_BERLIN)

        self.assertEqual(berlin_time.strftime("%d-%m-%Y"), "16-01-2026")

    def test_date_prefix_at_10_june_0019_berlin_not_utc(self):
        """10.06. 00:19 Berlin — UTC-Code würde fälschlich 09-06 liefern."""
        berlin_time = datetime(2026, 6, 10, 0, 19, tzinfo=_BERLIN)
        utc_same_instant = datetime(2026, 6, 9, 22, 19, tzinfo=timezone.utc)

        self.assertEqual(berlin_time.strftime("%d-%m-%Y"), "10-06-2026")
        self.assertEqual(utc_same_instant.strftime("%d-%m-%Y"), "09-06-2026")
        self.assertEqual(
            utc_same_instant.astimezone(_BERLIN).strftime("%d-%m-%Y"),
            "10-06-2026",
        )

    @patch(f"{_MAIN}._run_async", new_callable=AsyncMock, return_value=([], 0))
    @patch(f"{_MAIN}._ensure_bucket_exists")
    @patch(f"{_MAIN}._resolve_bucket_name", return_value="test-bucket")
    @patch(f"{_MAIN}._load_feed_list", return_value=[])
    @patch(f"{_MAIN}.boto3")
    @patch(f"{_MAIN}.datetime")
    def test_handler_uses_berlin_date_prefix(
        self,
        mock_datetime,
        mock_boto3,
        _mock_load,
        _mock_bucket,
        _mock_ensure,
        mock_run_async,
    ):
        fixed = datetime(2026, 6, 9, 1, 0, tzinfo=_BERLIN)
        mock_datetime.now.return_value = fixed
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        mock_boto3.client.return_value = MagicMock()

        response = main.handler({}, None)

        self.assertEqual(response["statusCode"], 200)
        mock_run_async.assert_awaited_once()
        date_prefix = mock_run_async.call_args.args[5]
        self.assertEqual(date_prefix, "09-06-2026")
        mock_datetime.now.assert_called_with(main._TZ)

    def test_process_one_feed_uploads_parsed_json_array(self):
        asyncio.run(self._run_process_one_feed_assertions())

    async def _run_process_one_feed_assertions(self) -> None:
        with (
            patch(f"{_MAIN}.secrets.token_hex", return_value="abcd"),
            patch(f"{_MAIN}.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread,
        ):
            client = MagicMock()
            response = MagicMock()
            response.status_code = 200
            response.content = _SAMPLE_RSS_BYTES
            response.headers = {"Content-Type": "application/xml"}
            client.get = AsyncMock(return_value=response)

            s3_client = MagicMock()
            item = {
                "xmlUrl": "https://rss.example.com/feed.xml",
                "title": "Test",
            }

            result = await main._process_one_feed(
                client,
                item,
                "test-bucket",
                s3_client,
                "09-06-2026",
            )

            self.assertTrue(result["ok"])
            self.assertEqual(result["s3Key"], "feeds/example/09-06-2026-abcd.json")
            self.assertEqual(result["itemCount"], 1)

            body_bytes = mock_to_thread.await_args.kwargs["Body"]
            payload = json.loads(body_bytes.decode("utf-8"))
            self.assertIsInstance(payload, list)
            self.assertEqual(payload[0]["title"], "Test Article")
            self.assertEqual(payload[0]["link"], "https://example.com/test")


class ProcessOneFeedRssIntegrationTests(unittest.TestCase):
    def test_invalid_rss_xml_returns_error(self):
        async def run() -> None:
            client = MagicMock()
            response = MagicMock()
            response.status_code = 200
            response.content = b"<rss><broken>"
            response.headers = {"Content-Type": "application/xml"}
            client.get = AsyncMock(return_value=response)

            result = await main._process_one_feed(
                client,
                {"xmlUrl": "https://rss.example.com/feed.xml", "title": "Test"},
                "test-bucket",
                MagicMock(),
                "09-06-2026",
            )
            self.assertFalse(result["ok"])
            self.assertIn("invalid RSS XML", result["error"])

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
