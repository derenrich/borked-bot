from typing import Literal, Union
import pywikibot
from .yt_follows.update_yt_follows import fixed_gen, template_gen, update_yt_subs, should_update_enwiki, enwiki_gen, all_gen
from .yt_chan_fill.update_yt_chan import update_yt_chan, all_gen as yt_chan_all_gen
from .yt_vid_fill.run import update_yt_vid
import time
import fire
import dotenv

dotenv.load_dotenv()

wikidata_site = pywikibot.Site("wikidata", "wikidata")
enwiki_site = pywikibot.Site("en", "wikipedia")
repo = wikidata_site.data_repository()


class BorkedBot:
    def yt_follows(self, dry_run: bool=False, mode: Union[Literal['enwiki'], Literal['all'], Literal['fixed'], Literal['template']] ='enwiki', qid: str =None, only_best: bool=True):

        if not isinstance(only_best, bool):
            raise ValueError("only_best must be a boolean value (True or False)")
        if not isinstance(dry_run, bool):
            raise ValueError("dry_run must be a boolean value (True or False)")

        print("Updating YouTube follower counts for enwiki accounts...")
        t = time.time()
        if mode == 'all':
            update_yt_subs(repo, all_gen(wikidata_site), lambda old, new: True, dry_run=dry_run, only_best=only_best)
        elif mode == 'enwiki':
            update_yt_subs(repo, enwiki_gen(wikidata_site), should_update_enwiki, " (enwiki)", dry_run=dry_run, min_age_days=365, only_best=only_best)
        elif mode == 'fixed' and qid is not None:
            update_yt_subs(repo, fixed_gen(wikidata_site, qid), should_update_enwiki, dry_run=dry_run, min_age_days=0, only_best=only_best)
        elif mode == 'template':
            update_yt_subs(repo, template_gen(enwiki_site, 'Template:Infobox social media personality'), should_update_enwiki, dry_run=dry_run, min_age_days=30, only_best=only_best)
        else:
            raise ValueError(f"Unknown yt_follows mode: {mode}")
        print(f"Finished updating YouTube follower counts for enwiki accounts in {time.time() - t} seconds.")


    def yt_chan(self, dry_run: bool=False):
        print("Updating YouTube channel data...")
        t = time.time()
        update_yt_chan(repo, yt_chan_all_gen(wikidata_site), dry_run=dry_run)
        print(f"Finished updating YouTube channel data in {time.time() - t} seconds.")

    def yt_vid(self, dry_run: bool=False):
        print("Updating YouTube video data...")
        t = time.time()
        
        update_yt_vid(repo, wikidata_site, dry_run=dry_run)
        print(f"Finished updating YouTube video data in {time.time() - t} seconds.")

    def migrate_kymeme(self, dry_run: bool=False):
        print("Migrating Know Your Meme IDs...")
        t = time.time()
        from .kymeme.update_kym import migrate_kymeme
        migrate_kymeme(repo, wikidata_site, dry_run=dry_run)
        print(f"Finished migrating Know Your Meme IDs in {time.time() - t} seconds.")

    def bsky_did(self, dry_run: bool=False):
        print("Updating Bluesky DIDs...")
        t = time.time()
        from .bsky.set_bsky_did import update_bsky_did
        update_bsky_did(repo, wikidata_site, dry_run=dry_run)
        print(f"Finished updating Bluesky DIDs in {time.time() - t} seconds.")

    def steam_data(self, dry_run: bool=False):
        print("Updating Steam data...")
        t = time.time()
        from .steam.update_steam_data import update_steam_data
        update_steam_data(repo, wikidata_site, dry_run=dry_run)
        print(f"Finished updating Steam data in {time.time() - t} seconds.")

    def ballotpedia_page(self, dry_run: bool=False):
        print("Updating Ballotpedia page data...")
        t = time.time()
        from .ballotpedia_page.run import update_ballotpedia_data
        update_ballotpedia_data(repo, wikidata_site, dry_run=dry_run)
        print(f"Finished updating Ballotpedia page data in {time.time() - t} seconds.")

    def fandom_page(self, dry_run: bool=False):
        print("Updating Fandom page data...")
        t = time.time()
        from .fandom_page.run import update_fandom_data
        update_fandom_data(repo, wikidata_site, dry_run=dry_run)
        print(f"Finished updating Fandom page data in {time.time() - t} seconds.")

if __name__ == '__main__':
    fire.Fire(BorkedBot, name='borked-bot')