"""交互界面层：菜单与提示。"""

from .menus import App, check_ff, detect_dependencies, main_menu
from .prompts import check_out_path, show_license, show_message_subset

# 兼容旧名称
loadMain = main_menu
checkFF = check_ff
checkOutPath = check_out_path
showMessageSubset = show_message_subset
cLicense = show_license
