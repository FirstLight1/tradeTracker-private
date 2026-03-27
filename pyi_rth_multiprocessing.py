#-----------------------------------------------------------------------------
# Copyright (c) 2022, PyInstaller Development Team.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
#
# The full license is in the file COPYING.txt, distributed with this software.
#-----------------------------------------------------------------------------

# Runtime hook for multiprocessing to prevent "cannot load module more than once" error
import sys
import os

# Ensure multiprocessing uses 'spawn' on Windows when frozen
if sys.platform.startswith('win') and getattr(sys, 'frozen', False):
    import multiprocessing
    multiprocessing.set_start_method('spawn', force=True)
