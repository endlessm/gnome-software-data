# Copyright 2023 Endless OS Foundation, LLC
# SPDX-License-Identifier: GPL-2.0-or-later

default: all

all update-po:
	@$(MAKE) -C app-info $@

check: all
	./lint.sh
	./validate.sh

sync: check
	./sync-s3.sh

.PHONY: default all update-po check sync
