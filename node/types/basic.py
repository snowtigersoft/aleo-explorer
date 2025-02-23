import socket
import struct
from decimal import Decimal

from .traits import *


class Bech32m:

    def __init__(self, data: bytes, prefix: str):
        self.data = data
        self.prefix = prefix

    def __str__(self):
        return aleo.bech32_encode(self.prefix, self.data)

    def __repr__(self):
        return str(self)


class IntProtocol(Sized, Compare, AddWrapped, SubWrapped, MulWrapped, DivWrapped, And, Or, Xor, Not, Shl, Shr, RemWrapped, Protocol):
    min: int
    max: int

class Int(int, Serializable, IntProtocol):
    size = -1
    min = 2**256
    max = -2**256

    def __new__(cls, value: int | Decimal = 0):
        if isinstance(value, Decimal):
            value = int(value)
        if not cls.min <= value <= cls.max:
            raise OverflowError(f"value {value} out of range for {cls.__name__}")
        return int.__new__(cls, value)

    @classmethod
    def loads(cls, value: str):
        value = value.replace(cls.__name__, "")
        return cls(int(value))

    def __add__(self, other: int | Self):
        if type(other) is int:
            return self.__class__(int.__add__(self, other))
        if type(other) is not type(self):
            raise TypeError("unsupported operand type(s) for +: '{}' and '{}'".format(type(self), type(other)))
        return self.__class__(int.__add__(self, other))

    @classmethod
    def wrap_value(cls, value: int):
        if value < 0:
            value &= cls.max
        elif value > cls.max:
            if cls.min == 0:
                value = value & cls.max
            else:
                value = value & ((cls.max << 1) + 1)
                value = (value & cls.max) + cls.min
        return value

    def add_wrapped(self, other: int | Self):
        if isinstance(other, Int):
            other = int(other)
        value = int(self) + other
        return self.__class__(self.wrap_value(value))


    def __sub__(self, other: int | Self):
        if type(other) is int:
            return self.__class__(int.__sub__(self, other))
        if type(other) is not type(self):
            raise TypeError("unsupported operand type(s) for -: '{}' and '{}'".format(type(self), type(other)))
        return self.__class__(int.__sub__(self, other))

    def sub_wrapped(self, other: int | Self):
        if isinstance(other, Int):
            other = int(other)
        value = int(self) - other
        return self.__class__(self.wrap_value(value))

    def __mul__(self, other: int | Self):
        if type(other) is int:
            return self.__class__(int.__mul__(self, other))
        if type(other) is not type(self):
            raise TypeError("unsupported operand type(s) for *: '{}' and '{}'".format(type(self), type(other)))
        return self.__class__(int.__mul__(self, other))

    def mul_wrapped(self, other: int | Self):
        if isinstance(other, Int):
            other = int(other)
        value = int(self) * other
        return self.__class__(self.wrap_value(value))

    def __eq__(self, other: object):
        if type(other) is int:
            return int.__eq__(self, other)
        if type(other) is not type(self):
            return False
        return int.__eq__(self, other)

    def __hash__(self):
        return int.__hash__(self)

    def __invert__(self):
        if self.min == 0:
            return self.__class__(~int(self) & self.max)
        return self.__class__(~int(self))

    # we are deviating from python's insane behavior here
    # this is actually __truncdiv__
    def __floordiv__(self, other: int | Self):
        if type(other) is int:
            return self.__class__(int(self / other))
        if type(other) is not type(self):
            raise TypeError("unsupported operand type(s) for //: '{}' and '{}'".format(type(self), type(other)))
        if other == 0:
            raise ZeroDivisionError("division by zero")
        return self.__class__(int(self / other))

    def div_wrapped(self, other: int | Self):
        if isinstance(other, Int):
            other = int(other)
        value = int(int(self) / other)
        return self.__class__(self.wrap_value(value))

    def __lshift__(self, other: int | Self):
        if type(other) is int:
            return self.__class__(int.__lshift__(self, other))
        if not issubclass(type(other), Int):
            raise TypeError("unsupported operand type(s) for <<: '{}' and '{}'".format(type(self), type(other)))
        return self.__class__(int.__lshift__(self, other))

    def __rshift__(self, other: int | Self):
        if type(other) is int:
            return self.__class__(int.__rshift__(self, other))
        if not issubclass(type(other), Int):
            raise TypeError("unsupported operand type(s) for >>: '{}' and '{}'".format(type(self), type(other)))
        return self.__class__(int.__rshift__(self, other))

    def __and__(self, other: int | Self):
        if type(other) is int:
            return self.__class__(int.__and__(self, other))
        if not issubclass(type(other), Int):
            raise TypeError("unsupported operand type(s) for &: '{}' and '{}'".format(type(self), type(other)))
        return self.__class__(int.__and__(self, other))

    def __or__(self, other: int | Self):
        if type(other) is int:
            return self.__class__(int.__or__(self, other))
        if not issubclass(type(other), Int):
            raise TypeError("unsupported operand type(s) for |: '{}' and '{}'".format(type(self), type(other)))
        return self.__class__(int.__or__(self, other))

    def __mod__(self, other: int | Self):
        if type(other) is int:
            return self.__class__(int.__mod__(self, other))
        if not issubclass(type(other), Int):
            raise TypeError("unsupported operand type(s) for %: '{}' and '{}'".format(type(self), type(other)))
        return self.__class__(int.__mod__(self, other))

    def mod_wrapped(self, other: int | Self):
        return self.__mod__(other)

    def dump(self) -> bytes:
        raise TypeError("cannot deserialize Int base class")

    @classmethod
    def load(cls, data: BytesIO) -> Self:
        raise TypeError("cannot serialize Int base class")


class IntEnumu8(Serializable, IntEnum, metaclass=ProtocolEnumMeta):

    def dump(self) -> bytes:
        return struct.pack("<B", self.value)

    @classmethod
    def load(cls, data: BytesIO):
        if data.tell() >= data.getbuffer().nbytes:
            raise ValueError("incorrect length")
        self = cls(struct.unpack("<B", data.read(1))[0])
        return self


class IntEnumu16(Serializable, IntEnum, metaclass=ProtocolEnumMeta):

    def dump(self) -> bytes:
        return struct.pack("<H", self.value)

    @classmethod
    def load(cls, data: BytesIO):
        if data.tell() + 2 > data.getbuffer().nbytes:
            raise ValueError("incorrect length")
        self = cls(struct.unpack("<H", data.read(2))[0])
        return self


class IntEnumu32(Serializable, IntEnum, metaclass=ProtocolEnumMeta):

    def dump(self) -> bytes:
        return struct.pack("<I", self.value)

    @classmethod
    def load(cls, data: BytesIO):
        if data.tell() + 4 > data.getbuffer().nbytes:
            raise ValueError("incorrect length")
        self = cls(struct.unpack("<I", data.read(4))[0])
        return self


class u8(Int):
    size = 1
    min = 0
    max = 255

    def dump(self) -> bytes:
        return struct.pack("<B", self)

    @classmethod
    def load(cls, data: BytesIO):
        self = cls(struct.unpack("<B", data.read(1))[0])
        return self


class u16(Int):
    size = 2
    min = 0
    max = 65535

    def dump(self) -> bytes:
        return struct.pack("<H", self)

    @classmethod
    def load(cls, data: BytesIO):
        self = cls(struct.unpack("<H", data.read(2))[0])
        return self


class u32(Int):
    size = 4
    min = 0
    max = 4294967295

    def dump(self) -> bytes:
        return struct.pack("<I", self)

    @classmethod
    def load(cls, data: BytesIO):
        self = cls(struct.unpack("<I", data.read(4))[0])
        return self


class u64(Int):
    size = 8
    min = 0
    max = 18446744073709551615

    def dump(self) -> bytes:
        return struct.pack("<Q", self)

    @classmethod
    def load(cls, data: BytesIO):
        self = cls(struct.unpack("<Q", data.read(8))[0])
        return self

# Obviously we only support 64bit
usize = u64

class u128(Int):
    size = 16
    min = 0
    max = 340282366920938463463374607431768211455

    def dump(self) -> bytes:
        return struct.pack("<QQ", self & 0xFFFF_FFFF_FFFF_FFFF, self >> 64)

    @classmethod
    def load(cls, data: BytesIO):
        lo, hi = struct.unpack("<QQ", data.read(16))
        self = cls((hi << 64) | lo)
        return self


class i8(Int):
    size = 1
    min = -128
    max = 127

    def dump(self) -> bytes:
        return struct.pack("<b", self)

    @classmethod
    def load(cls, data: BytesIO):
        self = cls(struct.unpack("<b", data.read(1))[0])
        return self


class i16(Int):
    size = 2
    min = -32768
    max = 32767

    def dump(self) -> bytes:
        return struct.pack("<h", self)

    @classmethod
    def load(cls, data: BytesIO):
        self = cls(struct.unpack("<h", data.read(2))[0])
        return self


class i32(Int):
    size = 4
    min = -2147483648
    max = 2147483647

    def dump(self) -> bytes:
        return struct.pack("<i", self)

    @classmethod
    def load(cls, data: BytesIO):
        self = cls(struct.unpack("<i", data.read(4))[0])
        return self


class i64(Int):
    size = 8
    min = -9223372036854775808
    max = 9223372036854775807

    def dump(self) -> bytes:
        return struct.pack("<q", self)

    @classmethod
    def load(cls, data: BytesIO):
        self = cls(struct.unpack("<q", data.read(8))[0])
        return self


class i128(Int):
    size = 16
    min = -170141183460469231731687303715884105728
    max = 170141183460469231731687303715884105727

    def dump(self) -> bytes:
        return struct.pack("<qq", self & 0xFFFF_FFFF_FFFF_FFFF, self >> 64)

    @classmethod
    def load(cls, data: BytesIO):
        lo, hi = struct.unpack("<qq", data.read(16))
        self = cls((hi << 64) | lo)
        return self


class bool_(Sized, Serializable):

    size = 1

    def __init__(self, value: bool = False):
        self.value = value

    def dump(self) -> bytes:
        return struct.pack("<B", 1 if self else 0)

    @classmethod
    def load(cls, data: BytesIO):
        value = struct.unpack("<B", data.read(1))[0]
        if value == 0:
            value = False
        elif value == 1:
            value = True
        else:
            breakpoint()
            raise ValueError("invalid value for bool")
        self = cls(value)
        return self

    @classmethod
    def loads(cls, value: str):
        if value.lower() == "true":
            return cls(True)
        if value.lower() == "false":
            return cls()
        raise ValueError("invalid value for bool")

    def __str__(self):
        if self:
            return "true"
        return "false"

    def __repr__(self):
        if self:
            return "True"
        return "False"

    def __invert__(self):
        return bool_(not self)

    def __and__(self, other: bool | Self):
        if isinstance(other, bool):
            return bool_(self.value and other)
        return bool_(self.value and other.value)

    def __or__(self, other: bool | Self):
        if isinstance(other, bool):
            return bool_(self.value or other)
        return bool_(self.value or other.value)

    def __bool__(self):
        return self.value

    def __eq__(self, other: object):
        if isinstance(other, bool):
            return self.value == other
        if isinstance(other, bool_):
            return self.value == other.value
        return False

    __match_args__ = ("value",)



class SocketAddr(Serializable):
    def __init__(self, *, ip: int, port: int):
        if ip < 0 or ip > 4294967295:
            raise ValueError("ip must be between 0 and 4294967295")
        if port < 0 or port > 65535:
            raise ValueError("port must be between 0 and 65535")
        self.ip = ip
        self.port = port

    def dump(self) -> bytes:
        raise NotImplementedError

    @classmethod
    def load(cls, data: BytesIO):
        data.read(4)
        ip = u32.load(data)
        port = u16.load(data)
        return cls(ip=ip, port=port)

    def __str__(self):
        return ":".join(self.ip_port())

    def ip_port(self):
        return socket.inet_ntoa(struct.pack('<L', self.ip)), str(self.port)