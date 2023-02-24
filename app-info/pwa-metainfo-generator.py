#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2021-2022 Matthew Leeds
# SPDX-License-Identifier: GPL-2.0+

"""\
Generates AppStream metainfo for a set of Progressive Web Apps

The YAML should consists of a sequence of web apps. Each app is a map
supporting the follwing fields:

- url (required, string):
  The URL to the main page of the app.
- name_property (optional, string):
  The manifest attribute to use for the app name. This can be either
  'name' or 'short_name'. If left empty, 'short_name' will be preferred
  if it's defined in the manifest.
- summary (optional, string):
  A custom summary to override the app's description of itself.
- description (required, string):
  A long description of the app. Some HTML markup is supported.
- license (required, string):
  A SPDX license expression, such as AGPL-3.0-only.
- categories (optional, sequence of strings):
  A sequence of category names, as defined by the desktop menu specification.
- content_rating (optional, sequence of strings):
  A sequence of OARS content ratings, for example:
    content_rating:
      - social-audio=moderate
      - social-contacts=intense
- adaptive (optional, boolean):
  true if the app works well on phones, false if it does not. If the value is
  not provided, no control or display recommendations will be added.

The output will be written to a file with the same name as the input but a .xml
file ending.

This tool uses the web app's manifest to fill out the AppStream info, so an
Internet connection is required.
"""

import argparse
import os
import xml.etree.ElementTree as ET
import requests
import json
import hashlib
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import yaml

# w3c categories: https://github.com/w3c/manifest/wiki/Categories
# appstream categories: https://specifications.freedesktop.org/menu-spec/latest/apa.html
# left out due to no corresponding appstream category:
# entertainment, food, government, kids, lifestyle, personalization, politics, shopping,
# travel
w3c_to_appstream_categories = {
    "books": "Literature",
    "business": "Office",
    "education": "Education",
    "finance": "Finance",
    "fitness": "Sports",
    "games": "Game",
    "health": "MedicalSoftware",
    "magazines": "News",
    "medical": "MedicalSoftware",
    "music": "Music",
    "navigation": "Maps",
    "news": "News",
    "photo": "Photography",
    "productivity": "Office",
    "security": "Security",
    "social": "Chat",
    "sports": "Sports",
    "utilities": "Utility",
    "weather": "Utility"
}


class ManifestNotFoundException(Exception):
    """
    Raised if a web manifest can't be found for a URL.
    """


def get_manifest_for_url(url):
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, features="lxml")

    if soup.head:
        manifest_link = soup.head.find("link", rel="manifest", href=True)
    else:
        manifest_link = soup.find("link", rel="manifest", href=True)

    if manifest_link:
        manifest_path = manifest_link["href"]
    else:
        # Discourse doesn't include the web manifest link in the initial page content
        generator = soup.head.find("meta", attrs={"name": "generator"})
        if generator and generator["content"].startswith("Discourse "):
            manifest_path = "/manifest.webmanifest"
        else:
            raise ManifestNotFoundException(url)

    manifest_response = requests.get(urljoin(url, manifest_path))
    manifest_response.raise_for_status()
    return json.loads(manifest_response.text)


def get_app_id_for_url(url):
    # Generate a unique app ID that meets the spec requirements. A different
    # app ID will be used upon install that is determined by the backing browser
    # Note, the algorithm used here is also used in the epiphany plugin, so it
    # cannot be changed.
    hashed_url = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return "org.gnome.Software.WebApp_" + hashed_url


def create_component_for_app(app):
    app_component = ET.Element('component')
    app_component.set('type', 'web-application')

    url = app["url"]
    manifest = get_manifest_for_url(url)

    app_id = get_app_id_for_url(url)
    ET.SubElement(app_component, 'id').text = app_id + '.desktop'

    name_property = app.get('name_property')
    if name_property is None:
        # Short name seems more suitable in practice
        name_property = 'short_name' if 'short_name' in manifest else 'name'
    elif name_property not in ('name', 'short_name'):
        raise ValueError(
            "name_property must be set to 'name' or 'short_name', not {}"
            .format(name_property)
        )
    ET.SubElement(app_component, 'name').text = manifest[name_property]

    launchable = ET.SubElement(app_component, 'launchable')
    launchable.set('type', 'url')
    launchable.text = url

    url_element = ET.SubElement(app_component, 'url')
    url_element.set('type', 'homepage')
    url_element.text = url

    summary = app.get('summary') or manifest.get('description')
    if summary:
        # appstreamcli validate recommends summary not ending with '.'
        if summary.endswith('.'):
            summary = summary[:-1]
        # ...and not containing newlines
        summary = summary.replace('\n', ' ').strip()
        ET.SubElement(app_component, 'summary').text = summary

    description = app['description']
    description_element = ET.SubElement(app_component, 'description')
    try:
        # Try to parse the description as XML since it will look nicer.
        description_xml = ET.fromstring(description)
        description_element.append(description_xml)
    except ET.ParseError:
        # Fallback to just adding it as text in the description node.
        description_element.text = description

    project_license = ET.SubElement(app_component, 'project_license')
    project_license.text = app["license"]

    # metadata license is a required field but we don't have one, assume FSFAP?
    metadata_license = ET.SubElement(app_component, 'metadata_license')
    metadata_license.text = 'FSFAP'

    # Avoid using maskable icons if we can, they don't have nice rounded edges
    normal_icon_exists = False
    for icon in manifest['icons']:
        if 'purpose' not in icon or icon['purpose'] == 'any':
            normal_icon_exists = True

    for icon in manifest['icons']:
        if 'purpose' in icon and icon['purpose'] != 'any' and normal_icon_exists:
            continue
        icon_element = ET.SubElement(app_component, 'icon')
        icon_element.text = urljoin(url, icon['src'])
        icon_element.set('type', 'remote')
        size = icon['sizes'].split(' ')[-1]
        icon_element.set('width', size.split('x')[0])
        icon_element.set('height', size.split('x')[1])

    if 'screenshots' in manifest:
        screenshots_element = ET.SubElement(app_component, 'screenshots')
        for screenshot in manifest['screenshots']:
            screenshot_element = ET.SubElement(screenshots_element, 'screenshot')
            screenshot_element.set('type', 'default')
            image_element = ET.SubElement(screenshot_element, 'image')
            image_element.text = urljoin(url, screenshot['src'])
            size = screenshot['sizes'].split(' ')[-1]
            image_element.set('width', size.split('x')[0])
            image_element.set('height', size.split('x')[1])
            if 'label' in screenshot:
                ET.SubElement(screenshot_element, 'caption').text = screenshot['label']

    categories_element = ET.SubElement(app_component, 'categories')
    user_categories = app.get('categories', [])
    for category in user_categories:
        if len(category) > 0:
            ET.SubElement(categories_element, 'category').text = category
    if 'categories' in manifest:
        for category in manifest['categories']:
            try:
                mapped_category = w3c_to_appstream_categories[category]
                if mapped_category not in user_categories:
                    ET.SubElement(categories_element, 'category').text = mapped_category
            except KeyError:
                pass

    content_ratings = app.get('content_rating', [])
    if len(content_ratings) > 0:
        ratings_element = ET.SubElement(app_component, 'content_rating')
        ratings_element.set('type', 'oars-1.1')
        for rating in content_ratings:
            if len(rating) > 0:
                rating_element = ET.SubElement(ratings_element, 'content_attribute')
                rating_element.text = rating.split('=')[1]
                rating_element.set('id', rating.split('=')[0])

    adaptive = app.get('adaptive')
    if adaptive is not None:
        recommends_element = ET.SubElement(app_component, 'recommends')
        ET.SubElement(recommends_element, 'control').text = 'pointing'
        ET.SubElement(recommends_element, 'control').text = 'keyboard'
        if adaptive:
            ET.SubElement(recommends_element, 'control').text = 'touch'
        display_element = ET.SubElement(recommends_element, 'display_length')
        display_element.set('compare', 'ge')
        if adaptive:
            display_element.text = 'small'
        else:
            display_element.text = 'medium'

    return app_component


def main():
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n")[0],
        epilog="\n".join(__doc__.split("\n")[1:]),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "input",
        type=argparse.FileType("r"),
        metavar="input.yaml",
        help="YAML file, with one sequence element per site",
    )
    parser.add_argument(
        "-O", "--output",
        help=(
            "metainfo output directory (default: metainfo subdirectory of the input "
            "YAML file directory)"
        ),
    )
    args = parser.parse_args()

    input_filename = args.input.name
    if args.output is None:
        args.output = os.path.join(os.path.dirname(args.input.name), "metainfo")
    os.makedirs(args.output, exist_ok=True)
    with args.input as input_yaml:
        data = yaml.safe_load(input_yaml)

    components = ET.Element('components')
    components.set('version', '0.15')
    for app in data:
        url = app["url"]
        print('Processing entry \'{}\' from file \'{}\''
              .format(url, input_filename))
        app_component = create_component_for_app(app)

        app_id = get_app_id_for_url(url)
        out_filename = os.path.join(args.output, app_id + ".metainfo.xml")
        print("Generating {} metainfo file {}".format(url, out_filename))
        app_component.tail = "\n"
        tree = ET.ElementTree(app_component)
        ET.indent(tree)
        tree.write(
            out_filename,
            xml_declaration=True,
            encoding='utf-8',
            method='xml',
        )


if __name__ == '__main__':
    main()
