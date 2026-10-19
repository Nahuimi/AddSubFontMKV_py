"""打包入口（Nuitka / PyInstaller 共用），等价于 ``python -m asfmkv``。"""

import sys

from asfmkv.cli import main

if __name__ == "__main__":
    sys.exit(main())
