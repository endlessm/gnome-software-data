#!/bin/bash -e

# Sync appstream, screenshots and thumbnails to S3

SRCDIR=$(dirname "$0")
S3_BUCKET=gnome-software-data.endlessm.com
S3_REGION=us-west-2

usage() {
    cat <<EOF
Usage: $0 [OPTION]...

  --bucket		S3 bucket name (default: $S3_BUCKET)
  --region		S3 bucket region (default: $S3_REGION)
  -n, --dry-run		only show what would be done
  -h, --help		display this help and exit

Syncs the appstream, screenshots and thumbnails to the S3 bucket
EOF
}

ARGS=$(getopt -n "$0" \
              -o nh \
              -l bucket:,region:,dry-run,help \
              -- "$@")
eval set -- "$ARGS"

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
        -n|--dry-run)
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
for prog in gzip aws; do
    if ! type -p $prog >/dev/null; then
        echo "Cannot find $prog program" >&2
        exit 1
    fi
done

# Create the eos-extra.xml.gz file if it doesn't exist or is older than
# eos-extra.xml
XML="$SRCDIR/app-info/eos-extra.xml"
XML_GZ="$SRCDIR/s3/app-info/eos-extra.xml.gz"
XML_GZ_CSUM="${XML_GZ}.sha256sum"
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
