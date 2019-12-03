import re
import time
import aiohttp


CHANGE_CLOTHES = True
# Use swap gear
ACCOUNT_ID = 'b8dd6d09-0bf1-4455-99c5-4cec41b3a789'
# account id goes here


class DuelsAPI:
    def __init__(self, account_id, **kwargs):
        self.account_id = account_id
        self.API_ENTRY = kwargs.get('api_entry_url',
                                    'https://api-duels.galapagosgames.com')
        self._session = aiohttp.ClientSession()
        self._auth_data = dict()
        self._all_data = dict()

    @property
    def profile(self):
        return self._all_data.get('profile')

    async def login(self):
        app_version = await self.get_app_version()
        data = {
            'ids': [self.account_id],
            'appBundle': 'com.deemedyainc.duels',
            'appVersion': app_version,
            'platform': 'Android',
            'language': 'English'
        }
        all_data = await self._request('/general/login', data)
        self._auth_data['id'] = all_data['profile']['_id']
        self._auth_data['appVersion'] = app_version
        self._auth_data['token'] = all_data['profile']['token']
        self._all_data = all_data
        return self._all_data

    async def get_app_version(self):
        app_version = self._auth_data.get('appVersion')
        if app_version is not None:
            return app_version

        google_play_url = ('https://play.google.com/store/apps/details?id'
                           '=com.deemedyainc.duels&hl=en')
        async with self._session.get(google_play_url) as resp:
            data = await resp.text()
        pattern = (r'<div class="hAyfc"><div class="BgcNfc">Current '
                   r'Version</div><span class="htlgb"><div '
                   r'class="IQ1z0d"><span class="htlgb">(?P<version>.*?)'
                   r'</span></div></span></div>')
        version = re.search(pattern, data)
        return version['version']

    async def skip_queue(self, container_id):
        return await self._request('/queue/claim',
                                   {'containerId': container_id})

    async def equip_part(self, part_id):
        return await self._request('/inventory/equip', {'partId': part_id})

    async def get_clan(self, clan_id):
        return await self._request('/clan/info', {'clanId': clan_id})

    async def get_player(self, player_id):
        return await self._request('/profiles/details',
                                   {'playerId': player_id})

    async def play_lootfight(self):
        return await self._request('/battle/loot/v2')

    async def get_opponent(self, repeat_roll=False):
        return await self._request('/battle/loot/opponent/v2',
                                   {'reroll': repeat_roll})

    async def get_dungeons_leaderboard(self):
        return await self._request('/dungeons/leaderboards/top')

    async def search_clan(self, clan_name, only_joinable=False, min_level=1):
        payload = {'search': clan_name, 'onlyJoinable': only_joinable}
        if min_level > 1:
            payload.update({'lvl': min_level})
        return await self._request('/clans/search', payload)

    async def close(self):
        if not self._session.closed:
            await self._session.close()

    async def _request(self, endpoint, additional_data={}, method='POST'):
        additional_data.update(self._auth_data)
        func_to_call = getattr(self._session, method.lower())
        url = self.API_ENTRY + endpoint
        async with func_to_call(url, json=additional_data) as resp:
            return await resp.json()


async def main():
    api = DuelsAPI(ACCOUNT_ID)
    await api.login()
    bad_equipment_ids = {}
    now_equipment_ids = {}
    if CHANGE_CLOTHES:
        input(
            'Pick better equipment in the game, and press `Enter` to continue'
        )
        for part in api.profile['character']['parts']:
            now_equipment_ids.update({part['__type']: part['__id']})
        for item in api.profile['inventory']['items']:
            bad_item = bad_equipment_ids.get(item['__type'])
            if bad_item is not None:
                if bad_item['stat_value'] < item['stat']['value']:
                    continue
            payload = {'id': item['__id'], 'stat_value': item['stat']['value']}
            bad_equipment_ids[item['__type']] = payload
    total_keys = api.profile['Key@Value']
    start_time = time.time()
    while True:
        try:
            for item_value in bad_equipment_ids.values():
                await api.equip_part(item_value['id'])
            await api.get_opponent()

            for item_type, item_value in now_equipment_ids.items():
                if bad_equipment_ids.get(item_type) is not None:
                    await api.equip_part(item_value)

            loot_fight = await api.play_lootfight()
            if loot_fight['battle']['result']:
                print('[+] Ez win, win streak: {}'.format(
                    loot_fight['_u']['WinStreak@Value']
                ))
                for queue in loot_fight['_q']:
                    await api.skip_queue(queue['_id'])
                    await api.skip_queue(queue['pid'])

                    if queue.get('steps') is None:
                        continue

                    for step in queue['steps']:
                        if step['type'] == 'RewardQueue':
                            if step['items'][0]['type'] != 'Key':
                                continue
                            keys_reward = step['items'][0]['reward']
                            total_keys += keys_reward
                            print('[+] We have got +{} keys!'.format(
                                keys_reward))
                            print('[+] Total keys: {}'.format(total_keys))
                            print('[+] Time elapsed: {}'.format(
                                time.time() - start_time
                            ))
            else:
                print('[-] Ez lose!')
            await asyncio.sleep(1.0)
        except KeyboardInterrupt:
            print('[+] Exit...')
            break


if __name__ == '__main__':
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
