from enum import StrEnum

EVAA_ADDRESS = "0:4e9fed5bfb7d79a2078297995f3d85b4badeac8c0d9eab82d3751bf9bc92754a"
BEMO_ADDRESS = "0:cd872fa7c5816052acdf5332260443faec9aacc8c21cca4d92e7f47034d11892"


class OpType(StrEnum):
    burn = "burns"
    internal_transfer = "internal_transfers"


class OpCode(StrEnum):
    burn = hex(0x7BDD97DE)
    internal_transfer = hex(0x178D4519)
