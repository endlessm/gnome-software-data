## Mechanism by which apps appear in the ‘Featured’ tab in App Center

* Our external-appstream is currently a file named `org.gnome.Software-eos-extra.xml.gz` and can be found in `/var/cache/app-info/xmls/`. The contents of this file are [here](./eos-extra.xml).
* The content of `eos-extra.xml` are published to an [S3 URL](https://d3lapyynmdp1i9.cloudfront.net/app-info/eos-extra.xml.gz) via [this job](https://ci.endlessm-sf.com/job/gnome-software-data/).
* The S3 URL [is preset](https://github.com/endlessm/eos-theme/blob/9bd2312ad7650654c09f4267759ea6217a8d9d40/settings/com.endlessm.settings.gschema.override.in#L121) as the `external-appstream-urls` GSetting for `org.gnome.software` when images are built. The external-appstream plugin of gnome-software fetches the file at this S3 URL and places it at `/var/cache/app-info/xmls/org.gnome.Software-eos-extra.xml.gz` on disk.
* The appstream plugin of gnome-software [checks these paths](https://github.com/endlessm/gnome-software/blob/master/plugins/core/gs-plugin-appstream.c#L464-L482) for appstream files availability and creates `GsApp`s for all the apps present in these appstream files. 
* Now comes the `gs_plugin_add_popular` vfunc which is executed on the appstream-plugin. This vfunc creates another set of temporary (or ‘wildcard’) `GsApp` objects based on the fact that the app is marked as a popular app inside the XML. These apps are marked with the `GS_APP_QUIRK_IS_WILDCARD` quirk to denote that it's a wildcard `GsApp` object and then added to the pool of apps (a `GsAppList`) which is passed to subsequent plugins.

NOTE: Wildcard `GsApp` objects are never supposed to be shown in the UI.

* We mention `<bundle type="flatpak"/>` in the `eos-extra.xml` so that the wildcard apps created by the external-appstream file can be adopted by the flatpak plugin. See `gs_plugin_adopt_app`.
* The plugin loader starts a refine operation at the end of completion of `GS_PLUGIN_ACTION_GET_POPULAR` (plugin loader does refine for others actions as well). The main thing to notice here is that regular `GsApp` objects are refined using `gs_plugin_refine_app` and wildcard `GsApp`s are refined using `gs_plugin_refine_wildcard`. Take a look at `gs_plugin_refine_wildcard` for the flatpak plugin. The function first finds a regular `GsApp` corresponding to the wildcard's app-id and then **subsumes** the metadata of the wildcard (one of which is  the popular kudo metadata) into the regular `GsApp` object it found earlier. This is how a regular `GsApp` object gets the popular app kudo via external appstream and a wildcard app bridging.
* Other point to note here is the popular kudo (`<kudo>GnomeSoftware::popular</kudo>`) in the app reflects the apps in the `Featured` category of our app-center. On the upstream gnome-software, these ties to the “Editors’ pick” column. The upstream GNOME Software also has following sub-buckets of featuring an app which doesn't align with our design goals as of now:
   * App banner on landing page - Associated with `GnomeSoftware::FeatureTile-css` metadata
   * Per-category featured apps: Associated metadata

```
<categories>
  <category>Featured</category>
  <category>Utility</category>
</categories> 
```

## How to add a Flathub app (or non-com.endless* app) in the ‘Featured’ category?

* Add the app to [eos-extra.txt](./eos-extra.txt)
* Run [generate-eos-extra](./generate-eos-extra)
* Commit the result and submit a pull request
