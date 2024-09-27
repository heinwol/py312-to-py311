from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import (
    Any,
    Literal,
    Self,
    overload,
)

from ast_grep_py import SgNode
from returns.maybe import Maybe, Nothing, Some


@dataclass
class KindAndNode[K: str]:
    kind: K
    node: SgNode

    def __post_init__(self) -> None:
        logging.debug(f"{self.kind} == {self.node.kind()}")
        assert self.kind == self.node.kind()

    @classmethod
    def find_all(cls, kind: K, node: SgNode) -> list[Self]:
        return [cls(kind=kind, node=node_) for node_ in node.find_all(kind=cls.kind)]


type TypeParameterNode = KindAndNode[Literal["type_parameter"]]


class NamedChildrenAccessor:
    def __init__(self, node: SgNode | KindAndNode[Any]) -> None:
        self.node: SgNode = node if isinstance(node, SgNode) else node.node
        self._named_children_list: list[SgNode] = [
            child for child in self.node.children() if child.is_named()
        ]

    @overload
    def named_children(self, functoral: Literal[True]) -> list[Self]: ...

    @overload
    def named_children(self, functoral: Literal[False]) -> list[SgNode]: ...

    @overload
    def named_children(self) -> list[Self]: ...

    @overload
    def named_children(self, functoral: bool = True) -> list[SgNode] | list[Self]: ...

    def named_children(self, functoral: bool = True) -> list[SgNode] | list[Self]:
        return (
            self._named_children_list
            if not functoral
            else [type(self)(it) for it in self._named_children_list]
        )

    @overload
    def named_child(self, i: int, functoral: Literal[False]) -> Maybe[SgNode]: ...

    @overload
    def named_child(self, i: int, functoral: Literal[True]) -> Maybe[Self]: ...

    @overload
    def named_child(self, i: int) -> Maybe[Self]: ...

    @overload
    def named_child(self, i: int, functoral: bool = True) -> Maybe[SgNode | Self]: ...

    def named_child(self, i: int, functoral: bool = True) -> Maybe[SgNode | Self]:
        return (
            Some(
                type(self)(self._named_children_list[i])
                if functoral
                else self._named_children_list[i]
            )
            if i < len(self._named_children_list)
            else Nothing
        )
