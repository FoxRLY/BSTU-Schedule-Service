import pytest
import asyncio
from src.download_html import ScheduleDownloader

@pytest.mark.asyncio
class TestDownloader:
    async def test_page_download_success(self, default_agent):
        downloader = ScheduleDownloader(default_agent)
        response, status = await downloader.try_download_page("https://google.com")
        assert status
        assert response != ""

    async def test_page_download_fail(self, default_agent):
        downloader = ScheduleDownloader(default_agent)
        response, status = await downloader.try_download_page("bruh://bruh.brom")
        assert not status
        assert response == ""

    async def test_api_call_success(self, default_agent, api_url, good_api_header):
        downloader = ScheduleDownloader(default_agent)
        response, status = await downloader.try_get_request(api_url, good_api_header, 0)
        assert status
        assert response != ""
        
    async def test_api_call_bad(self, default_agent, api_url, bad_api_header):
        downloader = ScheduleDownloader(default_agent)
        response, status = await downloader.try_get_request(api_url, bad_api_header, 0)
        assert not status
        assert response == ""

@pytest.fixture
def default_agent() -> dict:
    agent = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:101.0) Gecko/20100101 Firefox/101.0'}
    return agent

@pytest.fixture
def good_api_header() -> dict:
    return dict(entity="gruppy", id="528", week="0", device="desktop")

@pytest.fixture
def bad_api_header() -> dict:
    return dict(entity="bruppy", id="-127", week="355", device="bobter")

@pytest.fixture
def api_url() -> str:
    return "https://t.bstu.ru/web/api/events"
