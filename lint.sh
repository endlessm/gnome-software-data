#!/bin/bash

# Copyright 2023 Endless OS Foundation, LLC
# SPDX-License-Identifier: GPL-2.0-or-later

# Very simple lint driver. This is primarily because shellcheck needs to
# be told the files to check as arguments.

set -e

PROGDIR=$(dirname "$0")
cd "$PROGDIR"

# Python
flake8

# Shell
#
# Gather the scripts into an array first. This assumes all the shell
# scripts have a .sh suffix.
readarray -t shell_scripts < <(git ls-files -- '*.sh')
shellcheck "${shell_scripts[@]}"
