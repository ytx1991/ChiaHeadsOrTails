import aiohttp
import asyncio

from pprint import pprint
from chia.types.coin_spend import CoinSpend
from chia.rpc.full_node_rpc_client import FullNodeRpcClient
from chia.util.default_root import DEFAULT_ROOT_PATH
from chia.util.config import load_config
from chia.util.ints import uint16
from chia.types.blockchain_format.coin import Coin


async def get_client():
    try:
        config = load_config(DEFAULT_ROOT_PATH, "config.yaml")
        self_hostname = config["self_hostname"]
        full_node_rpc_port = config["full_node"]["rpc_port"]
        full_node_client = await FullNodeRpcClient.create(self_hostname, uint16(full_node_rpc_port), DEFAULT_ROOT_PATH, config)
        return full_node_client
    except Exception as e:
        if isinstance(e, aiohttp.ClientConnectorError):
            pprint(f"Connection error. Check if full node is running at {full_node_rpc_port}")
        else:
            pprint(f"Exception from 'harvester' {e}")
        return None


def get_coins_by_puzzle_hash(puzzle_hash, show_unspend=False):
    async def query(puzzle_hash):
        try:
            node_client = await get_client()
            coin_records = await node_client.get_coin_records_by_puzzle_hashes([puzzle_hash], show_unspend)
            coin_records = [rec.to_json_dict() for rec in coin_records]
            cr_dict = {}
            for record in coin_records:
                cr_dict[Coin.from_json_dict(record["coin"]).name().hex()] = record
            return cr_dict
        finally:
            node_client.close()
            await node_client.await_closed()
    return asyncio.get_event_loop().run_until_complete(query(bytes.fromhex(puzzle_hash[2:])))


def get_coins_by_parent(parent_id, show_unspend=False):
    async def query(parent_id):
        try:
            node_client = await get_client()
            coin_records = await node_client.get_coin_records_by_parent_ids([parent_id], show_unspend)
            coin_records = [rec.to_json_dict() for rec in coin_records]
            cr_dict = {}
            for record in coin_records:
                cr_dict[Coin.from_json_dict(record["coin"]).name().hex()] = record
            return cr_dict
        finally:
            node_client.close()
            await node_client.await_closed()
    return asyncio.get_event_loop().run_until_complete(query(bytes.fromhex(parent_id[2:])))


def get_coin_details(coin_id, block_height) -> CoinSpend:
    async def do_command():
        try:
            node_client = await get_client()
            coin_spend = await node_client.get_puzzle_and_solution(bytes.fromhex(coin_id), block_height)
            return coin_spend
        finally:
            node_client.close()
            await node_client.await_closed()
    return asyncio.get_event_loop().run_until_complete(do_command())


def push_tx(spend_bundles):
    async def do_command():
        try:
            node_client = await get_client()
            try:
                result = await node_client.fetch("push_tx", {"spend_bundle": spend_bundles})
                pprint(result)
            except ValueError as e:
                pprint(str(e))
        finally:
            node_client.close()
            await node_client.await_closed()
    asyncio.get_event_loop().run_until_complete(do_command())
