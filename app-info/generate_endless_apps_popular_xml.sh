#!/bin/bash

# Refer https://phabricator.endlessm.com/w/software/gnome-software/featured-apps/ for documentation.

IFS=$'\n'; for row in $(flatpak remote-ls eos-apps --app --columns=application,ref | grep "com.endless");
do
	IFS=$'\t '
	cells=($row)
	app_id=${cells[0]}
	ref=${cells[1]}
	cat <<< '  <component type="desktop" merge="append">'
	cat <<< '    <id>'$app_id'</id>'
	cat <<< '    <kudos>'
	cat <<< '      <kudo>GnomeSoftware::popular</kudo>'
	cat <<< '    </kudos>'
	cat <<< '    <bundle type="flatpak">'$ref'</bundle>'
	cat <<< '  </component>'
done
