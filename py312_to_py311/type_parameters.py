from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import (
    ClassVar,
    Literal,
    Self,
)

from ast_grep_py import SgNode


def _parse_maybe_splat(
    kind_and_node: KindAndNode[Literal["type"]],
) -> tuple[type[TypeIntroduction], str]:
    text = kind_and_node.node.text()
    if text.find("**") != -1:
        return (ParamSpecIntroduction, text[2:])
    elif text.find("*") != -1:
        return (TypeVarTupleIntroduction, text[1:])
    else:
        return (IdentifierIntroduction, text)


def _parse_type(node: SgNode) -> TypeIntroduction:
    match node.kind():
        case "constrained_type":
            lhs, rhs = node.children()[0:2]
            lhs = KindAndNode[Literal["type"]]("type", lhs)
            rhs = KindAndNode[Literal["type"]]("type", rhs)
            lhs_type, lhs_identifier = _parse_maybe_splat(lhs)
            assert lhs_type is IdentifierIntroduction
            return IdentifierIntroduction(
                ConstrainedType(
                    identifier=lhs_identifier, constraint_text=rhs.node.text()
                )
            )
        case "identifier" | "splat_type":
            return IdentifierIntroduction(UnconstrainedType(node.text()))
        case _ as t:
            raise ValueError(f"Incorrect type: {t}")


def type_parameter_collect_type_introductions(
    type_parameter: TypeParameterNode,
) -> list[TypeIntroduction]:
    result: list[TypeIntroduction] = []
    for type_ in type_parameter.node.children():
        kinded_type = KindAndNode[Literal["type"]]("type", type_)
        child_of_type = kinded_type.node.child(0)
        if child_of_type is None:
            raise RuntimeError("Somehow child of 'type' is None")
        result.append(_parse_type(child_of_type))
    return result


@dataclass
class UnconstrainedType:
    identifier: str

    def generate_type_var(
        self, type_of_constraint: Literal["TypeVar", "TypeVarTuple", "ParamSpec"]
    ) -> str:
        return f'{self.identifier} = {type_of_constraint}("{self.identifier}")'


@dataclass
class ConstrainedType:
    identifier: str
    constraint_text: str

    _regex_for_replacing_in_constraint_text: ClassVar[re.Pattern] = re.compile(
        r"[\s\n]*", flags=re.MULTILINE
    )

    def __post_init__(self) -> None:
        self.constraint_text = "".join(
            self._regex_for_replacing_in_constraint_text.split(self.constraint_text)
        )
        logging.debug(self.constraint_text)

    def generate_type_var(self) -> str:
        return f'{self.identifier} = TypeVar("{self.identifier}", bound="{self.constraint_text}")'


@dataclass
class IdentifierIntroduction:
    type_: UnconstrainedType | ConstrainedType

    def generate_type_var(self) -> str:
        return (
            self.type_.generate_type_var("TypeVar")
            if isinstance(self.type_, UnconstrainedType)
            else self.type_.generate_type_var()
        )


@dataclass
class TypeVarTupleIntroduction:
    type_: UnconstrainedType

    def generate_type_var(self) -> str:
        return self.type_.generate_type_var("TypeVarTuple")


@dataclass
class ParamSpecIntroduction:
    type_: UnconstrainedType

    def generate_type_var(self) -> str:
        return self.type_.generate_type_var("ParamSpec")


type TypeIntroduction = (
    IdentifierIntroduction | TypeVarTupleIntroduction | ParamSpecIntroduction
)


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
