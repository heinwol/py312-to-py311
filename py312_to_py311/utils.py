from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Iterator, Sequence
from copy import copy
from functools import reduce
from typing import (
    Callable,
    Hashable,
    Iterable,
    Never,
    Optional,
    Protocol,
    TypeVar,
)

logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)


def raises(f: Callable[[], Exception]) -> Never:
    raise f()


def flatten[T](seq: Iterable[Iterable[T]]) -> list[T]:
    return reduce(lambda acc, it: acc + list(it), seq, [])


def separate_into_kinds[T, K: Hashable](
    kind_function: Callable[[T], K], seq: Iterable[T]
) -> defaultdict[K, list[T]]:
    result = defaultdict[K, list[T]](lambda: [])
    for item in seq:
        kind = kind_function(item)
        result[kind].append(item)
    return result


def apply_binary[T, V](func: Callable[[T, T], V], seq: Sequence[T]) -> Iterator[V]:
    for i in range(len(seq)):
        for j in range(i + 1, len(seq)):
            yield func(seq[i], seq[j])


def all_binary[T](relation: Callable[[T, T], bool], seq: Sequence[T]) -> bool:
    return all(apply_binary(relation, seq))


def intersperse_with[T](seq: Sequence[T], val: T) -> list[T]:
    if len(seq) <= 1:
        return list(seq)
    result: list[T] = []
    for i in range(len(seq) - 1):
        result.append(seq[i])
        result.append(copy(val))
    result.append(seq[-1])
    return result


# int.__le__()


class Ord(Protocol):
    def __le__(self: _OrdT, other: _OrdT, /) -> bool: ...


_OrdT = TypeVar("_OrdT", bound=Ord)


def argmax[T, O: Ord](func: Callable[[T], O], seq: Iterable[T]) -> Optional[T]:
    max_value_so_far: Optional[O] = None
    argmax_value: Optional[T] = None
    for elt in seq:
        ord_result = func(elt)
        if max_value_so_far is None or max_value_so_far <= ord_result:
            max_value_so_far = ord_result
            argmax_value = elt
    return argmax_value
