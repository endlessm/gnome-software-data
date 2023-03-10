#!/bin/bash -e

# Copyright 2017 Endless Mobile, Inc.
# Copyright 2023 Endless OS Foundation, LLC
# SPDX-License-Identifier: GPL-2.0-or-later

# Sync appstream, screenshots and thumbnails to S3

SRCDIR=$(dirname "$0")
S3_BUCKET=gnome-software-data.endlessm.com
S3_REGION=us-west-2
CLOUDFRONT_ID=E25OA28V3N5IK1

usage() {
    cat <<EOF
Usage: $0 [OPTION]...

  --bucket		S3 bucket name (default: $S3_BUCKET)
  --region		S3 bucket region (default: $S3_REGION)
  --cloudfront          CloudFront distribution ID (default: $CLOUDFRONT_ID)
  -n, --dry-run		only show what would be done
  -h, --help		display this help and exit

Syncs the appstream, screenshots and thumbnails to the S3 bucket
EOF
}

ARGS=$(getopt -n "$0" \
              -o nh \
              -l bucket:,region:,cloudfront:,dry-run,help \
              -- "$@")
eval set -- "$ARGS"

DRY_RUN=false
AWS_OPTS=()
while true; do
    case "$1" in
        --bucket)
            S3_BUCKET=$2
            shift 2
            ;;
        --region)
            S3_REGION=$2
            shift 2
            ;;
        --cloudfront)
            CLOUDFRONT_ID=$2
            shift 2
            ;;
        -n|--dry-run)
            DRY_RUN=true
            AWS_OPTS+=(--dryrun)
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        --)
            shift
            break
            ;;
    esac
done

# Check that the needed programs exist
for prog in gzip aws appstream-util; do
    if ! type -p $prog >/dev/null; then
        echo "Cannot find $prog program" >&2
        exit 1
    fi
done

# Create the eos-extra.xml.gz file if it doesn't exist or is older than
# eos-extra.xml. Validate it first.
XML="$SRCDIR/app-info/eos-extra.xml"
XML_GZ="$SRCDIR/s3/app-info/eos-extra.xml.gz"
XML_GZ_CSUM="${XML_GZ}.sha256sum"

# FIXME: It would be preferable to use validate-strict, but currently
# our appstream-util doesn't know about the launchable tag used in web
# applications. Furthermore, it would probably be better to use
# appstreamcli validate, but that doesn't seem to understand the
# merge="append" entries and errors on missing tags that would come from
# the upstream appstream.
appstream-util validate --nonet "$XML"

mkdir -p "$SRCDIR/s3/app-info"
if [ ! -f "$XML_GZ" ] || [ "$XML" -nt "$XML_GZ" ]; then
    echo "Generating $XML_GZ"
    gzip -c "$XML" > "${XML_GZ}.tmp"
    mv "${XML_GZ}.tmp" "$XML_GZ"
fi
if [ ! -f "$XML_GZ_CSUM" ] || [ "$XML_GZ" -nt "$XML_GZ_CSUM" ]; then
    echo "Generating $XML_GZ_CSUM"
    csum=$(sha256sum "$XML_GZ" | cut -d' ' -f1)
    echo -n "$csum" > "$XML_GZ_CSUM"
fi

# Sync the assets to AWS. --size-only is used since the local
# modificaton times will be updated by the git checkout.
for dir in screenshots thumbnails; do
    echo "Syncing $dir to $S3_BUCKET"
    aws s3 sync "${AWS_OPTS[@]}" --size-only --region "$S3_REGION" \
        "$SRCDIR/s3/$dir" "s3://$S3_BUCKET/$dir"
done

# Now sync the appstream data since the things it references are in
# place.
echo "Syncing app-info to $S3_BUCKET"
aws s3 sync "${AWS_OPTS[@]}" --region "$S3_REGION" \
    "$SRCDIR/s3/app-info" "s3://$S3_BUCKET/app-info"

# Invalidate the CloudFront distribution so it fetches new versions of
# any files.
#
# FIXME: This is very wasteful as it's likely most of the files haven't
# changed and can don't need to be invalidated. Unfortunately, aws s3
# sync doesn't report the files it uploads in a reasonable way. See
# https://github.com/endlessm/eos-helpcenter/blob/master/publish-docs.py
# for a smarter uploader.
echo "Invalidating CloudFront distribution $CLOUDFRONT_ID"
if ! "$DRY_RUN"; then
    aws cloudfront create-invalidation --distribution-id "$CLOUDFRONT_ID" \
        --paths '/*'
fi
