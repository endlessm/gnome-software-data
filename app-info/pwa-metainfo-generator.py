#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2021-2022 Matthew Leeds
# Copyright 2023 Endless OS Foundation, LLC
# SPDX-License-Identifier: GPL-2.0-or-later

"""\
Generates AppStream metainfo for a set of Progressive Web App URLs

The output will be written to a file using the generated app ID.

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
import textwrap

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


def get_soup_for_url(url, language=None):
    headers = {}
    if language:
        headers["Accept-Language"] = language
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return BeautifulSoup(response.text, features="lxml")


def get_manifest(soup, url):
    if soup.head:
        manifest_link = soup.head.find("link", rel="manifest", href=True)
    else:
        manifest_link = soup.find("link", rel="manifest", href=True)

    if manifest_link:
        manifest_path = manifest_link.get("href")
    else:
        # Discourse doesn't include the web manifest link in the initial page content
        generator = soup.head.find("meta", attrs={"name": "generator"})
        if generator and generator["content"].startswith("Discourse "):
            manifest_path = "/manifest.webmanifest"
        else:
            return {}

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
    LANGUAGES = ("es", "fr", "pt")

    def __init__(self, url):
        self.url = url
        self.id = self._get_app_id()
        self.soup = get_soup_for_url(self.url)
        self.lang_soup = self._get_lang_soup()
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

    def _get_lang_soup(self):
        lang_soup = {}
        for lang in self.LANGUAGES:
            soup = get_soup_for_url(self.url, lang)
            if soup != self.soup:
                lang_soup[lang] = soup
        return lang_soup

    def _add_comment(self, element, text):
        text = textwrap.fill(text, break_long_words=False, break_on_hyphens=False)
        text = f' {text} '.replace('\n', '\n       ')
        comment = ET.Comment(text)
        element.append(comment)

    @staticmethod
    def _join_words(words):
        num_words = len(words)
        if num_words == 0:
            return ""
        elif num_words == 1:
            return words[0]
        return ", ".join(words[:-1]) + f" and {words[-1]}"

    def _add_name(self, app_component):
        self._add_comment(
            app_component,
            textwrap.dedent("""\
            A human-readable name for this web app. See
            https://www.freedesktop.org/software/appstream/docs/chap-Metadata.html#tag-name
            for details.
            """),
        )

        # Build a list of name and comment tuples.
        names_data = [
            (og_property_from_head(self.soup, "site_name"), "OpenGraph name"),
            (self.manifest.get("name"), "Manifest name"),
            (self.manifest.get("short_name"), "Manifest short_name"),
        ]

        # Reassmble it into a dictionary to prune and deduplicate names.
        names = {}
        for name, comment in names_data:
            if not name:
                continue
            comments = names.setdefault(name, [])
            comments.append(comment)

        num_names = len(names)
        if num_names > 1:
            self._add_comment(
                app_component,
                "Multiple names detected. Delete all but one name element below.",
            )
        elif num_names == 0:
            self._add_comment(
                app_component,
                "No app name detected. Update the placeholder below.",
            )
            ET.SubElement(app_component, 'name').text = "Placeholder"

        for name, comments in names.items():
            self._add_comment(app_component, self._join_words(comments))
            ET.SubElement(app_component, 'name').text = name

        # Add translated names if available.
        for lang, soup in sorted(self.lang_soup.items()):
            lang_name = og_property_from_head(soup, "site_name")
            if not lang_name or lang_name in names:
                continue
            self._add_comment(app_component, f"OpenGraph {lang} name")
            lang_element = ET.SubElement(app_component, "name")
            lang_element.set("xml:lang", lang)
            lang_element.text = lang_name

    def _add_launchable(self, app_component):
        launchable = ET.SubElement(app_component, 'launchable')
        launchable.set('type', 'url')
        launchable.text = self.url

    def _add_url(self, app_component):
        url_element = ET.SubElement(app_component, 'url')
        url_element.set('type', 'homepage')
        url_element.text = self.url

    @staticmethod
    def _canonicalize_summary(summary):
        if not summary:
            return summary

        # appstreamcli validate recommends summary not ending with '.'
        if summary.endswith('.'):
            summary = summary[:-1]
        # ...and not containing newlines
        return summary.replace('\n', ' ').strip()

    def _add_summary(self, app_component):
        self._add_comment(
            app_component,
            textwrap.dedent("""\
            A short summary of what this web app does. See
            https://www.freedesktop.org/software/appstream/docs/chap-Metadata.html#tag-summary
            for details.
            """),
        )

        # Build a list of summary and comment tuples.
        summaries_data = [
            (
                self._canonicalize_summary(og_property_from_head(self.soup, 'title')),
                "OpenGraph summary"
            ),
            (
                self._canonicalize_summary(self.manifest.get('description')),
                "Manifest summary"
            ),
        ]

        # Reassmble it into a dictionary to prune and deduplicate names.
        summaries = {}
        for summary, comment in summaries_data:
            if not summary:
                continue
            comments = summaries.setdefault(summary, [])
            comments.append(comment)

        num_summaries = len(summaries)
        if num_summaries > 1:
            self._add_comment(
                app_component,
                textwrap.dedent("""\
                Multiple summaries detected. Delete all but one summary element below.
                """),
            )
        elif num_summaries == 0:
            self._add_comment(
                app_component,
                "No summary detected. Update the placeholder below.",
            )
            ET.SubElement(app_component, 'summary').text = "A placeholder summary"

        for summary, comments in summaries.items():
            self._add_comment(app_component, self._join_words(comments))
            ET.SubElement(app_component, 'summary').text = summary

        # Add translated summaries if available.
        for lang, soup in sorted(self.lang_soup.items()):
            lang_summary = self._canonicalize_summary(
                og_property_from_head(soup, 'title')
            )
            if not lang_summary or lang_summary in summaries:
                continue
            self._add_comment(app_component, f"OpenGraph {lang} summary")
            lang_element = ET.SubElement(app_component, "summary")
            lang_element.set("xml:lang", lang)
            lang_element.text = lang_summary

    @staticmethod
    def _add_description_content(element, description):
        try:
            # Try to parse the description as XML since it will look nicer.
            description_xml = ET.fromstring(description)
        except ET.ParseError:
            # Fallback to just adding it as text wrapped in a <p> node.
            description_xml = ET.Element("p")
            description_xml.text = description

        element.append(description_xml)

    def _add_description(self, app_component):
        self._add_comment(
            app_component,
            textwrap.dedent("""\
            A long description of this web app. Some markup can be used. See
            https://www.freedesktop.org/software/appstream/docs/chap-Metadata.html#tag-description
            for details.
            """),
        )
        description = og_property_from_head(self.soup, "description")
        description_element = ET.Element("description")
        if description:
            self._add_comment(app_component, "OpenGraph description")
            app_component.append(description_element)
            self._add_description_content(description_element, description)
        else:
            self._add_comment(
                app_component,
                "No description was found. Update the placeholder below.",
            )
            app_component.append(description_element)
            ET.SubElement(description_element, "p").text = (
                "A placeholder description for the app."
            )
            ET.SubElement(description_element, "p").text = (
                "The description can use some markup such as multiple paragraphs."
            )

        # Add translated descriptions if available.
        for lang, soup in sorted(self.lang_soup.items()):
            lang_description = og_property_from_head(soup, "description")
            if not lang_description or lang_description == description:
                continue
            self._add_comment(app_component, f"OpenGraph {lang} description")
            lang_element = ET.SubElement(app_component, "description")
            lang_element.set("xml:lang", lang)
            self._add_description_content(lang_element, lang_description)

    def _add_project_license(self, app_component):
        self._add_comment(
            app_component,
            textwrap.dedent("""\
            The license of the web app in SPDX format. See
            https://www.freedesktop.org/software/appstream/docs/chap-Metadata.html#tag-project_license
            for details.
            """),
        )
        ET.SubElement(app_component, "project_license").text = "Placeholder"

    def _add_metadata_license(self, app_component):
        self._add_comment(
            app_component,
            textwrap.dedent("""\
            The license of this metadata in SPDX format. See
            https://www.freedesktop.org/software/appstream/docs/chap-Metadata.html#tag-metadata_license
            for details. A potential license to use is FSFAP.
            """),
        )
        ET.SubElement(app_component, "metadata_license").text = "Placeholder"

    def _add_developer_name(self, app_component):
        self._add_comment(
            app_component,
            textwrap.dedent("""\
            The developer or project responsible for the web app. See
            https://www.freedesktop.org/software/appstream/docs/chap-Metadata.html#tag-developer_name
            for details.
            """),
        )
        ET.SubElement(app_component, "developer_name").text = "Placeholder"

    def _add_icons(self, app_component):
        # Avoid using maskable icons if we can, they don't have nice rounded edges
        normal_icon_exists = False
        for icon in self.manifest.get('icons', []):
            if 'purpose' not in icon or icon['purpose'] == 'any':
                normal_icon_exists = True

        for icon in self.manifest.get('icons', []):
            if 'purpose' in icon and icon['purpose'] != 'any' and normal_icon_exists:
                continue
            icon_element = ET.SubElement(app_component, 'icon')
            icon_element.text = urljoin(self.url, icon['src'])
            icon_element.set('type', 'remote')
            size = icon['sizes'].split(' ')[-1]
            icon_element.set('width', size.split('x')[0])
            icon_element.set('height', size.split('x')[1])

    def _add_screenshots(self, app_component):
        self._add_comment(
            app_component,
            textwrap.dedent("""\
            One or more images displaying the web app interface. See
            https://www.freedesktop.org/software/appstream/docs/chap-Metadata.html#tag-screenshots
            for details.
            """),
        )
        screenshots = self.manifest.get('screenshots', [])
        screenshots_element = ET.Element('screenshots')

        if screenshots:
            self._add_comment(app_component, "Manifest screenshots")
            app_component.append(screenshots_element)

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
        else:
            self._add_comment(
                app_component,
                "No screenshots found. Update the placeholders below.",
            )
            app_component.append(screenshots_element)
            for x in range(1, 3):
                screenshot_element = ET.SubElement(screenshots_element, "screenshot")
                if x == 1:
                    screenshot_element.set('type', 'default')
                image_element = ET.SubElement(screenshot_element, 'image')
                image_element.text = f"https://example.com/screenshot{x}.jpg"
                image_element.set("width", "1600")
                image_element.set("height", "900")
                ET.SubElement(screenshot_element, 'caption').text = f"Screenshot {x}"

    def _add_categories(self, app_component):
        self._add_comment(
            app_component,
            textwrap.dedent("""\
            One or more categories describing the web app. See
            https://www.freedesktop.org/software/appstream/docs/chap-Metadata.html#tag-categories
            for details.
            """),
        )
        categories = self.manifest.get('categories', [])
        categories_element = ET.Element('categories')
        mapped_categories = list(
            filter(
                None,
                [w3c_to_appstream_categories.get(c) for c in categories],
            )
        )
        if mapped_categories:
            app_component.append(categories_element)
        else:
            self._add_comment(
                app_component,
                "No categories found in manifest. Update the placeholders below.",
            )
            app_component.append(categories_element)
            mapped_categories = ["Placeholder1", "Placeholder2"]

        for category in mapped_categories:
            ET.SubElement(categories_element, "category").text = category

    def _add_keywords(self, app_component):
        self._add_comment(
            app_component,
            textwrap.dedent("""\
            One or more keywords describing the web app. See
            https://www.freedesktop.org/software/appstream/docs/chap-Metadata.html#tag-keywords
            for details.
            """),
        )
        keywords = keywords_from_head(self.soup)
        keywords_element = ET.Element("keywords")
        if not keywords:
            self._add_comment(
                app_component,
                "No keywords found in page. Update the placeholders below.",
            )
            keywords = ["placeholder1", "placeholder2"]
        app_component.append(keywords_element)
        for keyword in keywords:
            ET.SubElement(keywords_element, "keyword").text = keyword

        # Add translated keywords if available.
        for lang, soup in sorted(self.lang_soup.items()):
            lang_keywords = keywords_from_head(soup)
            for keyword in lang_keywords:
                if keyword in keywords:
                    continue
                lang_element = ET.SubElement(keywords_element, "keyword")
                lang_element.set("xml:lang", lang)
                lang_element.text = keyword

    def _add_content_rating(self, app_component):
        self._add_comment(
            app_component,
            textwrap.dedent("""\
            Add content rating metadata if applicable. Update or remove the
            placeholder elements below. See
            https://www.freedesktop.org/software/appstream/docs/chap-Metadata.html#tag-content_rating
            for details.
            """),
        )
        ratings_element = ET.SubElement(app_component, "content_rating")
        ratings_element.set("type", "oars-1.1")
        for attr in ("social-info", "social-chat"):
            rating_element = ET.SubElement(ratings_element, "content_attribute")
            rating_element.set("id", attr)
            rating_element.text = "moderate"

    def _add_recommends(self, app_component):
        self._add_comment(
            app_component,
            textwrap.dedent("""\
            Add recommended controls and display sizes. See
            https://www.freedesktop.org/software/appstream/docs/chap-Metadata.html#tag-relations
            for details.
            """),
        )
        recommends_element = ET.SubElement(app_component, 'recommends')
        ET.SubElement(recommends_element, 'control').text = 'pointing'
        ET.SubElement(recommends_element, 'control').text = 'keyboard'
        ET.SubElement(recommends_element, 'control').text = 'touch'

        self._add_comment(
            recommends_element,
            "If the website is adaptive, change this to small.",
        )
        display_element = ET.SubElement(recommends_element, 'display_length')
        display_element.set('compare', 'ge')
        display_element.text = 'medium'


def main():
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n")[0],
        epilog="\n".join(__doc__.split("\n")[1:]),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # It would be nice to use a mutually exclusive group to handle
    # positional URLs vs a URL file, but argparse doesn't handle
    # optional positional arguments in that scenario.
    parser.add_argument(
        "urls",
        metavar="URL",
        nargs="*",
        help="URL to the main page of the app",
    )
    parser.add_argument(
        "-f", "--url-file",
        type=argparse.FileType("r"),
        help="file containing URLs to process",
    )
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument(
        "-O", "--output",
        help=(
            "metainfo output directory (default: metainfo subdirectory of this program)"
        ),
    )
    output_group.add_argument(
        "-p", "--print",
        action="store_true",
        help="print the metainfo instead of saving to files",
    )
    args = parser.parse_args()

    if args.urls and args.url_file:
        parser.error("argument -f/--url-file not allowed with URL arguments")
    elif not (args.urls or args.url_file):
        parser.error("either -f/--url-file or URL arguments are required")

    if args.url_file:
        with args.url_file as f:
            args.urls = sorted(
                filter(
                    lambda url: url and not url.startswith("#"),
                    {line.strip() for line in f},
                )
            )

    if not args.print:
        if args.output is None:
            args.output = os.path.join(os.path.dirname(__file__), "metainfo")
        os.makedirs(args.output, exist_ok=True)

    for url in args.urls:
        print(f"Processing URL {url}")
        app = App(url)
        out_filename = app.id + ".metainfo.xml.in"
        if args.print:
            out_file = sys.stdout.buffer
            print(f"# {out_filename}", flush=True)
        else:
            out_file = os.path.join(args.output, out_filename)
            print("Generating {} metainfo file {}".format(app.url, out_file))
        app.write_metainfo(out_file)


if __name__ == '__main__':
    main()
