from clvm_tools.binutils import disassemble, assemble

class GameHash:
    def __init__(self, game_hash):
        token = game_hash.split('|')
        if len(token) != 5:
            raise Exception('Invalid game hash, please check.')
        self.dealer_reward_puzzle_hash = token[0]
        self.amount = token[1]
        self.toss_hash = token[2]
        self.freeze_seconds = token[3]
        self.dealer_coin_puzzle_hash = token[4]

    def to_string(self):
        return '{0}|{1}|{2}|{3}|{4}'.format(self.dealer_reward_puzzle_hash, self.amount, self.toss_hash, self.freeze_seconds, self.dealer_coin_puzzle_hash)
