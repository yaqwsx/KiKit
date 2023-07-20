# SPDX-FileCopyrightText: 2023 Jan Mrázek <email@honzamrazek.cz>
#
# SPDX-License-Identifier: MIT

from ._version import get_versions
__version__ = get_versions()['version']
del get_versions
