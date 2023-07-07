# stableswappy
Curve Stableswap translated to python, no external dependencies needed

## Usage
Install this repo `pip install git+https://github.com/eldief/stableswappy.git`


Import Stableswap and utils in your project 
```
    from stableswappy import Stableswap, rate_multiplier, ADDRESS_ZERO
```


Create new Stableswap and initialize:
```
    DECIMALS_USDC = 6
    DECIMALS_CRVUSD = 18

    pool = Stableswap()
    pool.initialize(
        _coins=[ADDRESS_USDC, ADDRESS_CRVUSD, ADDRESS_ZERO, ADDRESS_ZERO], 
        _rate_multipliers=[rate_multiplier(DECIMALS_USDC), rate_multiplier(DECIMALS_CRVUSD), 0, 0], 
        _A=500, 
        _fee=10 ** 6, 
        block_timestamp=1684066067
    )
```

Simulate execution:
```
    DECIMALS_USDC = 6
    DECIMALS_CRVUSD = 18

    amounts = [250000 * 10 ** DECIMALS_USDC, 250000 * 10 ** DECIMALS_CRVUSD]
    pool.add_liquidity(block_timestamp=1684066067 + 1, _amounts=amounts)
```

Print price:

```
    print('last_price', pool.last_price()) # 1000000000000000000 
    print('ema_price', pool.ema_price()) # 1000000000000000000 
```
