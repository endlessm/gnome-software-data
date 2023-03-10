#!/bin/sh

# Copyright 2023 Endless OS Foundation, LLC
# SPDX-License-Identifier: GPL-2.0-or-later

# Validate AppStream catalog.

set -e

PROGDIR=$(dirname "$0")
cd "$PROGDIR"

# Ideally we'd use appstreamcli, but the version in EOS is currently too
# old and has bugs with merge="append" entries.
appstream-util validate --nonet app-info/eos-extra.xml
