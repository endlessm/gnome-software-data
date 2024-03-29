## Mechanism by which apps appear in the ‘Featured’ tab in App Center

Firstly, read [the upstream documentation on how Featured apps and Editor’s
Choice work](https://gitlab.gnome.org/GNOME/gnome-software/-/blob/main/doc/vendor-customisation.md#user-content-featured-apps-and-editors-choice)
in GNOME Software.

The Endless-specific infrastructure is:

* Our external-appstream is currently a file named `org.gnome.Software-eos-extra.xml.gz` and can be found in `/var/cache/app-info/xmls/`. The contents of this file are [here](./eos-extra.xml).
* The content of `eos-extra.xml` are published to an [S3 URL](https://appstream.endlessos.org/app-info/eos-extra.xml.gz) via [this job](https://ci.endlessm-sf.com/job/gnome-software-data/).
* The S3 URL [is preset](https://github.com/endlessm/eos-theme/blob/9bd2312ad7650654c09f4267759ea6217a8d9d40/settings/com.endlessm.settings.gschema.override.in#L121) as the `external-appstream-urls` GSetting for `org.gnome.software` when images are built. The external-appstream plugin of gnome-software fetches the file at this S3 URL and places it at `/var/cache/app-info/xmls/org.gnome.Software-eos-extra.xml.gz` on disk.
* We mention `<bundle type="flatpak"/>` in the `eos-extra.xml` so that the wildcard apps created by the external-appstream file can be adopted by the flatpak plugin. See `gs_plugin_adopt_app()`.

GNOME Software picks up the `eos-extra.xml` file as per its `external-appstream-urls`
configuration, using the upstream functionality.

## How to add a Flathub app (or non-com.endless* app) in the ‘Featured’ category?

* Install the `appstream-util`, `gettext`, `gir1.2-appstreamglib-1.0`,
  `itstool` and `make` packages.
* Add the app to [eos-extra.txt](./eos-extra.txt)
* Run [generate-eos-extra-metainfo](./generate-eos-extra-metainfo)
* Run `make` to regenerate the [eos-extra.xml](./eos-extra.xml)
  AppStream catalog
* Commit the result and submit a pull request

## How to add a Progressive Web Application?

* Install the `appstream-util`, `gettext`, `itstool`, `make`,
  `python3-bs4` and `python3-requests` packages.
* Run [pwa-metainfo-generator.py](./pwa-metainfo-generator.py) with the
  website's URL. This will generate or update a metainfo XML template
  file in the [metainfo](./metainfo) directory.
* Edit the metainfo XML until it's in a publishable form. Run `git add
  metainfo` to include a new metainfo XML file.
* If necessary, add screenshots in [s3/screenshots](../s3/screenshots)
  in a subdirectory named by with the generated app ID. Use
  `https://appstream.endlessos.org/` as the base URL. Run `git add
  ../s3/screenshots` to include any new screenshots.
* Run `make` to regenerate the [eos-extra.xml](./eos-extra.xml)
  AppStream catalog. If there are any validation errors, correct them in
  the metainfo file and run `make` again.
* Record the website URL in the [eos-extra-pwa.txt](./eos-extra-pwa.txt)
  file.
* Commit the result and submit a pull request.
