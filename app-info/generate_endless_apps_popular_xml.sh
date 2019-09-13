#!/bin/bash

# Refer https://phabricator.endlessm.com/w/software/gnome-software/featured-apps/ for documentation.

for app in $(flatpak remote-ls eos-apps --app --columns=application | grep "com.endless");
do
	cat <<< '<component type="desktop" merge="append">'
	cat <<< '<id>'$app'</id>'
	cat <<< '<kudos>'
	cat <<< '<kudo>GnomeSoftware::popular</kudo>'
	cat <<< '</kudos>'
	cat <<< '<bundle type="flatpak"/>'
	cat <<< '</component>'
done
