from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import tyro

# from returns.io import impure
from py312_to_py311.rewriting import rewrite_src


# @impure
def rewrite_file(file: Path, output_file: Optional[Path] = None) -> None:
    src = file.read_text()
    result = rewrite_src(src)
    output_file = output_file or file
    output_file.write_text(result)


@dataclass(frozen=True)
class Single:
    """Process single file"""

    input_file: tyro.conf.Positional[Path]
    output_file: Optional[Path] = None


@dataclass(frozen=True)
class Batch:
    """Process multiple files (implies in-place)"""

    files: tyro.conf.Positional[list[Path]]


def main(cmd: Single | Batch) -> None:
    match cmd:
        case Single(input_file, output_file):
            rewrite_file(input_file, output_file)
        case Batch(files):
            for file in files:
                if file.is_dir():
                    for sub_file in file.rglob(r"*.py"):
                        rewrite_file(sub_file)
                else:
                    rewrite_file(file)


def entrypoint() -> None:
    tyro.cli(main, config=(tyro.conf.OmitSubcommandPrefixes,))


if __name__ == "__main__":
    entrypoint()
