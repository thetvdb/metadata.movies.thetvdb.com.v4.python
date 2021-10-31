import enum
import urllib.parse

from resources.lib import simple_requests as requests
from resources.lib.utils import logger

apikey = "#*apikey*#"
apikey_with_pin = "#*apikey_with_pin*#"

USER_AGENT = 'TheTVDB v.4 Movie Scraper for Kodi'


class ArtworkType(enum.IntEnum):
    BANNER = 1
    POSTER = 2
    FANART = 3


class Auth:
    logger.debug("logging in")

    def __init__(self, url, apikey, pin="", **kwargs):
        loginInfo = {"apikey": apikey}
        if pin:
            loginInfo["pin"] = pin
            loginInfo["apikey"] = apikey_with_pin
        loginInfo.update(kwargs)
        logger.debug("body in auth call")
        logger.debug(loginInfo)
        headers = {
            'User-Agent': USER_AGENT,
            'Accept': 'application/json',
        }
        response = requests.post(url, headers=headers, json=loginInfo)
        if not response.ok:
            response.raise_for_status()
        self.token = response.json()['data']['token']

    def get_token(self):
        return self.token


class Request:
    def __init__(self, auth_token):
        self.auth_token = auth_token
        self.cache = {}

    def make_api_request(self, url):
        logger.debug(f"about to make request to url {url}")
        logger.debug(url)
        data = self.cache.get(url, None)
        if data:
            return data
        headers = {
            'User-Agent': USER_AGENT,
            'Accept': 'application/json',
            'Authorization': f'Bearer {self.auth_token}'
        }
        response = requests.get(url, headers=headers)
        if not response.ok:
            response.raise_for_status()
        data = response.json()['data']
        self.cache[url] = data
        return data

    @staticmethod
    def make_web_request(url):
        logger.debug(f"about to make request to url {url}")
        headers = {
            'User-Agent': USER_AGENT,
            'Accept': 'text/html',
        }
        response = requests.get(url, headers=headers)
        if not response.ok:
            response.raise_for_status()
        return response.text


class Url:
    def __init__(self):
        self.base_url = "https://api4.thetvdb.com/v4"

    def login_url(self):
        return "{}/login".format(self.base_url)

    def artwork_url(self, id, extended=False):
        url = "{}/artwork/{}".format(self.base_url, id)
        if extended:
            url = "{}/extended".format(url)
        return url

    def movies_url(self, page=0):
        url = "{}/movies".format(self.base_url, id)
        return url

    def movie_url(self, id, extended=False):
        url = "{}/movies/{}".format(self.base_url, id)
        if extended:
            url = "{}/extended".format(url)
        return url

    def list_url(self, id, extended=False):
        url = "{}/lists/{}".format(self.base_url, id)
        if extended:
            url = "{}/extended".format(url)
        return url

    def movie_translation_url(self, id, language="eng"):
        url = f'{self.base_url}/movies/{id}/translations/{language}'
        return url

    def list_translation_url(self, id, language="eng"):
        url = f'{self.base_url}/lists/{id}/translations/{language}'
        return url

    def search_url(self, query, filters):
        filters["query"] = query
        qs = urllib.parse.urlencode(filters)
        url = "{}/search?{}".format(self.base_url, qs)
        return url


class TVDB:
    def __init__(self, apikey: str, pin="", **kwargs):
        self.url = Url()
        login_url = self.url.login_url()
        self.auth = Auth(login_url, apikey, pin)
        auth_token = self.auth.get_token()
        self.request = Request(auth_token)

    def get_artwork(self, id: int) -> dict:
        """Returns an artwork dictionary"""
        url = self.url.artwork_url(id)
        return self.request.make_api_request(url)

    def get_artwork_extended(self, id: int) -> dict:
        """Returns an artwork extended dictionary"""
        url = self.url.artwork_url(id, True)
        return self.request.make_api_request(url)

    def get_all_movies(self, page=0) -> list:
        """Returns a list of movies"""
        url = self.url.movies_url(page)
        return self.request.make_api_request(url)

    def get_movie(self, id: int) -> dict:
        """Returns a movie dictionary"""
        url = self.url.movie_url(id, False)
        return self.request.make_api_request(url)

    def get_movie_extended(self, id: int) -> dict:
        """Returns a movie extended dictionary"""
        url = self.url.movie_url(id, True)
        return self.request.make_api_request(url)

    def get_movie_translation(self, id, lang: str) -> dict:
        """Returns a movie translation dictionary"""
        url = self.url.movie_translation_url(id, lang)
        return self.request.make_api_request(url)

    def get_list_extended(self, id: int) -> dict:
        """Returns a movie translation dictionary"""
        url = self.url.list_url(id, True)
        return self.request.make_api_request(url)

    def get_list_translation(self, id: int, lang: str) -> dict:
        """Returns a movie translation dictionary"""
        url = self.url.list_translation_url(id, lang)
        return self.request.make_api_request(url)

    def search(self, query, **kwargs) -> list:
        """Returns a list of search results"""
        url = self.url.search_url(query, kwargs)
        return self.request.make_api_request(url)

    def get_movie_details_api(self, id, settings=None, language="eng") -> dict:
        movie = self.get_movie_extended(id)
        translations = self.get_movie_translation(id, language)
        overview = translations.get("overview", "")
        movie["overview"] = overview
        name = translations.get("name", "")
        movie["name"] = name
        return movie

    def get_movie_set_info(self, id, settings):
        list = self.get_list_extended(id)
        lang = settings.get("language", "eng")
        name = None
        overview = None
        try:
            trans = self.get_list_translation(id, lang)
            name = trans.get("name", "")
            overview = trans.get("overview", "")
        except:
            name = list.get("name", "")
        movie_id = None
        entities = list.get("entities", [])
        if not entities:
            return None
        for item in entities:
            if item["movieId"] is not None:
                movie_id = item["movieId"]
                break
        return {
            "movie_id": movie_id,
            "name": name,
            "overview": overview,
        }


class Client:
    _instance = None

    def __new__(cls, settings=None):
        settings = settings or {}
        if cls._instance is None:
            pin = settings.get("pin", "")
            gender = settings.get("gender", "Other")
            uuid = settings.get("uuid", "")
            birth_year = settings.get("year", "")
            cls._instance = TVDB(apikey, pin=pin, gender=gender, birthYear=birth_year, uuid=uuid)
        return cls._instance
