from ..credentials import CREDENTIALS
from twitchAPI.twitch import Twitch


async def make_twitch_client():
    return await Twitch(CREDENTIALS["twitch-client-id"], CREDENTIALS["twitch-secret"])


async def batch_get_twitch_ids(twitch, handles):
    # There is a limit of 100 users at one time. I'm assuming the client will give a
    # good descriptive exception when we exceed that, otherwise we should add a check.
    users = twitch.get_users(logins=handles)
    return {
        user.login: user.id
        async for user in users
    }

async def get_twitch_follows(twitch, numeric_user_id):
    r = await twitch.get_channel_followers(numeric_user_id)
    return r.total