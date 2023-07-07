import utils
from stableswap import Stableswap

DECIMALS_USDC = 6
ADDRESS_USDC = '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'.lower()

DECIMALS_CRVUSD = 18
ADDRESS_CRVUSD = '0xf939E0A03FB07F59A73314E73794Be0E57ac1b4E'.lower()

pool = Stableswap()

def init_pool():
    pool.initialize(
        _coins=[ADDRESS_USDC, ADDRESS_CRVUSD, utils.ADDRESS_ZERO, utils.ADDRESS_ZERO], 
        _rate_multipliers=[utils.rate_multiplier(DECIMALS_USDC), utils.rate_multiplier(DECIMALS_CRVUSD), 0, 0], 
        _A=500, 
        _fee=10 ** 6, 
        block_timestamp=1684066067
    )


def add_liquidity(pool):
    amounts = [250000 * 10 ** DECIMALS_USDC, 250000 * 10 ** DECIMALS_CRVUSD]
    pool.add_liquidity(block_timestamp=1684066067 + 1, _amounts=amounts)


def print_prices(pool):
    print('last_price', pool.last_price())
    print('ema_price', pool.ema_price())


def main():
    init_pool()
    add_liquidity(pool)
    print_prices(pool)


if __name__ == '__main__':
    main()
