#!/usr/bin/env bash
# Builds the two prebuilt environments the demo fixture is tested against.
set -euo pipefail
cd "$(dirname "$0")/../demo"
OLD=$(grep -oE '[0-9][0-9.]+' pydantic_service/requirements.txt | head -1)
NEW=${TARGET_PYDANTIC:-2.14.2}
uv venv --python 3.12 -q .venv-old && uv pip install -q --python .venv-old/bin/python "pydantic==$OLD" pytest
uv venv --python 3.12 -q .venv-new && uv pip install -q --python .venv-new/bin/python "pydantic==$NEW" pytest
echo "old=$OLD new=$NEW"
