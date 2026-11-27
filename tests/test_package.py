import re

import efatura_ubl_tr


def test_version_is_semver() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+(?:[.-]?\w+)?", efatura_ubl_tr.__version__)
