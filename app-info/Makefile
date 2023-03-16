# Copyright 2023 Endless OS Foundation, LLC
# SPDX-License-Identifier: GPL-2.0-or-later

NULL :=

CATALOG := eos-extra.xml
LINGUAS := \
	es \
	fr \
	pt \
	$(NULL)
POT := po/eos-extra.pot
METAINFO_IN := $(wildcard metainfo/*.metainfo.xml.in)
METAINFO_OUT := $(METAINFO_IN:%.in=%)
ALL_METAINFO := $(wildcard metainfo/*.metainfo.xml) $(METAINFO_OUT)
POFILES := $(LINGUAS:%=po/%.po)
MOFILES := $(POFILES:%.po=%.mo)

default: all

all: catalog

catalog: $(CATALOG)
$(CATALOG): $(ALL_METAINFO)
	./generate-eos-extra-appstream

pot: $(POT)
$(POT): $(METAINFO_IN)
	@mkdir -p $(@D)
	xgettext --itstool -o $@ $^

update-po: $(POFILES)
%.po: $(POT)
	@set -e; \
	if [ -f $@ ]; then \
	  cmd="msgmerge -q --update $@ $<"; \
	else \
	  lang=`basename $@ .po`; \
	  cmd="msginit -l $$lang -i $< -o $@ --no-translator"; \
	fi; \
	echo "$$cmd"; \
	$$cmd

%.mo: %.po
	msgfmt -o $@ $<

%.xml: %.xml.in $(MOFILES)
	itstool -j $< -o $@ $(MOFILES)

.PHONY: default all catalog pot update-po
.INTERMEDIATE: $(MOFILES) $(METAINFO_OUT)
