from typing import TypedDict, Optional, List, Dict, Any

import requests


BASE_URL = "https://store.steampowered.com/api/appdetails?appids="


class SteamAppData(TypedDict, total=False):
    type: str
    name: str
    steam_appid: int
    required_age: int
    is_free: bool
    controller_support: str
    detailed_description: str
    about_the_game: str
    short_description: str
    supported_languages: str
    header_image: str
    capsule_image: str
    capsule_imagev5: str
    website: str
    pc_requirements: Dict[str, str]
    mac_requirements: Dict[str, str]
    linux_requirements: Dict[str, str]
    developers: List[str]
    publishers: List[str]
    demos: List[Dict[str, Any]]
    price_overview: Dict[str, Any]
    packages: List[int]
    package_groups: List[Dict[str, Any]]
    platforms: Dict[str, bool]
    metacritic: Dict[str, Any]
    categories: List[Dict[str, Any]]
    genres: List[Dict[str, Any]]
    screenshots: List[Dict[str, Any]]
    movies: List[Dict[str, Any]]
    recommendations: Dict[str, int]
    release_date: Dict[str, Any]
    support_info: Dict[str, str]
    background: str
    background_raw: str
    content_descriptors: Dict[str, Any]
    ratings: Dict[str, Any]

def get_steam_app_details(appid: int, session: requests.Session) -> Optional[SteamAppData]:
    url = BASE_URL + str(appid)
    resp = session.get(url)
    if resp.status_code != 200:
        print(f"Error fetching details for appid {appid}: HTTP {resp.status_code}")
        return None
    data = resp.json()
    if str(appid) in data and data[str(appid)]['success']:
        return data[str(appid)]['data']
    else:
        print(f"No data found for appid {appid}")
        return None