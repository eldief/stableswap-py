import utils

class Stableswap:
    # CONST
    N_COINS = 2
    N_COINS_128 = 2
    PRECISION = 10 ** 18
    ADMIN_ACTIONS_DEADLINE_DT = 86400 * 3

    FEE_DENOMINATOR = 10 ** 10
    ADMIN_FEE = 5000000000

    A_PRECISION = 100
    MAX_FEE = 5 * 10 ** 9
    MAX_A = 10 ** 6
    MAX_A_CHANGE = 10
    MIN_RAMP_TIME = 86400

    coins = [0 for _ in range(N_COINS)]
    balances = [0 for _ in range(N_COINS)]
    fee = 0  # fee * 1e10
    future_fee = 0
    admin_action_deadline = 0

    initial_A = 0
    future_A = 0
    initial_A_time = 0
    future_A_time = 0

    rate_multipliers = [0 for _ in range(N_COINS)]

    totalSupply = 0
    unpacked_last_price = 0
    unpacked_ma_price = 0
    ma_exp_time = 0
    ma_last_time = 0

    # @external
    def __init__(self):
        self.factory = "0x0000000000000000000000000000000000000001"

    # @external
    def initialize(self, _coins, _rate_multipliers, _A, _fee, block_timestamp):
        """
        @notice Contract constructor
        @param _name Name of the new pool
        @param _symbol Token symbol
        @param _coins List of all ERC20 conract addresses of coins
        @param _rate_multipliers List of number of decimals in coins
        @param _A Amplification coefficient multiplied by n ** (n - 1)
        @param _fee Fee to charge for exchanges
        """
        for i in range(self.N_COINS):
            coin = _coins[i]
            if coin == utils.ADDRESS_ZERO:
                break
            self.coins[i] = coin
            self.rate_multipliers[i] = _rate_multipliers[i]

        A = _A * self.A_PRECISION
        self.initial_A = A
        self.future_A = A
        self.fee = _fee
        self.ma_exp_time = 866  # = 600 / ln(2)
        self.unpacked_last_price = 10 ** 18
        self.unpacked_ma_price = 10 ** 18
        self.ma_last_time = block_timestamp

    # @view
    # @external
    def last_price(self):
        return self.unpacked_last_price

    # @view
    # @external
    def ema_price(self):
        return self.unpacked_ma_price

    # @view
    # @external
    def get_balances(self):
        return self.balances

    # @view
    # @internal
    def _A(self, block_timestamp):
        """
        Handle ramping A up or down
        """
        t1 = self.future_A_time
        A1 = self.future_A

        if block_timestamp < t1:
            A0 = self.initial_A
            t0 = self.initial_A_time
            # Expressions in uint256 cannot have negative numbers, thus "if"
            if A1 > A0:
                return A0 + (A1 - A0) * (block_timestamp - t0) // (t1 - t0)
            else:
                return A0 - (A0 - A1) * (block_timestamp - t0) // (t1 - t0)

        else:  # when t1 == 0 or block.timestamp >= t1
            return A1

    # @view
    # @external
    def admin_fee(self):
        return self.ADMIN_FEE

    # @view
    # @external
    def A(self, block_timestamp):
        return self._A(block_timestamp) // self.A_PRECISION

    # @view
    # @external
    def A_precise(self, block_timestamp):
        return self._A(block_timestamp)

    # @pure
    # @internal
    def _xp_mem(self, _rates, _balances):
        result = [0 for _ in range(self.N_COINS)]
        for i in range(self.N_COINS):
            result[i] = _rates[i] * _balances[i] // self.PRECISION
        return result

    # @pure
    # @internal
    def get_D(self, _xp, _amp):
        """
        D invariant calculation in non-overflowing integer operations
        iteratively

        A * sum(x_i) * n**n + D = A * D * n**n + D**(n+1) / (n**n * prod(x_i))

        Converging solution:
        D[j+1] = (A * n**n * sum(x_i) - D[j]**(n+1) / (n**n prod(x_i))) / (A * n**n - 1)
        """
        S = 0
        for x in _xp:
            S += x
        if S == 0:
            return 0

        D = S
        Ann = _amp * self.N_COINS
        for i in range(255):
            D_P = D * D // _xp[0] * D // _xp[1] // self.N_COINS ** self.N_COINS
            Dprev = D
            D = (Ann * S // self.A_PRECISION + D_P * self.N_COINS) * D // ((Ann - self.A_PRECISION) * D // self.A_PRECISION + (self.N_COINS + 1) * D_P)
            # Equality with the precision of 1
            if D > Dprev:
                if D - Dprev <= 1:
                    return D
            else:
                if Dprev - D <= 1:
                    return D
        # convergence typically occurs in 4 rounds or less, this should be unreachable!
        # if it does happen the pool is borked and LPs can withdraw via `remove_liquidity`
        raise

    # @view
    # @internal
    def get_D_mem(self, _rates, _balances, _amp):
        xp = self._xp_mem(_rates, _balances)
        return self.get_D(xp, _amp)

    # @internal
    # @view
    def _get_p(self, xp, amp, D):
        # dx_0 / dx_1 only, however can have any number of coins in pool
        ANN = amp * self.N_COINS
        Dr = D // (self.N_COINS ** self.N_COINS)
        for i in range(self.N_COINS):
            Dr = Dr * D // xp[i]
        return 10**18 * (ANN * xp[0] // self.A_PRECISION + Dr * xp[0] // xp[1]) // (ANN * xp[0] // self.A_PRECISION + Dr)

    # @external
    # @view
    def get_p(self, block_timestamp):
        amp = self._A(block_timestamp)
        xp = self._xp_mem(self.rate_multipliers, self.balances)
        D = self.get_D(xp, amp)
        return self._get_p(xp, amp, D)

    # @internal
    # @view
    def exp(self, power):
        if power <= -42139678854452767551:
            return 0

        if power >= 135305999368893231589:
            raise "exp overflow"

        x = utils.utils.unsafe_div(utils.unsafe_mul(power, 2**96), 10**18)

        k = utils.unsafe_div(
            utils.unsafe_add(
                utils.unsafe_div(utils.unsafe_mul(x, 2**96), 54916777467707473351141471128),
                2**95),
            2**96)
        x = utils.unsafe_sub(x, utils.unsafe_mul(k, 54916777467707473351141471128))

        y = utils.unsafe_add(x, 1346386616545796478920950773328)
        y = utils.unsafe_add(utils.unsafe_div(utils.unsafe_mul(y, x), 2**96), 57155421227552351082224309758442)
        p = utils.unsafe_sub(utils.unsafe_add(y, x), 94201549194550492254356042504812)
        p = utils.unsafe_add(utils.unsafe_div(utils.unsafe_mul(p, y), 2**96), 28719021644029726153956944680412240)
        p = utils.unsafe_add(utils.unsafe_mul(p, x), (4385272521454847904659076985693276 * 2**96))

        q = x - 2855989394907223263936484059900
        q = utils.unsafe_add(utils.unsafe_div(utils.unsafe_mul(q, x), 2**96), 50020603652535783019961831881945)
        q = utils.unsafe_sub(utils.unsafe_div(utils.unsafe_mul(q, x), 2**96), 533845033583426703283633433725380)
        q = utils.unsafe_add(utils.unsafe_div(utils.unsafe_mul(q, x), 2**96), 3604857256930695427073651918091429)
        q = utils.unsafe_sub(utils.unsafe_div(utils.unsafe_mul(q, x), 2**96), 14423608567350463180887372962807573)
        q = utils.unsafe_add(utils.unsafe_div(utils.unsafe_mul(q, x), 2**96), 26449188498355588339934803723976023)

        return utils.shift(
            utils.unsafe_mul(utils.unsafe_div(p, q), 3822833074963236453042738258902158003155416615667),
            utils.unsafe_sub(k, 195))

    # @internal
    # @view
    def _ma_price(self, block_timestamp):
        ma_last_time = self.ma_last_time

        last_price = self.unpacked_last_price
        last_ema_price = self.unpacked_ma_price

        if ma_last_time < block_timestamp:
            alpha = self.exp(- (block_timestamp - ma_last_time) * 10**18 // self.ma_exp_time)
            return (last_price * (10**18 - alpha) + last_ema_price * alpha) // 10**18

        else:
            return last_ema_price

    # @external
    # @view
    def price_oracle(self, block_timestamp):
        return self._ma_price(block_timestamp)

    # @internal
    def save_p_from_price(self, block_timestamp, last_price):
        """
        Saves current price and its EMA
        """
        if last_price != 0:
            self.unpacked_last_price = last_price
            self.unpacked_ma_price  = self._ma_price(block_timestamp)
            # self.pack_prices(last_price, self._ma_price(block_timestamp))
            if self.ma_last_time < block_timestamp:
                self.ma_last_time = block_timestamp

    # @internal
    def save_p(self, block_timestamp, xp, amp, D):
        """
        Saves current price and its EMA
        """
        self.save_p_from_price(block_timestamp, self._get_p(xp, amp, D))

    # @view
    # @external
    def get_virtual_price(self, block_timestamp):
        """
        @notice The current virtual price of the pool LP token
        @dev Useful for calculating profits
        @return LP token virtual price normalized to 1e18
        """
        amp = self._A(block_timestamp)
        xp = self._xp_mem(self.rate_multipliers, self.balances)
        D = self.get_D(xp, amp)
        # D is in the units similar to DAI (e.g. converted to precision 1e18)
        # When balanced, D = n * x_u - total virtual value of the portfolio
        return D * self.PRECISION // self.totalSupply


    # @view
    # @external
    def calc_token_amount(self, _amounts, _is_deposit):
        """
        @notice Calculate addition or reduction in token supply from a deposit or withdrawal
        @param _amounts Amount of each coin being deposited
        @param _is_deposit set True for deposits, False for withdrawals
        @return Expected amount of LP tokens received
        """
        amp = self._A()
        old_balances = self.balances
        rates = self.rate_multipliers

        # Initial invariant
        D0 = self.get_D_mem(rates, old_balances, amp)

        total_supply = self.totalSupply
        new_balances = old_balances
        for i in range(self.N_COINS):
            amount = _amounts[i]
            if _is_deposit:
                new_balances[i] += amount
            else:
                new_balances[i] -= amount

        # Invariant after change
        D1 = self.get_D_mem(rates, new_balances, amp)

        # We need to recalculate the invariant accounting for fees
        # to calculate fair user's share
        D2 = D1
        if total_supply > 0:
            # Only account for fees if we are not the first to deposit
            base_fee = self.fee * self.N_COINS // (4 * (self.N_COINS - 1))
            for i in range(self.N_COINS):
                ideal_balance = D1 * old_balances[i] // D0
                difference = 0
                new_balance = new_balances[i]
                if ideal_balance > new_balance:
                    difference = ideal_balance - new_balance
                else:
                    difference = new_balance - ideal_balance
                new_balances[i] -= base_fee * difference // self.FEE_DENOMINATOR
            xp = self._xp_mem(rates, new_balances)
            D2 = self.get_D(xp, amp)
        else:
            return D1  # Take the dust if there was any


        diff = 0
        if _is_deposit:
            diff = D2 - D0
        else:
            diff = D0 - D2
        return diff * total_supply // D0


    # @external
    # @nonreentrant('lock')
    def add_liquidity(self, block_timestamp, _amounts):
        """
        @notice Deposit coins into the pool
        @param _amounts List of amounts of coins to deposit
        @param _min_mint_amount Minimum amount of LP tokens to mint from the deposit
        @param _receiver Address that owns the minted LP tokens
        @return Amount of LP tokens received by depositing
        """
        amp = self._A(block_timestamp)
        old_balances = self.balances
        rates = self.rate_multipliers

        # Initial invariant
        D0 = self.get_D_mem(rates, old_balances, amp)

        total_supply = self.totalSupply
        new_balances = old_balances
        for i in range(self.N_COINS):
            amount = _amounts[i]
            if amount > 0:
                new_balances[i] += amount
            else:
                assert total_supply != 0  # dev: initial deposit requires all coins

        # Invariant after change
        D1 = self.get_D_mem(rates, new_balances, amp)
        assert D1 > D0

        # We need to recalculate the invariant accounting for fees
        # to calculate fair user's share
        fees = [0 for _ in range(self.N_COINS)]
        mint_amount = 0

        if total_supply > 0:
            # Only account for fees if we are not the first to deposit
            base_fee = self.fee * self.N_COINS // (4 * (self.N_COINS - 1))
            for i in range(self.N_COINS):
                ideal_balance = D1 * old_balances[i] // D0
                difference = 0
                new_balance = new_balances[i]
                if ideal_balance > new_balance:
                    difference = ideal_balance - new_balance
                else:
                    difference = new_balance - ideal_balance
                fees[i] = base_fee * difference // self.FEE_DENOMINATOR
                self.balances[i] = new_balance - (fees[i] * self.ADMIN_FEE // self.FEE_DENOMINATOR)
                new_balances[i] -= fees[i]

            xp = self._xp_mem(rates, new_balances)
            D2 = self.get_D(xp, amp)
            mint_amount = total_supply * (D2 - D0) // D0
            self.save_p(block_timestamp, xp, amp, D2)

        else:
            self.balances = new_balances
            mint_amount = D1  # Take the dust if there was any

        # Mint pool tokens
        total_supply += mint_amount
        self.totalSupply = total_supply

        return mint_amount


    # @view
    # @internal
    def get_y(self, block_timestamp, i, j, x, xp, _amp, _D):
        """
        Calculate x[j] if one makes x[i] = x

        Done by solving quadratic equation iteratively.
        x_1**2 + x_1 * (sum' - (A*n**n - 1) * D / (A * n**n)) = D ** (n + 1) / (n ** (2 * n) * prod' * A)
        x_1**2 + b*x_1 = c

        x_1 = (x_1**2 + c) / (2*x_1 + b)
        """
        # x in the input is converted to the same price/precision

        assert i != j       # dev: same coin
        assert j >= 0       # dev: j below zero
        assert j < self.N_COINS_128  # dev: j above N_COINS

        # should be unreachable, but good for safety
        assert i >= 0
        assert i < self.N_COINS_128

        amp = _amp
        D = _D
        if _D == 0:
            amp = self._A(block_timestamp)
            D = self.get_D(xp, amp)
        S_ = 0
        _x = 0
        y_prev = 0
        c = D
        Ann = amp * self.N_COINS

        for _i in range(self.N_COINS_128):
            if _i == i:
                _x = x
            elif _i != j:
                _x = xp[_i]
            else:
                continue
            S_ += _x
            c = c * D // (_x * self.N_COINS)

        c = c * D * self.A_PRECISION // (Ann * self.N_COINS)
        b = S_ + D * self.A_PRECISION // Ann  # - D
        y = D

        for _i in range(255):
            y_prev = y
            y = (y * y + c) // (2 * y + b - D)
            # Equality with the precision of 1
            if y > y_prev:
                if y - y_prev <= 1:
                    return y
            else:
                if y_prev - y <= 1:
                    return y
        raise


    # @view
    # @external
    def get_dy(self, block_timestamp, i, j, dx):
        """
        @notice Calculate the current output dy given input dx
        @dev Index values can be found via the `coins` public getter method
        @param i Index value for the coin to send
        @param j Index valie of the coin to recieve
        @param dx Amount of `i` being exchanged
        @return Amount of `j` predicted
        """
        rates = self.rate_multipliers
        xp = self._xp_mem(rates, self.balances)

        x = xp[i] + (dx * rates[i] // self.PRECISION)
        y = self.get_y(block_timestamp, i, j, x, xp, 0, 0)
        dy = xp[j] - y - 1
        fee = self.fee * dy // self.FEE_DENOMINATOR
        return (dy - fee) * self.PRECISION // rates[j]


    # @view
    # @external
    def get_dx(self, block_timestamp, i, j, dy):
        """
        @notice Calculate the current input dx given output dy
        @dev Index values can be found via the `coins` public getter method
        @param i Index value for the coin to send
        @param j Index valie of the coin to recieve
        @param dy Amount of `j` being received after exchange
        @return Amount of `i` predicted
        """
        rates = self.rate_multipliers
        xp = self._xp_mem(rates, self.balances)

        y = xp[j] - (dy * rates[j] // self.PRECISION + 1) * self.FEE_DENOMINATOR // (self.FEE_DENOMINATOR - self.fee)
        x = self.get_y(block_timestamp, j, i, y, xp, 0, 0)
        return (x - xp[i]) * self.PRECISION // rates[i]


    # @external
    # @nonreentrant('lock')
    def exchange(self, block_timestamp, i, j, _dx):
        """
        @notice Perform an exchange between two coins
        @dev Index values can be found via the `coins` public getter method
        @param i Index value for the coin to send
        @param j Index valie of the coin to recieve
        @param _dx Amount of `i` being exchanged
        @param _min_dy Minimum amount of `j` to receive
        @return Actual amount of `j` received
        """
        rates = self.rate_multipliers
        old_balances = self.balances
        xp = self._xp_mem(rates, old_balances)

        x = xp[i] + _dx * rates[i] // self.PRECISION

        amp = self._A(block_timestamp)
        D = self.get_D(xp, amp)
        y = self.get_y(block_timestamp, i, j, x, xp, amp, D)

        dy = xp[j] - y - 1  # -1 just in case there were some rounding errors
        dy_fee = dy * self.fee // self.FEE_DENOMINATOR

        # Convert all to real units
        dy = (dy - dy_fee) * self.PRECISION // rates[j]

        # xp is not used anymore, so we reuse it for price calc
        xp[i] = x
        xp[j] = y
        # D is not changed because we did not apply a fee
        self.save_p(block_timestamp, xp, amp, D)

        dy_admin_fee = dy_fee * self.ADMIN_FEE // self.FEE_DENOMINATOR
        dy_admin_fee = dy_admin_fee * self.PRECISION // rates[j]

        # Change balances exactly in same way as we change actual ERC20 coin amounts
        self.balances[i] = old_balances[i] + _dx
        # When rounding errors happen, we undercharge admin fee in favor of LP
        self.balances[j] = old_balances[j] - dy - dy_admin_fee

        return dy


    # @external
    # @nonreentrant('lock')
    def remove_liquidity(self, _burn_amount):
        """
        @notice Withdraw coins from the pool
        @dev Withdrawal amounts are based on current deposit ratios
        @param _burn_amount Quantity of LP tokens to burn in the withdrawal
        @param _min_amounts Minimum amounts of underlying coins to receive
        @param _receiver Address that receives the withdrawn coins
        @return List of amounts of coins that were withdrawn
        """
        total_supply = self.totalSupply
        amounts = [0 for _ in range(self.N_COINS)]

        for i in range(self.N_COINS):
            old_balance = self.balances[i]
            value = old_balance * _burn_amount // total_supply
            self.balances[i] = old_balance - value
            amounts[i] = value

        total_supply -= _burn_amount
        self.totalSupply = total_supply

        return amounts


    # @external
    # @nonreentrant('lock')
    def remove_liquidity_imbalance(self, block_timestamp, _amounts):
        """
        @notice Withdraw coins from the pool in an imbalanced amount
        @param _amounts List of amounts of underlying coins to withdraw
        @param _max_burn_amount Maximum amount of LP token to burn in the withdrawal
        @param _receiver Address that receives the withdrawn coins
        @return Actual amount of the LP token burned in the withdrawal
        """
        amp = self._A(block_timestamp)
        rates = self.rate_multipliers
        old_balances = self.balances
        D0 = self.get_D_mem(rates, old_balances, amp)

        new_balances = old_balances
        for i in range(self.N_COINS):
            amount = _amounts[i]
            if amount != 0:
                new_balances[i] -= amount

        D1 = self.get_D_mem(rates, new_balances, amp)

        fees = [0 for _ in range(self.N_COINS)]
        base_fee = self.fee * self.N_COINS // (4 * (self.N_COINS - 1))
        for i in range(self.N_COINS):
            ideal_balance = D1 * old_balances[i] // D0
            difference = 0
            new_balance = new_balances[i]
            if ideal_balance > new_balance:
                difference = ideal_balance - new_balance
            else:
                difference = new_balance - ideal_balance
            fees[i] = base_fee * difference // self.FEE_DENOMINATOR
            self.balances[i] = new_balance - (fees[i] * self.ADMIN_FEE // self.FEE_DENOMINATOR)
            new_balances[i] -= fees[i]
        new_balances = self._xp_mem(rates, new_balances)
        D2 = self.get_D(new_balances, amp)

        self.save_p(block_timestamp, new_balances, amp, D2)

        total_supply = self.totalSupply
        burn_amount = ((D0 - D2) * total_supply // D0) + 1
        assert burn_amount > 1  # dev: zero tokens burned

        total_supply -= burn_amount
        self.totalSupply = total_supply

        return burn_amount


    # @pure
    # @internal
    def get_y_D(self, A, i, xp, D):
        """
        Calculate x[i] if one reduces D from being calculated for xp to D

        Done by solving quadratic equation iteratively.
        x_1**2 + x_1 * (sum' - (A*n**n - 1) * D / (A * n**n)) = D ** (n + 1) / (n ** (2 * n) * prod' * A)
        x_1**2 + b*x_1 = c

        x_1 = (x_1**2 + c) / (2*x_1 + b)
        """
        # x in the input is converted to the same price/precision

        assert i >= 0  # dev: i below zero
        assert i < self.N_COINS_128  # dev: i above N_COINS

        S_ = 0
        _x = 0
        y_prev = 0
        c = D
        Ann = A * self.N_COINS

        for _i in range(self.N_COINS_128):
            if _i != i:
                _x = xp[_i]
            else:
                continue
            S_ += _x
            c = c * D // (_x * self.N_COINS)

        c = c * D * self.A_PRECISION // (Ann * self.N_COINS)
        b = S_ + D * self.A_PRECISION // Ann
        y = D

        for _i in range(255):
            y_prev = y
            y = (y*y + c) // (2 * y + b - D)
            # Equality with the precision of 1
            if y > y_prev:
                if y - y_prev <= 1:
                    return y
            else:
                if y_prev - y <= 1:
                    return y
        raise


    # @view
    # @internal
    def _calc_withdraw_one_coin(self, block_timestamp, _burn_amount, i):
        # First, need to calculate
        # * Get current D
        # * Solve Eqn against y_i for D - _token_amount
        amp = self._A(block_timestamp)
        rates = self.rate_multipliers
        xp = self._xp_mem(rates, self.balances)
        D0 = self.get_D(xp, amp)

        total_supply = self.totalSupply
        D1 = D0 - _burn_amount * D0 // total_supply
        new_y = self.get_y_D(amp, i, xp, D1)

        base_fee = self.fee * self.N_COINS // (4 * (self.N_COINS - 1))
        xp_reduced = [0 for _ in range(self.N_COINS)]

        for j in range(self.N_COINS_128):
            dx_expected = 0
            xp_j = xp[j]
            if j == i:
                dx_expected = xp_j * D1 // D0 - new_y
            else:
                dx_expected = xp_j - xp_j * D1 // D0
            xp_reduced[j] = xp_j - base_fee * dx_expected // self.FEE_DENOMINATOR

        dy = xp_reduced[i] - self.get_y_D(amp, i, xp_reduced, D1)
        dy_0 = (xp[i] - new_y) * self.PRECISION // rates[i]  # w/o fees
        dy = (dy - 1) * self.PRECISION // rates[i]  # Withdraw less to account for rounding errors

        xp[i] = new_y
        last_p = 0
        if new_y > 0:
            last_p = self._get_p(xp, amp, D1)

        return [dy, dy_0 - dy, last_p]


    # @view
    # @external
    def calc_withdraw_one_coin(self, block_timestamp, _burn_amount, i):
        """
        @notice Calculate the amount received when withdrawing a single coin
        @param _burn_amount Amount of LP tokens to burn in the withdrawal
        @param i Index value of the coin to withdraw
        @return Amount of coin received
        """
        return self._calc_withdraw_one_coin(block_timestamp, _burn_amount, i)[0]


    # @external
    # @nonreentrant('lock')
    def remove_liquidity_one_coin(self, block_timestamp, _burn_amount, i):
        """
        @notice Withdraw a single coin from the pool
        @param _burn_amount Amount of LP tokens to burn in the withdrawal
        @param i Index value of the coin to withdraw
        @param _min_received Minimum amount of coin to receive
        @param _receiver Address that receives the withdrawn coins
        @return Amount of coin received
        """
        dy = self._calc_withdraw_one_coin(block_timestamp, _burn_amount, i)

        self.balances[i] -= (dy[0] + dy[1] * self.ADMIN_FEE // self.FEE_DENOMINATOR)
        total_supply = self.totalSupply - _burn_amount
        self.totalSupply = total_supply

        self.save_p_from_price(block_timestamp, dy[2])

        return dy[0]