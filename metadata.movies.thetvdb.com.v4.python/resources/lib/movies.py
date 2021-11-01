import enum
import re

import xbmcgui
import xbmcplugin

from . import tvdb
from .utils import logger, get_language


ARTWORK_URL_PREFIX = "https://artworks.thetvdb.com"

SUPPORTED_REMOTE_IDS = {
    'IMDB': 'imdb',
    'TheMovieDB.com': 'tmdb',
}


class ArtworkType(enum.IntEnum):
    POSTER = 14
    BACKGROUND = 15



def search_movie(title, settings, handle, year=None) -> None:
    # add the found shows to the list

    tvdb_client = tvdb.Client(settings)
    kwargs = {'limit': 10}
    if year is not None:
        kwargs['year'] = year
    search_results = tvdb_client.search(title, type="movie", **kwargs)
    if not search_results:
        return
    items = []
    for movie in search_results:
        name = movie['name']
        if movie.get('year'):
            name += name + f' ({movie["year"]})'
        liz = xbmcgui.ListItem(name, offscreen=True)
        url = str(movie['tvdb_id'])
        is_folder = True
        items.append((url, liz, is_folder))
    xbmcplugin.addDirectoryItems(
        handle,
        items,
        len(items)
    )


def get_movie_details(id, settings, handle):
    # get the details of the found series
    tvdb_client = tvdb.Client(settings)

    movie = tvdb_client.get_movie_details_api(id, settings)
    if not movie:
        xbmcplugin.setResolvedUrl(
            handle, False, xbmcgui.ListItem(offscreen=True))
        return
    liz = xbmcgui.ListItem(movie["name"], offscreen=True)
    people = get_cast(movie)
    liz.setCast(people["cast"])
    genres = get_genres(movie)
    details = {
        'title': movie["name"],
        'plot': movie["overview"],
        'plotoutline': movie["overview"],
        'mediatype': 'movie',
        'writer': people["writers"],
        'director': people["directors"],
        'genre': genres,
    }
    years = get_year(movie)
    if years:
        details["year"] = years["year"]
        details["premiered"] = years["premiered"]
    rating = get_rating(movie)
    if rating:
        details["mpaa"] = rating
    
    country = movie.get("originalCountry", None)
    if country:
        details["country"] = country

    studio = get_studio(movie)
    if studio:
        details["studio"] = studio
    
    tags = get_tags(movie)
    if tags:
        details["tag"] = tags
    
    trailer = get_trailer(movie)
    if trailer:
        details["trailer"] = trailer

    _set = get_set(movie)
    set_poster = None
    if _set:
        set_info = tvdb_client.get_movie_set_info(_set["id"], settings)
        details["set"] = set_info["name"]
        details["set.overview"] = set_info["overview"]
        first_movie_in_set_id = set_info["movie_id"]
        if first_movie_in_set_id:
            first_movie_in_set = tvdb_client.get_movie_details_api(first_movie_in_set_id, settings)
            set_poster = first_movie_in_set["image"]
        
    liz.setInfo('video', details)

    unique_ids = get_unique_ids(movie)
    liz.setUniqueIDs(unique_ids, 'tvdb')

    add_artworks(movie, liz, set_poster)
    xbmcplugin.setResolvedUrl(handle=handle, succeeded=True, listitem=liz)


def get_cast(movie):
    cast = []
    directors = []
    writers = []
    for char in movie["characters"]:
        if char["peopleType"] == "Actor":
            d = {
                'name': char["personName"],
                'role': char["name"],
            }
            if char.get('image'):
                d['thumbnail'] = ARTWORK_URL_PREFIX + char['image']
            cast.append(d)
        if char["peopleType"] == "Director":
            directors.append(char["personName"])
        if char["peopleType"] == "Writer":
            writers.append(char["personName"])
    return {
        "directors": directors,
        "writers": writers,
        "cast": cast,
    }


def get_artworks_from_movie(movie: dict):
    artworks = movie.get("artworks", [{}])

    posters = sorted([art for art in artworks if art.get("type", 0) == ArtworkType.POSTER], key=lambda image: image.get("score", 0),reverse=True)
    backgrounds = sorted([art for art in artworks if art.get("type", 0) == ArtworkType.BACKGROUND], key=lambda image: image.get("score", 0),reverse=True)
    artwork_dict = {
        "posters": posters[0:10],
        "fanarts": backgrounds[0:10],
    }
    return artwork_dict


def add_artworks(movie, liz, set_poster=None):
    
    artworks = get_artworks_from_movie(movie)
    posters = artworks.get("posters", [])
    fanarts = artworks.get("fanarts", [])

    if set_poster:
        liz.addAvailableArtwork(set_poster, 'set.poster')



    for poster in posters:
        image = poster.get("image", "")
        if ARTWORK_URL_PREFIX not in image:
            image = ARTWORK_URL_PREFIX + image
        liz.addAvailableArtwork(image, 'poster')

    fanart_items = []
    for fanart in fanarts:
        image = fanart.get("image", "")
        thumb  = fanart["thumbnail"]
        if ARTWORK_URL_PREFIX not in image:
            image = ARTWORK_URL_PREFIX + image
            thumb = ARTWORK_URL_PREFIX + thumb
        fanart_items.append(
            {'image': image, 'preview': thumb})
    if fanarts:
        liz.setAvailableFanart(fanart_items)


def get_artworks(id, settings, handle):
    tvdb_client = tvdb.Client(settings)
    movie = tvdb_client.get_series_details_api(id, settings)
    if not movie:
        xbmcplugin.setResolvedUrl(
            handle, False, xbmcgui.ListItem(offscreen=True))
        return
    liz = xbmcgui.ListItem(id, offscreen=True)
    add_artworks(movie, liz)
    xbmcplugin.setResolvedUrl(handle=handle, succeeded=True, listitem=liz)


def get_year(movie):
    country = movie.get("originalCountry", "")
    releases = movie.get("releases", [])
    global_release_str = ""
    release_str = ""
    if len(releases) < 1:
        return None
    for release in releases:
        release_country =release["country"]
        if  release_country == country:
            release_str = release["date"]
        if release_country == "global":
            global_release_str = release["date"]
    if not release_str and not global_release_str:
        return None
    if not release_str and global_release_str:
        release_str = global_release_str
    year = int(release_str.split("-")[0])
    return {
        "year": year,
        "premiered": release_str,
    }


def get_genres(movie):
    return [genre["name"] for genre in movie.get("genres", [])]


def get_rating(movie):
    ratings = movie.get("contentRatings", None)
    rating = ""
    if ratings is not None:
        for r in ratings:
            if r["country"] == "usa":
                rating = r["name"]
        if rating == "" and len(ratings) != 0:
            rating = ratings[0]["name"]
    
    return rating


def get_studio(movie):
    studios = movie.get("studios", [])
    if not studios or len(studios) == 0:
        return None
    name = studios[0]["name"]
    return name


def get_tags(movie):
    tags = []
    tag_options = movie.get("tagOptions", [])
    if tag_options:
        for tag in tag_options:
            tags.append(tag["name"])
    return tags


def get_set(movie):
    lists = movie.get("lists", None)
    if not lists:
        return None
    
    name = ""
    id = 0
    score = float('inf')
    logger.debug(lists)
    for l in lists:
        if l["isOfficial"]:
            if l["score"] < score:
                score = l["score"]
                name = l["name"]
                id = l["id"]
    if name and id:
        logger.debug("name and id in get set")
        logger.debug(name)
        logger.debug(id)
        return {
            "name": name,
            "id": id,
        }
 
    return None


def get_trailer(movie):
    trailer_url = ""
    originalLang = movie.get("originalLanguage", None)
    if not originalLang:
        originalLang = "eng"
    
    trailers = movie.get("trailers", None)
    if not trailers:
        return None

    for trailer in trailers:
        if trailer["language"] == originalLang:
            trailer_url = trailer["url"]
    
    match = re.search("youtube", trailer_url)
    if not match:
        return None

    trailer_id_match = re.search("\?v=[A-z]+", trailer_url)
    if not trailer_id_match:
        return None
    trailer_id = trailer_id_match.group(0)
    url = f'plugin://plugin.video.youtube/play/?video_id={trailer_id}'
    return url


def get_unique_ids(movie):
    unique_ids = {'tvdb': movie['id']}
    remote_ids = movie.get('remoteIds')
    if remote_ids:
        for remote_id_info in remote_ids:
            source_name = remote_id_info.get('sourceName')
            if source_name in SUPPORTED_REMOTE_IDS:
                unique_ids[SUPPORTED_REMOTE_IDS[source_name]] = remote_id_info['id']
    return unique_ids

