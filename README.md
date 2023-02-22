# gnome-software-data

This repo provides AppStream data to be consumed by GNOME Software.
There are 2 flavors of data here:

* AppStream XML in [eos-extra.xml](app-info/eos-extra.xml) to supplement
  the data that typically comes from Flatpak repositories. Currently
  this is used to make specific apps featured in GNOME Software.

* Screenshots and thumbnails that are referenced from AppStream XML.
  Typically we do this for our own apps but occasionally for 3rd party
  apps where we've patched the app's XML to use our assets.

## GNOME Software External Appstream

GNOME Software is configured in EOS to download external AppStream from
a URL that this data is published to. The data in the [s3](s3) directory
is published to an AWS S3 bucket using the [`sync-s3.sh`](sync-s3.sh)
script. An AWS CloudFront CDN has been configured in front of the S3
bucket to improve global distribution.

The URL is configured in the `external-appstream-urls` key in the
gsettings `org.gnome.software` schema. This can be queried with
`gsettings get org.gnome.software external-appstream-urls`. At runtime,
GNOME Software will download the `eos-extra.xml` AppStream XML.

## GNOME Software Caching

In addition to the external AppStream data downloaded at runtime,
eos-image-builder tries to preseed the GNOME Software cache with the XML
as well as any screenshots and thumbnails present here. The GNOME
Software on-disk cache is organized differently than the external
appstream source. Each of the [app-info](app-info),
[screenshots](screenshots) and [thumbnails](thumbnails) directories is
copied to disk so that GNOME Software starts with local copies of all
the data present here.
