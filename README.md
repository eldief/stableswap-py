# stableswap-py
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
        _coins=[utils.ADDRESS_USDC, utils.ADDRESS_CRVUSD, utils.ADDRESS_ZERO, utils.ADDRESS_ZERO], 
        _rate_multipliers=[utils.rate_multiplier(utils.DECIMALS_USDC), utils.rate_multiplier(utils.DECIMALS_CRVUSD), 0, 0], 
        _A=500, 
        _fee=10 ** 6, 
        block_timestamp=1684066067
    )
```