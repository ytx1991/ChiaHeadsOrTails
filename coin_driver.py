
from blspy import PrivateKey, AugSchemeMPL
from chia.types.blockchain_format.program import Program
from chia.util.hash import std_hash
from clvm_tools.binutils import disassemble, assemble
from chia.util.bech32m import encode_puzzle_hash, decode_puzzle_hash
from clvm.casts import int_to_bytes

from cdv.util.load_clvm import load_clvm
from game_hash import GameHash

DEALER_MOD = load_clvm('dealer_coin.clsp','clsp')
PLAYER_MOD = load_clvm('player_coin.clsp','clsp')
STAKE_MOD = load_clvm('stake_coin.clsp','clsp')


def create_dealer_coin_puzzle_hash(reward_puzzle_hash, amount, toss_hash, freeze_seconds):
    return DEALER_MOD.curry(reward_puzzle_hash, amount, toss_hash, freeze_seconds, STAKE_MOD.get_tree_hash()).get_tree_hash()


def get_dealer_coin_reveal(game_hash: GameHash):
    return str(DEALER_MOD.curry(assemble(game_hash.dealer_reward_puzzle_hash), assemble(game_hash.amount), assemble(game_hash.toss_hash), assemble(game_hash.freeze_seconds), STAKE_MOD.get_tree_hash()))


def create_player_coin_puzzle_hash(public_key, reward_puzzle_hash, amount):
    return PLAYER_MOD.curry(assemble(hex(public_key)), reward_puzzle_hash, amount).get_tree_hash()


def get_player_coin_reveal(public_key, reward_puzzle_hash, amount):
    return str(PLAYER_MOD.curry(assemble(hex(public_key)), reward_puzzle_hash, amount))


def get_stake_coin_reveal(game_hash: GameHash, player_puzzle_hash, guess):
    return str(STAKE_MOD.curry(assemble(game_hash.dealer_reward_puzzle_hash), assemble(player_puzzle_hash), assemble(str(int(game_hash.amount) * 2)), assemble(game_hash.toss_hash), assemble(guess), assemble(game_hash.freeze_seconds)))


def puzzle_to_address(puzzle_hash):
    return encode_puzzle_hash(puzzle_hash, 'xch')


def get_toss_hash(random_key, head_or_tail):
    return std_hash(bytes(random_key + head_or_tail, encoding='ascii'))


def validate_game_hash(game_hash: GameHash):
    return DEALER_MOD.curry(assemble(game_hash.dealer_reward_puzzle_hash), assemble(game_hash.amount), assemble(game_hash.toss_hash), assemble(game_hash.freeze_seconds), STAKE_MOD.get_tree_hash()).get_tree_hash() == assemble(game_hash.dealer_coin_puzzle_hash)


def serialize_solution(args):
    solution_args = [assemble(arg) for arg in args]
    return str(Program.to(solution_args))


def sign_transaction(private_key, coin_id, player_puzzle_hash, guess, total_amount):
    return str(AugSchemeMPL.sign(PrivateKey.from_bytes(bytes.fromhex(private_key[2:])), std_hash(bytes.fromhex(coin_id) + bytes.fromhex(player_puzzle_hash[2:]) + bytes(guess, encoding='ascii') + int_to_bytes(total_amount))))
