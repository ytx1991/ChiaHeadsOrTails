import configparser
import click
import coin_driver
import rpc
import random
import string
from game_hash import GameHash

@click.group()
def game():
    pass


@click.command("new", short_help="Start a new game. You are the dealer.")
@click.option('--amount', prompt='The mojos you bet for this game (1 XCH = 1000000000000 mojo)',
              help='The mojos you want to bet on this game. 1 XCH = 1 000 000 000 000 mojo')
@click.option('--head_or_trail', prompt='You flipped the coin and saw it is (HEAD or TAIL)',
              help='The result of the coin flipping, can only be HEAD or TAIL. If the player guess is right you will lose your bet.')
def new_game(amount, head_or_trail):
    # Validate inputs
    amount = int(amount)
    if amount <= 0:
        print('Why do you think the bet can be negative or zero?')
        return
    if head_or_trail != 'HEAD' and head_or_trail != 'TAIL':
        print('A coin can only be "HEAD" or "TAIL"')
        return
    # Generate dealer coin
    random_key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
    toss_hash = coin_driver.get_toss_hash(random_key, head_or_trail)
    coin_puzzle_hash = coin_driver.create_dealer_coin_puzzle_hash(REWARD_PUZZLE_HASH, amount, toss_hash, FREEZE_SECONDS)
    address = coin_driver.puzzle_to_address(coin_puzzle_hash)

    f = open('0x' + str(toss_hash) + '.key', 'w')
    f.write('Coin Puzzle Hash: 0x{0}\n'.format(coin_puzzle_hash))
    f.write('Coin Address: {0}\n'.format(address))
    f.write('Game Hash: 0x{0}|{1}|0x{2}|{3}|0x{4}\n'.format(hex(REWARD_PUZZLE_HASH)[2:].zfill(64), amount, toss_hash, FREEZE_SECONDS, coin_puzzle_hash))
    f.write('Reveal Key: {0}'.format(random_key))
    f.close()
    print('PLEASE SAFELY KEEP THE 0x{0}.key FILE and FILE NAME, OTHERWISE YOU WILL LOSE!'.format(toss_hash))
    print('Now, please transfer your bet {0} mojos to the dealer coin address {1}.'.format(amount, address))
    print('You can track the transaction at https://chia.tt/info/address/{0}'.format(address))
    print('Send the game hash to your friends to start the game:\n0x{0}|{1}|0x{2}|{3}|0x{4}'.format(hex(REWARD_PUZZLE_HASH)[2:].zfill(64), amount, toss_hash , FREEZE_SECONDS, coin_puzzle_hash))
    print('NOTE: As the dealer you need to reveal the winner in {0} seconds after the player committed the guess.'.format(FREEZE_SECONDS))
    return


@click.command('play', short_help='Play the game hosted by one dealer. Use the game hash published by the dealer.')
@click.option('--game_hash_string', prompt='Input the game hash you want to play',
              help='The game hash published by dealer')
def play_game(game_hash_string):
    game_hash = GameHash(game_hash_string)
    # Validate game hash
    if not coin_driver.validate_game_hash(game_hash):
        print('Invalid game hash, please ensure you input the full game hash and check with the dealer.')
        return
    # Check if the dealer coin exist
    coin_records = rpc.get_coins_by_puzzle_hash(game_hash.dealer_coin_puzzle_hash)
    if len(coin_records) == 0:
        print('The dealer has not pay the bet yet.')
        return
    # generate player coin
    amount = int(game_hash.amount)
    player_coin_puzzle_hash = coin_driver.create_player_coin_puzzle_hash(SIGN_PUBLIC_KEY, REWARD_PUZZLE_HASH, amount)
    address = coin_driver.puzzle_to_address(player_coin_puzzle_hash)
    print('This is a valid game.')
    print('Now you need to pay your bet {0} mojos to address {1} before the guess.'.format(amount, address))
    print('You can track the transaction at https://chia.tt/info/address/{0}'.format(address))
    return


@click.command('commit', short_help='As a player, you commit the game. No one can cancel the game after the commit.')
@click.option('--game_hash_string', prompt='Input the game hash you want to commit',
              help='The game hash published by dealer')
@click.option('--guess', prompt='You guess the coin is (HEAD or TAIL)',
              help='The guess made by the player. It can only be HEAD or TAIL')
def commit_game(game_hash_string, guess):
    game_hash = GameHash(game_hash_string)
    if guess != 'HEAD' and guess != 'TAIL':
        print('A coin can only be "HEAD" or "TAIL"')
        return
    # Validate game hash
    if not coin_driver.validate_game_hash(game_hash):
        print('Invalid game hash, please ensure you input the full game hash and check with the dealer.')
        return
    # Check if the dealer coin exist
    dealer_coins = rpc.get_coins_by_puzzle_hash(game_hash.dealer_coin_puzzle_hash)
    if len(dealer_coins) == 0:
        print('The dealer has not pay the bet yet.')
        return
    dealer_coin = list(dealer_coins.items())[0]
    # Check if the player coin exist
    amount = int(game_hash.amount)
    player_coin_puzzle_hash = coin_driver.create_player_coin_puzzle_hash(SIGN_PUBLIC_KEY, REWARD_PUZZLE_HASH, amount)
    player_coins = rpc.get_coins_by_puzzle_hash('0x{0}'.format(player_coin_puzzle_hash))
    address = coin_driver.puzzle_to_address(player_coin_puzzle_hash)
    if len(player_coins) == 0:
        print('You have not pay the bet yet.')
        print('Now you need to pay your bet {0} mojos to address {1} before the guess.'.format(amount, address))
        print('You can track the transaction at https://chia.tt/info/address/{0}'.format(address))
        return
    player_coin = list(player_coins.items())[0]
    # Commit the guess, spend both coins
    spend_bundle = {}
    spend_bundle['coin_spends'] = []
    spend_dealer = {}
    spend_player = {}
    spend_bundle['coin_spends'].append(spend_dealer)
    spend_bundle['coin_spends'].append(spend_player)
    # dealer coin
    spend_dealer['coin'] = dealer_coin[1]['coin']
    spend_dealer['puzzle_reveal'] =coin_driver.get_dealer_coin_reveal(game_hash)
    spend_dealer['solution'] = coin_driver.serialize_solution(['0x' + hex(REWARD_PUZZLE_HASH)[2:].zfill(64), str(amount * 2), guess, game_hash.dealer_coin_puzzle_hash, str(0)])
    # player coin
    spend_player['coin'] = player_coin[1]['coin']
    spend_player['puzzle_reveal'] = coin_driver.get_player_coin_reveal(SIGN_PUBLIC_KEY, REWARD_PUZZLE_HASH, amount)
    spend_player['solution'] = coin_driver.serialize_solution(['0x{0}'.format(dealer_coin[0]), guess, str(amount * 2), '0x{0}'.format(player_coin_puzzle_hash), str(0)])
    # sign
    spend_bundle['aggregated_signature'] = coin_driver.sign_transaction(hex(SIGN_PRIVATE_KEY), dealer_coin[0], hex(REWARD_PUZZLE_HASH), guess, amount * 2)
    # Push tx

    rpc.push_tx(spend_bundle)
    print('The game is set. Wait the dealer reveal the winner. If the game is timeout you can claim all Mojos by the "timeout" command.')


@click.command('refund', short_help='You want to refund your bet before commit the game.')
@click.option('--game_hash_string', prompt='Input the game hash you want to refund',
              help='The game hash published by dealer')
@click.option('--is_dealer', prompt='Are you the dealer of the game? (Y or N)',
              help='Indicate if the user is the dealer or player')
def refund_game(game_hash_string, is_dealer):
    game_hash = GameHash(game_hash_string)
    if is_dealer == 'Y':
        print('Refunding dealer ...')
        dealer_coins = rpc.get_coins_by_puzzle_hash(game_hash.dealer_coin_puzzle_hash)
        if len(dealer_coins) == 0:
            print('No coin found. Make sure you paid the bet.')
            return
        dealer_coin = list(dealer_coins.items())[0]
        spend_bundle = {}
        spend_bundle['coin_spends'] = []
        spend_dealer = {}
        spend_bundle['coin_spends'].append(spend_dealer)
        spend_dealer['coin'] = dealer_coin[1]['coin']
        spend_dealer['puzzle_reveal'] =coin_driver.get_dealer_coin_reveal(game_hash)
        spend_dealer['solution'] = coin_driver.serialize_solution(['0', '0', '0', game_hash.dealer_coin_puzzle_hash, str(1)])
        spend_bundle['aggregated_signature'] = "0xc00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        # Push tx
        rpc.push_tx(spend_bundle)
        print('Your {0} mojo is refunded to {1}.'.format(game_hash.amount, game_hash.dealer_reward_puzzle_hash))
    elif is_dealer == 'N':
        print('Refunding player ...')
        amount = int(game_hash.amount)
        player_coin_puzzle_hash = coin_driver.create_player_coin_puzzle_hash(SIGN_PUBLIC_KEY, REWARD_PUZZLE_HASH, amount)
        player_coins = rpc.get_coins_by_puzzle_hash('0x{0}'.format(player_coin_puzzle_hash))
        player_coin = list(player_coins.items())[0]
        spend_bundle = {}
        spend_bundle['coin_spends'] = []
        spend_player = {}
        spend_bundle['coin_spends'].append(spend_player)
        spend_player['coin'] = player_coin[1]['coin']
        spend_player['puzzle_reveal'] = coin_driver.get_player_coin_reveal(SIGN_PUBLIC_KEY, REWARD_PUZZLE_HASH, amount)
        spend_player['solution'] = coin_driver.serialize_solution(['0', '0', '0', '0x{0}'.format(player_coin_puzzle_hash), str(1)])
        spend_bundle['aggregated_signature'] = "0xc00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        # Push tx
        rpc.push_tx(spend_bundle)
        print('Your {0} mojo is refunded to 0x{1}.'.format(game_hash.amount, hex(REWARD_PUZZLE_HASH)[2:].zfill(64)))
    else:
        print('Who are you?')


@click.command('reveal', short_help='Reveal the winner as the dealer. All mojos will go to the winner address. Failed to reveal the winner in time will cause dealer lose.')
@click.option('--game_hash_string', prompt='Input the game hash you want to reveal',
              help='The game hash published by dealer')
def reveal_game(game_hash_string):
    game_hash = GameHash(game_hash_string)
    # Load reveal key
    f = open(game_hash.toss_hash + '.key', 'r')
    reveal_key = f.read()[-16:]
    print('Reveal key is {0}'.format(reveal_key))
    # Scan dealer coin
    dealer_coins = rpc.get_coins_by_puzzle_hash(game_hash.dealer_coin_puzzle_hash, True)
    count = 0
    for cid, coin in dealer_coins.items():
        if coin['spent']:
            print('Dealer coin {0} spent, revealing the winner ...'.format(cid))
            count += 1
            # Retrieve solution
            solution = rpc.get_coin_details(cid, coin['spent_block_index']).solution.to_program()
            player_reward_puzzle = '0x' + hex(solution.first().as_int())[2:].zfill(64)
            guess = str(solution.rest().rest().first().as_python(), 'ascii')
            print('Player {0} guessed the coin is {1}'.format(player_reward_puzzle, guess))
            stake_coins = rpc.get_coins_by_parent('0x{0}'.format(cid))
            if len(stake_coins) == 0:
                print('The winner already revealed.')
            else:
                spend_bundle = {}
                spend_bundle['coin_spends'] = []
                stake_coin = list(stake_coins.items())[0]
                spend_stake = {}
                spend_bundle['coin_spends'].append(spend_stake)
                spend_stake['coin'] = stake_coin[1]['coin']
                spend_stake['puzzle_reveal'] = coin_driver.get_stake_coin_reveal(game_hash, player_reward_puzzle, guess)
                spend_stake['solution'] = coin_driver.serialize_solution([stake_coin[1]['coin']['puzzle_hash'], reveal_key, str(0)])
                spend_bundle['aggregated_signature'] = "0xc00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
                # Push tx
                print('Spending the stake coin id: {0}, puzzle_hash:{1}'.format(stake_coin[0], stake_coin[1]['coin']['puzzle_hash']))
                rpc.push_tx(spend_bundle)
                if '0x{0}'.format(coin_driver.get_toss_hash(reveal_key, guess)) == game_hash.toss_hash:
                    print('You lose! {0} mojo will send to the player address {1}.'.format(int(game_hash.amount) * 2, player_reward_puzzle))
                else:
                    print('You win! {0} mojo will send to your address {1}.'.format(int(game_hash.amount) * 2, game_hash.dealer_reward_puzzle_hash))
    if count == 0:
        print("No player join the game yet.")


@click.command('timeout', short_help='Player can withdraw all mojos if the dealer does not reveal the winner in time.')
@click.option('--game_hash_string', prompt='Input the game hash you think it is timeout',
              help='The game hash published by dealer')
def timeout_game(game_hash_string):
    game_hash = GameHash(game_hash_string)
    print('Trying to withdraw timeout game ...')
    # Scan dealer coin
    dealer_coins = rpc.get_coins_by_puzzle_hash(game_hash.dealer_coin_puzzle_hash, True)
    count = 0
    for cid, coin in dealer_coins.items():
        if coin['spent']:
            print('Dealer coin {0} spent, revealing the winner ...'.format(cid))
            count += 1
            # Retrieve solution
            solution = rpc.get_coin_details(cid, coin['spent_block_index']).solution.to_program()
            player_reward_puzzle = '0x' + hex(solution.first().as_int())[2:].zfill(64)
            guess = str(solution.rest().rest().first().as_python(), 'ascii')
            print('Player {0} guessed the coin is {1}'.format(player_reward_puzzle, guess))
            stake_coins = rpc.get_coins_by_parent('0x{0}'.format(cid))
            if len(stake_coins) == 0:
                print('The winner already revealed.')
            else:
                spend_bundle = {}
                spend_bundle['coin_spends'] = []
                stake_coin = list(stake_coins.items())[0]
                spend_stake = {}
                spend_bundle['coin_spends'].append(spend_stake)
                spend_stake['coin'] = stake_coin[1]['coin']
                spend_stake['puzzle_reveal'] = coin_driver.get_stake_coin_reveal(game_hash, player_reward_puzzle, guess)
                spend_stake['solution'] = coin_driver.serialize_solution([stake_coin[1]['coin']['puzzle_hash'], '0', str(1)])
                spend_bundle['aggregated_signature'] = "0xc00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
                # Push tx
                rpc.push_tx(spend_bundle)
                print('You win! {0} mojo will send to your address {1}.'.format(int(game_hash.amount) * 2, player_reward_puzzle))
    if count == 0:
        print("No player join the game yet.")


game.add_command(new_game)
game.add_command(play_game)
game.add_command(commit_game)
game.add_command(refund_game)
game.add_command(reveal_game)
game.add_command(timeout_game)

if __name__ == '__main__':
    # Load configurations
    config = configparser.ConfigParser()
    config.read('config.ini')
    global REWARD_PUZZLE_HASH
    global SIGN_PRIVATE_KEY
    global SIGN_PUBLIC_KEY
    global FREEZE_SECONDS
    REWARD_PUZZLE_HASH = int(config['GameSetting']['RewardPuzzleHash'], 16)
    SIGN_PRIVATE_KEY = int(config['GameSetting']['SignPrivateKey'], 16)
    SIGN_PUBLIC_KEY = int(config['GameSetting']['SignPublicKey'], 16)
    FREEZE_SECONDS = int(config['GameSetting']['FreezeSeconds'])
    game()
