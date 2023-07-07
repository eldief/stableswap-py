UINT_256_MAX = 115792089237316195423570985008687907853269984665640564039457584007913129639935
ADDRESS_ZERO = "0x0000000000000000000000000000000000000000".lower()

def rate_multiplier(decimals):
    return 10 ** (36 - decimals)

def unsafe_div(a, b):
    return int(a // b)

def unsafe_mul(a, b):
    return int(a * b)

def unsafe_add(a, b):
    return int(a + b)

def unsafe_sub(a, b):
    return int(a - b)

def shift(n, p):
    if (p > 0):
        return n << p
    else:
        return n >> (p * -1)
    