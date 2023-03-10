#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2021-2022 Matthew Leeds
# Copyright 2023 Endless OS Foundation, LLC
# SPDX-License-Identifier: GPL-2.0-or-later

"""\
Generates AppStream metainfo for a set of Progressive Web Apps

The YAML should consists of a sequence of web apps. Each app is a map
supporting the follwing fields:

- url (required, string):
  The URL to the main page of the app.
- name (optional, string):
  A custom name to override the name in the app's manifest.
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
- developer_name (optional, string):
  The developers or project responsible for the app.
- screenshots (optional, sequence of maps):
  A sequence of screenshots. Each screenshot entry must have 'src', 'width'
  and 'height' properties. Each entry may have an optional boolean 'default'
  field. It is assumed false if not specified. If no screenshots have been set
  as the default, the first screenshot will be the default. Each entry may also
  have an optional 'caption' field. For example:
    screenshots:
      - src: https://example.com/screenshot1.jpg
        default: true
        width: 800
        height: 600
        caption: Super App's main window.
      - src: https://example.com/screenshot2.jpg
        width: 800
        height: 600
- categories (optional, sequence of strings):
  A sequence of category names, as defined by the desktop menu specification.
- keywords (optional, sequence of strings):
  A sequence of keywords to be used for searching.
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
import sys
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


def get_soup_for_url(url):
    response = requests.get(url)
    response.raise_for_status()
    return BeautifulSoup(response.text, features="lxml")


def get_manifest(soup, url):
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


def og_property_from_head(soup, og_property):
    tag = soup.head.find("meta", attrs={"property": f"og:{og_property}"})

    if tag is None:
        return None
    return tag.get("content")


def prop_from_head(soup, name):
    tag = soup.head.find("meta", attrs={"name": f"{name}"})

    if tag is None:
        return None
    return tag.get("content")


def keywords_from_head(soup):
    keywords_value = prop_from_head(soup, "keywords")

    if keywords_value:
        keywords = keywords_value.split(", ")
    else:
        keywords = []

    return keywords


class App:
    def __init__(self, config):
        self.config = config
        self.url = self.config["url"]
        self.id = self._get_app_id()
        self.soup = get_soup_for_url(self.url)
        self.manifest = get_manifest(self.soup, self.url)

    def write_metainfo(self, path):
        component = self.create_component()
        component.tail = "\n"
        tree = ET.ElementTree(component)
        ET.indent(tree)
        tree.write(
            path,
            xml_declaration=True,
            encoding='utf-8',
            method='xml',
        )

    def create_component(self):
        app_component = ET.Element('component')
        app_component.set('type', 'web-application')

        ET.SubElement(app_component, 'id').text = self.id + '.desktop'

        self._add_name(app_component)
        self._add_launchable(app_component)
        self._add_url(app_component)
        self._add_summary(app_component)
        self._add_description(app_component)
        self._add_project_license(app_component)
        self._add_metadata_license(app_component)
        self._add_developer_name(app_component)
        self._add_icons(app_component)
        self._add_screenshots(app_component)
        self._add_categories(app_component)
        self._add_keywords(app_component)
        self._add_content_rating(app_component)
        self._add_recommends(app_component)

        return app_component

    def _get_app_id(self):
        # Generate a unique app ID that meets the spec requirements. A
        # different app ID will be used upon install that is determined
        # by the backing browser Note, the algorithm used here is also
        # used in the epiphany plugin, so it cannot be changed.
        hashed_url = hashlib.sha1(self.url.encode("utf-8")).hexdigest()
        return "org.gnome.Software.WebApp_" + hashed_url

    def _add_name(self, app_component):
        name = self.config.get('name')
        if not name:
            # No name was configured. First try the OpenGraph name.
            name = og_property_from_head(self.soup, "site_name")
            if not name:
                # No OpenGraph name. Try the manifest name, allowing the property to be
                # chosen.
                name_property = self.config.get('name_property')
                if name_property is None:
                    # Short name seems more suitable in practice
                    if "short_name" in self.manifest:
                        name_property = "short_name"
                    else:
                        name_property = "name"
                elif name_property not in ('name', 'short_name'):
                    raise ValueError(
                        "name_property must be set to 'name' or 'short_name', not '{}'"
                        .format(name_property)
                    )
                name = self.manifest[name_property]
        ET.SubElement(app_component, 'name').text = name

    def _add_launchable(self, app_component):
        launchable = ET.SubElement(app_component, 'launchable')
        launchable.set('type', 'url')
        launchable.text = self.url

    def _add_url(self, app_component):
        url_element = ET.SubElement(app_component, 'url')
        url_element.set('type', 'homepage')
        url_element.text = self.url

    def _add_summary(self, app_component):
        summary = (
            self.config.get('summary', og_property_from_head(self.soup, "title"))
            or self.manifest.get('description')
        )

        if summary:
            # appstreamcli validate recommends summary not ending with '.'
            if summary.endswith('.'):
                summary = summary[:-1]
            # ...and not containing newlines
            summary = summary.replace('\n', ' ').strip()
            ET.SubElement(app_component, 'summary').text = summary

    def _add_description(self, app_component):
        description = self.config.get(
            'description',
            og_property_from_head(self.soup, "description"),
        )
        description_element = ET.SubElement(app_component, 'description')

        try:
            # Try to parse the description as XML since it will look nicer.
            description_xml = ET.fromstring(description)
            description_element.append(description_xml)
        except ET.ParseError:
            # Fallback to just adding it as text in the description node.
            description_element.text = description

    def _add_project_license(self, app_component):
        project_license = ET.SubElement(app_component, 'project_license')
        project_license.text = self.config["license"]

    def _add_metadata_license(self, app_component):
        # metadata license is a required field but we don't have one, assume FSFAP?
        metadata_license = ET.SubElement(app_component, 'metadata_license')
        metadata_license.text = 'FSFAP'

    def _add_developer_name(self, app_component):
        developer_name = self.config.get('developer_name')
        if developer_name:
            ET.SubElement(app_component, 'developer_name').text = developer_name

    def _add_icons(self, app_component):
        # Avoid using maskable icons if we can, they don't have nice rounded edges
        normal_icon_exists = False
        for icon in self.manifest['icons']:
            if 'purpose' not in icon or icon['purpose'] == 'any':
                normal_icon_exists = True

        for icon in self.manifest['icons']:
            if 'purpose' in icon and icon['purpose'] != 'any' and normal_icon_exists:
                continue
            icon_element = ET.SubElement(app_component, 'icon')
            icon_element.text = urljoin(self.url, icon['src'])
            icon_element.set('type', 'remote')
            size = icon['sizes'].split(' ')[-1]
            icon_element.set('width', size.split('x')[0])
            icon_element.set('height', size.split('x')[1])

    def _add_screenshots(self, app_component):
        screenshots = self.config.get('screenshots', self.manifest.get('screenshots'))
        if screenshots:
            screenshots_element = ET.SubElement(app_component, 'screenshots')

            # Make sure at least one of the screenshots is the default.
            has_default = any([s.get('default', False) for s in screenshots])
            if not has_default:
                # Make the first one the default.
                screenshots[0]['default'] = True

            for screenshot in screenshots:
                screenshot_element = ET.SubElement(screenshots_element, 'screenshot')
                if screenshot.get('default', False):
                    screenshot_element.set('type', 'default')
                image_element = ET.SubElement(screenshot_element, 'image')
                image_element.text = urljoin(self.url, screenshot['src'])
                if 'sizes' in screenshot:
                    size = screenshot['sizes'].split(' ')[-1]
                    image_element.set('width', size.split('x')[0])
                    image_element.set('height', size.split('x')[1])
                else:
                    image_element.set('width', str(screenshot['width']))
                    image_element.set('height', str(screenshot['height']))
                caption = screenshot.get('caption') or screenshot.get('label')
                if caption:
                    ET.SubElement(screenshot_element, 'caption').text = caption

    def _add_categories(self, app_component):
        categories_element = ET.SubElement(app_component, 'categories')
        user_categories = self.config.get('categories', [])
        for category in user_categories:
            if len(category) > 0:
                ET.SubElement(categories_element, 'category').text = category
        if 'categories' in self.manifest:
            for category in self.manifest['categories']:
                try:
                    mapped_category = w3c_to_appstream_categories[category]
                    if mapped_category not in user_categories:
                        ET.SubElement(categories_element, 'category').text = (
                            mapped_category
                        )
                except KeyError:
                    pass

    def _add_keywords(self, app_component):
        keywords = self.config.get('keywords', keywords_from_head(self.soup))
        if keywords:
            keywords_element = ET.SubElement(app_component, 'keywords')
            for keyword in keywords:
                ET.SubElement(keywords_element, 'keyword').text = keyword

    def _add_content_rating(self, app_component):
        content_ratings = self.config.get('content_rating', [])
        if len(content_ratings) > 0:
            ratings_element = ET.SubElement(app_component, 'content_rating')
            ratings_element.set('type', 'oars-1.1')
            for rating in content_ratings:
                if len(rating) > 0:
                    rating_element = ET.SubElement(ratings_element, 'content_attribute')
                    rating_element.text = rating.split('=')[1]
                    rating_element.set('id', rating.split('=')[0])

    def _add_recommends(self, app_component):
        adaptive = self.config.get('adaptive')
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
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument(
        "-O", "--output",
        help=(
            "metainfo output directory (default: metainfo subdirectory of the input "
            "YAML file directory)"
        ),
    )
    output_group.add_argument(
        "-s", "--stdout",
        action="store_true",
        help="print the metainfo instead of saving to files",
    )
    args = parser.parse_args()

    input_filename = args.input.name
    with args.input as input_yaml:
        data = yaml.safe_load(input_yaml)

    if not args.stdout:
        if args.output is None:
            args.output = os.path.join(os.path.dirname(input_filename), "metainfo")
        os.makedirs(args.output, exist_ok=True)

    for config in data:
        print("Processing entry '{}' from file '{}'"
              .format(config["url"], input_filename))
        app = App(config)
        out_filename = app.id + ".metainfo.xml"
        if args.stdout:
            out_file = sys.stdout.buffer
            print(f"# {out_filename}", flush=True)
        else:
            out_file = os.path.join(args.output, out_filename)
            print("Generating {} metainfo file {}".format(app.url, out_file))
        app.write_metainfo(out_file)


if __name__ == '__main__':
    main()
