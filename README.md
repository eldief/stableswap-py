# stableswappy
Curve Stableswap translated to python, no external dependencies needed

## Usage
Clone this repo `git clone https://github.com/eldief/stableswap-py`


Import Stableswap and utils in your project 
```
    import utils
    from stableswap import Stableswap
```


Create new Stableswap and initialize:
```
    pool = Stableswap()
    pool.initialize(
        _coins=[ADDRESS_USDC, ADDRESS_CRVUSD, utils.ADDRESS_ZERO, utils.ADDRESS_ZERO], 
        _rate_multipliers=[utils.rate_multiplier(DECIMALS_USDC), utils.rate_multiplier(DECIMALS_CRVUSD), 0, 0], 
        _A=500, 
        _fee=10 ** 6, 
        block_timestamp=1684066067
    )
```
